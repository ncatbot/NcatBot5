from __future__ import annotations

import json
import logging
import pickle
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer, ObserverType

logger = logging.getLogger("FileReloader")


class DictProxy(dict):
    """继承 dict，仅对 Python 层能走到的方法做覆盖。"""

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._log: list[tuple[str, Any, Any]] = []

    # ---------- 拦截 ----------
    def __setitem__(self, key: Any, value: Any) -> None:
        self._log.append(("SET", key, value))
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self._log.append(("DEL", key))
        super().__delitem__(key)

    def pop(self, key: Any, *default: Any) -> Any:
        self._log.append(("POP", key))
        return super().pop(key, *default)

    # ---------- 辅助 ----------
    def to_dict(self) -> Dict[str, Any]:
        """返回纯 dict，方便序列化。"""
        return dict(self)

    @property
    def logs(self) -> tuple:
        return tuple(self._log)


class FileFormat(Enum):
    """支持的文件格式"""

    JSON = "json"
    PICKLE = "pickle"
    TEXT = "txt"
    YAML = "yaml"


class ReloadMode(Enum):
    """重载模式"""

    AUTO = "auto"  # 自动监听文件变化
    MANUAL = "manual"  # 手动触发重载
    TIMED = "timed"  # 定时重载


class SingleFileReloader:
    """
    单文件重载器
    支持多种格式的文件读写和自动重载
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        format: FileFormat = FileFormat.JSON,
        reload_mode: ReloadMode = ReloadMode.AUTO,
        encoding: str = "utf-8",
        auto_save: bool = True,
        save_delay: float = 0.5,  # 防抖延迟
        default_data: Optional[Dict] = None,
    ):
        """
        初始化重载器

        Args:
            file_path: 文件路径
            format: 文件格式
            reload_mode: 重载模式
            encoding: 文件编码
            auto_save: 是否自动保存
            save_delay: 保存防抖延迟(秒)
            default_data: 默认数据(文件不存在时使用)
        """
        self.file_path = Path(file_path)
        self.format = format
        self.reload_mode = reload_mode
        self.encoding = encoding
        self.auto_save = auto_save
        self.save_delay = save_delay
        self.default_data = default_data or {}

        # 内部状态
        self._data = DictProxy()
        self._original_data_hash = None
        self._is_modified = False
        self._save_timer: Optional[threading.Timer] = None
        self._observer: Optional[ObserverType] = None
        self._observer_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._callbacks: list[Callable[[DictProxy], None]] = []

        # 确保目录存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # 根据格式选择序列化器
        self._serializer = self._get_serializer()

        # 初始化数据
        self._initialize_data()

    def _get_serializer(self) -> Callable:
        """获取序列化器"""
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

    def _json_serializer(self, data: Dict, mode: str = "dump") -> Any:
        """JSON序列化器"""
        if mode == "dump":
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:  # load
            return json.loads(data)

    def _pickle_serializer(self, data: Dict, mode: str = "dump") -> Any:
        """Pickle序列化器"""
        if mode == "dump":
            return pickle.dumps(data)
        else:  # load
            return pickle.loads(data)

    def _text_serializer(self, data: Dict, mode: str = "dump") -> Any:
        """文本序列化器"""
        if mode == "dump":
            lines = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                lines.append(f"{key}={value}")
            return "\n".join(lines)
        else:  # load
            result = {}
            for line in data.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    # 尝试解析JSON
                    try:
                        value = json.loads(value)
                    except json.decoder.JSONDecodeError:
                        pass
                    result[key.strip()] = value
            return result

    def _yaml_serializer(self, data: Dict, mode: str = "dump") -> Any:
        """YAML序列化器(需要pyyaml)"""
        try:
            import yaml
        except ImportError:
            raise ImportError("YAML格式需要安装pyyaml: pip install pyyaml")

        if mode == "dump":
            return yaml.dump(data, allow_unicode=True, default_flow_style=False)
        else:  # load
            return yaml.safe_load(data)

    def _initialize_data(self) -> None:
        """初始化数据"""
        try:
            if self.file_path.exists():
                self._load_from_file()
            else:
                # 文件不存在，使用默认数据
                self._data = DictProxy(self.default_data)
                if self.auto_save:
                    self.save()
        except Exception as e:
            logger.error(f"初始化数据失败: {e}")
            self._data = DictProxy(self.default_data)

        # 计算数据哈希
        self._update_data_hash()

        # 根据重载模式启动监听
        if self.reload_mode == ReloadMode.AUTO:
            self._start_file_watcher()
        elif self.reload_mode == ReloadMode.TIMED:
            self._start_timed_reloader()

    def _update_data_hash(self) -> None:
        """更新数据哈希"""
        import hashlib

        data_str = json.dumps(self._data.to_dict(), sort_keys=True)
        self._original_data_hash = hashlib.md5(data_str.encode()).hexdigest()

    def _load_from_file(self) -> None:
        """从文件加载数据"""
        with self._lock:
            try:
                if self.format == FileFormat.PICKLE:
                    with open(self.file_path, "rb") as f:
                        raw_data = f.read()
                        loaded = self._serializer(raw_data, mode="load")
                else:
                    with open(self.file_path, "r", encoding=self.encoding) as f:
                        raw_data = f.read()
                        loaded = self._serializer(raw_data, mode="load")

                if not isinstance(loaded, dict):
                    raise ValueError(f"文件内容必须是字典格式，实际为: {type(loaded)}")

                self._data = DictProxy(loaded)
                self._is_modified = False
                logger.debug(f"从文件加载数据: {self.file_path}")

            except Exception as e:
                logger.error(f"加载文件失败 {self.file_path}: {e}")
                raise

    def _save_to_file(self) -> None:
        """保存数据到文件"""
        with self._lock:
            try:
                # 创建临时文件
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

                # 原子操作：重命名临时文件
                temp_file.replace(self.file_path)
                self._is_modified = False
                self._update_data_hash()
                logger.debug(f"数据保存到文件: {self.file_path}")

            except Exception as e:
                logger.error(f"保存文件失败 {self.file_path}: {e}")
                raise

    def _start_file_watcher(self) -> None:
        """启动文件监听器"""

        class FileChangeHandler(FileSystemEventHandler):
            def __init__(self, reloader: SingleFileReloader):
                self.reloader = reloader
                self._last_modified = 0

            def on_modified(self, event: FileModifiedEvent) -> None:
                if not isinstance(event, FileModifiedEvent):
                    return

                if str(Path(event.src_path)) == str(self.reloader.file_path):
                    current_time = time.time()
                    # 防抖：避免频繁触发
                    if current_time - self._last_modified > 0.1:
                        self._last_modified = current_time
                        logger.debug(f"检测到文件变更: {event.src_path}")
                        # 延迟加载，避免文件被其他进程占用
                        threading.Timer(0.1, self.reloader.reload).start()

        try:
            self._observer = Observer()
            handler = FileChangeHandler(self)
            self._observer.schedule(
                handler, str(self.file_path.parent), recursive=False
            )
            self._observer.start()
            logger.debug(f"开始监听文件: {self.file_path}")
        except Exception as e:
            logger.error(f"启动文件监听器失败: {e}")

    def _start_timed_reloader(self) -> None:
        """启动定时重载器"""

        def timed_reload():
            while True:
                time.sleep(30)  # 每30秒检查一次
                if self._check_external_modification():
                    self.reload()

        self._observer_thread = threading.Thread(
            target=timed_reload,
            daemon=True,
            name=f"TimedReloader-{self.file_path.name}",
        )
        self._observer_thread.start()

    def _check_external_modification(self) -> bool:
        """检查文件是否被外部修改"""
        if not self.file_path.exists():
            return False

        try:
            with open(self.file_path, "rb") as f:
                content = f.read()

            import hashlib

            current_hash = hashlib.md5(content).hexdigest()
            return current_hash != self._original_data_hash
        except Exception:
            return False

    def reload(self) -> None:
        """
        重新加载文件数据
        """
        with self._lock:
            try:
                if not self.file_path.exists():
                    logger.warning(f"文件不存在: {self.file_path}")
                    return

                old_data = self._data.to_dict().copy()
                self._load_from_file()

                # 触发回调
                for callback in self._callbacks:
                    try:
                        callback(self._data)
                    except Exception as e:
                        logger.error(f"回调函数执行失败: {e}")

                # 记录差异
                self._log_changes(old_data, self._data.to_dict())

            except Exception as e:
                logger.error(f"重新加载失败: {e}")

    def _log_changes(self, old_data: Dict, new_data: Dict) -> None:
        """记录数据变化"""
        # 找出变化的键
        all_keys = set(old_data.keys()) | set(new_data.keys())
        changed_keys = []

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                changed_keys.append(key)

        # if changed_keys:
        #     logger.debug(f"数据已更新，变化的键: {changed_keys}")

    def save(self, force: bool = False) -> None:
        """
        保存数据到文件

        Args:
            force: 是否强制立即保存(忽略防抖)
        """
        if not self._is_modified and not force:
            return

        if self.save_delay > 0 and not force:
            # 防抖处理
            if self._save_timer:
                self._save_timer.cancel()

            self._save_timer = threading.Timer(self.save_delay, self._save_to_file)
            self._save_timer.start()
        else:
            self._save_to_file()

    def mark_modified(self) -> None:
        """标记数据已修改"""
        self._is_modified = True
        if self.auto_save:
            self.save()

    def register_callback(self, callback: Callable[[DictProxy], None]) -> None:
        """
        注册数据变更回调

        Args:
            callback: 回调函数，接收更新后的DictProxy
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[DictProxy], None]) -> None:
        """取消注册回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_data(self) -> DictProxy:
        """获取数据代理"""
        return self._data

    def get_raw_data(self) -> Dict:
        """获取原始数据"""
        return self._data.to_dict()

    def update_data(self, data: Dict) -> None:
        """更新数据"""
        with self._lock:
            self._data.update(data)
            self.mark_modified()

    def clear_data(self) -> None:
        """清空数据"""
        with self._lock:
            self._data.clear()
            self.mark_modified()

    def backup(self, backup_dir: Optional[Union[str, Path]] = None) -> str:
        """
        创建备份

        Args:
            backup_dir: 备份目录，默认为文件所在目录

        Returns:
            备份文件路径
        """
        if backup_dir is None:
            backup_dir = self.file_path.parent

        backup_path = (
            Path(backup_dir) / f"{self.file_path.stem}.backup{self.file_path.suffix}"
        )

        import shutil

        if self.file_path.exists():
            shutil.copy2(self.file_path, backup_path)
            logger.debug(f"创建备份: {backup_path}")

        return str(backup_path)

    def restore(self, backup_path: Union[str, Path]) -> bool:
        """
        从备份恢复

        Args:
            backup_path: 备份文件路径

        Returns:
            是否恢复成功
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return False

        try:
            import shutil

            shutil.copy2(backup_path, self.file_path)
            self.reload()
            logger.debug(f"从备份恢复: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    def close(self) -> None:
        """关闭重载器，释放资源"""
        # 取消保存定时器
        if self._save_timer:
            self._save_timer.cancel()

        # 停止文件监听
        if self._observer:
            self._observer.stop()
            self._observer.join()

        # 保存未保存的数据
        if self._is_modified:
            self.save(force=True)

        logger.debug(f"重载器已关闭: {self.file_path}")

    def __enter__(self) -> SingleFileReloader:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.mark_modified()

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self.mark_modified()

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return (
            f"SingleFileReloader(file={self.file_path}, modified={self._is_modified})"
        )
