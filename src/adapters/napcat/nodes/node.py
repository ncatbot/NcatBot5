from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Literal, Optional

from .node_base import BaseNode, NodeT

if TYPE_CHECKING:
    pass


# ==================== 基础消息节点 ====================


@dataclass
class Text(BaseNode):
    """文本消息节点"""

    text: str
    _node_type: str = "text"

    def get_summary(self) -> str:
        return self.text


@dataclass
class Face(BaseNode):
    """表情消息节点"""

    id: str
    face_text: str = "[表情]"
    _node_type: str = "face"

    def __post_init__(self):
        self.id = str(self.id)

    def get_summary(self) -> str:
        return self.face_text

    def __str__(self):
        return self.face_text


# ==================== 可下载消息节点 ====================


@dataclass
class DownloadableNode(BaseNode):
    """可下载消息节点基类"""

    file: Optional[str] = field(default=None)
    url: Optional[str] = field(default=None)
    file_id: Optional[str] = field(default=None)
    file_size: Optional[int] = field(default=None)
    file_name: Optional[str] = field(default=None)
    file_type: Optional[str] = field(default=None)
    base64: Optional[str] = field(default=None, repr=False)
    _node_type: str = ""
    _repr_exclude: tuple = field(default=("base64",), repr=False)


@dataclass
class Image(DownloadableNode):
    """图片消息节点"""

    summary: str = "[图片]"
    sub_type: int = 0  # 0: 一般图片; 1: 动画表情
    type: Optional[Literal["flash"]] = None
    _node_type: str = "image"

    def is_flash_image(self) -> bool:
        return getattr(self, "type", None) == "flash"

    def is_animated_image(self) -> bool:
        return self.sub_type == 1

    def get_summary(self) -> str:
        return self.summary


@dataclass
class File(DownloadableNode):
    """文件消息节点"""

    _node_type: str = "file"

    def get_summary(self) -> str:
        return f"[文件]{self.file_name or ''}"


@dataclass
class Record(DownloadableNode):
    """语音消息节点"""

    _node_type: str = "record"

    def get_summary(self) -> str:
        return "[语音]"


@dataclass
class Video(DownloadableNode):
    """视频消息节点"""

    _node_type: str = "video"

    def get_summary(self) -> str:
        return "[视频]"


# ==================== 交互消息节点 ====================


@dataclass
class At(BaseNode):
    """@消息节点"""

    qq: str
    _node_type: str = "at"

    def __post_init__(self):
        self.qq = str(self.qq)


@dataclass
class AtAll(At):
    """@全体成员消息节点"""

    qq: str = field(default="all")

    def __str__(self) -> str:
        return "AtAll()"


@dataclass
class Rps(BaseNode):
    """猜拳消息节点"""

    _node_type: str = "rps"


@dataclass
class Dice(BaseNode):
    """骰子消息节点"""

    _node_type: str = "dice"


@dataclass
class Shake(BaseNode):
    """抖动消息节点"""

    _node_type: str = "shake"


@dataclass
class Poke(BaseNode):
    """戳一戳消息节点"""

    id: str
    type: Optional[Literal["poke"]] = None
    _node_type: str = "poke"


@dataclass
class Anonymous(BaseNode):
    """匿名消息节点"""

    _node_type: str = "anonymous"


# ==================== 分享类消息节点 ====================


@dataclass
class Share(BaseNode):
    """分享消息节点"""

    url: str
    title: str = "分享"
    content: Optional[str] = None
    image: Optional[str] = None
    _node_type: str = "share"


@dataclass
class Contact(BaseNode):
    """联系人分享消息节点"""

    type: Literal["qq", "group"]
    id: str
    _node_type: str = "contact"


@dataclass
class Location(BaseNode):
    """位置消息节点"""

    lat: float
    lon: float
    title: str = "位置分享"
    content: Optional[str] = None
    _node_type: str = "location"


@dataclass
class Music(BaseNode):
    """音乐消息节点"""

    type: Literal["qq", "163", "custom"]
    id: Optional[str] = None
    url: Optional[str] = None
    audio: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    _node_type: str = "music"

    def __post_init__(self):
        if self.id is not None:
            self.id = str(self.id)


# ==================== 回复与转发消息节点 ====================


@dataclass
class Reply(BaseNode):
    """回复消息节点"""

    id: str
    _node_type: str = "reply"

    def __post_init__(self):
        self.id = str(self.id)


@dataclass
class Node(BaseNode):
    """消息节点（用于转发消息）"""

    user_id: str = "123456"
    nickname: str = "QQ用户"
    content: Optional[List["NodeT"]] = None
    _node_type: str = "node"

    def __post_init__(self):
        self.user_id = str(self.user_id)

    def get_summary(self) -> str:
        if self.content:
            content_summary = "".join(
                msg.get_summary() if hasattr(msg, "get_summary") else str(msg)
                for msg in self.content
            )
            return f"{self.nickname}: {content_summary}"
        return f"{self.nickname}: [空消息]"


@dataclass
class Forward(BaseNode):
    """转发消息节点"""

    id: Optional[str] = None
    message_type: Optional[Literal["group", "friend"]] = None
    content: Optional[List[Node]] = None
    _node_type: str = "forward"

    def __post_init__(self):
        if self.id is not None:
            self.id = str(self.id)

    def get_summary(self) -> str:
        return "[聊天记录]"


# ==================== 富文本消息节点 ====================


@dataclass
class XML(BaseNode):
    """XML消息节点"""

    data: str
    _node_type: str = "xml"


@dataclass
class Json(BaseNode):
    """JSON消息节点"""

    data: str  # json字符串
    _node_type: str = "json"


@dataclass
class Markdown(BaseNode):
    """Markdown消息节点"""

    content: str
    _node_type: str = "markdown"
