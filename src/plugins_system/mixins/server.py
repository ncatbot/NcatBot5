from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps
from logging import Logger
from threading import RLock
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Final,
    Iterable,
    List,
    Optional,
    TypeAlias,
    Union,
    cast,
)
from uuid import UUID

from ..core.lazy_resolver import LazyDecoratorResolver, tagged_decorator
from ..core.mixin import PluginMixin

if TYPE_CHECKING:
    from ..core.events import Event, EventBus
    from ..core.plugins import Plugin
    from ..utils.types import PluginName

# ---------- 基础类型 ----------
ServiceName: TypeAlias = str
ServiceAddr: TypeAlias = str
SERVICE_FORMAT: Final[str] = "service.{plugin}.{service}"


# ---------- 元数据类型 ----------
@dataclass
class CallerInfo:
    """调用者信息"""

    plugin_name: str
    source: Optional[str] = None
    call_time: float = field(default_factory=lambda: __import__("time").time())


@dataclass
class ServiceMeta:
    """服务调用元数据"""

    service_info: ServiceInfo
    caller_info: CallerInfo
    event_id: Optional[UUID] = None


# ---------- 状态 ----------
class ServiceState(Enum):
    """服务运行状态枚举"""

    ONLINE = auto()  # 在线，可正常处理请求
    PAUSED = auto()  # 暂停，拒绝处理请求
    OFFLINE = auto()  # 离线，完全不可用


# ---------- 服务调用结果 ----------
@dataclass
class ServiceResult:
    """服务调用结果"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0

    @classmethod
    def success_result(
        cls, data: Any = None, execution_time: float = 0.0
    ) -> ServiceResult:
        return cls(success=True, data=data, execution_time=execution_time)

    @classmethod
    def error_result(cls, error: str, execution_time: float = 0.0) -> ServiceResult:
        return cls(success=False, error=error, execution_time=execution_time)


# ---------- 状态检查器 ----------
StateChecker: TypeAlias = Callable[[ServiceState, ServiceState], bool]


# ---------- 服务元数据 ----------
@dataclass
class ServiceInfo:
    """单个服务的完整描述信息"""

    name: ServiceName
    addr: ServiceAddr
    handler: Callable
    owner: PluginName
    state: ServiceState = ServiceState.ONLINE
    state_checker: Optional[StateChecker] = None
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    created_time: float = field(default_factory=lambda: __import__("time").time())

    @property
    def is_available(self) -> bool:
        """服务是否可用"""
        return self.state == ServiceState.ONLINE


# ---------- 内部服务包装工具 ----------
def _create_service_handler(
    func: Callable[..., Any],
    service_info: ServiceInfo,
    logger: Logger,
    event_mod: bool = False,
) -> Callable[[Event], Any]:
    """
    创建最终的服务事件处理器（二级包装）

    返回的函数只接受一个参数：e: Event
    """
    sig = inspect.signature(func)
    pos_params: List[str] = []
    kwonly_params: List[str] = []
    has_var_pos = has_var_kw = False
    has_meta_param = False
    # meta_param_required = False
    # meta_param_name = "meta"

    # 分析函数参数
    for p in sig.parameters.values():
        if p.kind is inspect.Parameter.VAR_POSITIONAL:
            has_var_pos = True
        elif p.kind is inspect.Parameter.VAR_KEYWORD:
            has_var_kw = True
        elif p.kind is inspect.Parameter.KEYWORD_ONLY:
            kwonly_params.append(p.name)
        else:
            pos_params.append(p.name)

        # 检查是否有名为 'meta' 的参数
        if p.name == "meta":
            has_meta_param = True
            # 检查meta参数是否是必需的（没有默认值）
            # if p.default is inspect.Parameter.empty:
            #     meta_param_required = True

    def _create_meta(e: Event, start_time: float) -> ServiceMeta:
        """创建元数据对象"""
        caller_info = CallerInfo(
            plugin_name=service_info.owner, source=e.source, call_time=start_time
        )
        return ServiceMeta(
            service_info=service_info, caller_info=caller_info, event_id=e.id
        )

    def _inject_meta_if_needed(
        kwargs: Dict[str, Any], meta: ServiceMeta
    ) -> Dict[str, Any]:
        """如果需要，注入meta参数"""
        if has_meta_param and "meta" not in kwargs:
            kwargs["meta"] = meta
        return kwargs

    def _call_with_meta(args: tuple, kwargs: Dict[str, Any], meta: ServiceMeta) -> Any:
        """使用meta参数调用函数"""
        final_kwargs = _inject_meta_if_needed(kwargs, meta)
        return func(*args, **final_kwargs)

    async def _acall_with_meta(
        args: tuple, kwargs: Dict[str, Any], meta: ServiceMeta
    ) -> Any:
        """使用meta参数调用异步函数"""
        final_kwargs = _inject_meta_if_needed(kwargs, meta)
        return await func(*args, **final_kwargs)

    if inspect.iscoroutinefunction(func):
        # 异步函数包装
        async def _async_event_handler(e: Event) -> ServiceResult:
            import time

            start_time = time.time()

            if not service_info.is_available:
                logger.warning(
                    "服务 %s 当前不可用，状态: %s",
                    service_info.name,
                    service_info.state,
                )
                return ServiceResult.error_result(
                    f"服务不可用，当前状态: {service_info.state}"
                )

            try:
                # 创建meta对象（在所有模式下都创建）
                meta = _create_meta(e, start_time)

                if event_mod:
                    # 事件模式：直接传递Event对象，但也要支持meta
                    if has_meta_param:
                        # 如果函数需要meta参数，同时传递Event和meta
                        result = await _acall_with_meta((e,), {}, meta)
                    else:
                        # 如果函数不需要meta，只传递Event
                        result = await func(e)
                    return ServiceResult.success_result(
                        result, time.time() - start_time
                    )

                data = e.data

                # ---------- 1. 字典分支 ----------
                if isinstance(data, dict):
                    # 1.1 参数检查（排除meta参数）
                    effective_pos_params = [p for p in pos_params if p != "meta"]
                    effective_kwonly_params = [p for p in kwonly_params if p != "meta"]

                    missing_pos = [p for p in effective_pos_params if p not in data]
                    missing_kwonly = [
                        p for p in effective_kwonly_params if p not in data
                    ]

                    if missing_pos or (missing_kwonly and not has_var_kw):
                        error_msg = f"参数缺失: 位置参数{missing_pos}, 关键字参数{missing_kwonly}"
                        logger.error("%s | 期望签名 %s", error_msg, sig)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

                    # 1.2 类型检查（排除meta参数）
                    type_errors = {}
                    for k, v in data.items():
                        if k in sig.parameters and k != "meta":
                            param = sig.parameters[k]
                            if not _isinstance_safe(v, param.annotation):
                                type_errors[k] = (
                                    f"期望 {param.annotation}, 收到 {type(v).__name__}"
                                )

                    if type_errors:
                        error_msg = f"参数类型错误: {type_errors}"
                        logger.error("%s | 期望签名 %s", error_msg, sig)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

                    # 1.3 执行调用（自动注入meta）
                    try:
                        result = await _acall_with_meta((), data, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        logger.error("服务调用异常 | 原因 %s | 参数 %s", ex, data)
                        return ServiceResult.error_result(
                            f"调用异常: {ex}", time.time() - start_time
                        )

                # ---------- 2. 序列分支 ----------
                elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
                    seq = tuple(data)

                    # 处理序列调用，考虑meta参数
                    need = len([p for p in pos_params if p != "meta"])  # 排除meta参数

                    if not has_var_pos and len(seq) != need:
                        error_msg = (
                            f"位置参数数量不符: 收到 {len(seq)} 个，需要 {need} 个"
                        )
                        logger.error("%s | 期望签名 %s", error_msg, sig)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

                    try:
                        result = await _acall_with_meta(seq, {}, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        logger.error("序列调用异常 | 原因 %s | 参数 %s", ex, seq)
                        return ServiceResult.error_result(
                            f"调用异常: {ex}", time.time() - start_time
                        )

                # ---------- 3. 无参调用分支 ----------
                elif isinstance(data, type(None)):
                    # 处理无参调用
                    try:
                        result = await _acall_with_meta((), {}, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        logger.error("无参调用异常 | 原因 %s", ex)
                        return ServiceResult.error_result(
                            f"调用异常: {ex}", time.time() - start_time
                        )

                else:
                    # 尝试直接传递数据
                    try:
                        result = await _acall_with_meta((data,), {}, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        error_msg = f"参数类型不支持: 期望 dict 或序列，收到 {type(data).__name__}"
                        logger.error("%s | 原因 %s", error_msg, ex)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

            except Exception as ex:
                logger.error("服务处理过程中发生未预期异常: %s", ex, exc_info=True)
                return ServiceResult.error_result(
                    f"服务内部错误: {ex}", time.time() - start_time
                )

        return _async_event_handler

    else:
        # 同步函数包装
        def _sync_event_handler(e: Event) -> ServiceResult:
            import time

            start_time = time.time()

            if not service_info.is_available:
                logger.warning(
                    "服务 %s 当前不可用，状态: %s",
                    service_info.name,
                    service_info.state,
                )
                return ServiceResult.error_result(
                    f"服务不可用，当前状态: {service_info.state}"
                )

            try:
                # 创建meta对象（在所有模式下都创建）
                meta = _create_meta(e, start_time)

                if event_mod:
                    # 事件模式：直接传递Event对象，但也要支持meta
                    if has_meta_param:
                        # 如果函数需要meta参数，同时传递Event和meta
                        result = _call_with_meta((e,), {}, meta)
                    else:
                        # 如果函数不需要meta，只传递Event
                        result = func(e)
                    return ServiceResult.success_result(
                        result, time.time() - start_time
                    )

                data = e.data

                # ---------- 1. 字典分支 ----------
                if isinstance(data, dict):
                    # 1.1 参数检查（排除meta参数）
                    effective_pos_params = [p for p in pos_params if p != "meta"]
                    effective_kwonly_params = [p for p in kwonly_params if p != "meta"]

                    missing_pos = [p for p in effective_pos_params if p not in data]
                    missing_kwonly = [
                        p for p in effective_kwonly_params if p not in data
                    ]

                    if missing_pos or (missing_kwonly and not has_var_kw):
                        error_msg = f"参数缺失: 位置参数{missing_pos}, 关键字参数{missing_kwonly}"
                        logger.error("%s | 期望签名 %s", error_msg, sig)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

                    # 1.2 类型检查（排除meta参数）
                    type_errors = {}
                    for k, v in data.items():
                        if k in sig.parameters and k != "meta":
                            param = sig.parameters[k]
                            if not _isinstance_safe(v, param.annotation):
                                type_errors[k] = (
                                    f"期望 {param.annotation}, 收到 {type(v).__name__}"
                                )

                    if type_errors:
                        error_msg = f"参数类型错误: {type_errors}"
                        logger.error("%s | 期望签名 %s", error_msg, sig)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

                    # 1.3 执行调用（自动注入meta）
                    try:
                        result = _call_with_meta((), data, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        logger.error("服务调用异常 | 原因 %s | 参数 %s", ex, data)
                        return ServiceResult.error_result(
                            f"调用异常: {ex}", time.time() - start_time
                        )

                # ---------- 2. 序列分支 ----------
                elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
                    seq = tuple(data)

                    # 处理序列调用，考虑meta参数
                    need = len([p for p in pos_params if p != "meta"])  # 排除meta参数

                    if not has_var_pos and len(seq) != need:
                        error_msg = (
                            f"位置参数数量不符: 收到 {len(seq)} 个，需要 {need} 个"
                        )
                        logger.error("%s | 期望签名 %s", error_msg, sig)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

                    try:
                        result = _call_with_meta(seq, {}, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        logger.error("序列调用异常 | 原因 %s | 参数 %s", ex, seq)
                        return ServiceResult.error_result(
                            f"调用异常: {ex}", time.time() - start_time
                        )

                # ---------- 3. 无参调用分支 ----------
                elif isinstance(data, type(None)):
                    # 处理无参调用
                    try:
                        result = _call_with_meta((), {}, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        logger.error("无参调用异常 | 原因 %s", ex)
                        return ServiceResult.error_result(
                            f"调用异常: {ex}", time.time() - start_time
                        )

                else:
                    # 尝试直接传递数据
                    try:
                        result = _call_with_meta((data,), {}, meta)
                        return ServiceResult.success_result(
                            result, time.time() - start_time
                        )
                    except Exception as ex:
                        error_msg = f"参数类型不支持: 期望 dict 或序列，收到 {type(data).__name__}"
                        logger.error("%s | 原因 %s", error_msg, ex)
                        return ServiceResult.error_result(
                            error_msg, time.time() - start_time
                        )

            except Exception as ex:
                logger.error("服务处理过程中发生未预期异常: %s", ex, exc_info=True)
                return ServiceResult.error_result(
                    f"服务内部错误: {ex}", time.time() - start_time
                )

        return _sync_event_handler


def service_pack(
    func: Callable[..., Any], event_mod: bool = False
) -> Callable[[ServiceInfo, Logger], Callable[[Event], Any]]:
    """
    服务包装器工厂 - 一级包装

    返回一个函数，该函数接受 ServiceInfo 和 Logger 并返回最终的事件处理器

    Args:
        func: 要包装的原始函数
        event_mod: 是否使用事件模式

    Returns:
        包装器工厂函数
    """

    @wraps(func)
    def _wrapper_factory(
        service_info: ServiceInfo, logger: Logger
    ) -> Callable[[Event], Any]:
        """
        包装器工厂 - 二级包装

        绑定具体的 ServiceInfo 和 Logger，返回最终的事件处理器
        """
        return _create_service_handler(func, service_info, logger, event_mod)

    return _wrapper_factory


# ---------- 辅助函数 ----------
def _isinstance_safe(value: Any, annotation: Any) -> bool:
    """安全类型检查，支持 Union 和字符串注解"""
    if annotation is inspect.Parameter.empty:
        return True

    # 处理 Union 类型
    if getattr(annotation, "__origin__", None) is Union:
        return any(_isinstance_safe(value, arg) for arg in annotation.__args__)

    # 处理字符串注解
    if isinstance(annotation, str):
        try:
            annotation = eval(annotation, globals())
        except (NameError, SyntaxError, TypeError):  #  eval 常见的三类错误
            return True  # 解析失败时跳过检查

    try:
        # 处理类型别名和 NewType
        if hasattr(annotation, "__supertype__"):  # NewType
            annotation = annotation.__supertype__

        return isinstance(value, annotation)
    except Exception:
        pass
    return True  # 检查失败时放过


# ---------- 辅助函数 ----------
def _isinstance_safe(value: Any, annotation: Any) -> bool:
    """安全类型检查，支持 Union 和字符串注解"""
    if annotation is inspect.Parameter.empty:
        return True

    # 处理 Union 类型
    if getattr(annotation, "__origin__", None) is Union:
        return any(_isinstance_safe(value, arg) for arg in annotation.__args__)

    # 处理字符串注解
    if isinstance(annotation, str):
        try:
            annotation = eval(annotation, globals())
        except (NameError, SyntaxError, TypeError):  #  eval 常见的三类错误
            return True  # 解析失败时跳过检查

    try:
        # 处理类型别名和 NewType
        if hasattr(annotation, "__supertype__"):  # NewType
            annotation = annotation.__supertype__

        return isinstance(value, annotation)
    except Exception:
        return True  # 检查失败时放过


# ---------- 核心 Mixin ----------
class ServiceMixin(PluginMixin):
    """为插件提供服务的注册、地址管理与状态管理功能"""

    __all_services: Dict[ServiceName, ServiceInfo] = {}
    __lock = RLock()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化服务混入类"""
        super().__init__(*args, **kwargs)

        # 服务注册表：服务名 -> UUID
        self._services: Dict[ServiceName, UUID] = {}
        # 服务统计信息
        self._service_stats: Dict[ServiceName, Dict[str, Any]] = {}

    @property
    def services(self) -> Dict[ServiceName, UUID]:
        """当前插件已注册的服务名到 UUID 的映射"""
        return self._services.copy()

    # -------------------- 服务注册 --------------------
    def register_service(
        self,
        service_name: ServiceName,
        handler: Callable,
        state_checker: Optional[StateChecker] = None,
        description: str = "",
        version: str = "1.0.0",
        tags: Optional[List[str]] = None,
        event_mod: bool = False,
    ) -> Optional[UUID]:
        """
        注册一个服务

        Args:
            service_name: 服务名称
            handler: 服务处理函数
            state_checker: 状态检查器
            description: 服务描述
            version: 服务版本
            tags: 服务标签
            event_mod: 是否使用事件模式

        Returns:
            服务UUID（注册失败返回None）
        """
        with self.__lock:
            # 1. 检查服务名冲突
            if service_name in self._services:
                self.logger.warning("服务 %s 重复注册，旧服务将被覆盖", service_name)
                old_uuid = self._services[service_name]
                self.context.unregister_handler(old_uuid)
                if service_name in self.__all_services:
                    del self.__all_services[service_name]

            # 2. 检查全局冲突（其他插件占用）
            existing_info = self.__all_services.get(service_name)
            if existing_info and existing_info.owner != self.plugin.name:
                self.logger.error(
                    "服务 %s 已被插件 %s 占用，跳过注册",
                    service_name,
                    existing_info.owner,
                )
                return None

            # 3. 创建服务信息
            addr = SERVICE_FORMAT.format(plugin=self.plugin.name, service=service_name)
            service_info = ServiceInfo(
                name=service_name,
                addr=addr,
                handler=handler,  # 保存原始处理器
                owner=self.plugin.name,
                state_checker=state_checker,
                description=description,
                version=version,
                tags=tags or [],
            )

            # 4. 使用 service_pack 创建最终的事件处理器
            # 一级包装：创建包装器工厂
            handler_factory = service_pack(handler, event_mod=event_mod)
            # 二级包装：绑定 ServiceInfo 和 Logger，创建最终处理器
            final_handler = handler_factory(service_info, self.plugin.logger)

            # 5. 注册到事件总线
            uuid_ = self.context.register_handler(addr, final_handler)

            # 6. 更新服务信息的处理器为最终处理器
            service_info.handler = final_handler

            # 7. 更新注册表
            self._services[service_name] = uuid_
            self.__all_services[service_name] = service_info

            # 8. 初始化统计信息
            self._service_stats[service_name] = {
                "call_count": 0,
                "success_count": 0,
                "error_count": 0,
                "total_execution_time": 0.0,
                "last_call_time": None,
            }

            self.logger.info("服务注册成功: %s -> %s", service_name, addr)
            return uuid_

    def unregister_service(self, service_name: ServiceName) -> bool:
        """注销服务"""
        with self.__lock:
            if service_name not in self._services:
                self.logger.warning("尝试注销未注册的服务: %s", service_name)
                return False

            uuid_ = self._services[service_name]
            success = self.context.unregister_handler(uuid_)

            if success:
                del self._services[service_name]
                if service_name in self.__all_services:
                    del self.__all_services[service_name]
                if service_name in self._service_stats:
                    del self._service_stats[service_name]

                self.logger.info("服务注销成功: %s", service_name)
            else:
                self.logger.error("服务注销失败: %s", service_name)

            return success

    def get_service_info(self, service_name: ServiceName) -> Optional[ServiceInfo]:
        """获取服务信息"""
        with self.__lock:
            return self.__all_services.get(service_name)

    def list_services(self, available_only: bool = False) -> List[ServiceInfo]:
        """列出所有服务"""
        with self.__lock:
            services = list(self.__all_services.values())
            if available_only:
                services = [s for s in services if s.is_available]
            return services

    # -------------------- 服务调用 --------------------
    async def call_service(
        self,
        service_name: ServiceName,
        data: Any = None,
        source: Optional[str] = None,
        target: Optional[str] = None,
        timeout: float = 30.0,
    ) -> ServiceResult:
        """
        调用服务

        Args:
            service_name: 服务名称
            data: 调用数据
            source: 调用源
            target: 调用目标
            timeout: 超时时间

        Returns:
            服务调用结果
        """
        service_info = self.get_service_info(service_name)
        if not service_info:
            return ServiceResult.error_result(f"服务不存在: {service_name}")

        if not service_info.is_available:
            return ServiceResult.error_result(f"服务不可用: {service_name}")

        try:
            # 使用事件总线进行请求-响应调用
            results = await self.context.event_bus.request(
                event=service_info.addr,
                data=data,
                source=source or self.plugin.name,
                target=target,
                timeout=timeout,
            )

            # 更新统计信息
            self._update_service_stats(service_name, results)

            # 返回第一个结果（通常只有一个处理器）
            if results:
                first_result = next(iter(results.values()))
                if isinstance(first_result, Exception):
                    return ServiceResult.error_result(f"调用异常: {first_result}")
                return first_result
            else:
                return ServiceResult.error_result("服务无响应")

        except Exception as ex:
            self.logger.error("服务调用失败: %s, 错误: %s", service_name, ex)
            return ServiceResult.error_result(f"调用失败: {ex}")

    def _update_service_stats(
        self, service_name: ServiceName, results: Dict[UUID, Any]
    ) -> None:
        """更新服务统计信息"""
        if service_name not in self._service_stats:
            return

        stats = self._service_stats[service_name]
        stats["call_count"] += 1
        stats["last_call_time"] = __import__("time").time()

        if results:
            for result in results.values():
                if isinstance(result, ServiceResult):
                    if result.success:
                        stats["success_count"] += 1
                    else:
                        stats["error_count"] += 1
                    stats["total_execution_time"] += result.execution_time
                elif isinstance(result, Exception):
                    stats["error_count"] += 1

    def get_service_stats(self, service_name: ServiceName) -> Optional[Dict[str, Any]]:
        """获取服务统计信息"""
        return self._service_stats.get(service_name)

    # -------------------- 状态管理 --------------------
    def get_service_state(self, service_name: ServiceName) -> Optional[ServiceState]:
        """查询服务状态"""
        with self.__lock:
            info = self.__all_services.get(service_name)
            return info.state if info else None

    def set_service_state(
        self,
        service_name: ServiceName,
        new_state: ServiceState,
        force: bool = False,
    ) -> bool:
        """设置服务状态"""
        with self.__lock:
            info = self.__all_services.get(service_name)
            if info is None:
                self.logger.error("服务 %s 不存在", service_name)
                return False

            # 检查权限：只有所有者或强制模式可以修改状态
            if info.owner != self.plugin.name and not force:
                self.logger.warning(
                    "插件 %s 无权修改服务 %s 的状态",
                    self.plugin.name,
                    service_name,
                )
                return False

            return self.__do_set_service_state(info, new_state, force)

    def toggle_service_state(self, service_name: ServiceName) -> bool:
        """切换服务状态（ONLINE <-> PAUSED）"""
        current_state = self.get_service_state(service_name)
        if current_state == ServiceState.ONLINE:
            return self.set_service_state(service_name, ServiceState.PAUSED)
        elif current_state == ServiceState.PAUSED:
            return self.set_service_state(service_name, ServiceState.ONLINE)
        else:
            self.logger.warning(
                "服务 %s 当前状态 %s 不允许切换", service_name, current_state
            )
            return False

    def __do_set_service_state(
        self,
        info: ServiceInfo,
        new_state: ServiceState,
        force: bool,
    ) -> bool:
        """实际执行状态切换"""
        if info.state == new_state:
            return True

        # 检查状态转换是否允许
        if force:
            info.state = new_state
            self.logger.info(
                "服务 %s 状态强制切换: %s -> %s", info.name, info.state, new_state
            )
            return True

        checker = info.state_checker
        if checker is None or checker(info.state, new_state):
            old_state = info.state
            info.state = new_state
            self.logger.info(
                "服务 %s 状态切换: %s -> %s", info.name, old_state, new_state
            )
            return True

        self.logger.warning(
            "服务 %s 状态切换被拒绝: %s -> %s", info.name, info.state, new_state
        )
        return False

    # -------------------- 服务发现 --------------------
    def discover_services(
        self,
        pattern: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
        available_only: bool = True,
    ) -> List[ServiceInfo]:
        """发现服务"""
        with self.__lock:
            services = list(self.__all_services.values())

            # 过滤条件
            if pattern:
                services = [
                    s for s in services if pattern in s.name or pattern in s.addr
                ]
            if owner:
                services = [s for s in services if s.owner == owner]
            if tags:
                services = [s for s in services if any(tag in s.tags for tag in tags)]
            if available_only:
                services = [s for s in services if s.is_available]

            return services

    # -------------------- 混入类生命周期 --------------------
    async def on_mixin_load(self) -> None:
        """混入类加载时的回调"""
        self.logger.debug(f"服务混入类加载完成，当前服务数: {len(self._services)}")

    async def on_mixin_unload(self) -> None:
        """混入类卸载时的回调 - 清理所有注册的服务"""
        with self.__lock:
            # 取消注册所有事件处理器
            for service_name, uuid_ in list(self._services.items()):
                self.context.unregister_handler(uuid_)
                # 从全局注册表中移除
                if service_name in self.__all_services:
                    del self.__all_services[service_name]

            # 清空本地注册表
            self._services.clear()
            self._service_stats.clear()

        self.logger.info(f"插件 {self.plugin.name} 的服务混入类已卸载")


# ---------- 服务装饰器解析器 ----------
class ServiceResolver(LazyDecoratorResolver):
    """服务装饰器解析器"""

    tag = "service"
    space = "service"
    required_mixin = ServiceMixin

    def handle(
        self, plugin: Plugin | ServiceMixin, func: Callable, event_bus: EventBus
    ) -> None:
        """处理服务注册逻辑"""
        try:
            # 从命名空间获取元数据
            service_name = self.kwd["service_name"]
            state_checker = self.kwd.get("state_checker")
            description = self.kwd.get("description", "")
            version = self.kwd.get("version", "1.0.0")
            tags = self.kwd.get("tags", [])
            event_mod = self.kwd.get("event_mod", False)

            # 注册服务
            uuid_ = plugin.register_service(
                service_name=service_name,
                handler=func,
                state_checker=state_checker,
                description=description,
                version=version,
                tags=tags,
                event_mod=event_mod,
            )

            if uuid_:
                plugin.logger.debug(
                    f"服务注册: '{service_name}' v{version} "
                    f"(事件模式: {event_mod}, 标签: {tags})"
                )
            else:
                plugin.logger.error(f"服务注册失败: '{service_name}'")

        except KeyError as e:
            plugin.logger.error(f"服务注册缺少必要参数: {e}")
        except Exception as e:
            plugin.logger.error(f"服务注册异常: {e}")
        finally:
            self.clear_cache()


# ==================== 快捷装饰器 ====================


def service(
    service_name: str,
    state_checker: Optional[StateChecker] = None,
    description: str = "",
    version: str = "1.0.0",
    tags: Optional[List[str]] = None,
    event_mod: bool = False,
) -> Callable[[Callable], Callable]:
    """服务注册装饰器（同步 / 异步双兼容）"""
    _tagged = tagged_decorator(
        "service",
        space="service",
        service_name=service_name,
        state_checker=state_checker,
        description=description,
        version=version,
        tags=tags or [],
        event_mod=event_mod,
    )

    def service_wrapper(func: Callable) -> Callable:
        func = _tagged(func)

        # 异步分支
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            _async_wrapper.__mate__ = cast(dict, func.__mate__)
            return _async_wrapper

        # 同步分支
        @wraps(func)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        _sync_wrapper.__mate__ = cast(dict, func.__mate__)
        return _sync_wrapper

    return service_wrapper


def online_service(
    service_name: str,
    description: str = "",
    version: str = "1.0.0",
    tags: Optional[List[str]] = None,
    **kwargs: Any,
) -> Callable:
    """创建始终在线的服务装饰器"""

    def always_online(old_state: ServiceState, new_state: ServiceState) -> bool:
        return new_state == ServiceState.ONLINE

    return service(
        service_name,
        state_checker=always_online,
        description=description,
        version=version,
        tags=tags,
        **kwargs,
    )


def toggleable_service(
    service_name: str,
    description: str = "",
    version: str = "1.0.0",
    tags: Optional[List[str]] = None,
    **kwargs: Any,
) -> Callable:
    """创建可自由切换状态的服务装饰器"""

    def allow_toggle(old_state: ServiceState, new_state: ServiceState) -> bool:
        return new_state in [ServiceState.ONLINE, ServiceState.PAUSED]

    return service(
        service_name,
        state_checker=allow_toggle,
        description=description,
        version=version,
        tags=tags,
        **kwargs,
    )


def event_service(
    service_name: str,
    description: str = "",
    version: str = "1.0.0",
    tags: Optional[List[str]] = None,
    **kwargs: Any,
) -> Callable:
    """创建事件模式服务装饰器（直接接收Event对象）"""
    return service(
        service_name,
        description=description,
        version=version,
        tags=tags,
        event_mod=True,
        **kwargs,
    )
