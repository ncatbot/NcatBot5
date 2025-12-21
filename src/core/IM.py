# IMabc.py
"""
Instant Messaging Software Development Kit
所有快捷操作都委托给IMClient
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    # 防止循环导入
    from .client import IMClient

from ..core.nodes import MessageNode
from ..utils.decorators import requires_client
from ..utils.typec import GroupID, MsgId, UserID


@dataclass
class MessageContent:
    """消息内容容器"""

    nodes: List[MessageNode] = field(default_factory=list)

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        nodes_data = []
        for node in self.nodes:
            node_dict = {"type": type(node).__name__.lower()}
            node_dict.update(node.__dict__)
            nodes_data.append(node_dict)
        return json.dumps(nodes_data, ensure_ascii=False)

    @property
    def text_preview(self) -> str:
        """获取纯文本预览"""
        preview_parts = []
        for node in self.nodes:
            preview_parts.append(str(node))

        return "".join(preview_parts)


# ========== 扩展信息类 ==========
@dataclass
class UserInfo:
    """用户扩展信息"""

    is_online: bool = False
    last_active: Optional[dt.datetime] = None
    is_friend: bool = False
    remark: Optional[str] = None
    gender: Optional[str] = None
    region: Optional[str] = None
    signature: Optional[str] = None
    join_time: Optional[dt.datetime] = None


@dataclass
class GroupInfo:
    """群组扩展信息"""

    member_count: int = 0
    max_members: int = 500
    owner_id: Optional[UserID] = None
    is_mute_all: bool = False
    description: Optional[str] = None
    create_time: Optional[dt.datetime] = None
    admin_ids: List[UserID] = field(default_factory=list)
    announcement: Optional[str] = None  # 新增：群公告


@dataclass
class MessageInfo:
    """消息扩展信息"""

    edited: bool = False
    edit_time: Optional[dt.datetime] = None
    reactions: Dict[str, List[UserID]] = field(default_factory=dict)
    read_count: int = 0
    read_users: List[UserID] = field(default_factory=list)


# ========== 核心数据类 ==========


class Message:
    """消息实体类"""

    _client: Optional["IMClient"] = None

    # 缓存
    _sender: User = None
    _group: Group = None

    def __init__(
        self,
        msg_id: MsgId,
        sender_id: UserID,
        content: MessageContent,
        timestamp: dt.datetime,
        group_id: Optional[GroupID] = None,
        reply_to: Optional[MsgId] = None,
        forward_from: Optional[MsgId] = None,
    ):
        self._id = msg_id
        self._sender_id = sender_id
        self._content = content
        self._timestamp = timestamp
        self._group_id = group_id
        self._reply_to = reply_to
        self._forward_from = forward_from
        from .client import IMClient

        self._client = IMClient.get_current()
        if not self._client:
            raise ValueError("没有选择协议")
        self.info = MessageInfo()

    @property
    def id(self) -> MsgId:
        return self._id

    @property
    def sender_id(self) -> UserID:
        return self._sender_id

    @property
    def content(self) -> MessageContent:
        return self._content

    @property
    def timestamp(self) -> dt.datetime:
        return self._timestamp

    @property
    def reply_to(self) -> Optional[MsgId]:
        return self._reply_to

    @property
    def forward_from(self) -> Optional[MsgId]:
        return self._forward_from

    @property
    def group_id(self) -> Optional[GroupID]:
        return self._group_id

    @property
    def is_group_message(self) -> bool:
        return self._group_id is not None

    @property
    def is_private_message(self) -> bool:
        return self._group_id is None

    # ---------- 动态属性 ----------

    async def get_sender(self) -> "User":
        """获取发送者对象"""
        if isinstance(self._sender, User):
            return self._sender

        if self.group_id:
            members: List[User] = await self._client.get_group_members(self._group_id)
            group_members = {user.uid: user for user in members}
            sender = group_members.get(self.sender_id)
            if not sender:
                sender = await self._client.get_user(self._sender_id)
        else:
            sender = await self._client.get_user(self._sender_id)

        self._sender = sender
        return sender

    async def get_group(self) -> Optional["Group"]:
        """获取群组对象（如果是群消息）"""
        if self._group:
            return self._group

        if self.group_id:
            self._group = await self._client.get_group(self._group_id)
            return self._group
        else:
            return None

    # ---------- 快捷操作 ----------
    # 私聊和群聊共用的方法

    async def reply_text(self, text: str) -> "Message":
        """快捷回复文本消息"""
        from .IM import ReplyNode, TextNode

        nodes = [
            ReplyNode(
                message_id=self._id,
                sender_id=self._sender_id,
                preview=self._content.text_preview[:50],
            ),
            TextNode(content=text),
        ]
        content = MessageContent(nodes=nodes)

        if self.is_group_message:
            return await self._client.send_group_message(self._group_id, content)
        else:
            return await self._client.send_private_message(self._sender_id, content)

    async def reply(self, content: MessageContent) -> "Message":
        """回复富文本消息"""
        from .IM import ReplyNode

        reply_node = ReplyNode(
            message_id=self._id,
            sender_id=self._sender_id,
            preview=self._content.text_preview[:50],
        )
        content.nodes.insert(0, reply_node)

        if self.is_group_message:
            return await self._client.send_group_message(self._group_id, content)
        else:
            return await self._client.send_private_message(self._sender_id, content)

    async def recall(self) -> bool:
        """撤回消息（本人消息）"""
        return await self._client.recall_message(self._id)

    async def forward_to_group(self, group: Group | GroupID) -> "Message":
        """转发到群组"""
        from .IM import ForwardNode

        forward_content = MessageContent(
            nodes=[
                ForwardNode(
                    message_id=self._id,
                    sender_id=self._sender_id,
                    preview=self._content.text_preview,
                    timestamp=self._timestamp,
                )
            ]
        )

        if isinstance(group, Group):
            group_id = group.gid
        else:
            group_id = group

        return await self._client.send_group_message(group_id, forward_content)

    async def forward_to_user(self, user: Union["User", UserID]) -> "Message":
        """转发到用户"""
        from .IM import ForwardNode

        forward_content = MessageContent(
            nodes=[
                ForwardNode(
                    message_id=self._id,
                    sender_id=self._sender_id,
                    preview=self._content.text_preview,
                    timestamp=self._timestamp,
                )
            ]
        )

        if isinstance(user, User):
            user_id = user.uid
        else:
            user_id = user

        return await self._client.send_private_message(user_id, forward_content)

    async def copy(self) -> "MessageContent":
        """复制消息内容"""
        # 深拷贝节点列表
        from copy import deepcopy

        return MessageContent(nodes=deepcopy(self.content.nodes))


class User:
    """用户实体类"""

    _client: Optional["IMClient"] = None

    def __init__(
        self,
        uid: UserID,
        nickname: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ):
        from .client import IMClient

        self._uid = uid
        self._nickname = nickname
        self._avatar_url = avatar_url
        self._client = IMClient.get_current()
        if not self._client:
            raise ValueError("没有选择协议")
        self.info = UserInfo()

    @property
    def uid(self) -> UserID:
        return self._uid

    async def get_nickname(self) -> str:
        """获取昵称（支持陌生人）"""
        if self._nickname:
            return self._nickname
        # 尝试从客户端获取最新信息
        user_info = await self._client.get_user_info(self._uid)
        self._nickname = user_info.get("nickname", "未知用户")
        return self._nickname

    async def get_avatar_url(self) -> Optional[str]:
        """获取头像URL（支持陌生人）"""
        if self._avatar_url:
            return self._avatar_url
        # 尝试从客户端获取最新信息
        user_info = await self._client.get_user_info(self._uid)
        self._avatar_url = user_info.get("avatar_url")
        return self._avatar_url

    # ---------- 私聊快捷操作 ----------

    async def send_text(self, text: str) -> "Message":
        """发送文本消息（私聊）"""
        return await self._client.send_text_to_user(self._uid, text)

    async def send_message(self, content: MessageContent) -> "Message":
        """发送富文本消息（私聊）"""
        return await self._client.send_private_message(self._uid, content)

    # ---------- 好友管理快捷操作 ----------

    async def add_friend(self, remark: Optional[str] = None) -> bool:
        """发起加好友请求"""
        return await self._client.add_friend(self._uid, remark)

    async def delete_friend(self) -> bool:
        """删除好友"""
        return await self._client.delete_friend(self._uid)

    async def block(self) -> bool:
        """拉黑用户"""
        return await self._client.block_user(self._uid)

    async def unblock(self) -> bool:
        """解除拉黑"""
        return await self._client.unblock_user(self._uid)

    async def set_remark(self, remark: str) -> bool:
        """设置好友备注"""
        return await self._client.set_friend_remark(self._uid, remark)

    # ---------- 静态方法：好友请求处理 ----------
    @staticmethod
    async def accept_friend_request(request_id: str) -> bool:
        """通过好友请求"""
        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")
        return await client.accept_friend_request(request_id)

    @staticmethod
    async def reject_friend_request(request_id: str) -> bool:
        """拒绝好友请求"""
        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")
        return await client.reject_friend_request(request_id)

    # 快捷属性
    @property
    def display_name(self) -> str:
        """显示名称：优先使用备注，其次昵称"""
        if self.info.remark:
            return self.info.remark
        if self._nickname:
            return self._nickname
        return str(self._uid)


class Group:
    """群组实体类"""

    _client: Optional["IMClient"] = None

    def __init__(
        self,
        gid: GroupID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ):
        self._gid = gid
        self._name = name
        self._description = description
        self._avatar_url = avatar_url
        from .client import IMClient

        self._client = IMClient.get_current()
        if not self._client:
            raise ValueError("没有选择协议")
        self.info = GroupInfo()

    @property
    def gid(self) -> GroupID:
        return self._gid

    @property
    def name(self) -> str:
        return self._name or f"群组 {self._gid}"

    @property
    def avatar_url(self) -> Optional[str]:
        return self._avatar_url

    async def get_info(self) -> Dict[str, Any]:
        """获取群组详细信息"""
        return await self._client.get_group_info(self._gid)

    # ---------- 群聊快捷操作 ----------

    async def send_text(self, text: str) -> "Message":
        """发送文本消息到群组"""
        return await self._client.send_text_to_group(self._gid, text)

    async def send_message(self, content: MessageContent) -> "Message":
        """发送富文本消息到群组"""
        return await self._client.send_group_message(self._gid, content)

    async def recall_message(self, message_id: MsgId) -> bool:
        """撤回群消息（本人消息）"""
        return await self._client.recall_message(message_id)

    # ---------- 群管理快捷操作 ----------

    async def create_group(name: str, initial_members: List[UserID] = None) -> "Group":
        """创建群组（静态方法）"""
        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")
        return await client.create_group(name, initial_members)

    async def set_admin(
        self, user: Union["User", UserID], is_admin: bool = True
    ) -> bool:
        """设置/取消管理员"""
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.set_group_admin(self._gid, user_id, is_admin)

    async def invite_member(self, user: Union["User", UserID]) -> bool:
        """邀请成员"""
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.invite_to_group(self._gid, user_id)

    async def remove_member(
        self, user: Union["User", UserID], reason: Optional[str] = None
    ) -> bool:
        """移除成员"""
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.kick_group_member(self._gid, user_id, reason)

    # async def set_announcement(self, announcement: str) -> bool:
    #     """发布/编辑群公告"""
    #     return await self._client.set_group_announcement(self._gid, announcement)

    async def set_name(self, new_name: str) -> bool:
        """修改群名称"""
        result = await self._client.set_group_name(self._gid, new_name)
        if result:
            self._name = new_name
        return result

    async def set_avatar(self, avatar_url: str) -> bool:
        """修改群头像"""
        result = await self._client.set_group_avatar(self._gid, avatar_url)
        if result:
            self._avatar_url = avatar_url
        return result

    async def disband(self) -> bool:
        """解散群"""
        return await self._client.disband_group(self._gid)

    async def transfer_ownership(self, new_owner: Union["User", UserID]) -> bool:
        """转让群主"""
        new_owner_id = new_owner.uid if isinstance(new_owner, User) else new_owner
        return await self._client.transfer_group_ownership(self._gid, new_owner_id)

    async def get_members(self) -> List["User"]:
        """获取群成员列表"""
        return await self._client.get_group_members(self._gid)

    async def leave(self) -> bool:
        """退出群组（非群主）"""
        return await self._client.leave_group(self._gid)

    # 快捷属性
    @property
    def member_count(self) -> int:
        return self.info.member_count

    @property
    def owner_id(self) -> Optional[UserID]:
        return self.info.owner_id


class Me(User):
    """当前用户类——禁止直接构造，必须从 User 升级而来"""

    # 堵死实例化
    def __new__(cls, *_, **__):
        raise TypeError("Me 不允许直接实例化，请使用 Me.from_user(user) 进行升级")

    def __init__(self, *_):
        pass

    @property
    def uid(self) -> UserID:
        return self._client.protocol.self_id

    # ---------- 工厂 ----------
    @classmethod
    def from_user(cls, user: "User") -> "Me":
        """把任意 User 实例无损转成 Me 实例（唯一合法入口）"""
        # 先建空壳
        me = object.__new__(cls)
        # 字段搬家
        me.__dict__.update(user.__dict__)
        if hasattr(user, "_client"):
            from .client import IMClient

            me._client = IMClient.get_current()
        return me

    # ---------- 快捷操作 ----------
    @requires_client
    async def get_friends(self) -> list["User"]:
        return await self._client.get_friends()

    @requires_client
    async def get_groups(self) -> list["Group"]:
        return await self._client.get_groups()

    # ---------- 个人资料管理 ----------

    async def set_nickname(self, nickname: str) -> bool:
        """设置/修改本人昵称"""
        return await self._client.set_self_nickname(nickname)

    async def set_avatar(self, avatar_url: str) -> bool:
        """设置/修改本人头像"""
        return await self._client.set_self_avatar(avatar_url)

    async def set_signature(self, signature: str) -> bool:
        """设置/修改本人签名/状态"""
        return await self._client.set_self_signature(signature)

    async def update_profile(self, **kwargs) -> bool:
        """批量更新个人资料"""
        return await self._client.update_self_profile(kwargs)
