"""
事件核心类

包含事件相关的核心数据类和实现
"""

import asyncio
import inspect
import logging
import threading
import time
import traceback
from abc import abstractmethod
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

from ..abc.events import EventBus
from ..utils.constants import DEBUG_MODE, FeatureFlags
from ..utils.helpers import _get_current_task_name
from ..utils.types import EventHandler, EventInterceptor, PluginName

T = TypeVar("T")

logger = logging.getLogger("PluginsSys")


@dataclass
class Event(Generic[T]):
    """事件类

    表示在事件总线中传递的事件对象

    Attributes:
        event: 事件名称
        data: 事件数据
        source: 事件源
        target: 事件目标
        timestamp: 事件时间戳
        id: 事件唯一ID
        created_thread: 创建事件的线程名称
        created_task: 创建事件的任务名称
        creation_stack: 创建堆栈（调试模式）
        metadata: 事件元数据
    """

    event: str
    data: Optional[T] = None
    source: Optional[Any] = None
    target: Optional[Any] = None
    timestamp: float = field(default_factory=time.time)
    id: UUID = field(default_factory=uuid4)
    created_thread: str = field(default_factory=lambda: threading.current_thread().name)
    created_task: Optional[str] = field(default_factory=_get_current_task_name)

    if DEBUG_MODE:
        creation_stack: Optional[str] = field(
            default_factory=lambda: "".join(traceback.format_stack(limit=6))
        )
    else:
        creation_stack: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """返回事件的字符串表示

        Returns:
            格式化的事件字符串
        """
        src = self.source or "None"
        dst = self.target or "*"
        return (
            "Event("
            f'"{self.event}", '
            f"[{src}]->[{dst}], "
            f"id={self.id}, "
            f"timestamp={self.timestamp:.3f})"
            ")"
        )

    def __repr__(self) -> str:
        """返回事件的详细表示

        Returns:
            事件的详细字符串表示
        """
        return f"Event.from_dict({self.to_dict()!r})"

    def to_dict(self, *, include_stack: bool = False) -> Dict[str, Any]:
        """将事件转换为字典

        Args:
            include_stack: 是否包含堆栈信息

        Returns:
            事件字典表示
        """
        if not DEBUG_MODE and include_stack:
            logger.warning(
                "包含堆栈信息（include_stack=True）在非调试模式（DEBUG_MODE=False）下 "
            )

        d = {
            "id": str(self.id),
            "event": self.event,
            "data": self.data,
            "source": repr(self.source),
            "target": repr(self.target),
            "timestamp": self.timestamp,
            "created_thread": self.created_thread,
            "created_task": self.created_task,
            "metadata": self.metadata,
        }
        if include_stack:
            d["creation_stack"] = self.creation_stack
        return d


@dataclass
class EventHandlerInfo:
    """事件处理器信息类

    Attributes:
        handler: 事件处理器函数
        event_pattern: 事件模式
        handler_id: 处理器ID
        is_regex: 是否为正则表达式模式
        plugin_name: 关联的插件名称
    """

    handler: EventHandler
    event_pattern: Union[str, Pattern[str]]
    handler_id: UUID
    is_regex: bool = False
    plugin_name: Optional["PluginName"] = None

    def matches_event(self, event_name: str) -> bool:
        """检查事件是否匹配处理器

        Args:
            event_name: 事件名称

        Returns:
            如果匹配返回True，否则返回False
        """
        if self.is_regex:
            return self.event_pattern.match(event_name) is not None
        else:
            return self.event_pattern == event_name


class EventBusBase(EventBus):
    """事件总线基类

    实现事件总线的通用行为

    Attributes:
        _handlers: 处理器映射
        _plugin_handlers: 插件处理器映射
        _lock: 线程锁
        _closed: 是否已关闭
    """

    def __init__(self) -> None:
        """初始化事件总线基类"""
        self._handlers: Dict[UUID, EventHandlerInfo] = {}
        self._plugin_handlers: Dict[PluginName, Set[UUID]] = {}
        self._interceptors: Dict[UUID, EventInterceptor] = {}
        self._interceptor_order: List[UUID] = []
        self._lock = threading.RLock()
        self._closed = False

    def register_interceptor(
        self,
        interceptor: EventInterceptor,
    ) -> UUID:
        """注册事件拦截器

        Args:
            interceptor: 事件拦截器实例

        Returns:
            拦截器UUID

        Raises:
            RuntimeError: 当事件总线已关闭时
            NotImplementedError: 当事件总线不支持拦截器时抛出
        """
        if self._closed:
            raise RuntimeError("事件总线已关闭")

        interceptor_id = uuid4()

        with self._lock:
            self._interceptors[interceptor_id] = interceptor
            self._interceptor_order.append(interceptor_id)

        logger.debug(f"[{self.__class__.__name__}] 注册拦截器: {interceptor_id}")
        return interceptor_id

    def unregister_interceptor(self, uuid: UUID) -> bool:
        """取消注册事件拦截器

        Args:
            uuid: 要取消的拦截器id

        Returns:
            如果成功取消返回True，否则返回False

        Raises:
            NotImplementedError: 当事件总线不支持拦截器时抛出
        """
        with self._lock:
            if uuid in self._interceptors:
                del self._interceptors[uuid]
                if uuid in self._interceptor_order:
                    self._interceptor_order.remove(uuid)
                logger.debug(f"[{self.__class__.__name__}] 卸载拦截器: {uuid}")
                return True
        return False

    async def _run_interceptors(self, event: Event) -> Tuple[Event, bool]:
        """执行所有拦截器

        Args:
            event: 原始事件对象

        Returns:
            Tuple[处理后的事件, 是否被拦截]
        """
        current_event = event
        intercepted = False

        for interceptor_id in self._interceptor_order:
            if interceptor_id not in self._interceptors:
                continue

            interceptor = self._interceptors[interceptor_id]

            try:
                if inspect.iscoroutinefunction(interceptor):
                    result = await interceptor(current_event)
                else:
                    result = interceptor(current_event)

                # 处理拦截器返回值
                if result is True:
                    # 拦截事件，停止后续处理
                    intercepted = True
                    if FeatureFlags.INTERCEPTOR_SHORT_CIRCUIT:
                        logger.debug(
                            f"拦截器 {interceptor_id} 拦截了事件: {current_event}"
                        )
                        return current_event, True
                    # 如果不短路，继续执行但标记为已拦截
                    intercepted = True

                elif isinstance(result, Event):
                    # 替换事件
                    logger.debug(f"拦截器 {interceptor_id} 替换了事件: {result}")
                    current_event = result

                elif result is False or result is None:
                    # 无行为，继续执行
                    pass

                else:
                    logger.warning(
                        f"拦截器 {interceptor_id} 返回了不支持的类型: {type(result)}"
                    )

            except Exception as e:
                logger.exception(f"拦截器 {interceptor_id} 执行异常: {e}")
                # 拦截器异常不影响其他拦截器执行

        return current_event, intercepted

    def register_handler(
        self,
        event: Union[str, Pattern[str]],
        handler: EventHandler,
        plugin_name: Optional[PluginName] = None,
    ) -> UUID:
        """注册事件处理器

        Args:
            event: 事件模式
            handler: 事件处理器
            plugin_name: 插件名称

        Returns:
            处理器ID

        Raises:
            RuntimeError: 当事件总线已关闭时
        """
        if self._closed:
            raise RuntimeError("事件总线已关闭")

        from ..utils.helpers import compile_event_pattern, handler_to_uuid

        pattern, is_regex = compile_event_pattern(event)
        handler_id = handler_to_uuid(handler)

        with self._lock:
            if handler_id in self._handlers:
                logger.warning(f"处理器 {handler_id} 已存在，将被覆盖")

            self._handlers[handler_id] = EventHandlerInfo(
                handler=handler,
                event_pattern=pattern,
                handler_id=handler_id,
                is_regex=is_regex,
                plugin_name=plugin_name,
            )

            if plugin_name:
                if plugin_name not in self._plugin_handlers:
                    self._plugin_handlers[plugin_name] = set()
                self._plugin_handlers[plugin_name].add(handler_id)

        logger.debug(
            f"[{handler.__class__.__name__}] 注册 handler: {pattern} -> {handler_id}"
        )
        return handler_id

    def register_handlers(
        self,
        event_handlers: Dict[Union[str, Pattern[str]], EventHandler],
        plugin_name: Optional[PluginName] = None,
    ) -> Dict[Union[str, Pattern[str]], UUID]:
        """批量注册事件处理器

        Args:
            event_handlers: 事件处理器字典
            plugin_name: 插件名称

        Returns:
            处理器ID字典
        """
        return {
            event: self.register_handler(event, handler, plugin_name)
            for event, handler in event_handlers.items()
        }

    def unregister_handler(self, handler_id: UUID) -> bool:
        """取消注册事件处理器

        Args:
            handler_id: 处理器ID

        Returns:
            如果成功取消返回True，否则返回False
        """
        with self._lock:
            handler_info = self._handlers.pop(handler_id, None)
            if handler_info and handler_info.plugin_name:
                plugin_handlers = self._plugin_handlers.get(handler_info.plugin_name)
                if plugin_handlers and handler_id in plugin_handlers:
                    plugin_handlers.remove(handler_id)

        if handler_info:
            logger.debug(f"[{self.__class__.__name__}] 卸载 handler: {handler_id}")
            return True
        return False

    def unregister_plugin_handlers(self, plugin_name: PluginName) -> int:
        """取消注册指定插件的所有处理器

        Args:
            plugin_name: 插件名称

        Returns:
            取消注册的处理器数量
        """
        count = 0
        with self._lock:
            if plugin_name in self._plugin_handlers:
                handler_ids = self._plugin_handlers.pop(plugin_name)
                for handler_id in handler_ids:
                    if handler_id in self._handlers:
                        del self._handlers[handler_id]
                        count += 1

        logger.debug(
            f"[{self.__class__.__name__}] 卸载插件 {plugin_name} 的 {count} 个处理器"
        )
        return count

    def is_closed(self) -> bool:
        """检查事件总线是否已关闭

        Returns:
            如果已关闭返回True，否则返回False
        """
        return self._closed

    def _get_matching_handlers(self, event_name: str) -> List[EventHandlerInfo]:
        """获取匹配指定事件名的所有处理器

        Args:
            event_name: 事件名称

        Returns:
            匹配的处理器列表
        """
        with self._lock:
            return [
                handler_info
                for handler_info in self._handlers.values()
                if handler_info.matches_event(event_name)
            ]

    def publish(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
    ) -> None:
        """发布-订阅模式（字符串事件名版本）

        发布一个事件，所有匹配的事件处理器将异步执行

        Args:
            event: 事件名称
            data: 事件数据
            source: 事件源
            target: 事件目标

        Raises:
            RuntimeError: 当事件总线已关闭时
        """
        if self._closed:
            raise RuntimeError("事件总线已关闭")

        event_obj = Event(event, data, source, target)
        self.publish_event(event_obj)

    def publish_event(self, event: Event) -> None:
        """发布-订阅模式（Event实例版本）

        直接发布一个Event实例，所有匹配的事件处理器将异步执行

        Args:
            event: Event实例

        Raises:
            RuntimeError: 当事件总线已关闭时
        """
        if self._closed:
            raise RuntimeError("事件总线已关闭")

        # 创建异步任务执行拦截器和处理器
        asyncio.create_task(self._async_publish(event), name=f"Publish-{event.event}")

    async def request(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Dict[UUID, Union[Any, Exception]]:
        """请求-响应模式（字符串事件名版本）

        发布一个事件并等待所有匹配处理器的响应

        Args:
            event: 事件名称
            data: 事件数据
            source: 事件源
            target: 事件目标
            timeout: 超时时间

        Returns:
            处理器ID到结果的映射

        Raises:
            RuntimeError: 当事件总线已关闭时
        """
        if self._closed:
            raise RuntimeError("事件总线已关闭")

        event_obj = Event(event, data, source, target)
        return await self.request_event(event_obj, timeout)

    async def request_event(
        self, event: Event, timeout: float = 10.0
    ) -> Dict[UUID, Union[Any, Exception]]:
        """请求-响应模式（Event实例版本）

        直接发布一个Event实例并等待所有匹配处理器的响应

        Args:
            event: Event实例
            timeout: 超时时间

        Returns:
            处理器ID到结果的映射

        Raises:
            RuntimeError: 当事件总线已关闭时
        """
        if self._closed:
            raise RuntimeError("事件总线已关闭")

        # 执行拦截器
        processed_event, intercepted = await self._run_interceptors(event)

        # 如果被拦截，返回空结果
        if intercepted:
            logger.debug(f"事件被拦截器拦截: {processed_event}")
            return {}

        handlers = self._get_matching_handlers(processed_event.event)

        if not handlers:
            # logger.debug(f"无处理器匹配事件: {processed_event.event}")
            return {}

        tasks: Dict[UUID, asyncio.Task] = {}
        for handler_info in handlers:
            try:
                task = asyncio.create_task(
                    self._execute_handler(handler_info.handler, processed_event),
                    name=f"Request-{processed_event.event}-{handler_info.handler_id}",
                )
                tasks[handler_info.handler_id] = task
            except Exception as e:
                logger.error(f"创建请求任务失败 {handler_info.handler_id}: {e}")

        results: Dict[UUID, Union[Any, Exception]] = {}
        for handler_id, task in tasks.items():
            try:
                result = await asyncio.wait_for(task, timeout)
                results[handler_id] = result
            except asyncio.TimeoutError:
                logger.warning(f"处理器 {handler_id} 执行超时")
                results[handler_id] = asyncio.TimeoutError(
                    f"处理器执行超时 ({timeout}s)"
                )
            except Exception as e:
                logger.error(f"处理器 {handler_id} 执行异常: {e}")
                results[handler_id] = e

        return results

    async def _execute_handler(self, handler: EventHandler, event: Event) -> Any:
        """执行事件处理器

        Args:
            handler: 事件处理器
            event: 事件对象

        Returns:
            处理器的执行结果
        """
        try:
            if inspect.iscoroutinefunction(handler):
                return await handler(event)
            else:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, handler, event)
        except Exception as e:
            logger.exception(f"事件处理器({handler})执行异常:\n{e}")
            raise

    def _handle_publish_result(self, task: asyncio.Task) -> None:
        """处理发布模式下的执行结果

        Args:
            task: 完成的任务
        """
        try:
            task.result()
        except Exception as e:
            logger.exception(f"发布模式处理器执行异常:\n{e}")

    async def _async_publish(self, event: Event) -> None:
        """异步执行发布操作（包含拦截器处理）

        Args:
            event: 原始事件对象
        """
        # 执行拦截器
        processed_event, intercepted = await self._run_interceptors(event)

        # 如果被拦截，停止后续处理
        if intercepted:
            logger.debug(f"发布事件被拦截器拦截: {processed_event}")
            return

        handlers = self._get_matching_handlers(processed_event.event)

        if not handlers:
            # logger.debug(f"无处理器匹配事件: {processed_event.event}")
            return

        for handler_info in handlers:
            try:
                task = asyncio.create_task(
                    self._execute_handler(handler_info.handler, processed_event),
                    name=f"Publish-{processed_event.event}-{handler_info.handler_id}",
                )
                task.add_done_callback(self._handle_publish_result)
            except Exception as e:
                logger.error(f"创建发布任务失败 {handler_info.handler_id}: {e}")

    def close(self) -> None:
        """关闭事件总线"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._handlers.clear()
            self._plugin_handlers.clear()
            self._interceptors.clear()
            self._interceptor_order.clear()
        logger.info(f"[{self.__class__.__name__}] 已关闭")

    @abstractmethod
    def _dispatch(
        self, handler: EventHandler, event: Event
    ) -> Union[Future, Awaitable[Any]]:
        """调度处理器执行

        Args:
            handler: 事件处理器
            event: 事件对象

        Returns:
            Future或Awaitable对象

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError
