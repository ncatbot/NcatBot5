"""
Instant Messaging Software Development Kit
所有快捷操作都委托给 IMClient
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Iterable, Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
class MessageChain(Sequence[MessageNode]):
    __slots__ = ("_nodes",)

    def __init__(self, nodes: Iterable[MessageNode] | None = None):
        self._nodes: tuple[MessageNode, ...] = tuple(nodes) if nodes else ()

    # Sequence 接口
    def __getitem__(self, index: int | slice) -> MessageNode | MessageChain:
        return (
            MessageChain(self._nodes[index])
            if isinstance(index, slice)
            else self._nodes[index]
        )

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterator[MessageNode]:
        return iter(self._nodes)

    def __repr__(self) -> str:
        return f"MessageChain(nodes={list(self._nodes)!r})"

    def __str__(self) -> str:
        return self.text_preview

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, MessageChain) and self._nodes == other._nodes

    def __hash__(self) -> int:
        return hash(self._nodes)

    def __add__(self, other: MessageChain | Iterable[MessageNode]) -> MessageChain:
        if isinstance(other, MessageChain):
            return MessageChain(self._nodes + other._nodes)
        return MessageChain(list(self._nodes) + list(other))

    # 工具
    @property
    def text_preview(self) -> str:
        return "".join(str(node) for node in self._nodes)

    # 工厂
    @classmethod
    def empty(cls) -> MessageChain:
        return cls()

    @classmethod
    def of(cls, *nodes: MessageNode) -> MessageChain:
        return cls(nodes)

    @classmethod
    def from_text(cls, text: str) -> MessageChain:
        from .IM import TextNode

        return cls([TextNode(content=text)])

    @classmethod
    def from_nodes(cls, nodes: List[MessageNode]) -> MessageChain:
        return cls(nodes)

    # 转换
    def to_json(self) -> str:
        return json.dumps([node.to_dict() for node in self._nodes], ensure_ascii=False)

    def to_list(self) -> List[MessageNode]:
        return deepcopy(list(self._nodes))

    # 查询
    def filter(self, predicate) -> MessageChain:
        return MessageChain(node for node in self._nodes if predicate(node))

    def find_first(self, predicate) -> MessageNode | None:
        for node in self._nodes:
            if predicate(node):
                return node
        return None

    def contains_type(self, node_type: type) -> bool:
        return any(isinstance(node, node_type) for node in self._nodes)

    def get_nodes_by_type(self, node_type: type) -> List[MessageNode]:
        return [node for node in self._nodes if isinstance(node, node_type)]

    @property
    def text_nodes(self) -> List[MessageNode]:
        from .IM import TextNode

        return self.get_nodes_by_type(TextNode)

    @property
    def text_content(self) -> str:
        from .IM import TextNode

        return "".join(
            node.content for node in self._nodes if isinstance(node, TextNode)
        )


# ---------------- 引用 / 转发信息（仅依赖 MsgId, UserID） ----------------
@dataclass(frozen=True)
class MessageReference:
    message_id: MsgId
    sender_id: UserID
    preview: str
    timestamp: dt.datetime

    async def get_message(self) -> Message | None:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_message(self.message_id)
            except Exception:
                return None
        return None

    async def get_sender(self) -> User | None:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_user(self.sender_id)
            except Exception:
                return None
        return None


@dataclass(frozen=True)
class ForwardInfo:
    original_message_id: MsgId
    original_sender_id: UserID
    original_timestamp: dt.datetime
    forwarder_id: UserID

    async def get_original_message(self) -> Message | None:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_message(self.original_message_id)
            except Exception:
                return None
        return None

    async def get_original_sender(self) -> User | None:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_user(self.original_sender_id)
            except Exception:
                return None
        return None

    async def get_forwarder(self) -> User | None:
        client = IMClient.get_current()
        if client:
            try:
                return await client.get_user(self.forwarder_id)
            except Exception:
                return None
        return None


# ---------------- 消息实体（依赖 MessageChain / 引用 / 转发） ----------------
class Message:
    NORMAL = "normal"
    REPLY = "reply"
    FORWARD = "forward"
    SYSTEM = "system"

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
        msg_id: MsgId,
        sender_id: UserID,
        content: MessageChain,
        timestamp: dt.datetime,
        message_type: str = NORMAL,
        group_id: GroupID | None = None,
        reference: MessageReference | None = None,
        forward_info: ForwardInfo | None = None,
    ):
        self._id = msg_id
        self._sender_id = sender_id
        self._sender_cache: User | None = None
        self._content = content
        self._timestamp = timestamp
        self._group_id = group_id
        self._group_cache: Group | None = None
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
    def id(self) -> MsgId:
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
    def group_id(self) -> GroupID | None:
        return self._group_id

    @property
    def message_type(self) -> str:
        return self._message_type

    @property
    def reference(self) -> MessageReference | None:
        return self._reference

    @property
    def forward_info(self) -> ForwardInfo | None:
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
    def __getitem__(self, index: int | slice) -> MessageNode | MessageChain:
        return self._content[index]

    def __len__(self) -> int:
        return len(self._content)

    def __iter__(self) -> Iterator[MessageNode]:
        return iter(self._content)

    def __contains__(self, item: MessageNode) -> bool:
        return item in self._content

    def __repr__(self) -> str:
        return (
            f"Message(id={self._id}, type={self._message_type}, "
            f"sender_id={self._sender_id}, group_id={self._group_id})"
        )

    def __str__(self) -> str:
        return str(self._content)

    # 便捷属性
    @property
    def text_preview(self) -> str:
        return self._content.text_preview

    @property
    def text_content(self) -> str:
        return self._content.text_content

    # 异步获取完整对象
    async def get_sender(self) -> User:
        if self._sender_cache is None:
            self._sender_cache = await self._client.get_user(self._sender_id)
        return self._sender_cache

    async def get_group(self) -> Group | None:
        if self._group_id is None:
            return None
        if self._group_cache is None:
            self._group_cache = await self._client.get_group(self._group_id)
        return self._group_cache

    async def get_referenced_message(self) -> Message | None:
        return await self._reference.get_message() if self._reference else None

    async def get_original_message(self) -> Message | None:
        return (
            await self._forward_info.get_original_message()
            if self._forward_info
            else None
        )

    # 消息操作
    def as_reply(
        self,
        reply_to_msg_id: MsgId,
        reply_to_sender_id: UserID,
        reply_to_timestamp: dt.datetime,
        preview: str | None = None,
    ) -> Message:
        return Message(
            msg_id=self._id,
            sender_id=self._sender_id,
            content=self._content,
            timestamp=self._timestamp,
            message_type=self.REPLY,
            group_id=self._group_id,
            reference=MessageReference(
                message_id=reply_to_msg_id,
                sender_id=reply_to_sender_id,
                preview=preview or self.text_preview[:100],
                timestamp=reply_to_timestamp,
            ),
        )

    def as_forward(self, forwarder_id: UserID) -> Message:
        return Message(
            msg_id=self._id,
            sender_id=forwarder_id,
            content=self._content,
            timestamp=dt.datetime.now(),
            message_type=self.FORWARD,
            group_id=self._group_id,
            forward_info=ForwardInfo(
                original_message_id=self._id,
                original_sender_id=self._sender_id,
                original_timestamp=self._timestamp,
                forwarder_id=forwarder_id,
            ),
        )

    async def reply(self, content: MessageChain) -> Message:
        if self.is_group_message:
            return await self._client.send_group_message(self._group_id, content)
        else:
            return await self._client.send_private_message(self._sender_id, content)

    async def reply_text(self, text: str) -> Message:
        return await self.reply(MessageChain.from_text(text))

    async def forward_to_user(self, user_id: UserID) -> Message:
        return await self._client.send_private_message(user_id, self._content)

    async def forward_to_group(self, group_id: GroupID) -> Message:
        return await self._client.send_group_message(group_id, self._content)

    async def recall(self) -> bool:
        return await self._client.recall_message(self._id)

    def copy_content(self) -> MessageChain:
        return MessageChain(self._content.to_list())


# ---------------- 用户 / 群组 / Me（依赖 Message / MessageChain） ----------------
class User:
    _client: IMClient | None = None

    def __init__(
        self,
        uid: UserID,
        nickname: str | None = None,
        avatar_url: str | None = None,
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

    async def get_avatar_url(self) -> str | None:
        if self._avatar_url:
            return self._avatar_url
        user_info = await self._client.get_user_info(self._uid)
        self._avatar_url = user_info.get("avatar_url")
        return self._avatar_url

    # 私聊快捷
    async def send_text(self, text: str) -> Message:
        return await self._client.send_text_to_user(self._uid, text)

    async def send_message(self, content: MessageChain) -> Message:
        return await self._client.send_private_message(self._uid, content)

    # 好友管理
    async def add_friend(self, remark: str | None = None) -> bool:
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
        if not client:
            raise ValueError("没有选择协议")
        return await client.accept_friend_request(request_id)

    @staticmethod
    async def reject_friend_request(request_id: str) -> bool:
        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")
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
    _client: IMClient | None = None

    def __init__(
        self,
        gid: GroupID,
        name: str | None = None,
        description: str | None = None,
        avatar_url: str | None = None,
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
    def avatar_url(self) -> str | None:
        return self._avatar_url

    async def get_info(self) -> Dict[str, Any]:
        return await self._client.get_group_info(self._gid)

    # 群聊快捷
    async def send_text(self, text: str) -> Message:
        return await self._client.send_text_to_group(self._gid, text)

    async def send_message(self, content: MessageChain) -> Message:
        return await self._client.send_group_message(self._gid, content)

    async def recall_message(self, message_id: MsgId) -> bool:
        return await self._client.recall_message(message_id)

    # 群管理
    @staticmethod
    async def create_group(
        name: str, initial_members: List[UserID] | None = None
    ) -> Group:
        client = IMClient.get_current()
        if not client:
            raise ValueError("没有选择协议")
        return await client.create_group(name, initial_members)

    async def set_admin(self, user: User | UserID, is_admin: bool = True) -> bool:
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.set_group_admin(self._gid, user_id, is_admin)

    async def invite_member(self, user: User | UserID) -> bool:
        user_id = user.uid if isinstance(user, User) else user
        return await self._client.invite_to_group(self._gid, user_id)

    async def remove_member(
        self, user: User | UserID, reason: str | None = None
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

    async def transfer_ownership(self, new_owner: User | UserID) -> bool:
        new_owner_id = new_owner.uid if isinstance(new_owner, User) else new_owner
        return await self._client.transfer_group_ownership(self._gid, new_owner_id)

    async def get_members(self) -> List[User]:
        return await self._client.get_group_members(self._gid)

    async def leave(self) -> bool:
        return await self._client.leave_group(self._gid)

    # 快捷属性
    @property
    def member_count(self) -> int:
        return self.info.member_count

    @property
    def owner_id(self) -> UserID | None:
        return self.info.owner_id


class Me(User):
    def __new__(cls, *_, **__):
        raise TypeError("Me 不允许直接实例化，请使用 Me.from_user(user) 进行升级")

    def __init__(self, *_):
        pass

    @property
    def uid(self) -> UserID:
        return self._client.protocol.self_id

    @classmethod
    def from_user(cls, user: User) -> Me:
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
    def __init__(self) -> None:
        self._msg_id: MsgId | None = None
        self._sender_id: UserID | None = None
        self._content: MessageChain | None = None
        self._timestamp: dt.datetime | None = None
        self._msg_type: str = Message.NORMAL
        self._group_id: GroupID | None = None
        self._reference: MessageReference | None = None
        self._forward_info: ForwardInfo | None = None

    def id(self, msg_id: MsgId) -> MessageBuilder:
        self._msg_id = msg_id
        return self

    def sender(self, sender_id: UserID) -> MessageBuilder:
        self._sender_id = sender_id
        return self

    def content(self, content: MessageChain) -> MessageBuilder:
        self._content = content
        return self

    def text(self, text: str) -> MessageBuilder:
        self._content = MessageChain.from_text(text)
        return self

    def timestamp(self, ts: dt.datetime) -> MessageBuilder:
        self._timestamp = ts
        return self

    def now(self) -> MessageBuilder:
        self._timestamp = dt.datetime.now()
        return self

    def type(self, tp: str) -> MessageBuilder:
        self._msg_type = tp
        return self

    def group(self, gid: GroupID) -> MessageBuilder:
        self._group_id = gid
        return self

    def private(self) -> MessageBuilder:
        self._group_id = None
        return self

    def reply_to(
        self,
        msg_id: MsgId,
        sender_id: UserID,
        ts: dt.datetime,
        preview: str | None = None,
    ) -> MessageBuilder:
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
        forwarder: UserID,
    ) -> MessageBuilder:
        self._msg_type = Message.FORWARD
        self._forward_info = ForwardInfo(
            original_message_id=msg_id,
            original_sender_id=orig_sender,
            original_timestamp=orig_ts,
            forwarder_id=forwarder,
        )
        return self

    def build(self) -> Message:
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

        if self._msg_id is None:
            self._msg_id = f"temp_{uuid.uuid4().hex[:8]}"

        return Message(
            msg_id=self._msg_id,
            sender_id=self._sender_id,
            content=self._content,
            timestamp=self._timestamp,
            message_type=self._msg_type,
            group_id=self._group_id,
            reference=self._reference,
            forward_info=self._forward_info,
        )
