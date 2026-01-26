"""
配置管理器

负责插件的配置加载和保存
"""

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

    负责管理插件的配置文件

    Attributes:
        config_base_dir: 配置基础目录
    """

    def __init__(self, config_base_dir: Path) -> None:
        """初始化配置管理器

        Args:
            config_base_dir: 配置基础目录
        """
        self.config_base_dir = config_base_dir

    async def load_config(self, plugin_name: PluginName) -> Dict[str, Any]:
        """加载插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            插件配置字典
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
                            return yaml.safe_load(content) or {}
                        else:
                            return json.loads(content) or {}
                except Exception as e:
                    logger.warning(f"加载配置 {config_file} 失败:\n{e}")

        return {}

    async def save_config(
        self, plugin_name: PluginName, config: Dict[str, Any]
    ) -> bool:
        """保存插件配置

        Args:
            plugin_name: 插件名称
            config: 配置字典

        Returns:
            如果成功保存返回True，否则返回False
        """
        try:
            config = dict(config)
            plugin_config_dir = self.config_base_dir / plugin_name
            await aiofiles.os.makedirs(plugin_config_dir, exist_ok=True)

            config_file = plugin_config_dir / f"{plugin_name}.yaml"
            async with aiofiles.open(config_file, "w", encoding="utf-8") as f:
                await f.write(
                    yaml.dump(config, default_flow_style=False, allow_unicode=True)
                )

            return True
        except Exception as e:
            logger.error(f"保存配置失败 {plugin_name}:\n{e}")
            return False


class ConfigerMixin(PluginMixin):

    __config_manager: ClassVar[ConfigManager]

    def __init__(self):
        self.__config_manager = ConfigManager(self.context.config_dir)
        self._config = DictProxy()
        self._data = DictProxy()

    async def on_mixin_load(self):
        await self.__config_manager.load_config(self.name)

    # ---------- 只读访问 ----------
    @property
    def config(self) -> DictProxy:
        return self._config

    @property
    def data(self) -> DictProxy:
        return self._data

    # ---------- 整表替换 ----------
    @config.setter
    def config(self, val: Dict[str, Any] | DictProxy) -> None:
        if not getattr(self, "_config", None):
            self._config = DictProxy()
        if isinstance(val, dict):
            self._config = DictProxy(val)
        elif isinstance(val, DictProxy):
            self._config = val
        else:
            raise ValueError("未知的字典设置类型")

    @data.setter
    def data(self, val: Dict[str, Any] | DictProxy) -> None:
        if not getattr(self, "_data", None):
            self._config = DictProxy()
        if isinstance(val, dict):
            self._config = DictProxy(val)
        elif isinstance(val, DictProxy):
            self._config = val
        else:
            raise ValueError("未知的字典设置类型")


class ReloadableConfigerMixin(ConfigerMixin):
    """
    支持文件重载的ConfigerMixin扩展
    """

    def __init__(self):
        """
        初始化

        Args:
            config_file: 配置文件路径
            **kwargs: 传递给SingleFileReloader的参数
        """
        ConfigerMixin.__init__(self)
        self._reloader: Optional[SingleFileReloader] = None

    async def on_mixin_load(self):
        await ConfigerMixin.on_mixin_load(self)
        config_dir: Path = self.config_dir
        config_file_path = config_dir / f"{self.name}.yaml"
        if not config_file_path.is_file():
            config_file_path.parent.mkdir(parents=True, exist_ok=True)
            config_file_path.touch(exist_ok=True)
            config_file_path.write_text(r"{}", encoding="utf-8")
        self.setup_config_file(config_file_path)

    def setup_config_file(
        self, config_file: Union[str, Path], **reloader_kwargs
    ) -> None:
        """
        设置配置文件

        Args:
            config_file: 配置文件路径
            **reloader_kwargs: 传递给SingleFileReloader的参数
        """
        # 关闭现有的重载器
        if self._reloader:
            self._reloader.close()

        # 创建新的重载器
        self._reloader = SingleFileReloader(
            file_path=config_file, format=FileFormat.YAML, **reloader_kwargs
        )

        # 将重载器的数据同步到config
        self.config = self._reloader.get_data()

        # 注册回调，当文件变化时更新config
        self._reloader.register_callback(self._on_config_reloaded)

    def _on_config_reloaded(self, new_data: DictProxy) -> None:
        """配置文件重新加载时的回调"""
        self.config = new_data
        # 可以在这里添加额外的处理逻辑
        self.on_config_reloaded()

    def on_config_reloaded(self) -> None:
        """配置文件重新加载时的钩子方法，子类可以重写"""
        pass

    def save_config(self) -> None:
        """保存配置到文件"""
        if self._reloader:
            self._reloader.save(force=True)

    def reload_config(self) -> None:
        """重新加载配置文件"""
        if self._reloader:
            self._reloader.reload()

    def backup_config(self, backup_dir: Optional[Union[str, Path]] = None) -> str:
        """备份配置文件"""
        if self._reloader:
            return self._reloader.backup(backup_dir)
        raise RuntimeError("未设置配置文件")

    def on_mixin_unload(self):
        """插件卸载时的处理"""
        if self._reloader:
            self._reloader.close()
