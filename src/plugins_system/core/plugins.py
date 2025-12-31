"""
插件核心类

包含插件相关的核心数据类和实现
"""

import asyncio
import inspect
import logging
import sys
import time
import uuid
from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from re import Pattern
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Type, Union
from uuid import UUID

from ..abc.events import EventBus
from ..core.lazy_resolver import LazyDecoratorResolver
from ..exceptions import PluginValidationError
from ..utils.constants import NAMESPACE, PROTOCOL_VERSION, PluginSourceType, PluginState
from ..utils.types import EventHandler, PluginName, PluginVersion
from .mixin import PluginMixin


@dataclass
class PluginStatus:
    """插件状态类"""

    state: PluginState
    error: Optional[Exception] = None
    last_updated: float = field(default_factory=time.time)

    def __str__(self) -> str:
        suffix = f": {self.error}" if self.error else ""
        return f"{self.state.name}{suffix}"


@dataclass
class PluginSource:
    """插件源类"""

    source_type: PluginSourceType
    path: Path
    module_name: str

    def cleanup(self) -> None:
        """清理插件源资源"""
        if self.source_type == PluginSourceType.ZIP_PACKAGE:
            zip_path = str(self.path)
            if zip_path in sys.path:
                sys.path.remove(zip_path)

            modules_to_remove = []
            for name, module in sys.modules.items():
                if (
                    hasattr(module, "__file__")
                    and module.__file__
                    and zip_path in module.__file__
                ):
                    modules_to_remove.append(name)

            for name in modules_to_remove:
                del sys.modules[name]


class PluginContext:
    """插件上下文类 - 简化版本"""

    def __init__(
        self,
        event_bus: EventBus,
        plugin_name: PluginName,
        data_dir: Path,
        config_dir: Path,
    ):
        self.event_bus = event_bus
        self.plugin_name = plugin_name
        self.data_dir = data_dir
        self.config_dir = config_dir
        self.event_handlers: Dict[UUID, Union[str, Pattern[str]]] = {}
        self.original_cwd: Optional[Path] = None

        # 功能开关
        # self._enable_data_dir_execution = FeatureFlags.ENABLE_RUN_IN_DATA_DIR

    def register_handler(
        self,
        event: Union[str, Pattern[str]],
        handler: EventHandler,
        # run_in_data_dir: Optional[bool] = None
    ) -> UUID:
        """注册事件处理器"""
        # should_run_in_data_dir = (
        #     run_in_data_dir if run_in_data_dir is not None
        #     else self._enable_data_dir_execution
        # )

        # if should_run_in_data_dir and not getattr(handler, '_data_dir_wrapped', False):
        #     handler = self._wrap_handler_for_data_dir(handler)

        handler_id = self.event_bus.register_handler(event, handler, self.plugin_name)
        self.event_handlers[handler_id] = event
        return handler_id

    # def _wrap_handler_for_data_dir(self, handler: EventHandler) -> EventHandler:
    #     """包装处理器以在数据目录中执行"""
    #     if inspect.iscoroutinefunction(handler):
    #         @functools.wraps(handler)
    #         async def async_wrapper(event: Event) -> Any:
    #             with self.working_directory():
    #                 return await handler(event)
    #         async_wrapper._data_dir_wrapped = True
    #         return async_wrapper
    #     else:
    #         @functools.wraps(handler)
    #         def sync_wrapper(event: Event) -> Any:
    #             with self.working_directory():
    #                 return handler(event)
    #         sync_wrapper._data_dir_wrapped = True
    #         return sync_wrapper

    def register_handlers(
        self,
        event_handlers: Dict[Union[str, Pattern[str]], EventHandler],
        # run_in_data_dir: Optional[bool] = None
    ) -> Dict[Union[str, Pattern[str]], UUID]:
        """批量注册事件处理器"""
        return {
            # event: self.register_handler(event, handler, run_in_data_dir)
            event: self.register_handler(event, handler)
            for event, handler in event_handlers.items()
        }

    def unregister_handler(self, handler_id: UUID) -> bool:
        """取消注册事件处理器"""
        if handler_id in self.event_handlers:
            result = self.event_bus.unregister_handler(handler_id)
            if result:
                del self.event_handlers[handler_id]
            return result
        return False

    # @contextmanager
    # def working_directory(self):
    #     """切换工作目录到插件数据目录"""
    #     if self.original_cwd is None:
    #         self.original_cwd = Path.cwd()
    #     try:
    #         self.data_dir.mkdir(parents=True, exist_ok=True)
    #         os.chdir(self.data_dir)
    #         yield self.data_dir
    #     finally:
    #         if self.original_cwd:
    #             os.chdir(self.original_cwd)

    # async def run_in_data_dir(self, coro_func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    #     """在插件数据目录中运行函数"""
    #     with self.working_directory():
    #         return await run_any(coro_func, *args, **kwargs)

    def get_data_dir(self) -> Path:
        """获取插件数据目录"""
        return self.data_dir

    def get_config_dir(self) -> Optional[Path]:
        """获取插件配置目录"""
        return self.config_dir

    def close(self) -> None:
        """清理上下文资源"""
        for handler_id in list(self.event_handlers.keys()):
            self.unregister_handler(handler_id)

        # if self.original_cwd:
        #     os.chdir(self.original_cwd)


class PluginMeta(ABCMeta):
    """插件元类 - 简化版本"""

    __All_Plugins: dict[UUID, "Plugin"] = {}

    def __init__(
        cls, name: str, bases: Tuple[type, ...], attrs: Dict[str, Any]
    ) -> None:
        super().__init__(name, bases, attrs)
        if getattr(cls, "__abstractmethods__", None):  # 这里用真值判断即可
            return

        # 验证必需属性
        if not hasattr(cls, "name") or not cls.name:
            raise PluginValidationError(f"插件 {name} 必须有一个非空的 'name' 属性")
        if not hasattr(cls, "version") or not cls.version:
            raise PluginValidationError(f"插件 {name} 必须有一个非空的 'version' 属性")

        # 类型转换和标准化
        if not isinstance(cls.name, str):
            cls.name = str(cls.name)
        if not isinstance(cls.version, str):
            cls.version = str(cls.version)

        # 设置id ( name + version + authors )
        unique_authors = {a.strip() for a in cls.authors if a.strip()}
        seed = f"{cls.name}|{cls.version}|{'|'.join(sorted(unique_authors))}"
        cls._id = uuid.uuid5(NAMESPACE, seed)

        # 设置混入类工具
        cls._plugin = cls

        # 处理作者信息
        raw = getattr(cls, "authors", None)
        if raw is None:
            cls.authors = []
        elif isinstance(raw, str):
            cls.authors = [raw]
        elif isinstance(raw, Iterable):
            cls.authors = [str(a) for a in raw if a is not None]
        else:
            cls.authors = []

        # 处理依赖和协议版本
        if not hasattr(cls, "dependency") or not isinstance(cls.dependency, dict):
            cls.dependency = {}
        if not hasattr(cls, "protocol_version"):
            cls.protocol_version = PROTOCOL_VERSION

        # 自动收集混入类
        cls._mixins: List[Type[PluginMixin]] = []
        for base in bases:
            if (
                inspect.isclass(base)
                and issubclass(base, PluginMixin)
                and base is not PluginMixin
            ):
                cls._mixins.append(base)

        # 从类属性中收集混入类
        for attr_name, attr_value in attrs.items():
            if (
                isinstance(attr_value, type)
                and issubclass(attr_value, PluginMixin)
                and attr_value is not PluginMixin
                and attr_value not in cls._mixins
            ):
                cls._mixins.append(attr_value)

        cls.__All_Plugins[cls._id] = cls


class Plugin(ABC, metaclass=PluginMeta):
    """插件基类"""

    # * 必需属性 - 子类必须覆盖
    name: PluginName
    version: PluginVersion

    # * 可选属性 - 子类可以覆盖
    authors: List[str] = []
    dependency: Dict[PluginName, str] = {}

    # * 只读属性 - 子类禁止覆盖
    protocol_version: int = PROTOCOL_VERSION
    id: UUID

    def __init__(
        self, context: PluginContext, config: Dict[str, Any], debug: bool = False
    ):
        """初始化插件

        Args:
            context: 插件上下文 - 用于保存插件运行环境数据
            config: 插件配置 - 支持子类覆盖默认配置
            debug: 调试模式
        """
        # 设置基本属性
        self.context = context
        self.config = config
        self._status = PluginStatus(PluginState.LOADED)
        self._module_name: Optional[str] = None
        self._debug = debug

        # 设置日志器
        self.logger = logging.getLogger(f"Plugin.{self.name}")

        # 混入类管理
        self._mixin_loaded: Set[Type[PluginMixin]] = set()

        # 调用父类初始化
        super().__init__()

        # 初始化混入类
        self._setup_mixins()

    # ==================== 便捷方法包装 ====================

    def register_handler(
        self,
        event: Union[str, Pattern[str]],
        handler: EventHandler,
        # run_in_data_dir: Optional[bool] = None
    ) -> UUID:
        """注册事件处理器"""
        # return self.context.register_handler(event, handler, run_in_data_dir)
        return self.context.register_handler(event, handler)

    def register_handlers(
        self,
        event_handlers: Dict[Union[str, Pattern[str]], EventHandler],
        # run_in_data_dir: Optional[bool] = None
    ) -> Dict[Union[str, Pattern[str]], UUID]:
        """批量注册事件处理器"""
        # return self.context.register_handlers(event_handlers, run_in_data_dir)
        return self.context.register_handlers(event_handlers)

    def unregister_handler(self, handler_id: UUID) -> bool:
        """取消注册事件处理器"""
        return self.context.unregister_handler(handler_id)

    def publish_event(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
    ) -> None:
        """发布事件

        Args:
            event: 事件名称
            data: 事件数据
            source: 事件源
            target: 事件目标
        """
        return self.event_bus.publish(
            event=event, data=data, source=source, target=target
        )

    async def request_event(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Dict[UUID, Union[Any, Exception]]:
        """请求-响应模式

        Args:
            event: 事件名称
            data: 事件数据
            source: 事件源
            target: 事件目标
            timeout: 超时时间（秒）

        Returns:
            处理器ID到结果的映射
        """
        return await self.event_bus.request(
            event=event,
            data=data,
            source=source,
            target=target,
            timeout=timeout,
        )

    # ==================== 路径管理 ====================

    @property
    def data_dir(self) -> Path:
        """获取插件数据目录"""
        return self.context.get_data_dir()

    @property
    def config_dir(self) -> Optional[Path]:
        """获取插件配置目录"""
        return self.context.get_config_dir()

    def get_config_file_path(self, filename: str) -> Path:
        """获取配置文件路径"""
        config_dir = self.context.get_config_dir()
        return config_dir / filename

    def get_data_file_path(self, filename: str) -> Path:
        """获取数据文件路径"""
        data_dir = self.context.get_data_dir()
        return data_dir / filename

    # ==================== 数据目录执行控制 ====================

    # async def run_in_data_dir(self, coro_func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    #     """在插件数据目录中运行函数"""
    #     return await self.context.run_in_data_dir(coro_func, *args, **kwargs)

    # @contextmanager
    # def working_directory(self):
    #     """切换工作目录到插件数据目录"""
    #     with self.context.working_directory():
    #         yield self.get_data_dir()

    # ==================== 混入类管理 ====================

    def _setup_mixins(self) -> None:
        """设置混入类"""
        for mixin_class in self._mixins:
            if isinstance(self, mixin_class):
                # 调用混入类的初始化方法
                if (
                    hasattr(mixin_class, "__init__")
                    and mixin_class.__init__ is not object.__init__
                ):
                    # 确保混入类的 __init__ 被正确调用
                    mixin_class.__init__(self)

                # 设置插件引用
                if hasattr(mixin_class, "_set_plugin"):
                    mixin_class._set_plugin(self, self)

    async def _load_mixins(self) -> None:
        """加载所有混入类"""
        for mixin_class in self._mixins:
            if mixin_class in self._mixin_loaded:
                continue

            if isinstance(self, mixin_class):
                # 调用混入类的加载方法
                if hasattr(mixin_class, "on_mixin_load"):
                    try:
                        method = getattr(mixin_class, "on_mixin_load")
                        result = await method(self)
                        if asyncio.iscoroutine(result):
                            await result
                        self._mixin_loaded.add(mixin_class)
                        self.logger.debug(f"混入类 {mixin_class.__name__} 加载完成")
                    except Exception as e:
                        self.logger.error(f"混入类 {mixin_class.__name__} 加载失败: {e}")

    async def _unload_mixins(self) -> None:
        """卸载所有混入类"""
        for mixin_class in reversed(list(self._mixin_loaded)):
            if isinstance(self, mixin_class):
                if hasattr(mixin_class, "on_mixin_unload"):
                    try:
                        method = getattr(mixin_class, "on_mixin_unload")
                        result = await method(self)
                        if asyncio.iscoroutine(result):
                            await result
                        self.logger.debug(f"混入类 {mixin_class.__name__} 卸载完成")
                    except Exception as e:
                        self.logger.error(f"混入类 {mixin_class.__name__} 卸载失败: {e}")

        self._mixin_loaded.clear()

    def _apply_decorators(self) -> None:
        """应用所有延迟装饰器"""
        event_bus = self.context.event_bus

        for attr_name in dir(self):
            # if attr_name.startswith('_'):
            #     continue

            attr_value = getattr(self, attr_name)

            if not callable(attr_value):
                continue

            for resolver in LazyDecoratorResolver.get_all_resolvers():
                if resolver.check(self, attr_value, event_bus):
                    try:
                        resolver.handle(self, attr_value, event_bus)
                        self.logger.debug(
                            f"应用装饰器: {resolver.__class__.__name__} -> {attr_name}"
                        )
                    except Exception as e:
                        self.logger.error(f"应用装饰器失败 {attr_name}: {e}")

    # ==================== 插件生命周期 ====================

    async def _internal_on_load(self) -> None:
        """内部加载方法"""
        try:
            # 加载混入类
            await self._load_mixins()

            # 应用延迟装饰器
            self._apply_decorators()

            # 调用用户定义的on_load
            result = self.on_load()
            if asyncio.iscoroutine(result):
                await result

            self._set_status(PluginState.RUNNING)

        except Exception as e:
            self.logger.error(f"插件 {self.name} 加载过程中发生错误: {e}")
            self._set_status(PluginState.FAILED, e)
            raise

    async def _internal_on_unload(self) -> None:
        """内部卸载方法"""
        try:
            # 调用用户定义的on_unload
            result = self.on_unload()
            if asyncio.iscoroutine(result):
                await result

            # 卸载混入类
            await self._unload_mixins()

            self._set_status(PluginState.UNLOADED)

        except Exception as e:
            self.logger.error(f"插件 {self.name} 卸载过程中发生错误: {e}")
            self._set_status(PluginState.FAILED, e)
            raise

    # ==================== 属性访问 ====================
    @property
    def id(cls) -> UUID:
        return cls._id

    @property
    def meta(self) -> Dict[str, Any]:
        """获取插件元数据"""
        return {
            "name": self.name,
            "version": self.version,
            "authors": self.authors,
            "dependency": self.dependency,
            "protocol_version": self.protocol_version,
        }

    @property
    def status(self) -> PluginStatus:
        """获取插件状态"""
        return self._status

    @property
    def debug(self) -> bool:
        """获取调试模式状态"""
        return self._debug

    @property
    def module_name(self) -> Optional[str]:
        """获取模块名称"""
        return self._module_name

    @module_name.setter
    def module_name(self, module_name: str) -> None:
        """设置模块名称"""
        self._module_name = module_name

    @property
    def mixins(self) -> List[Type[PluginMixin]]:
        """获取所有混入类类型"""
        return self._mixins.copy()

    @property
    def event_bus(self) -> EventBus:
        return self.context.event_bus

    def has_mixin(self, mixin_class: Type[PluginMixin]) -> bool:
        """检查是否具有指定类型的混入类"""
        return mixin_class in self._mixins

    def is_mixin_loaded(self, mixin_class: Type[PluginMixin]) -> bool:
        """检查指定混入类是否已加载"""
        return mixin_class in self._mixin_loaded

    @abstractmethod
    async def on_load(self) -> None:
        """插件加载时的回调 —— 子类允许同步或异步实现"""
        raise NotImplementedError

    async def on_unload(self) -> None:
        """插件卸载时的回调 - 子类允许同步或异步实现"""
        self.logger.info(f"插件 {self.name} 正在关闭...")

    def _set_status(
        self, state: PluginState, error: Optional[Exception] = None
    ) -> None:
        """设置插件状态"""
        self._status = PluginStatus(state, error, time.time())

    def __str__(self) -> str:
        """返回插件的字符串表示"""
        loaded_mixins = len(self._mixin_loaded)
        total_mixins = len(self._mixins)
        mixin_info = f", mixins={loaded_mixins}/{total_mixins}" if self._mixins else ""
        # data_dir_enabled = ", data_dir=enabled" if self.is_data_dir_execution_enabled() else ""
        # return f"Plugin({self.name}, v{self.version}, status={self.status}{mixin_info}{data_dir_enabled})"
        return f"Plugin({self.name}, v{self.version}, status={self.status}{mixin_info})"
