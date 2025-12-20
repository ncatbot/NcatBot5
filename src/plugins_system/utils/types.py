"""
类型定义

包含插件系统中使用的所有类型别名和新型类型定义
"""

from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias, Union

if TYPE_CHECKING:
    from ..core.events import Event

# 基础类型定义
PluginName: TypeAlias = str
"""插件名称类型"""

PluginVersion: TypeAlias = str
"""插件版本类型"""

# 事件处理器类型
SyncHandler: TypeAlias = Callable[["Event"], Any]
"""同步事件处理器类型"""

AsyncHandler: TypeAlias = Callable[["Event"], Awaitable[Any]]
"""异步事件处理器类型"""

EventHandler: TypeAlias = Union[SyncHandler, AsyncHandler]
"""通用事件处理器类型"""


# 事件拦截器
SyncInterceptor: TypeAlias = Callable[["Event"], Union[bool, "Event", None]]
"""同步事件处理器类型"""

AsyncInterceptor: TypeAlias = Callable[["Event"], Awaitable[Union[bool, "Event", None]]]
"""异步事件处理器类型"""

EventInterceptor: TypeAlias = Union[SyncInterceptor, AsyncInterceptor]
