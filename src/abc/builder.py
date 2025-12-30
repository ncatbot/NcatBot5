import datetime as dt
from typing import Optional, Protocol, Self

from src.core.IM import (
    ForwardInfo,
    Message,
    MessageChain,
    MessageNodeT,
    MessageReference,
)
from src.utils.helper import MsgId
from src.utils.typec import GroupID, UserID

# ---------------- Builder协议 ---------------


class MessageBuilder(Protocol):
    """消息构建器"""

    def __init__(self) -> None:
        self._msg_id: Optional[MsgId] = None
        self._sender_id: Optional[UserID] = None
        self._content: Optional[MessageChain] = None
        self._timestamp: Optional[dt.datetime] = None
        self._msg_type: str = Message.NORMAL
        self._group_id: Optional[GroupID] = None
        self._reference: Optional[MessageReference] = None
        self._forward_info: Optional[ForwardInfo] = None

    def id(self, msg_id: MsgId) -> "Self":
        self._msg_id = msg_id
        return self

    def sender(self, sender_id: UserID) -> "Self":
        self._sender_id = sender_id
        return self

    def content(self, content: MessageChain) -> "Self":
        self._content = content
        return self

    def timestamp(self, ts: dt.datetime) -> "Self":
        self._timestamp = ts
        return self

    def now(self) -> "Self":
        self._timestamp = dt.datetime.now()
        return self

    def type(self, tp: str) -> "Self":
        self._msg_type = tp
        return self

    def group(self, gid: GroupID) -> "Self":
        self._group_id = gid
        return self

    def private(self) -> "Self":
        self._group_id = None
        return self

    def text(self, text: str) -> "Self":
        """添加文本节点"""
        pass

    def node(self, node: MessageNodeT) -> "Self":
        """添加任意消息节点"""
        pass

    def build(self) -> MessageChain:
        """构建消息链"""
        pass
