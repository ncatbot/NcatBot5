# protocol_abc.py
"""
最小抽象层 - 定义固定接口签名，与具体协议无关
# !! 等待完善参数
"""
from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from ast import Tuple
from typing import TYPE_CHECKING, Any, Dict, Generic, List, NewType, Optional, TypeVar

from ..plugins_system.core.events import Event
from .api_base import APIBase
from .builder import MessageBuilder

APIBaseT = TypeVar("APIBaseT", bound="APIBase")
MessageBuilderT = TypeVar("MessageBuilderT", bound="MessageBuilder")

if TYPE_CHECKING:
    from ..connector.abc import ABCWebSocketClient, MessageType
    from ..core.IM import Group, Message, User
    from ..utils.typec import GroupID, MsgId, UserID


# def unsupported(func: Callable):
#     """标记协议暂不支持的方法"""
#     def de(self: "ProtocolABC", *args, **kw):
#         raise NotImplementedError(
#             f"协议 {self.protocol_name} 不支持{func.__doc__ if func.__doc__ else func.__name__}"
#         )
#     return de

# 仅供参考，只是提示这是同一个东西
RawMessage = NewType("RawMessage", object)
RawUser = NewType("RawUser", object)
RawGroup = NewType("RawGroup", object)
RawDate = NewType("RawDate", str)


class ProtocolMeta(ABCMeta):
    """自动收集所有协议子类"""

    _protocols: Dict[str, "ProtocolABC"] = {}

    def __new__(mcls, name, bases, namespace: Dict[str, Any]):
        cls = super().__new__(mcls, name, bases, namespace)

        # 跳过抽象基类（仍有抽象方法的类）
        if cls.__abstractmethods__:
            return cls

        protocol_name = namespace.get("protocol_name")
        if protocol_name:
            if protocol_name in mcls._protocols:
                raise ValueError(f"协议名称 '{protocol_name}' 已被占用")
            mcls._protocols[protocol_name] = cls
        return cls

    @classmethod
    def get_protocol(cls, protocol_name: str) -> ProtocolABC:
        """获取指定协议类"""
        protocol = cls._protocols.get(protocol_name)
        if not protocol:
            raise TypeError(f"无效的协议 {protocol_name}, 可用协议: {cls._protocols}")
        # TODO 自动类型检查
        return protocol

    @classmethod
    def list_protocols(cls) -> List[str]:
        """列出所有已注册的协议"""
        return list(cls._protocols.keys())


class ProtocolABC(Generic[APIBaseT, MessageBuilderT], ABC, metaclass=ProtocolMeta):
    """
    最小抽象层基类
    定义固定的接口签名，所有协议必须实现
    这些接口与具体协议无关，是通用抽象
    """

    def __init__(self, debug: bool = False):
        """初始化协议
        Args:
            url(str): 连接地址
        """
        # 验证协议名称
        self._debug = debug
        if not hasattr(self, "protocol_name") or not self.protocol_name:
            raise TypeError(f"{self.__class__.__name__} 必须定义 protocol_name")

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    @abstractmethod
    def protocol_name(self) -> str:
        """协议名称"""

    @property
    @abstractmethod
    def api(self) -> APIBaseT:
        """获取所属的APIBase实例"""

    @property
    @abstractmethod
    def msg_builder(self) -> MessageBuilderT:
        """获取所属的消息构造器"""

    @property
    @abstractmethod
    def self_id(self) -> str:
        """获取Bot账户id"""

    # ========== 必须实现的抽象方法 ==========
    # 这些是固定的接口签名，所有协议必须实现

    @abstractmethod
    async def send_group_message(self, gid: "GroupID", content: "Message") -> MsgId:
        """
        发送群消息
        Args:
            gid: 群组ID
            content: 消息内容
        Returns:
            原始响应数据
        """
        pass

    @abstractmethod
    async def send_private_message(self, uid: "UserID", content: "Message") -> MsgId:
        """
        发送私聊消息
        Args:
            uid: 用户ID
            content: 消息内容
        Returns:
            原始响应数据
        """
        pass

    @abstractmethod
    async def login(self, url: str, token: str, **kwd) -> ABCWebSocketClient:
        """
        登录
        Args:
            token: 登录令牌
        Returns:
            ABCWebSocketClient
        """
        pass

    # ========== 必须实现的解析方法 ==========
    @abstractmethod
    def _parse_event(
        self, raw: Tuple[RawDate, MessageType]
    ) -> Event | None:  # 服务器的主动推送
        """
        解析事件
        Args:
            raw: 原始数据
        Returns:
            Event: 发布事件
            None: 不发布事件
        """

    @abstractmethod
    def _parse_message(
        self,
        raw: RawMessage,
    ) -> "Message":
        """
        解析消息
        Args:
            raw: 原始数据
        Returns:
            Message对象
        """
        pass

    @abstractmethod
    def _parse_user(
        self,
        raw: RawUser,
    ) -> "User":
        """
        解析用户
        Args:
            raw: 原始数据
        Returns:
            User对象
        """
        pass

    @abstractmethod
    def _parse_group(
        self,
        raw: RawGroup,
    ) -> "Group":
        """
        解析群组
        Args:
            raw: 原始数据
        Returns:
            Group对象
        """
        pass

    # ========== 标准功能 ==========
    # 这些方法是协议最小功能集合

    @abstractmethod
    async def logout(self) -> bool:
        """登出"""

    @abstractmethod
    async def fetch_user(self, uid: "UserID") -> RawUser:
        """获取用户信息"""

    @abstractmethod
    async def fetch_group(self, gid: "GroupID") -> RawGroup:
        """获取群信息"""

    @abstractmethod
    async def fetch_friends(self) -> List[RawUser]:
        """获取好友列表"""

    @abstractmethod
    async def fetch_groups(self) -> List[RawGroup]:
        """获取群组列表"""

    @abstractmethod
    async def fetch_message(self, msg_id: "MsgId") -> RawMessage:
        """获取消息详情"""

    @abstractmethod
    async def recall_message(self, msg_id: "MsgId") -> bool:
        """撤回消息"""

    @abstractmethod
    async def fetch_group_members(self, gid: "GroupID") -> List[RawUser]:
        """获取群成员列表"""

    # ========== 好友管理 ==========

    @abstractmethod
    async def add_friend(self, user_id: "UserID", remark: Optional[str] = None) -> bool:
        """发起加好友请求"""

    @abstractmethod
    async def delete_friend(self, user_id: "UserID") -> bool:
        """删除好友"""

    @abstractmethod
    async def block_user(self, user_id: "UserID") -> bool:
        """拉黑用户"""

    @abstractmethod
    async def unblock_user(self, user_id: "UserID") -> bool:
        """解除拉黑"""

    @abstractmethod
    async def set_friend_remark(self, user_id: "UserID", remark: str) -> bool:
        """设置好友备注"""

    @abstractmethod
    async def accept_friend_request(self, request_id: str) -> bool:
        """通过好友请求"""

    @abstractmethod
    async def reject_friend_request(self, request_id: str) -> bool:
        """拒绝好友请求"""

    # ========== 群管理 ==========

    @abstractmethod
    async def create_group(
        self, name: str, initial_members: List["UserID"]
    ) -> RawGroup:
        """创建群组"""

    @abstractmethod
    async def set_group_admin(
        self, group_id: "GroupID", user_id: "UserID", is_admin: bool = True
    ) -> bool:
        """设置/取消管理员"""

    @abstractmethod
    async def invite_to_group(self, group_id: "GroupID", user_id: "UserID") -> bool:
        """邀请成员"""

    @abstractmethod
    async def kick_group_member(
        self, group_id: "GroupID", user_id: "UserID", reason: Optional[str] = None
    ) -> bool:
        """移除成员"""

    # TODO 待完善的接口抽象
    # @abstractmethod
    # async def set_group_announcement(self, group_id: "GroupID", announcement: str) -> bool:
    #     """发布/编辑群公告"""

    @abstractmethod
    async def set_group_name(self, group_id: "GroupID", name: str) -> bool:
        """修改群名称"""

    @abstractmethod
    async def set_group_avatar(self, group_id: "GroupID", avatar_uri: str) -> bool:
        """修改群头像"""

    @abstractmethod
    async def disband_group(self, group_id: "GroupID") -> bool:
        """解散群"""

    @abstractmethod
    async def transfer_group_ownership(
        self, group_id: "GroupID", new_owner_id: "UserID"
    ) -> bool:
        """转让群主"""

    @abstractmethod
    async def leave_group(self, group_id: "GroupID") -> bool:
        """退出群组"""

    # ========== 个人资料管理 ==========

    @abstractmethod
    async def set_self_nickname(self, nickname: str) -> bool:
        """设置/修改本人昵称"""

    @abstractmethod
    async def set_self_avatar(self, avatar_uri: str) -> bool:
        """设置/修改本人头像"""

    @abstractmethod
    async def set_self_signature(self, signature: str) -> bool:
        """设置/修改本人签名/状态"""

    @abstractmethod
    async def update_self_profile(self, profile_data: Dict[str, Any]) -> bool:
        """批量更新个人资料"""

    # ========== 信息显示 ==========

    @abstractmethod
    async def print_event(self, msg: Event) -> None:
        """打印事件"""
