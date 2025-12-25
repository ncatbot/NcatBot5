"""
Instant Messaging Software Development Kit
所有快捷操作都委托给 IMClient
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:
    from .client import IMClient

# ---------------- 前置工具类型 ----------------
from ..core.nodes import MessageNode
from ..utils.typec import GroupID, MsgId, UserID


# ---------------- 扩展信息（无依赖，放最前） ----------------
@dataclass
class UserInfo:
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
    member_count: int = 0
    max_members: int = 500
    owner_id: Optional[UserID] = None
    is_mute_all: bool = False
    description: Optional[str] = None
    create_time: Optional[dt.datetime] = None
    admin_ids: List[UserID] = field(default_factory=list)
    announcement: Optional[str] = None


@dataclass
class MessageInfo:
    edited: bool = False
    edit_time: Optional[dt.datetime] = None
    reactions: Dict[str, List[UserID]] = field(default_factory=dict)
    read_count: int = 0
    read_users: List[UserID] = field(default_factory=list)

    async def get_reaction_users(self, emoji: str) -> List[User]:
        if emoji not in self.reactions:
            return []
        client = IMClient.get_current()
        if not client:
            return []
        users: List[User] = []
        for uid in self.reactions[emoji]:
            try:
                users.append(await client.get_user(uid))
            except Exception:
                continue
        return users

    async def get_read_users(self) -> List[User]:
        client = IMClient.get_current()
        if not client:
            return []
        users: List[User] = []
        for uid in self.read_users:
            try:
                users.append(await client.get_user(uid))
            except Exception:
                continue
        return users


# ---------------- 消息链（仅依赖 MessageNode） ----------------
class MessageChain(Sequence[Union[MessageNode, str]]):
    """消息链，可以包含 MessageNode 或原生字符串"""

    __slots__ = ("_nodes",)

    def __init__(self, nodes: Iterable[Union[MessageNode, str]] | None = None):
        self._nodes: tuple[Union[MessageNode, str], ...] = tuple(nodes) if nodes else ()

    # Sequence 接口
    def __getitem__(
        self, index: int | slice
    ) -> Union[MessageNode, str, "MessageChain"]:
        if isinstance(index, slice):
            return MessageChain(self._nodes[index])
        return self._nodes[index]

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterator[Union[MessageNode, str]]:
        return iter(self._nodes)

    def __repr__(self) -> str:
        return f"MessageChain(nodes={list(self._nodes)!r})"

    def __str__(self) -> str:
        """更好的字符串表示"""
        nodes_str = []
        for node in self._nodes:
            if isinstance(node, str):
                nodes_str.append(node)
            else:
                # 调用MessageNode的__str__方法
                nodes_str.append(str(node))
        return "".join(nodes_str)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, MessageChain) and self._nodes == other._nodes

    def __hash__(self) -> int:
        return hash(self._nodes)

    def __add__(
        self, other: Union["MessageChain", Iterable[Union[MessageNode, str]]]
    ) -> "MessageChain":
        if isinstance(other, MessageChain):
            return MessageChain(self._nodes + other._nodes)
        return MessageChain(list(self._nodes) + list(other))

    # 工厂
    @classmethod
    def empty(cls) -> "MessageChain":
        return cls()

    @classmethod
    def of(cls, *nodes: Union[MessageNode, str]) -> "MessageChain":
        return cls(nodes)

    @classmethod
    def from_text(cls, text: str) -> "MessageChain":
        # 直接使用字符串，不转换为TextNode
        return cls([text])

    @classmethod
    def from_nodes(cls, nodes: List[MessageNode]) -> "MessageChain":
        return cls(nodes)

    @classmethod
    def from_strings(cls, *strings: str) -> "MessageChain":
        """从多个字符串创建消息链"""
        return cls(strings)

    # 转换
    def to_json(self) -> str:
        """转换为JSON字符串，协议需要自行处理字符串节点"""
        nodes_data = []
        for node in self._nodes:
            if isinstance(node, str):
                # 字符串节点，协议需要自行处理
                nodes_data.append({"type": "text", "content": node})
            else:
                # MessageNode，使用其自身的to_dict方法
                nodes_data.append(node.to_dict())
        return json.dumps(nodes_data, ensure_ascii=False)

    def to_list(self) -> List[Union[MessageNode, str]]:
        """返回节点列表的深拷贝"""
        result = []
        for node in self._nodes:
            if isinstance(node, MessageNode):
                result.append(deepcopy(node))
            else:
                # 字符串是不可变的，可以直接使用
                result.append(node)
        return result

    def to_raw_list(self) -> List[Union[MessageNode, str]]:
        """返回原始节点列表（浅拷贝）"""
        return list(self._nodes)

    # 查询
    def filter(
        self, predicate: Callable[[Union[MessageNode, str]], bool]
    ) -> "MessageChain":
        """过滤节点"""
        return MessageChain(node for node in self._nodes if predicate(node))

    def find_first(
        self, predicate: Callable[[Union[MessageNode, str]], bool]
    ) -> Union[MessageNode, str, None]:
        """查找第一个满足条件的节点"""
        for node in self._nodes:
            if predicate(node):
                return node
        return None

    def contains_type(self, node_type: type) -> bool:
        """检查是否包含指定类型的节点"""
        return any(
            isinstance(node, node_type)
            for node in self._nodes
            if isinstance(node, MessageNode)
        )

    def get_nodes_by_type(self, node_type: type) -> List[MessageNode]:
        """获取指定类型的所有节点（只返回MessageNode）"""
        return [node for node in self._nodes if isinstance(node, node_type)]

    def get_strings(self) -> List[str]:
        """获取所有字符串节点"""
        return [node for node in self._nodes if isinstance(node, str)]

    def get_message_nodes(self) -> List[MessageNode]:
        """获取所有MessageNode节点"""
        return [node for node in self._nodes if isinstance(node, MessageNode)]


# ---------------- 引用 / 转发信息（仅依赖 MsgId, UserID） ----------------
@dataclass(frozen=True)
class MessageReference:
    """消息引用信息"""

    message_id: MsgId
    sender_id: UserID
    preview: str
    timestamp: dt.datetime

    async def get_message(self) -> Optional["Message"]:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_message(self.message_id)
            except Exception:
                return None
        return None

    async def get_sender(self) -> Optional["User"]:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_user(self.sender_id)
            except Exception:
                return None
        return None


@dataclass(frozen=True)
class ForwardInfo:
    """转发信息"""

    original_message_id: MsgId
    original_sender_id: UserID
    original_timestamp: dt.datetime
    original_content: MessageChain  # 包含原始消息内容
    forwarder_id: UserID

    async def get_original_message(self) -> Optional["Message"]:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_message(self.original_message_id)
            except Exception:
                # 如果无法获取原始消息，使用存储的信息构建一个简化的消息对象
                return Message(
                    msg_id=self.original_message_id,
                    sender_id=self.original_sender_id,
                    content=self.original_content,
                    timestamp=self.original_timestamp,
                    message_type=Message.NORMAL,
                )
        return None

    async def get_original_sender(self) -> Optional["User"]:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_user(self.original_sender_id)
            except Exception:
                return None
        return None

    async def get_forwarder(self) -> Optional["User"]:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_user(self.forwarder_id)
            except Exception:
                return None
        return None


# ---------------- 消息实体（依赖 MessageChain / 引用 / 转发） ----------------
class Message:
    """消息实体，用于表示一条完整的消息

    消息类型说明：
    - NORMAL: 普通消息，content包含消息内容
    - REPLY: 回复消息，content包含回复内容，reference引用被回复的消息
    - FORWARD: 转发消息，content通常为空（除非添加评论），forward_info包含原始消息信息
    - SYSTEM: 系统消息，content包含系统消息内容
    """

    NORMAL = "normal"  # 普通消息
    REPLY = "reply"  # 回复消息（可添加内容）
    FORWARD = "forward"  # 转发消息（通常不添加内容）
    SYSTEM = "system"  # 系统消息

    __slots__ = (
        "_id",
        "_sender_id",
        "_sender_cache",
        "_content",
        "_timestamp",
        "_group_id",
        "_group_cache",
        "_message_type",
        "_reference",
        "_forward_info",
        "_client",
        "_info",
    )

    def __init__(
        self,
        msg_id: MsgId | None,
        sender_id: UserID,
        content: MessageChain,
        timestamp: dt.datetime,
        message_type: str = NORMAL,
        group_id: GroupID | None = None,
        reference: Optional[MessageReference] = None,
        forward_info: Optional[ForwardInfo] = None,
    ):
        self._id = msg_id
        self._sender_id = sender_id
        self._sender_cache: Optional["User"] = None
        self._content = content
        self._timestamp = timestamp
        self._group_id = group_id
        self._group_cache: Optional["Group"] = None
        self._message_type = message_type
        self._reference = reference
        self._forward_info = forward_info
        from .client import IMClient

        self._client = IMClient.get_current()
        if not self._client:
            raise ValueError("没有选择协议")
        self._info = MessageInfo()

    # 只读属性
    @property
    def id(self) -> Optional[MsgId]:
        return self._id

    @property
    def sender_id(self) -> UserID:
        return self._sender_id

    @property
    def content(self) -> MessageChain:
        return self._content

    @property
    def timestamp(self) -> dt.datetime:
        return self._timestamp

    @property
    def group_id(self) -> Optional[GroupID]:
        return self._group_id

    @property
    def message_type(self) -> str:
        return self._message_type

    @property
    def reference(self) -> Optional[MessageReference]:
        return self._reference

    @property
    def forward_info(self) -> Optional[ForwardInfo]:
        return self._forward_info

    @property
    def info(self) -> MessageInfo:
        return self._info

    @property
    def is_group_message(self) -> bool:
        return self._group_id is not None

    @property
    def is_private_message(self) -> bool:
        return self._group_id is None

    @property
    def is_reply(self) -> bool:
        return self._message_type == self.REPLY

    @property
    def is_forward(self) -> bool:
        return self._message_type == self.FORWARD

    @property
    def is_normal(self) -> bool:
        return self._message_type == self.NORMAL

    @property
    def is_system(self) -> bool:
        return self._message_type == self.SYSTEM

    # 代理到 content
    def __getitem__(self, index: int | slice) -> Union[MessageNode, str, MessageChain]:
        return self._content[index]

    def __len__(self) -> int:
        return len(self._content)

    def __iter__(self) -> Iterator[Union[MessageNode, str]]:
        return iter(self._content)

    def __contains__(self, item: Any) -> bool:
        return item in self._content

    def __repr__(self) -> str:
        return (
            f"Message(id={self._id}, type={self._message_type}, "
            f"sender_id={self._sender_id}, group_id={self._group_id})"
        )

    def __str__(self) -> str:
        return str(self._content)

    # 异步获取完整对象
    async def get_sender(self) -> "User":
        if self._sender_cache is None:
            self._sender_cache = await self._client.get_user(self._sender_id)
        return self._sender_cache

    async def get_group(self) -> Optional["Group"]:
        if self._group_id is None:
            return None
        if self._group_cache is None:
            self._group_cache = await self._client.get_group(self._group_id)
        return self._group_cache

    async def get_referenced_message(self) -> Optional["Message"]:
        return await self._reference.get_message() if self._reference else None

    async def get_original_message(self) -> Optional["Message"]:
        """获取转发消息的原始消息"""
        return (
            await self._forward_info.get_original_message()
            if self._forward_info
            else None
        )

    # 消息操作
    async def reply(self, content: MessageChain) -> "Message":
        """回复这条消息，添加新内容"""
        if self._id is None:
            raise ValueError("无法回复一条没有ID的消息")

        reply_msg = Message(
            msg_id=None,  # 发送时由服务器生成
            sender_id=self._client.protocol.self_id,
            content=content,
            timestamp=dt.datetime.now(),
            message_type=self.REPLY,
            group_id=self._group_id,
            reference=MessageReference(
                message_id=self._id,
                sender_id=self._sender_id,
                preview=str(self)[:10],
                timestamp=self._timestamp,
            ),
        )

        if self.is_group_message:
            return await self._client.send_group_message(self._group_id, reply_msg)
        else:
            return await self._client.send_private_message(self._sender_id, reply_msg)

    async def reply_text(self, text: str) -> "Message":
        """用文本回复这条消息"""
        return await self.reply(MessageChain.from_text(text))

    async def forward_to_user(
        self, user_id: UserID, extra_content: Optional[MessageChain] = None
    ) -> "Message":
        """转发消息给指定用户

        Args:
            user_id: 目标用户ID
            extra_content: 可选的额外内容（如转发时的评论）
        """
        # 构建转发消息，content通常是空或包含额外评论
        forward_content = extra_content or MessageChain.empty()

        msg = Message(
            msg_id=None,  # 发送时由服务器生成
            sender_id=self._client.protocol.self_id,
            content=forward_content,
            timestamp=dt.datetime.now(),
            message_type=self.FORWARD,
            group_id=None,  # 转发给用户，所以是私聊
            forward_info=ForwardInfo(
                original_message_id=self._id,
                original_sender_id=self._sender_id,
                original_timestamp=self._timestamp,
                original_content=self._content,  # 存储原始消息内容
                forwarder_id=self._client.protocol.self_id,
            )
            if self._id
            else None,
        )

        return await self._client.send_private_message(user_id, msg)

    async def forward_to_group(
        self, group_id: GroupID, extra_content: Optional[MessageChain] = None
    ) -> "Message":
        """转发消息到指定群组

        Args:
            group_id: 目标群组ID
            extra_content: 可选的额外内容（如转发时的评论）
        """
        # 构建转发消息，content通常是空或包含额外评论
        forward_content = extra_content or MessageChain.empty()

        msg = Message(
            msg_id=None,  # 发送时由服务器生成
            sender_id=self._client.protocol.self_id,
            content=forward_content,
            timestamp=dt.datetime.now(),
            message_type=self.FORWARD,
            group_id=group_id,  # 目标群组
            forward_info=ForwardInfo(
                original_message_id=self._id,
                original_sender_id=self._sender_id,
                original_timestamp=self._timestamp,
                original_content=self._content,  # 存储原始消息内容
                forwarder_id=self._client.protocol.self_id,
            )
            if self._id
            else None,
        )

        return await self._client.send_group_message(group_id, msg)

    async def resend(self) -> "Message":
        """重新发送这条消息的内容"""
        if self._group_id is None:
            # 重新发送给用户
            new_message = Message.create(
                content=self._content,
                sender_id=self._client.protocol.self_id,
                group_id=None,
            )
            return await self._client.send_private_message(self._sender_id, new_message)

        else:
            # 重新发送到群组
            new_message = Message.create(
                content=self._content,
                sender_id=self._client.protocol.self_id,
                group_id=self._group_id,
            )
            return await self._client.send_group_message(self._group_id, new_message)

    def copy_content(self) -> MessageChain:
        """复制消息内容"""
        return MessageChain(self._content.to_list())

    @classmethod
    def create(
        cls,
        content: MessageChain,
        sender_id: Optional[UserID] = None,
        group_id: Optional[GroupID] = None,
        reference: Optional[MessageReference] = None,
        forward_info: Optional[ForwardInfo] = None,
    ) -> "Message":
        """创建一条新消息（用于发送）"""
        from .client import IMClient

        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")

        if sender_id is None:
            sender_id = client.protocol.self_id

        return Message(
            msg_id=None,
            sender_id=sender_id,
            content=content,
            timestamp=dt.datetime.now(),
            message_type=cls.REPLY if reference else cls.NORMAL,
            group_id=group_id,
            reference=reference,
            forward_info=forward_info,
        )

    @classmethod
    def create_forward(
        cls,
        original_message: "Message",
        forwarder_id: Optional[UserID] = None,
        extra_content: Optional[MessageChain] = None,
        group_id: Optional[GroupID] = None,
    ) -> "Message":
        """创建转发消息

        Args
            original_message: 原始消息
            forwarder_id: 转发者ID，默认为当前用户
            extra_content: 额外内容（如转发评论）
            group_id: 如果是群聊转发，指定群组ID
        """
        from .client import IMClient

        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")

        if forwarder_id is None:
            forwarder_id = client.protocol.self_id

        # 构建转发消息
        forward_content = extra_content or MessageChain.empty()

        return Message(
            msg_id=None,  # 发送时由服务器生成
            sender_id=forwarder_id,
            content=forward_content,
            timestamp=dt.datetime.now(),
            message_type=cls.FORWARD,
            group_id=group_id,
            forward_info=ForwardInfo(
                original_message_id=original_message.id,
                original_sender_id=original_message.sender_id,
                original_timestamp=original_message.timestamp,
                original_content=original_message.content,
                forwarder_id=forwarder_id,
            )
            if original_message.id
            else None,
        )


# ---------------- 用户 / 群组 / Me（依赖 Message / MessageChain） ----------------
class User:
    _client: Optional["IMClient"] = None

    def __init__(
        self,
        uid: UserID,
        nickname: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ):
        self._uid = uid
        self._nickname = nickname
        self._avatar_url = avatar_url
        from .client import IMClient

        self._client = IMClient.get_current()
        if not self._client:
            raise ValueError("没有选择协议")
        self.info = UserInfo()

    @property
    def uid(self) -> UserID:
        return self._uid

    async def get_nickname(self) -> str:
        if self._nickname:
            return self._nickname
        user_info = await self._client.get_user_info(self._uid)
        self._nickname = user_info.get("nickname", "未知用户")
        return self._nickname

    async def get_avatar_url(self) -> Optional[str]:
        if self._avatar_url:
            return self._avatar_url
        user_info = await self._client.get_user_info(self._uid)
        self._avatar_url = user_info.get("avatar_url")
        return self._avatar_url

    # 私聊快捷
    async def send_text(self, text: str) -> Message:
        """发送文本消息"""
        message = Message.create(
            content=MessageChain.from_text(text),
            sender_id=self._client.protocol.self_id,
        )
        return await self._client.send_private_message(self._uid, message)

    async def send_message(self, message: Message) -> Message:
        """发送消息"""
        # 确保消息的发送者是当前用户
        if message.sender_id != self._client.protocol.self_id:
            # 如果消息的发送者不是当前用户，重新包装消息
            new_message = Message(
                msg_id=None,
                sender_id=self._client.protocol.self_id,
                content=message.content,
                timestamp=dt.datetime.now(),
                message_type=message.message_type,
                group_id=None,
                reference=message.reference,
                forward_info=message.forward_info,
            )
            return await self._client.send_private_message(self._uid, new_message)
        return await self._client.send_private_message(self._uid, message)

    async def send_message_chain(self, content: MessageChain) -> Message:
        """发送消息链"""
        message = Message.create(
            content=content,
            sender_id=self._client.protocol.self_id,
        )
        return await self._client.send_private_message(self._uid, message)

    async def forward_message(
        self, message: Message, extra_content: Optional[MessageChain] = None
    ) -> Message:
        """转发消息给当前用户"""
        return await self._client.forward_private_message(
            self._uid, message, extra_content
        )

    # 好友管理
    async def add_friend(self, remark: Optional[str] = None) -> bool:
        return await self._client.add_friend(self._uid, remark)

    async def delete_friend(self) -> bool:
        return await self._client.delete_friend(self._uid)

    async def block(self) -> bool:
        return await self._client.block_user(self._uid)

    async def unblock(self) -> bool:
        return await self._client.unblock_user(self._uid)

    async def set_remark(self, remark: str) -> bool:
        return await self._client.set_friend_remark(self._uid, remark)

    # 静态方法
    @staticmethod
    async def accept_friend_request(request_id: str) -> bool:
        client = IMClient.get_current()
        return await client.accept_friend_request(request_id)

    @staticmethod
    async def reject_friend_request(request_id: str) -> bool:
        client = IMClient.get_current()
        return await client.reject_friend_request(request_id)

    # 快捷属性
    @property
    def display_name(self) -> str:
        if self.info.remark:
            return self.info.remark
        if self._nickname:
            return self._nickname
        return str(self._uid)


class Group:
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
        return await self._client.get_group_info(self._gid)

    # 群聊快捷
    async def send_text(self, text: str) -> Message:
        """发送文本消息到群聊"""
        message = Message.create(
            content=MessageChain.from_text(text),
            sender_id=self._client.protocol.self_id,
            group_id=self._gid,
        )
        return await self._client.send_group_message(self._gid, message)

    async def send_message(self, message: Message) -> Message:
        """发送消息到群聊"""
        # 确保消息的发送者是当前用户且目标群组正确
        if (
            message.sender_id != self._client.protocol.self_id
            or message.group_id != self._gid
        ):
            # 重新包装消息
            new_message = Message(
                msg_id=None,
                sender_id=self._client.protocol.self_id,
                content=message.content,
                timestamp=dt.datetime.now(),
                message_type=message.message_type,
                group_id=self._gid,
                reference=message.reference,
                forward_info=message.forward_info,
            )
            return await self._client.send_group_message(self._gid, new_message)
        return await self._client.send_group_message(self._gid, message)

    async def send_message_chain(self, content: MessageChain) -> Message:
        """发送消息链到群聊"""
        message = Message.create(
            content=content,
            sender_id=self._client.protocol.self_id,
            group_id=self._gid,
        )
        return await self._client.send_group_message(self._gid, message)

    async def forward_message(
        self, message: Message, extra_content: Optional[MessageChain] = None
    ) -> Message:
        """转发消息到当前群组"""
        return await self._client.forward_group_message(
            self._gid, message, extra_content
        )

    async def recall_message(self, message_id: MsgId) -> bool:
        return await self._client.recall_message(message_id)

    # 群管理
    @staticmethod
    async def create_group(
        name: str, initial_members: Optional[List[UserID]] = None
    ) -> "Group":
        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")
        return await client.create_group(name, initial_members)

    async def set_admin(
        self, user: Union["User", UserID], is_admin: bool = True
    ) -> bool:
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.set_group_admin(self._gid, user_id, is_admin)

    async def invite_member(self, user: Union["User", UserID]) -> bool:
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.invite_to_group(self._gid, user_id)

    async def remove_member(
        self, user: Union["User", UserID], reason: Optional[str] = None
    ) -> bool:
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.kick_group_member(self._gid, user_id, reason)

    async def set_name(self, new_name: str) -> bool:
        result = await self._client.set_group_name(self._gid, new_name)
        if result:
            self._name = new_name
        return result

    async def set_avatar(self, avatar_url: str) -> bool:
        result = await self._client.set_group_avatar(self._gid, avatar_url)
        if result:
            self._avatar_url = avatar_url
        return result

    async def disband(self) -> bool:
        return await self._client.disband_group(self._gid)

    async def transfer_ownership(self, new_owner: Union["User", UserID]) -> bool:
        new_owner_id = new_owner.uid if isinstance(new_owner, User) else new_owner
        return await self._client.transfer_group_ownership(self._gid, new_owner_id)

    async def get_members(self) -> List["User"]:
        return await self._client.get_group_members(self._gid)

    async def leave(self) -> bool:
        return await self._client.leave_group(self._gid)

    # 快捷属性
    @property
    def member_count(self) -> int:
        return self.info.member_count

    @property
    def owner_id(self) -> Optional[UserID]:
        return self.info.owner_id


class Me(User):
    """当前登录用户"""

    def __new__(cls, *_, **__):
        raise TypeError("Me 不允许直接实例化，请使用 Me.from_user(user) 进行升级")

    def __init__(self, *_):
        pass

    @property
    def uid(self) -> UserID:
        return self._client.protocol.self_id

    @classmethod
    def from_user(cls, user: User) -> "Me":
        me = object.__new__(cls)
        me.__dict__.update(user.__dict__)
        if hasattr(user, "_client"):
            from .client import IMClient

            me._client = IMClient.get_current()
        return me

    # 个人操作
    async def get_friends(self) -> List[User]:
        return await self._client.get_friends()

    async def get_groups(self) -> List[Group]:
        return await self._client.get_groups()

    async def set_nickname(self, nickname: str) -> bool:
        return await self._client.set_self_nickname(nickname)

    async def set_avatar(self, avatar_url: str) -> bool:
        return await self._client.set_self_avatar(avatar_url)

    async def set_signature(self, signature: str) -> bool:
        return await self._client.set_self_signature(signature)

    async def update_profile(self, **kwargs) -> bool:
        return await self._client.update_self_profile(kwargs)


# ---------------- 消息构建器（最后，依赖以上全部） ----------------
class MessageBuilder:
    """消息构建器，用于构建用于发送的消息"""

    def __init__(self) -> None:
        self._msg_id: Optional[MsgId] = None
        self._sender_id: Optional[UserID] = None
        self._content: Optional[MessageChain] = None
        self._timestamp: Optional[dt.datetime] = None
        self._msg_type: str = Message.NORMAL
        self._group_id: Optional[GroupID] = None
        self._reference: Optional[MessageReference] = None
        self._forward_info: Optional[ForwardInfo] = None

    def id(self, msg_id: MsgId) -> "MessageBuilder":
        self._msg_id = msg_id
        return self

    def sender(self, sender_id: UserID) -> "MessageBuilder":
        self._sender_id = sender_id
        return self

    def content(self, content: MessageChain) -> "MessageBuilder":
        self._content = content
        return self

    def text(self, text: str) -> "MessageBuilder":
        self._content = MessageChain.from_text(text)
        return self

    def timestamp(self, ts: dt.datetime) -> "MessageBuilder":
        self._timestamp = ts
        return self

    def now(self) -> "MessageBuilder":
        self._timestamp = dt.datetime.now()
        return self

    def type(self, tp: str) -> "MessageBuilder":
        self._msg_type = tp
        return self

    def group(self, gid: GroupID) -> "MessageBuilder":
        self._group_id = gid
        return self

    def private(self) -> "MessageBuilder":
        self._group_id = None
        return self

    def reply_to(
        self,
        msg_id: MsgId,
        sender_id: UserID,
        ts: dt.datetime,
        preview: Optional[str] = None,
    ) -> "MessageBuilder":
        self._msg_type = Message.REPLY
        self._reference = MessageReference(
            message_id=msg_id,
            sender_id=sender_id,
            preview=preview or "",
            timestamp=ts,
        )
        return self

    def forward_of(
        self,
        msg_id: MsgId,
        orig_sender: UserID,
        orig_ts: dt.datetime,
        orig_content: MessageChain,
        forwarder: UserID,
    ) -> "MessageBuilder":
        self._msg_type = Message.FORWARD
        self._forward_info = ForwardInfo(
            original_message_id=msg_id,
            original_sender_id=orig_sender,
            original_timestamp=orig_ts,
            original_content=orig_content,
            forwarder_id=forwarder,
        )
        return self

    def build(self) -> Message:
        """构建消息（用于发送）"""
        if self._sender_id is None:
            from .client import IMClient

            client = IMClient.get_current()
            if client:
                self._sender_id = client.protocol.self_id
            else:
                raise ValueError(
                    "MessageBuilder: sender_id required and no client found"
                )

        if self._timestamp is None:
            self._timestamp = dt.datetime.now()

        if self._content is None:
            self._content = MessageChain.empty()

        # 发送消息时不需要id，由服务器生成
        # 只保留id设置，如果用户明确设置了id（如用于构建接收到的消息）

        return Message(
            msg_id=self._msg_id,  # 可以为None
            sender_id=self._sender_id,
            content=self._content,
            timestamp=self._timestamp,
            message_type=self._msg_type,
            group_id=self._group_id,
            reference=self._reference,
            forward_info=self._forward_info,
        )


class MessageChainBuilder:
    """流畅接口构建消息链"""

    def __init__(self):
        self._nodes = []

    def text(self, text: str) -> "MessageChainBuilder":
        self._nodes.append(text)
        return self

    def node(self, node: MessageNode) -> "MessageChainBuilder":
        self._nodes.append(node)
        return self

    def build(self) -> MessageChain:
        return MessageChain(self._nodes)
