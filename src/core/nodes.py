from dataclasses import dataclass
from typing import Optional
from ..utils.typec import UserID, MsgId
import datetime as dt


# ========== 消息节点系统 ==========
class MessageNode:
    """消息节点父类"""
    def __str__(self) -> str:
        return ''



@dataclass
class TextNode(MessageNode):
    content: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: Optional[str] = None

    def __str__(self) -> str:
        return self.content


@dataclass
class ImageNode(MessageNode):
    uri: str
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail: Optional[str] = None
    alt_text: Optional[str] = None

    def __str__(self) -> str:
        return self.alt_text or "[图片]"


@dataclass
class FileNode(MessageNode):
    name: str
    uri: str
    size: int
    file_type: str

    def __str__(self) -> str:
        return f"[文件] {self.name}"


@dataclass
class VoiceNode(MessageNode):
    url: str
    duration: int

    def __str__(self) -> str:
        return "[语音]"


@dataclass
class VideoNode(MessageNode):
    url: str
    duration: int
    width: int
    height: int
    thumbnail: Optional[str] = None

    def __str__(self) -> str:
        return "[视频]"


@dataclass
class AtNode(MessageNode):
    user_id: Optional[UserID]
    user_name: Optional[str]
    is_all: bool

    def __str__(self) -> str:
        if self.is_all:
            return "@all"
        return f"@{self.user_name or self.user_id}"


@dataclass
class ReplyNode(MessageNode):
    message_id: MsgId
    sender_id: UserID
    preview: str

    def __str__(self) -> str:
        return f"[回复 {self.preview}]"


@dataclass
class ForwardNode(MessageNode):
    message_id: MsgId
    sender_id: UserID
    preview: str
    timestamp: dt.datetime

    def __str__(self) -> str:
        return f"[转发 {self.preview}]"