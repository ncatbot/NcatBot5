"""
事件总线默认实现模块

重构后的事件总线实现：
- SimpleEventBus: 简便易用，适合大多数场景
- NonBlockingEventBus: 专注防止主线程阻塞，适合GUI或实时应用
"""

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
import inspect
import threading
from typing import Any, Dict, Optional, Set, Tuple, Union
from uuid import UUID

from ..core.events import EventBusBase, Event
from ..utils.types import EventHandler
from ..utils.constants import DEBUG_MODE
from ..logger import logger


class SimpleEventBus(EventBusBase):
    """简便事件总线
    
    适合大多数应用场景，使用当前线程的事件循环
    同步处理器在共享线程池中执行，不会阻塞事件循环
    
    Attributes:
        _executor: 共享线程池执行器（可选）
        _background_tasks: 后台任务集合
    """
    
    def __init__(self, max_workers: Optional[int] = None) -> None:
        """初始化简便事件总线
        
        Args:
            max_workers: 最大工作线程数，None则使用asyncio默认线程池
        """
        super().__init__()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="SimpleEventBus"
        ) if max_workers else None
        self._background_tasks: Set[asyncio.Task] = set()
    
    def _dispatch(self, handler: EventHandler, event: Event) -> asyncio.Task:
        """调度处理器执行
        
        Args:
            handler: 事件处理器
            event: 事件对象
            
        Returns:
            异步任务
        """
        return asyncio.create_task(self._execute_handler(handler, event))
    
    def publish(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None
    ) -> None:
        """发布事件到所有匹配的处理器
        
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

        original_event = Event(event, data, source, target)
        
        # 创建异步任务执行拦截器和处理器
        asyncio.create_task(
            self._async_publish(original_event),
            name=f"Publish-{event}"
        )
    
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
            logger.debug(f"无处理器匹配事件: {processed_event.event}")
            return

        for handler_info in handlers:
            try:
                task = asyncio.create_task(
                    self._execute_handler(handler_info.handler, processed_event),
                    name=f"Event-{processed_event.event}-{handler_info.handler_id}"
                )
                self._track_background_task(task)
            except Exception as e:
                logger.error(f"创建后台任务失败 {handler_info.handler_id}: {e}")
    
    async def request(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        timeout: float = 10.0
    ) -> Dict[UUID, Union[Any, Exception]]:
        """请求-响应模式
        
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

        original_event = Event(event, data, source, target)
        
        # 执行拦截器
        processed_event, intercepted = await self._run_interceptors(original_event)
        
        # 如果被拦截，返回空结果
        if intercepted:
            logger.debug(f"请求事件被拦截器拦截: {processed_event}")
            return {}

        handlers = self._get_matching_handlers(processed_event.event)
        
        if not handlers:
            logger.debug(f"无处理器匹配事件: {processed_event.event}")
            return {}

        tasks: Dict[UUID, asyncio.Task] = {}
        for handler_info in handlers:
            try:
                task = asyncio.create_task(
                    self._execute_handler(handler_info.handler, processed_event),
                    name=f"Request-{processed_event.event}-{handler_info.handler_id}"
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
                results[handler_id] = asyncio.TimeoutError(f"处理器执行超时 ({timeout}s)")
            except Exception as e:
                logger.error(f"处理器 {handler_id} 执行异常: {e}")
                results[handler_id] = e

        return results
    
    def _track_background_task(self, task: asyncio.Task) -> None:
        """跟踪后台任务并设置异常处理
        
        Args:
            task: 要跟踪的任务
        """
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(self._handle_task_exception)
    
    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """处理任务异常
        
        Args:
            task: 完成的任务
        """
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # 任务取消是正常的
        except Exception as e:
            logger.exception(f"事件处理器执行异常: {e}")
    
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
                # 同步函数在线程池中执行，不阻塞事件循环
                loop = asyncio.get_running_loop()
                if self._executor:
                    return await loop.run_in_executor(self._executor, handler, event)
                else:
                    return await asyncio.to_thread(handler, event)
        except Exception as e:
            logger.exception(f"事件处理器执行异常: {e}")
            raise
    
    def close(self) -> None:
        """关闭事件总线，取消所有后台任务"""
        super().close()
        
        # 取消所有后台任务
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=True)


class NonBlockingEventBus(EventBusBase):
    """非阻塞事件总线
    
    专注防止主线程阻塞，所有事件处理都在独立的后台线程中执行
    适合GUI应用、实时系统等对主线程响应性要求高的场景
    
    Attributes:
        _event_queue: 事件队列
        _worker_thread: 工作线程
        _worker_loop: 工作线程的事件循环
        _shutdown_event: 关闭事件
        _ready_event: 就绪事件
        _background_tasks: 后台任务集合
        _executor: 线程池执行器（可选）
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        queue_maxsize: int = 10_000
    ) -> None:
        """初始化非阻塞事件总线
        
        Args:
            max_workers: 最大工作线程数，None则使用asyncio默认线程池
            queue_maxsize: 事件队列最大大小
        """
        super().__init__()
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="NonBlockingEventBus"
        ) if max_workers else None
        
        # 后台线程相关
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=queue_maxsize)
        self._shutdown_event = threading.Event()
        self._ready_event = threading.Event()
        self._background_tasks: Set[asyncio.Task] = set()
        
        # 启动工作线程
        self._worker_thread = threading.Thread(
            target=self._run_worker_loop,
            name="NonBlockingEventBus-Worker",
            daemon=True
        )
        self._worker_thread.start()
        self._ready_event.wait(timeout=10)  # 等待工作线程就绪
    
    def _run_worker_loop(self) -> None:
        """工作线程主循环"""
        # 创建工作线程自己的事件循环
        self._worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._worker_loop)
        
        # 通知主线程工作线程已就绪
        self._ready_event.set()
        
        try:
            # 运行工作循环
            self._worker_loop.run_until_complete(self._worker_main())
        finally:
            # 清理工作线程
            self._cleanup_worker_loop()
    
    async def _worker_main(self) -> None:
        """工作线程主协程"""
        while not self._shutdown_event.is_set():
            try:
                # 等待事件或超时（用于检查关闭信号）
                event = await asyncio.wait_for(
                    self._event_queue.get(), 
                    timeout=1.0
                )
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue  # 超时，检查是否关闭
            except Exception as e:
                logger.exception(f"工作线程处理事件异常: {e}")
    
    async def _process_event(self, event: Event) -> None:
        """处理单个事件（在工作线程中执行拦截器和处理器）
        
        Args:
            event: 要处理的事件
        """
        # 在工作线程中执行拦截器
        processed_event, intercepted = await self._run_interceptors(event)
        
        # 如果被拦截，停止后续处理
        if intercepted:
            logger.debug(f"工作线程事件被拦截器拦截: {processed_event}")
            return

        if DEBUG_MODE:
            logger.info(f"\033[32mNonBlocking Event: \033[90m{processed_event}\033[0m")

        handlers = self._get_matching_handlers(processed_event.event)
        
        if not handlers:
            logger.debug(f"无处理器匹配事件: {processed_event.event}")
            return
        
        for handler_info in handlers:
            try:
                task = asyncio.create_task(
                    self._execute_handler(handler_info.handler, processed_event),
                    name=f"NonBlocking-{processed_event.event}-{handler_info.handler_id}"
                )
                self._track_background_task(task)
            except Exception as e:
                logger.error(f"创建工作线程任务失败 {handler_info.handler_id}: {e}")
    
    async def _worker_request(self, event: Event, timeout: float) -> Dict[UUID, Union[Any, Exception]]:
        """在工作线程中执行请求处理
        
        Args:
            event: 事件对象
            timeout: 超时时间
            
        Returns:
            处理器ID到结果的映射
        """
        # 执行拦截器
        processed_event, intercepted = await self._run_interceptors(event)
        
        # 如果被拦截，返回空结果
        if intercepted:
            logger.debug(f"工作线程请求事件被拦截器拦截: {processed_event}")
            return {}

        handlers = self._get_matching_handlers(processed_event.event)
        
        if not handlers:
            logger.debug(f"无处理器匹配事件: {processed_event.event}")
            return {}

        tasks: Dict[UUID, asyncio.Task] = {}
        for handler_info in handlers:
            try:
                task = asyncio.create_task(
                    self._execute_handler(handler_info.handler, processed_event),
                    name=f"WorkerRequest-{processed_event.event}-{handler_info.handler_id}"
                )
                tasks[handler_info.handler_id] = task
            except Exception as e:
                logger.error(f"创建工作线程请求任务失败 {handler_info.handler_id}: {e}")

        results: Dict[UUID, Union[Any, Exception]] = {}
        for handler_id, task in tasks.items():
            try:
                result = await asyncio.wait_for(task, timeout)
                results[handler_id] = result
            except asyncio.TimeoutError:
                logger.warning(f"工作线程处理器 {handler_id} 执行超时")
                results[handler_id] = asyncio.TimeoutError(f"处理器执行超时 ({timeout}s)")
            except Exception as e:
                logger.error(f"工作线程处理器 {handler_id} 执行异常: {e}")
                results[handler_id] = e

        return results
    
    def _track_background_task(self, task: asyncio.Task) -> None:
        """跟踪后台任务
        
        Args:
            task: 要跟踪的任务
        """
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(self._handle_task_exception)
    
    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """处理任务异常
        
        Args:
            task: 完成的任务
        """
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # 任务取消是正常的
        except Exception as e:
            logger.exception(f"工作线程任务执行异常: {e}")
    
    def _dispatch(self, handler: EventHandler, event: Event) -> Future:
        """调度处理器执行（在工作线程中）
        
        Args:
            handler: 事件处理器
            event: 事件对象
            
        Returns:
            Future对象用于跟踪执行状态
        """
        return asyncio.run_coroutine_threadsafe(
            self._execute_handler(handler, event), 
            self._worker_loop
        )
    
    def publish(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None
    ) -> None:
        """发布事件到工作线程（非阻塞）
        
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
        
        # 将事件放入队列（非阻塞操作）
        try:
            asyncio.run_coroutine_threadsafe(
                self._event_queue.put(event_obj),
                self._worker_loop
            )
        except Exception as e:
            logger.error(f"发布事件到工作线程失败: {e}")
    
    async def request(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        timeout: float = 10.0
    ) -> Dict[UUID, Union[Any, Exception]]:
        """请求-响应模式（在工作线程中执行）
        
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

        original_event = Event(event, data, source, target)
        
        # 在工作线程中执行拦截器和处理器
        future = asyncio.run_coroutine_threadsafe(
            self._worker_request(original_event, timeout),
            self._worker_loop
        )
        
        try:
            return future.result(timeout=timeout + 1.0)  # 额外给1秒处理时间
        except Exception as e:
            logger.error(f"请求执行失败: {e}")
            return {}
    
    async def _execute_handler(self, handler: EventHandler, event: Event) -> Any:
        """在工作线程中执行事件处理器
        
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
                # 同步函数在工作线程的线程池中执行
                if self._executor:
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(self._executor, handler, event)
                else:
                    return await asyncio.to_thread(handler, event)
        except Exception as e:
            logger.exception(f"工作线程处理器执行异常: {e}")
            raise
    
    def _cleanup_worker_loop(self) -> None:
        """清理工作线程事件循环"""
        try:
            # 取消所有待处理任务
            for task in self._background_tasks:
                task.cancel()
            
            # 等待任务完成或取消
            if self._worker_loop.is_running():
                pending = asyncio.all_tasks(self._worker_loop)
                if pending:
                    self._worker_loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
        except Exception as e:
            logger.error(f"清理工作线程异常: {e}")
        finally:
            self._worker_loop.close()
    
    def close(self) -> None:
        """关闭事件总线，停止工作线程"""
        super().close()
        
        # 通知工作线程关闭
        self._shutdown_event.set()
        
        # 等待工作线程结束
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
            if self._worker_thread.is_alive():
                logger.warning("工作线程超时未退出，强制关闭")
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=True)