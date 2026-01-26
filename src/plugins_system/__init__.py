"""插件系统主包

提供完整的插件系统功能，包括事件总线、插件管理和应用程序接口
"""

from .abc.events import EventBus
from .abc.plugins import PluginFinder, PluginLoader
from .app import PluginApplication
from .core.events import Event
from .core.lazy_resolver import LazyDecoratorResolver
from .core.plugins import Plugin, PluginContext, PluginMixin
from .implementations.event_bus import NonBlockingEventBus, SimpleEventBus
from .implementations.plugin_finder import DefaultPluginFinder
from .implementations.plugin_loader import DefaultPluginLoader
from .managers.plugin_manager import DefaultPluginManager, PluginManager

__author__ = "Fish-LP <Fish.zh@outlook.com>"
__status__ = "dev"
__version__ = "3.1.0-dev"

__all__ = [
    # ABC 接口
    "EventBus",
    "PluginManager",
    "PluginLoader",
    "PluginFinder",
    # 核心类
    "Plugin",
    "PluginContext",
    "PluginMixin",
    "Event",
    # 事件总线实现
    "NonBlockingEventBus",
    "SimpleEventBus",
    # 延迟解析
    "LazyDecoratorResolver",
    # 默认实现
    "DefaultPluginManager",
    "DefaultPluginLoader",
    "DefaultPluginFinder",
    # 管理器
    "PluginManager",
    # 应用
    "PluginApplication",
]
