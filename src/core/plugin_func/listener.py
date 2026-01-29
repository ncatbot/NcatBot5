import functools
import inspect
import re
from typing import (
    Any,
    Callable,
    Optional,
    Pattern,
    TypeVar,
    Union,
    overload,
)

# 假设这些是从你的项目结构中导入的
from src.plugins_system import LazyDecoratorResolver, Plugin
from src.plugins_system.abc.events import EventHandler
from src.plugins_system.core.events import Event
from src.plugins_system.core.lazy_resolver import create_namespaced_decorator

T = TypeVar("T", bound=Callable[..., Any])


class ListenerResolver(LazyDecoratorResolver):
    """监听器解析器"""

    tag = "listener"
    space = "listener"

    def handle(self, plugin: Plugin, func: EventHandler, event_bus) -> None:
        """将被标记的函数注册到事件总线，支持 `once` 和 `filter` 元数据。"""
        # 获取 'listener' 命名空间下的数据字典
        kw = self.get_kwd(func)

        # 修正：键名是 'event'，而不是 'listener'
        # 'listener' 是 space（命名空间），'event' 是存储在其中的参数名
        event = kw.get("event")
        if not event:
            return

        once = kw.get("once", False)
        raw = kw.get("raw", True)
        filter_fn = kw.get("filter")

        # 获取原始函数以检查是否为异步
        base_func = getattr(func, "__func__", func)
        is_async = inspect.iscoroutinefunction(base_func)

        # 用于存储注册后的 ID，以便在 once=True 时注销
        handler_id = None

        def _make_wrapper(target: Callable) -> Callable:
            """工厂函数：生成同步或异步的包装器"""
            if is_async:

                async def _wrapper(ev: Event):
                    nonlocal handler_id
                    try:
                        # 过滤检查
                        if filter_fn and not filter_fn(ev):
                            return

                        # 执行逻辑
                        if raw:
                            await target(ev)
                        else:
                            await target(ev.data)
                    finally:
                        # 如果是一次性监听，执行后注销
                        if once and handler_id:
                            plugin.unregister_handler(handler_id)

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

            return _wrapper

        # 创建包装器并保留原函数的元信息（如 __name__, __doc__）
        wrapper = _make_wrapper(func)
        wrapped = functools.wraps(base_func)(wrapper)

        # 注册处理器，获取 ID
        # 注意：handler_id 在 wrapper 定义后被赋值，由于闭包引用，wrapper 内部能获取到更新后的值
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
        event: 事件名称（字符串）或匹配模式（正则）。
        raw: 是否自动解包事件载荷。
        once: 是否仅触发一次后自动注销。
        filter: 可选的额外过滤函数。

    Returns:
        装饰器或装饰后的函数
    """

    # 获取命名空间装饰器工厂
    factory = create_namespaced_decorator("listener", "listener")

    # -------------------------------------------------------
    # 情况 1: 无参装饰器 @listener
    # 此时第一个参数 event 实际上是被装饰的函数
    # -------------------------------------------------------
    if callable(event) and not isinstance(event, str) and not hasattr(event, "pattern"):
        func: T = event

        # 使用默认参数构建装饰器
        return factory(event=re.compile(r".*"), raw=raw, once=once, filter=filter)(func)

    # -------------------------------------------------------
    # 情况 2: 带参数装饰器 @listener(...) 或 @listener("xxx")
    # -------------------------------------------------------

    # 处理默认事件：如果没有指定 event，则匹配所有
    actual_event = event if event is not None else re.compile(r".*")

    # 返回装饰器函数（等待接收被装饰的函数）
    return factory(event=actual_event, raw=raw, once=once, filter=filter)
