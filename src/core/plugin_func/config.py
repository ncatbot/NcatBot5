"""
混入类模块：ConfigerMixin 与 ReloadableConfigerMixin
修复：
1. 增加文件 Hash 校验，防止内容未变时的重复重载。
2. 回调函数参数改为 (old_data, new_data)，解决无法获取旧数据的问题。
3. 优化防抖逻辑，提升稳定性。
"""

import asyncio
import hashlib
import json
import logging
import pickle
import threading
import time
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Optional,
    Set,
    Union,
)

import aiofiles
import aiofiles.os
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.plugins_system.core.mixin import PluginMixin

# 尝试导入 yaml
try:
    import yaml
except ImportError:
    yaml = None


# ==============================
# 依赖组件实现
# ==============================


class DictProxy(dict):
    """数据代理，支持变更追踪"""

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._log: list[tuple[str, Any, Any]] = []

    def __setitem__(self, key: Any, value: Any) -> None:
        self._log.append(("SET", key, value))
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self._log.append(("DEL", key))
        super().__delitem__(key)

    def pop(self, key: Any, *default: Any) -> Any:
        self._log.append(("POP", key))
        return super().pop(key, *default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self)


class FileFormat(Enum):
    JSON = "json"
    PICKLE = "pickle"
    TEXT = "txt"
    YAML = "yaml"


class ReloadMode(Enum):
    AUTO = "auto"
    MANUAL = "manual"
    TIMED = "timed"


class GlobalFileObserver:
    """全局单例文件观察器"""

    _instance: Optional["GlobalFileObserver"] = None
    _lock = threading.Lock()

    _watched_dirs: Dict[Path, Set[Path]]
    _handlers: Dict[Path, "_DelegatedHandler"]

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._observer = Observer()
                    cls._instance._started = False
                    cls._instance._watched_dirs = {}
                    cls._instance._handlers = {}
        return cls._instance

    def start(self):
        if not self._started:
            self._observer.start()
            self._started = True

    def stop(self):
        if self._started:
            self._observer.stop()
            self._observer.join()
            self._started = False
            self._watched_dirs.clear()
            self._handlers.clear()

    def add_watch(self, file_path: Path, callback: Callable[[], None]):
        file_path = file_path.resolve()
        dir_path = file_path.parent

        with self._lock:
            if dir_path not in self._watched_dirs or not self._watched_dirs[dir_path]:
                handler = _DelegatedHandler(dir_path)
                self._observer.schedule(handler, str(dir_path), recursive=False)
                self._handlers[dir_path] = handler
                self._watched_dirs[dir_path] = set()

            self._watched_dirs[dir_path].add(file_path)
            self._handlers[dir_path].register_callback(file_path, callback)

            if not self._started:
                self.start()

    def remove_watch(self, file_path: Path):
        file_path = file_path.resolve()
        dir_path = file_path.parent

        with self._lock:
            if dir_path not in self._watched_dirs:
                return

            if file_path in self._watched_dirs[dir_path]:
                self._watched_dirs[dir_path].remove(file_path)
                self._handlers[dir_path].unregister_callback(file_path)


class _DelegatedHandler(FileSystemEventHandler):
    """目录事件分发器"""

    def __init__(self, watch_dir: Path):
        self.watch_dir = watch_dir
        self.callbacks: Dict[Path, Set[Callable[[], None]]] = {}
        self._last_trigger: Dict[Path, float] = {}
        self._lock = threading.Lock()

    def register_callback(self, file_path: Path, callback: Callable[[], None]):
        if file_path not in self.callbacks:
            self.callbacks[file_path] = set()
        self.callbacks[file_path].add(callback)

    def unregister_callback(self, file_path: Path):
        if file_path in self.callbacks:
            self.callbacks[file_path].clear()
            del self.callbacks[file_path]

    def on_modified(self, event):
        if event.is_directory:
            return

        src_path = Path(event.src_path).resolve()
        now = time.time()

        with self._lock:
            # 增加防抖时间至 1.0 秒，防止编辑器多次触发
            if src_path in self._last_trigger:
                if now - self._last_trigger[src_path] < 1.0:
                    return
            self._last_trigger[src_path] = now

        if src_path in self.callbacks:
            for cb in self.callbacks[src_path]:
                threading.Timer(0.2, cb).start()


class SingleFileReloader:
    """单文件重载器"""

    def __init__(
        self,
        file_path: Union[str, Path],
        format: FileFormat = FileFormat.JSON,
        reload_mode: ReloadMode = ReloadMode.AUTO,
        encoding: str = "utf-8",
        auto_save: bool = True,
        save_delay: float = 0.5,
        default_data: Optional[Dict] = None,
    ):
        self.file_path = Path(file_path).resolve()
        self.format = format
        self.reload_mode = reload_mode
        self.encoding = encoding
        self.auto_save = auto_save
        self.save_delay = save_delay
        self.default_data = default_data or {}

        self._data = DictProxy()
        self._is_modified = False
        self._save_timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()
        # 修改回调签名：接收 (old_data, new_data_proxy)
        self._callbacks: list[Callable[[Dict, DictProxy], None]] = []

        self._global_observer = GlobalFileObserver()
        self._last_file_hash: Optional[str] = None

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._serializer = self._get_serializer()
        self._initialize_data()

        if self.reload_mode == ReloadMode.AUTO:
            self._global_observer.add_watch(self.file_path, self._on_file_changed)

    def _get_serializer(self) -> Callable:
        if self.format == FileFormat.JSON:
            return self._json_serializer
        elif self.format == FileFormat.PICKLE:
            return self._pickle_serializer
        elif self.format == FileFormat.TEXT:
            return self._text_serializer
        elif self.format == FileFormat.YAML:
            return self._yaml_serializer
        else:
            raise ValueError(f"不支持的格式: {self.format}")

    def _json_serializer(self, data: Union[Dict, str], mode: str = "dump") -> Any:
        if mode == "dump":
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return json.loads(data)

    def _pickle_serializer(self, data: Union[Dict, bytes], mode: str = "dump") -> Any:
        if mode == "dump":
            return pickle.dumps(data)
        else:
            return pickle.loads(data)

    def _text_serializer(self, data: Union[Dict, str], mode: str = "dump") -> Any:
        if mode == "dump":
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                lines.append(f"{k}={v}")
            return "\n".join(lines)
        else:
            result = {}
            for line in data.strip().split("\n"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
                    result[k.strip()] = v
            return result

    def _yaml_serializer(self, data: Union[Dict, str], mode: str = "dump") -> Any:
        if yaml is None:
            raise ImportError("YAML格式需要安装pyyaml: pip install pyyaml")
        if mode == "dump":
            return yaml.dump(data, allow_unicode=True, default_flow_style=False)
        else:
            return yaml.safe_load(data)

    def _initialize_data(self) -> None:
        try:
            if self.file_path.exists():
                self._load_from_file()
            else:
                self._data = DictProxy(self.default_data)
                if self.auto_save:
                    self.save()
            # 初始化后计算一次 Hash
            self._update_file_hash()
        except Exception as e:
            logging.error(f"初始化数据失败: {e}")
            self._data = DictProxy(self.default_data)

    def _update_file_hash(self) -> None:
        """更新文件内容的哈希值"""
        try:
            if self.format == FileFormat.PICKLE:
                with open(self.file_path, "rb") as f:
                    content = f.read()
                    self._last_file_hash = hashlib.md5(content).hexdigest()
            else:
                with open(self.file_path, "r", encoding=self.encoding) as f:
                    content = f.read()
                    self._last_file_hash = hashlib.md5(content.encode()).hexdigest()
        except Exception:
            self._last_file_hash = None

    def _load_from_file(self) -> None:
        with self._lock:
            try:
                if self.format == FileFormat.PICKLE:
                    with open(self.file_path, "rb") as f:
                        loaded = self._serializer(f.read(), mode="load")
                else:
                    with open(self.file_path, "r", encoding=self.encoding) as f:
                        loaded = self._serializer(f.read(), mode="load")

                if not isinstance(loaded, dict):
                    raise ValueError("文件内容必须是字典(json/yaml)")

                new_dict = DictProxy(loaded)
                if dict(new_dict) != dict(self._data):
                    self._data = new_dict
                self._is_modified = False
            except Exception as e:
                logging.warning(f"加载文件失败 {self.file_path}: {e}")
                self.save(force=True)

    def _save_to_file(self) -> None:
        with self._lock:
            try:
                temp_file = self.file_path.with_suffix(".tmp")
                data_to_save = self._data.to_dict()
                serialized = self._serializer(data_to_save, mode="dump")

                if self.format == FileFormat.PICKLE:
                    if not isinstance(serialized, bytes):
                        serialized = pickle.dumps(serialized)
                    with open(temp_file, "wb") as f:
                        f.write(serialized)
                else:
                    if not isinstance(serialized, str):
                        serialized = str(serialized)
                    with open(temp_file, "w", encoding=self.encoding) as f:
                        f.write(serialized)

                temp_file.replace(self.file_path)
                self._is_modified = False
                # 保存后更新 Hash
                self._update_file_hash()
            except Exception as e:
                logging.error(f"保存文件失败 {self.file_path}: {e}")

    def _on_file_changed(self):
        try:
            self.reload()
        except Exception as e:
            logging.error(f"自动重载失败: {e}")

    def reload(self) -> None:
        with self._lock:
            try:
                if not self.file_path.exists():
                    return

                # 1. 读取文件内容以计算 Hash
                try:
                    if self.format == FileFormat.PICKLE:
                        with open(self.file_path, "rb") as f:
                            raw_content = f.read()
                    else:
                        with open(self.file_path, "r", encoding=self.encoding) as f:
                            raw_content = f.read()

                    if isinstance(raw_content, str):
                        current_hash = hashlib.md5(raw_content.encode()).hexdigest()
                    else:
                        current_hash = hashlib.md5(raw_content).hexdigest()

                    # 2. 如果 Hash 没变，直接返回，防止无效重载
                    if self._last_file_hash == current_hash:
                        return

                except Exception:
                    # 读取失败或 Hash 计算失败，尝试继续加载
                    current_hash = None

                # 3. 记录旧数据
                old_data = self._data.to_dict().copy()

                # 4. 加载新数据
                self._load_from_file()
                new_data_proxy = self._data

                # 5. 二次校验：如果字典内容没变，也不触发回调 (仅更新 Hash)
                if old_data == dict(new_data_proxy):
                    self._last_file_hash = current_hash
                    return

                # 6. 更新 Hash 并触发回调
                self._last_file_hash = current_hash

                for cb in self._callbacks:
                    try:
                        # 传入旧数据和新数据
                        cb(old_data, new_data_proxy)
                    except Exception as e:
                        logging.error(f"回调执行失败: {e}")

            except Exception as e:
                logging.error(f"重载失败: {e}")

    def save(self, force: bool = False) -> None:
        if not self._is_modified and not force:
            return
        if self.save_delay > 0 and not force:
            if self._save_timer:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(self.save_delay, self._save_to_file)
            self._save_timer.start()
        else:
            self._save_to_file()

    def mark_modified(self) -> None:
        self._is_modified = True
        if self.auto_save:
            self.save()

    def register_callback(self, callback: Callable[[Dict, DictProxy], None]) -> None:
        self._callbacks.append(callback)

    def get_data(self) -> DictProxy:
        return self._data

    def get_raw_data(self) -> Dict:
        return self._data.to_dict()

    def update_data(self, data: Dict) -> None:
        with self._lock:
            self._data.update(data)
            self.mark_modified()

    def close(self) -> None:
        if self._save_timer:
            self._save_timer.cancel()
        if self._is_modified:
            self.save(force=True)
        if self.reload_mode == ReloadMode.AUTO:
            self._global_observer.remove_watch(self.file_path)


class ConfigManager:
    _instances: ClassVar[Dict[Path, "ConfigManager"]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __new__(cls, config_base_dir: Path) -> "ConfigManager":
        if config_base_dir not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[config_base_dir] = instance
        return cls._instances[config_base_dir]

    def __init__(self, config_base_dir: Path) -> None:
        if hasattr(self, "_initialized"):
            return
        self.config_base_dir = Path(config_base_dir)
        self._initialized = True

    async def load_config(self, plugin_name: str) -> Dict[str, Any]:
        search_paths = [
            self.config_base_dir / f"{plugin_name}.{ext}"
            for ext in ["yaml", "yml", "json"]
        ]
        sub_dir = self.config_base_dir / plugin_name
        if sub_dir.exists() and sub_dir.is_dir():
            search_paths = [
                sub_dir / f"{plugin_name}.{ext}" for ext in ["yaml", "yml", "json"]
            ] + search_paths

        for config_file in search_paths:
            if await aiofiles.os.path.exists(config_file):
                try:
                    async with aiofiles.open(config_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                    if config_file.suffix in (".yaml", ".yml"):
                        if yaml:
                            data = yaml.safe_load(content)
                        else:
                            continue
                    else:
                        data = json.loads(content)
                    return data if isinstance(data, dict) else {}
                except Exception:
                    pass
        return {}

    async def save_config(
        self,
        plugin_name: str,
        config: Dict[str, Any],
        format: FileFormat = FileFormat.YAML,
    ) -> bool:
        config = dict(config)
        plugin_config_dir = self.config_base_dir
        try:
            await aiofiles.os.makedirs(plugin_config_dir, exist_ok=True)
            ext = "yaml" if format == FileFormat.YAML else "json"
            config_file = plugin_config_dir / f"{plugin_name}.{ext}"
            temp_file = plugin_config_dir / f".{plugin_name}.{ext}.tmp"

            if format == FileFormat.YAML:
                if not yaml:
                    raise ImportError("pyyaml not installed")
                content = yaml.dump(config, allow_unicode=True, sort_keys=False)
            else:
                content = json.dumps(config, ensure_ascii=False, indent=2)

            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(content)
            await aiofiles.os.replace(temp_file, config_file)
            return True
        except Exception as e:
            logging.error(f"保存配置失败 {plugin_name}: {e}")
            if "temp_file" in locals():
                try:
                    await aiofiles.os.remove(temp_file)
                except Exception:
                    pass
            return False


# ==============================
# 目标类
# ==============================


class ConfigerMixin(PluginMixin):
    """插件配置混入类"""

    def __init__(self):
        super().__init__()
        self._config_manager: ConfigManager = ConfigManager(self.context.config_dir)
        self._data_manager: ConfigManager = ConfigManager(self.context.data_dir)
        self._config = DictProxy()
        self._data = DictProxy()

    async def on_mixin_load(self):
        self._config = DictProxy(await self._config_manager.load_config(self.name))
        self._data = DictProxy(await self._data_manager.load_config(self.name))

    async def on_mixin_unload(self):
        await self._config_manager.save_config(self.name, self._config)
        await self._data_manager.save_config(self.name, self._data)

    @property
    def config(self) -> DictProxy:
        return self._config

    @property
    def data(self) -> DictProxy:
        return self._data

    @config.setter
    def config(self, val: Union[Dict[str, Any], DictProxy]) -> None:
        self._config = val if isinstance(val, DictProxy) else DictProxy(val)

    @data.setter
    def data(self, val: Union[Dict[str, Any], DictProxy]) -> None:
        self._data = val if isinstance(val, DictProxy) else DictProxy(val)


class ReloadableConfigerMixin(ConfigerMixin):
    """支持文件热重载的配置混入类"""

    def __init__(self):
        super().__init__()
        self._reloader: Optional[SingleFileReloader] = None
        self._first_load: bool = False

    async def on_mixin_load(self):
        await super().on_mixin_load()

        config_dir: Path = self.context.config_dir
        config_file_in_subdir = config_dir / self.name / f"{self.name}.yaml"
        config_file_in_root = config_dir / f"{self.name}.yaml"

        target_config = (
            config_file_in_subdir
            if config_file_in_subdir.parent.exists()
            else config_file_in_root
        )
        await self._ensure_config_file(target_config)
        self.setup_config_file(target_config)

    async def _ensure_config_file(self, config_path: Path) -> None:
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("# 插件配置\n{}\n", encoding="utf-8")
            self._first_load = True
            if hasattr(self, "logger"):
                self.logger.info(
                    f"已为插件 {self.name} 创建默认配置文件: {config_path}"
                )

    def setup_config_file(
        self, config_file: Union[str, Path], **reloader_kwargs
    ) -> None:
        config_path = Path(config_file)
        if self._reloader:
            self._reloader.close()

        if "format" not in reloader_kwargs:
            reloader_kwargs["format"] = FileFormat.YAML

        self._reloader = SingleFileReloader(file_path=config_path, **reloader_kwargs)

        current_data = self._config.to_dict()
        self._reloader.update_data(current_data)
        self._reloader._is_modified = False
        self._reloader._update_file_hash()  # 初始化 Hash

        self._config = self._reloader.get_data()
        self._reloader.register_callback(self._on_config_reloaded)

    def _on_config_reloaded(self, old_data: dict, new_data_proxy: DictProxy) -> None:
        """配置重载回调（内部使用）"""

        # 更新数据
        self.config = new_data_proxy
        self.logger.info(f"插件 {self.name} 配置已热重载")

        # 转换为 dict 传递给钩子
        self.on_config_reloaded(old_data, dict(new_data_proxy))

    def on_config_reloaded(self, old_data: dict, new_data: dict) -> None:
        """
        配置热重载钩子

        Args:
            old_data: 修改前的旧配置
            new_data: 修改后的新配置
        """
        pass

    async def save_config(self) -> None:
        if not self._reloader:
            await self._config_manager.save_config(self.name, self._config)
            return
        self._reloader.save(force=True)

    def reload_config(self) -> None:
        if not self._reloader:
            raise RuntimeError("重载器未初始化")
        self._reloader.reload()

    async def on_mixin_unload(self):
        if self._reloader:
            self._reloader.close()
            self._reloader = None
        await super().on_mixin_unload()

    @property
    def first_load(self) -> bool:
        return self._first_load
