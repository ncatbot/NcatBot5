"""
配置管理器

负责插件的配置加载和保存
"""

import asyncio
import json
from logging import getLogger
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Union

import aiofiles
import aiofiles.os
import yaml

from src.plugins_system.core.mixin import PluginMixin
from src.plugins_system.utils.types import PluginName
from src.utils.file_dog import DictProxy, FileFormat, SingleFileReloader

logger = getLogger("ConfigManager")


class ConfigManager:
    """配置管理器

    负责管理插件的配置文件，采用单例模式避免重复实例化

    Attributes:
        config_base_dir: 配置基础目录
        _instances: 类级别的实例缓存
    """

    _instances: ClassVar[Dict[Path, "ConfigManager"]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __new__(cls, config_base_dir: Path) -> "ConfigManager":
        """确保相同路径返回同一实例"""
        if config_base_dir not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[config_base_dir] = instance
        return cls._instances[config_base_dir]

    def __init__(self, config_base_dir: Path) -> None:
        """初始化（仅第一次有效）"""
        if hasattr(self, "_initialized"):
            return

        self.config_base_dir = Path(config_base_dir)
        self._initialized = True

    async def load_config(self, plugin_name: PluginName) -> Dict[str, Any]:
        """加载插件配置

        按优先级查找：.yaml > .yml > .json

        Args:
            plugin_name: 插件名称

        Returns:
            插件配置字典，失败返回空字典
        """
        plugin_config_dir = self.config_base_dir / plugin_name
        config_files = [
            plugin_config_dir / f"{plugin_name}.yaml",
            plugin_config_dir / f"{plugin_name}.yml",
            plugin_config_dir / f"{plugin_name}.json",
        ]

        for config_file in config_files:
            if await aiofiles.os.path.exists(config_file):
                try:
                    async with aiofiles.open(config_file, "r", encoding="utf-8") as f:
                        content = await f.read()

                    if config_file.suffix in (".yaml", ".yml"):
                        data = yaml.safe_load(content)
                    else:
                        data = json.loads(content)

                    return data if isinstance(data, dict) else {}

                except yaml.YAMLError as e:
                    logger.error(f"YAML解析错误 {config_file}: {e}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误 {config_file}: {e}")
                except Exception as e:
                    logger.warning(f"加载配置 {config_file} 失败: {e}")

        return {}

    async def save_config(
        self,
        plugin_name: PluginName,
        config: Dict[str, Any],
        format: FileFormat = FileFormat.YAML,
    ) -> bool:
        """保存插件配置（原子写入）

        Args:
            plugin_name: 插件名称
            config: 配置字典
            format: 保存格式，默认 YAML

        Returns:
            成功返回 True，失败返回 False
        """
        config = dict(config)
        plugin_config_dir = self.config_base_dir

        try:
            # 确保目录存在
            await aiofiles.os.makedirs(plugin_config_dir, exist_ok=True)

            # 根据格式确定扩展名
            ext = "yaml" if format == FileFormat.YAML else "json"
            config_file = plugin_config_dir / f"{plugin_name}.{ext}"
            temp_file = plugin_config_dir / f".{plugin_name}.{ext}.tmp"

            # 序列化内容
            if format == FileFormat.YAML:
                content = yaml.dump(
                    config,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,  # 保持字典顺序
                )
            else:
                content = json.dumps(config, ensure_ascii=False, indent=2)

            # 原子写入：先写临时文件，再重命名
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(content)

            # 备份旧配置（如果存在）
            if await aiofiles.os.path.exists(config_file):
                backup_file = plugin_config_dir / f"{plugin_name}.{ext}.bak"
                await aiofiles.os.replace(config_file, backup_file)

            await aiofiles.os.replace(temp_file, config_file)
            return True

        except Exception as e:
            logger.error(f"保存配置失败 {plugin_name}: {e}")
            # 清理临时文件
            try:
                if "temp_file" in locals():
                    await aiofiles.os.remove(temp_file)
            except Exception:
                pass
            return False


class ConfigerMixin(PluginMixin):
    """插件配置混入类

    为插件提供独立的 config（配置）和 data（数据）管理
    """

    def __init__(self):
        super().__init__()
        # 每个插件实例独立的管理器引用（通过单例模式共享实际实例）
        self._config_manager: ConfigManager = ConfigManager(self.context.config_dir)
        self._data_manager: ConfigManager = ConfigManager(self.context.data_dir)

        # 内部存储使用 DictProxy
        self._config = DictProxy()
        self._data = DictProxy()

    async def on_mixin_load(self):
        """加载时读取配置"""
        self._config = DictProxy(await self._config_manager.load_config(self.name))
        self._data = DictProxy(await self._data_manager.load_config(self.name))

    async def on_mixin_unload(self):
        """卸载时保存配置"""
        await self._config_manager.save_config(self.name, self._config)
        await self._data_manager.save_config(self.name, self._data)

    # ---------- 只读访问 ----------
    @property
    def config(self) -> DictProxy:
        """插件配置"""
        return self._config

    @property
    def data(self) -> DictProxy:
        """插件数据"""
        return self._data

    # ---------- 整表替换 ----------
    @config.setter
    def config(self, val: Union[Dict[str, Any], DictProxy]) -> None:
        """替换整个配置表"""
        if isinstance(val, dict):
            self._config = DictProxy(val)
        elif isinstance(val, DictProxy):
            self._config = val
        else:
            raise TypeError(f"config 必须是 dict 或 DictProxy，而非 {type(val)}")

    @data.setter
    def data(self, val: Union[Dict[str, Any], DictProxy]) -> None:
        """替换整个数据表"""
        if isinstance(val, dict):
            self._data = DictProxy(val)
        elif isinstance(val, DictProxy):
            self._data = val
        else:
            raise TypeError(f"data 必须是 dict 或 DictProxy，而非 {type(val)}")


class ReloadableConfigerMixin(ConfigerMixin):
    """支持文件热重载的配置混入类

    特性：
    - 监听配置文件变化自动重载
    - 支持手动触发重载
    - 自动创建默认配置文件
    """

    def __init__(self):
        super().__init__()
        self._reloader: Optional[SingleFileReloader] = None
        self._first_load: bool = False  # 是否为首次创建文件

    async def on_mixin_load(self):
        """初始化重载器"""
        await super().on_mixin_load()

        config_dir: Path = self.context.config_dir
        config_file_path = config_dir / f"{self.name}.yaml"

        # 自动创建默认配置文件
        await self._ensure_config_file(config_file_path)
        self.setup_config_file(config_file_path)

    async def _ensure_config_file(self, config_path: Path) -> None:
        """确保配置文件存在"""
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            # 使用 UTF-8 编码写入空对象
            config_path.write_text("# 插件配置\n{}\n", encoding="utf-8")
            self._first_load = True
            logger.info(f"已为插件 {self.name} 创建默认配置文件: {config_path}")

    def setup_config_file(
        self, config_file: Union[str, Path], **reloader_kwargs
    ) -> None:
        """设置配置文件监控

        Args:
            config_file: 配置文件路径
            **reloader_kwargs: 传递给 SingleFileReloader 的参数
        """
        config_path = Path(config_file)

        # 关闭旧的重载器
        if self._reloader:
            self._reloader.close()

        # 创建新的重载器
        self._reloader = SingleFileReloader(
            file_path=config_path, format=FileFormat.YAML, **reloader_kwargs
        )

        # 同步当前配置
        self._config = self._reloader.get_data()

        # 注册变更回调
        self._reloader.register_callback(self._on_config_reloaded)

    def _on_config_reloaded(self, new_data: DictProxy) -> None:
        """配置重载回调（内部使用）"""
        old_data = self._config.copy()
        self._config = new_data

        logger.info(f"插件 {self.name} 配置已热重载")

        # 调用钩子供子类扩展
        self.on_config_reloaded(dict(old_data), dict(new_data))

    def on_config_reloaded(self, old_data: dict, new_data: dict) -> None:
        """配置热重载钩子，子类可重写实现自定义逻辑

        Args:
            old_data: 重载前的配置
            new_data: 重载后的新配置
        """
        pass

    def save_config(self) -> None:
        """手动触发保存（同步调用）"""
        if not self._reloader:
            raise RuntimeError("重载器未初始化")
        self._reloader.save(force=True)

    def reload_config(self) -> None:
        """手动触发重载（同步调用）"""
        if not self._reloader:
            raise RuntimeError("重载器未初始化")
        self._reloader.reload()

    def backup_config(self, backup_dir: Optional[Union[str, Path]] = None) -> str:
        """备份当前配置"""
        if not self._reloader:
            raise RuntimeError("重载器未初始化")
        return self._reloader.backup(backup_dir)

    async def on_mixin_unload(self):
        """清理重载器资源"""
        if self._reloader:
            self._reloader.close()
            self._reloader = None
        await super().on_mixin_unload()

    @property
    def first_load(self) -> bool:
        """是否为首次加载（配置文件刚创建）"""
        return self._first_load
