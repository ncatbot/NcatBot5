from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Iterable, List, NewType, Optional

from .helper import MsgId as _MsgId
from .io import Resource

MsgId = _MsgId
UserID = NewType("UserID", str)
GroupID = NewType("GroupID", str)


class MessageType(Enum):
    """消息类型枚举"""

    Text = auto()
    Image = auto()
    File = auto()
    Voice = auto()
    Video = auto()
    Location = auto()
    Card = auto()
    System = auto()
    Face = auto()
    Reply = auto()


class MessageStatus(Enum):
    """消息状态枚举"""

    Sending = auto()
    Sent = auto()
    Delivered = auto()
    Read = auto()
    Failed = auto()
    Recalled = auto()


class Sex(str, Enum):
    """性别枚举"""

    Male = "male"
    Female = "female"
    Unknown = "unknown"


class Role(str, Enum):
    """群角色枚举"""

    Owner = "owner"
    Admin = "admin"
    Member = "member"
    None_ = "none"  # 避免与关键字冲突，加下划线


# ------------------- 参考 -------------------


@dataclass(slots=True)
class Sender:
    id: UserID
    nickname: str
    role: Role = Role.Member


@dataclass(slots=True)
class Message:
    id: MsgId
    sender: Sender
    content: Iterable  # 具体消息链
    timestamp: datetime = field(default_factory=datetime.now(timezone.utc))
    text: str = ""
    group_id: Optional[GroupID] = None
    type: MessageType = MessageType.Text
    status: MessageStatus = MessageStatus.Sent


@dataclass(slots=True)
class User:
    id: UserID
    nickname: str
    avatar: Optional[Resource] = None
    is_online: bool = False
    is_friend: bool = False
    remark: Optional[str] = None
    signature: Optional[str] = None
    gender: Sex = Sex.Unknown
    region: Optional[str] = None


@dataclass(slots=True)
class Group:
    id: GroupID
    name: str
    owner: User  # 完整对象
    admins: List[User] = field(default_factory=list)
    avatar: Optional[Resource] = None
    members: int = 0
    description: Optional[str] = None
    announcement: Optional[str] = None
    max_members: int = 500
    is_mute_all: bool = False
    is_mute: bool = False
    create_time: datetime = field(default_factory=datetime.now(timezone.utc))
