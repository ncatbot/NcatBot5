# IMClient.py
"""
IM客户端
"""
import logging
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Self, TypeVar

if TYPE_CHECKING:
    from ..abc.api_base import APIBase as APIBase
    from .IM import Group, Me, Message, User

    APIBaseT = TypeVar("APIBaseT", bound=APIBase)

from ..abc.protocol_abc import ProtocolABC
from ..utils.typec import GroupID, MsgId, UserID

log = logging.getLogger("IMClient")

# def unsupported_warning(func: Callable) -> Callable:
#     """
#     如果协议不支持该功能，捕获 NotImplementedError 并发出警告。
#     """
#     @wraps(func)
#     async def wrapper(self, *args, **kwargs):
#         protocol: "ProtocolABC" = getattr(self, "protocol", None)
#         if protocol is None:
#             raise RuntimeError("未找到 protocol 属性")

#         try:
#             return await func(self, *args, **kwargs)
#         except NotImplementedError:
#             doc = func.__doc__ or ""
#             warning_msg = f"协议 {protocol.protocol_name} 不支持 {doc.strip()}（{func.__name__}）"
#             raise RuntimeError(warning_msg)
#             return False

#     return wrapper


class IMClient:
    """
    IM客户端单例
    每个进程只能有一个实例
    通过类方法获取当前实例
    """

    _instance: Optional["IMClient"] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        # 双重检查锁定，确保线程安全
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, protocol: ProtocolABC):
        # 防止重复初始化
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            # 保存协议实例
            self._protocol: "ProtocolABC" = protocol
            self._me: Optional["Me"] = None
            self._initialized = True

            log.debug(f"IMClient 初始化完成，使用协议: {self.protocol_name}")

    @classmethod
    def get_current(cls) -> Optional[Self]:
        """获取当前IMClient实例"""
        if not cls._instance:
            raise ValueError("IMClient尚未初始化")
        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls._initialized

    @property
    def protocol(self) -> "ProtocolABC":
        """获取当前协议实例"""
        if not self._initialized:
            raise RuntimeError("IMClient未初始化")
        return self._protocol

    @property
    def protocol_name(self) -> str:
        """获取协议名称"""
        return self._protocol.protocol_name

    @property
    def me(self) -> Optional["Me"]:
        """当前用户"""
        if self._me:
            return self._me
        else:
            from .IM import Me, User

            me = Me.from_user(User(self.protocol.self_id))
            self._me = me
            return me

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._me is not None

    @property
    def api(self) -> "APIBaseT":
        """获取底层API（供高级用户直接使用）"""
        return self.protocol.api

    # ========== 核心方法 ==========

    async def send_group_message(
        self,
        group_id: GroupID,
        msg: "Message",
    ) -> "Message":
        """发送群消息"""
        response = await self.protocol.send_group_message(group_id, msg)
        return self.protocol._parse_message(response)

    async def send_private_message(
        self,
        user_id: UserID,
        msg: "Message",
    ) -> "Message":
        """发送私聊消息"""
        response = await self.protocol.send_private_message(user_id, msg)
        return self.protocol._parse_message(response)

    async def recall_message(self, msg_id: MsgId) -> bool:
        """撤回消息"""
        return await self.protocol.recall_message(msg_id)

    async def get_message(self, msg_id: MsgId) -> "Message":
        """获取消息对象"""
        response = await self.protocol.fetch_message(msg_id)
        return self.protocol._parse_message(response)

    async def get_user(self, user_id: UserID) -> "User":
        """获取用户对象"""
        response = await self.protocol.fetch_user(user_id)
        return self.protocol._parse_user(response)

    async def get_user_info(self, user_id: UserID) -> Dict[str, Any]:
        """获取用户详细信息"""
        try:
            response = await self.protocol.fetch_user(user_id)
            # 转换为字典格式
            if hasattr(response, "__dict__"):
                return response.__dict__
            elif isinstance(response, dict):
                return response
            else:
                return {"uid": user_id, "nickname": "未知用户"}
        except (NotImplementedError, Exception):
            return {"uid": user_id, "nickname": "未知用户"}

    async def get_friends(self) -> List["User"]:
        """获取好友列表"""
        response = await self.protocol.fetch_friends()

        users = []
        for user_data in response:
            users.append(self.protocol._parse_user(user_data))

        return users

    async def get_group(self, group_id: GroupID) -> "Group":
        """获取群组对象"""
        response = await self.protocol.fetch_group(group_id)
        return self.protocol._parse_group(response)

    async def get_group_info(self, group_id: GroupID) -> Dict[str, Any]:
        """获取群组详细信息"""
        try:
            response = await self.protocol.fetch_group(group_id)
            if hasattr(response, "__dict__"):
                return response.__dict__
            elif isinstance(response, dict):
                return response
            else:
                return {"gid": group_id, "name": "未知群组"}
        except (NotImplementedError, Exception):
            return {"gid": group_id, "name": "未知群组"}

    async def get_groups(self) -> List["Group"]:
        """获取加入的群组列表"""
        response = await self.protocol.fetch_groups()

        groups = []
        for group_data in response:
            groups.append(self.protocol._parse_group(group_data))

        return groups

    async def get_group_members(self, group_id: GroupID) -> List["User"]:
        """获取群成员列表"""
        response = await self.protocol.fetch_group_members(group_id)

        users = []
        for user_data in response:
            users.append(self.protocol._parse_user(user_data))

        return users

    # ========== 好友管理方法 ==========
    # @unsupported_warning
    async def add_friend(self, user_id: UserID, remark: Optional[str] = None) -> bool:
        """发起加好友请求"""
        return await self.protocol.add_friend(user_id, remark)

    # @unsupported_warning
    async def delete_friend(self, user_id: UserID) -> bool:
        """删除好友"""
        return await self.protocol.delete_friend(user_id)

    # @unsupported_warning
    async def block_user(self, user_id: UserID) -> bool:
        """拉黑用户"""
        return await self.protocol.block_user(user_id)

    # @unsupported_warning
    async def unblock_user(self, user_id: UserID) -> bool:
        """解除拉黑"""
        return await self.protocol.unblock_user(user_id)

    # @unsupported_warning
    async def set_friend_remark(self, user_id: UserID, remark: str) -> bool:
        """设置好友备注"""
        return await self.protocol.set_friend_remark(user_id, remark)

    # @unsupported_warning
    async def accept_friend_request(self, request_id: str) -> bool:
        """通过好友请求"""
        return await self.protocol.accept_friend_request(request_id)

    # @unsupported_warning
    async def reject_friend_request(self, request_id: str) -> bool:
        """拒绝好友请求"""
        return await self.protocol.reject_friend_request(request_id)

    # ========== 群管理方法 ==========

    # @unsupported_warning
    async def create_group(
        self, name: str, initial_members: List[UserID] = None
    ) -> "Group":
        """创建群组"""
        response = await self.protocol.create_group(name, initial_members or [])
        return self.protocol._parse_group(response)

    # @unsupported_warning
    async def set_group_admin(
        self, group_id: GroupID, user_id: UserID, is_admin: bool = True
    ) -> bool:
        """设置/取消管理员"""
        return await self.protocol.set_group_admin(group_id, user_id, is_admin)

    # @unsupported_warning
    async def invite_to_group(self, group_id: GroupID, user_id: UserID) -> bool:
        """邀请成员"""
        return await self.protocol.invite_to_group(group_id, user_id)

    # @unsupported_warning
    async def kick_group_member(
        self, group_id: GroupID, user_id: UserID, reason: Optional[str] = None
    ) -> bool:
        """移除成员"""
        return await self.protocol.kick_group_member(group_id, user_id, reason)

    # @unsupported_warning
    # async def set_group_announcement(self, group_id: GroupID, announcement: str) -> bool:
    #     """发布/编辑群公告"""
    #     return await self.protocol.set_group_announcement(group_id, announcement)

    # @unsupported_warning
    async def set_group_name(self, group_id: GroupID, name: str) -> bool:
        """修改群名称"""
        return await self.protocol.set_group_name(group_id, name)

    # @unsupported_warning
    async def set_group_avatar(self, group_id: GroupID, avatar_url: str) -> bool:
        """修改群头像"""
        return await self.protocol.set_group_avatar(group_id, avatar_url)

    # @unsupported_warning
    async def disband_group(self, group_id: GroupID) -> bool:
        """解散群"""
        return await self.protocol.disband_group(group_id)

    # @unsupported_warning
    async def transfer_group_ownership(
        self, group_id: GroupID, new_owner_id: UserID
    ) -> bool:
        """转让群主"""
        return await self.protocol.transfer_group_ownership(group_id, new_owner_id)

    # @unsupported_warning
    async def leave_group(self, group_id: GroupID) -> bool:
        """退出群组"""
        return await self.protocol.leave_group(group_id)

    # ========== 个人资料管理 ==========

    # @unsupported_warning
    async def set_self_nickname(self, nickname: str) -> bool:
        """设置/修改本人昵称"""
        return await self.protocol.set_self_nickname(nickname)

    # @unsupported_warning
    async def set_self_avatar(self, avatar_url: str) -> bool:
        """设置/修改本人头像"""
        return await self.protocol.set_self_avatar(avatar_url)

    # @unsupported_warning
    async def set_self_signature(self, signature: str) -> bool:
        """设置/修改本人签名/状态"""
        return await self.protocol.set_self_signature(signature)

    # @unsupported_warning
    async def update_self_profile(self, profile_data: Dict[str, Any]) -> bool:
        """批量更新个人资料"""
        return await self.protocol.update_self_profile(profile_data)

    # ========== 直接API访问 ==========

    # async def call_api(self, activity: str, **kwargs) -> Any:
    #     """直接调用底层API"""
    #     return await self.api.call(activity, **kwargs)

    # def can(self, func: str) -> bool:
    #     return self.protocol.can(func)
