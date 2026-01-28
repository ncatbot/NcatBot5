import re
from typing import (
    Callable,
    Optional,
    Pattern,
    TypeVar,
    Union,
    overload,
)

from src.plugins_system import LazyDecoratorResolver, Plugin
from src.plugins_system.abc.events import EventHandler
from src.plugins_system.core.events import Event
from src.plugins_system.core.lazy_resolver import create_namespaced_decorator

T = TypeVar("T")


class ListenerResolver(LazyDecoratorResolver):
    """监听器解析器"""

    tag = "listener"
    space = "event"

    def handle(self, plugin: Plugin, func: EventHandler, event_bus) -> None:
        """将被标记的函数注册到事件总线，支持 `once` 和 `filter` 元数据。"""
        kw = self.get_kwd(func)
        event = kw.get("event")
        if not event:
            return

        once = kw.get("once", False)
        raw = kw.get("raw", True)
        filter_fn = kw.get("filter")

        import functools
        import inspect

        target = func
        base_func = getattr(func, "__func__", func)
        is_async = inspect.iscoroutinefunction(base_func)

        handler_id = None

        if is_async:

            async def _wrapper(ev: Event):
                nonlocal handler_id
                try:
                    if filter_fn and not filter_fn(ev):
                        return
                    if raw:
                        await target(ev)
                    else:
                        await target(ev.data)

                finally:
                    if once and handler_id:
                        plugin.unregister_handler(handler_id)

            wrapped = functools.wraps(base_func)(_wrapper)
        else:

            def _wrapper(ev: Event):
                nonlocal handler_id
                try:
                    if filter_fn and not filter_fn(ev):
                        return
                    if raw:
                        target(ev)
                    else:
                        target(ev.data)
                finally:
                    if once and handler_id:
                        plugin.unregister_handler(handler_id)

            wrapped = functools.wraps(base_func)(_wrapper)

        # 注册处理器并保存 handler_id（用于 once 注销）
        handler_id = plugin.register_handler(event, wrapped)


@overload
def listener(event: Union[str, Pattern[str]], /) -> Callable[[T], T]:
    """
    基础用法：@listener("message")
    """
    ...


def listener(
    event: Optional[Union[str, Pattern[str]]] = None,
    *,
    raw: bool = True,
    once: bool = False,
    filter: Optional[Callable[[Event], bool]] = None,
) -> Union[Callable[[T], T], T]:
    """
    事件监听器装饰器

    包装 Plugin.register_handler 接口，支持字符串或正则匹配事件。

    Args:
        event: 事件名称（字符串）或匹配模式（正则）
        raw: 是否自动解包事件载荷
        once: 是否仅触发一次后自动注销
        filter: 可选的额外过滤函数

    Returns:
        装饰后的处理器函数，保留原函数签名

    Examples:
        >>> class MyPlugin(Plugin):
        ...     @listener
        ...     def handle_msg(self, e: Event):
        ...         '''监听所有事件'''
        ...         pass
        ...
        ...     @listener(re.compile(r"user_joined|user_left"))
        ...     def handle_members(self, event):
        ...         '''监听成员变动'''
        ...         pass
    """
    # 使用 lazy_resolver 提供的命名空间装饰器工厂，生成兼容的 __mate__ 元数据
    factory = create_namespaced_decorator("listener", "event")

    # 作为无参装饰器使用：@listener
    if (
        callable(event)
        and not isinstance(event, (str,))
        and not hasattr(event, "pattern")
    ):
        return factory(event=re.compile(r".*"))

    # 带参数用法：@listener("evt") 或 @listener(event=..., once=True)
    return factory(event=event, once=once, filter=filter, raw=raw)
