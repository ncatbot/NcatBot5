"""
插件加载器默认实现模块

负责从不同源加载插件类
"""

import asyncio
import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

import aiofiles
import aiofiles.os

from ..abc.events import EventBus
from ..abc.plugins import PluginLoader
from ..core.plugins import Plugin, PluginContext, PluginSource
from ..exceptions import PluginNotFound, PluginValidationError
from ..logger import logger
from ..managers.config_manager import ConfigManager
from ..utils.constants import PluginSourceType
from ..utils.types import PluginName


class DefaultPluginLoader(PluginLoader):
    """默认插件加载器

    支持增强的插件上下文功能
    """

    def __init__(
        self,
        event_bus: "EventBus",
        config_manager: ConfigManager,
        data_base_dir: Path,
        config_base_dir: Path,  # 新增配置基础目录参数
        debug_mode: bool = False,
    ):
        """初始化插件加载器

        Args:
            event_bus: 事件总线实例
            config_manager: 配置管理器
            data_base_dir: 数据基础目录
            config_base_dir: 配置基础目录
            debug_mode: 调试模式
        """
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.data_base_dir = data_base_dir
        self.config_base_dir = config_base_dir  # 保存配置基础目录
        self.debug_mode = debug_mode
        self.plugins: Dict[PluginName, Plugin] = {}
        self._lock = asyncio.Lock()
        self._loaded_modules: Dict[PluginName, Tuple[str, PluginSource]] = {}

    async def load_from_source(self, source: PluginSource) -> List[Plugin]:
        """从源加载插件"""
        _plugins = []
        try:
            if source.source_type == PluginSourceType.DIRECTORY:
                _plugins = await self._load_from_directory(source)
            elif source.source_type == PluginSourceType.ZIP_PACKAGE:
                _plugins = await self._load_from_zip(source)
            elif source.source_type == PluginSourceType.FILE:
                _plugins = await self._load_from_file(source)
            else:
                raise PluginValidationError(f"未知的插件源类型: {source.source_type}")
            self.plugins.update({p.name: p for p in _plugins})
        except PluginNotFound:
            logger.warning(f"{source.path.relative_to('.')})没有找到插件")
        except Exception as e:
            logger.error(f"从源({source.path})加载插件失败: {e}")
        finally:
            return _plugins

    async def _load_from_directory(self, source: PluginSource) -> List[Plugin]:
        """从目录加载插件"""
        plugin_dir = source.path
        module_name = source.module_name

        if not self.debug_mode and module_name in sys.modules:
            logger.debug(f"模块 {module_name} 已加载，跳过重新加载")
            return []

        config = await self.config_manager.load_config(PluginName(module_name))
        data_dir = self.data_base_dir / module_name
        config_dir = self.config_base_dir / module_name  # 创建配置目录

        await aiofiles.os.makedirs(data_dir, exist_ok=True)
        await aiofiles.os.makedirs(config_dir, exist_ok=True)

        sys.path.insert(0, str(plugin_dir.parent))

        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                spec = importlib.util.spec_from_file_location(
                    module_name, plugin_dir / "__init__.py"
                )
                if spec is None:
                    raise PluginValidationError(f"无法为 {plugin_dir} 创建导入规范")

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            plugin_classes = self._find_plugin_classes(module, module_name)
            plugins = []

            for plugin_cls in plugin_classes:
                # 使用插件上下文
                context = PluginContext(
                    event_bus=self.event_bus,
                    plugin_name=plugin_cls.name,
                    data_dir=data_dir,
                    config_dir=config_dir,  # 传入配置目录
                )
                plugin = plugin_cls(context, config, self.debug_mode)
                plugin.module_name = module_name
                self._loaded_modules[plugin.name] = (module_name, source)
                plugins.append(plugin)

            return plugins

        finally:
            if str(plugin_dir.parent) in sys.path:
                sys.path.remove(str(plugin_dir.parent))

    async def _load_from_zip(self, source: PluginSource) -> List[Plugin]:
        """从ZIP包加载插件"""
        try:
            module_name = source.module_name

            if not self.debug_mode and module_name in sys.modules:
                logger.debug(f"模块 {module_name} 已加载，跳过重新加载")
                return []

            config = await self.config_manager.load_config(PluginName(module_name))
            data_dir = self.data_base_dir / module_name
            config_dir = self.config_base_dir / module_name  # 创建配置目录

            await aiofiles.os.makedirs(data_dir, exist_ok=True)
            await aiofiles.os.makedirs(config_dir, exist_ok=True)

            zip_path = str(source.path)
            if zip_path not in sys.path:
                sys.path.insert(0, zip_path)

            try:
                if module_name in sys.modules:
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = importlib.import_module(module_name)

                plugin_classes = self._find_plugin_classes(module, module_name)
                plugins = []

                for plugin_cls in plugin_classes:
                    # 使用增强的插件上下文
                    context = PluginContext(
                        event_bus=self.event_bus,
                        plugin_name=plugin_cls.name,
                        data_dir=data_dir,
                        config_dir=config_dir,  # 传入配置目录
                    )
                    plugin = plugin_cls(context, config, self.debug_mode)
                    plugin.module_name = module_name
                    self._loaded_modules[plugin.name] = (module_name, source)
                    plugins.append(plugin)

                return plugins

            except ImportError as e:
                raise PluginValidationError(f"无法从ZIP文件导入模块 {module_name}:\n{e}")

        except Exception:
            zip_path = str(source.path)
            if zip_path in sys.path:
                sys.path.remove(zip_path)
            raise

    async def _load_from_file(self, source: PluginSource) -> List[Plugin]:
        """从文件加载插件"""
        plugin_file = source.path
        module_name = source.module_name

        if not self.debug_mode and module_name in sys.modules:
            logger.debug(f"模块 {module_name} 已加载，跳过重新加载")
            return []

        config = await self.config_manager.load_config(PluginName(module_name))
        data_dir = self.data_base_dir / module_name
        config_dir = self.config_base_dir / module_name  # 创建配置目录

        await aiofiles.os.makedirs(data_dir, exist_ok=True)
        await aiofiles.os.makedirs(config_dir, exist_ok=True)

        sys.path.insert(0, str(plugin_file.parent))

        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                if spec is None:
                    raise PluginValidationError(f"无法为 {plugin_file} 创建导入规范")

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            plugin_classes = self._find_plugin_classes(module, module_name)
            plugins = []

            for plugin_cls in plugin_classes:
                # 使用增强的插件上下文
                context = PluginContext(
                    event_bus=self.event_bus,
                    plugin_name=plugin_cls.name,
                    data_dir=data_dir.absolute(),
                    config_dir=config_dir.absolute(),  # 传入配置目录
                )
                plugin = plugin_cls(context, config, self.debug_mode)
                plugin.module_name = module_name
                self._loaded_modules[plugin.name] = (module_name, source)
                plugins.append(plugin)

            return plugins

        finally:
            if str(plugin_file.parent) in sys.path:
                sys.path.remove(str(plugin_file.parent))

    def _find_plugin_classes(self, module: Any, module_name: str) -> List[Type[Plugin]]:
        """在模块中查找插件类

        Args:
            module: 要搜索的模块
            module_name: 模块名称

        Returns:
            插件类列表

        Raises:
            PluginValidationError: 当未找到插件类时
        """
        plugin_classes = []

        export_names = getattr(module, "__all__", getattr(module, "__plugin__", None))

        if export_names:
            export_items = []
            for item in export_names:
                if isinstance(item, str):
                    export_items.append(item)
                elif inspect.isclass(item):
                    export_items.append(item.__name__)
                else:
                    logger.warning(f"忽略__all__中的非字符串/类元素: {item}")

            for name in export_items:
                try:
                    obj = getattr(module, name, None)
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, Plugin)
                        and obj is not Plugin
                        and not inspect.isabstract(obj)
                    ):
                        plugin_classes.append(obj)
                except Exception as e:
                    logger.warning(f"获取导出项 {name} 失败:\n{e}")
        else:
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, Plugin)
                    and obj is not Plugin
                    and not inspect.isabstract(obj)
                ):
                    plugin_classes.append(obj)

        if not plugin_classes:
            raise PluginNotFound(f"在模块 {module_name} 中未找到插件类")

        return plugin_classes

    async def unload_plugin_module(self, plugin_name: PluginName) -> bool:
        """卸载插件模块

        Args:
            plugin_name: 插件名称

        Returns:
            如果成功卸载返回True，否则返回False
        """
        if plugin_name not in self._loaded_modules:
            return False

        module_name, source = self._loaded_modules[plugin_name]
        source.cleanup()

        if module_name in self.plugins:
            await self.config_manager.save_config(
                module_name, self.plugins[module_name].config
            )

        # await self.config_manager.save_config(module_name, self.plugins[plugin_name].config)

        del self.plugins[plugin_name]
        del self._loaded_modules[plugin_name]
        return True
