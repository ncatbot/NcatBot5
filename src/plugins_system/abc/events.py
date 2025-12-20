"""
事件相关抽象基类

定义事件总线和其他事件相关组件的接口
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, Pattern, Union
from uuid import UUID

from ..utils.types import EventHandler, EventInterceptor, PluginName

if TYPE_CHECKING:
    from ..core.plugins import Event


"""通用事件处理器类型"""


class EventBus(ABC):
    """事件总线抽象基类

    负责事件的发布、订阅和请求-响应模式处理
    """

    @abstractmethod
    def register_handler(
        self,
        event: Union[str, Pattern[str]],
        handler: EventHandler,
        plugin_name: Optional["PluginName"] = None,
    ) -> UUID:
        """注册事件处理器

        Args:
            event: 事件模式，支持字符串或正则表达式
            handler: 事件处理器函数
            plugin_name: 关联的插件名称

        Returns:
            处理器ID
        """
        pass

    @abstractmethod
    def register_handlers(
        self,
        event_handlers: Dict[Union[str, Pattern[str]], EventHandler],
        plugin_name: Optional[PluginName] = None,
    ) -> Dict[Union[str, Pattern[str]], UUID]:
        """批量注册事件处理器

        Args:
            event_handlers: 事件处理器字典
            plugin_name: 关联的插件名称

        Returns:
            处理器ID字典
        """
        pass

    @abstractmethod
    def unregister_handler(self, handler_id: UUID) -> bool:
        """取消注册事件处理器

        Args:
            handler_id: 要取消的处理器ID

        Returns:
            如果成功取消返回True，否则返回False
        """
        pass

    @abstractmethod
    def unregister_plugin_handlers(self, plugin_name: PluginName) -> int:
        """取消注册指定插件的所有处理器

        Args:
            plugin_name: 插件名称

        Returns:
            取消注册的处理器数量
        """
        pass

    @abstractmethod
    async def request(
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
        pass

    @abstractmethod
    async def request_event(
        self, event: "Event", timeout: float = 10.0
    ) -> Dict[UUID, Union[Any, Exception]]:
        """请求-响应模式

        Args:
            event: Event实例
            timeout: 超时时间（秒）

        Returns:
            处理器ID到结果的映射
        """
        pass

    @abstractmethod
    def publish(
        self,
        event: str,
        data: Any = None,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
    ) -> None:
        """发布-订阅模式

        Args:
            event: 事件名称
            data: 事件数据
            source: 事件源
            target: 事件目标
        """
        pass

    @abstractmethod
    def publish_event(self, event: "Event") -> None:
        """发布-订阅模式

        Args:
            event: Event实例
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭事件总线"""
        pass

    @abstractmethod
    def is_closed(self) -> bool:
        """检查事件总线是否已关闭

        Returns:
            如果已关闭返回True，否则返回False
        """
        pass

    # 拦截器相关方法 - 提供默认实现表示不支持
    def register_interceptor(
        self,
        interceptor: EventInterceptor,
    ) -> UUID:
        """注册事件拦截器

        Args:
            interceptor: 事件拦截器实例

        Raises:
            NotImplementedError: 当事件总线不支持拦截器时抛出
        """
        raise NotImplementedError("此事件总线不支持拦截器")

    def unregister_interceptor(self, uuid: UUID) -> bool:
        """取消注册事件拦截器

        Args:
            uuid: 要取消的拦截器id

        Returns:
            如果成功取消返回True，否则返回False

        Raises:
            NotImplementedError: 当事件总线不支持拦截器时抛出
        """
        raise NotImplementedError("此事件总线不支持拦截器")
