from typing import Any, Dict, List, Literal, Optional

from src.utils.dto_tool import dataclass_dto


@dataclass_dto(frozen=False)
class BaseDto:
    def to_api_dict(self) -> Dict[str, Any]:
        """转换为 API 提交格式"""
        return self.to_dict(exclude_none=True)


# ==================== 基础消息DTO ====================


@dataclass_dto
class FaceDTO(BaseDto):
    """表情消息DTO"""

    id: str
    face_text: str = "[表情]"


# ==================== 可下载消息DTO ====================


@dataclass_dto
class DownloadableDTO(BaseDto):
    """可下载消息DTO基类"""

    file: str
    url: Optional[str] = None
    file_id: Optional[str] = None
    file_size: Optional[int] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    base64: Optional[str] = None


@dataclass_dto
class ImageDTO(DownloadableDTO):
    """图片消息DTO"""

    summary: str = "[图片]"
    sub_type: int = 0
    type: Optional[Literal["flash"]] = None


@dataclass_dto
class FileDTO(DownloadableDTO):
    """文件消息DTO"""

    pass


@dataclass_dto
class RecordDTO(DownloadableDTO):
    """语音消息DTO"""

    pass


@dataclass_dto
class VideoDTO(DownloadableDTO):
    """视频消息DTO"""

    pass


# ==================== 交互消息DTO ====================


@dataclass_dto
class AtDTO(BaseDto):
    """@消息DTO"""

    qq: str


@dataclass_dto
class AtAllDTO(AtDTO):
    """@全体成员消息DTO"""

    qq: str = "all"


@dataclass_dto
class RpsDTO(BaseDto):
    """猜拳消息DTO"""

    pass


@dataclass_dto
class DiceDTO(BaseDto):
    """骰子消息DTO"""

    pass


@dataclass_dto
class ShakeDTO(BaseDto):
    """抖动消息DTO"""

    pass


@dataclass_dto
class PokeDTO(BaseDto):
    """戳一戳消息DTO"""

    id: str
    type: int = None


@dataclass_dto
class AnonymousDTO(BaseDto):
    """匿名消息DTO"""

    pass


# ==================== 分享类消息DTO ====================


@dataclass_dto
class ShareDTO(BaseDto):
    """分享消息DTO"""

    url: str
    title: str = "分享"
    content: Optional[str] = None
    image: Optional[str] = None


@dataclass_dto
class ContactDTO(BaseDto):
    """联系人分享消息DTO"""

    type: Literal["qq", "group"]
    id: str


@dataclass_dto
class LocationDTO(BaseDto):
    """位置消息DTO"""

    lat: float
    lon: float
    title: str = "位置分享"
    content: Optional[str] = None


@dataclass_dto
class MusicDTO(BaseDto):
    """音乐消息DTO"""

    type: Literal["qq", "163", "custom"]
    id: Optional[str] = None
    url: Optional[str] = None
    audio: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None


# ==================== 回复与转发消息DTO ====================


@dataclass_dto
class ReplyDTO(BaseDto):
    """回复消息DTO"""

    id: str


@dataclass_dto
class NodeDTO(BaseDto):
    """消息节点DTO（用于转发消息）"""

    user_id: str = "123456"
    nickname: str = "QQ用户"
    content: Optional[List["BaseDto"]] = None


@dataclass_dto
class ForwardDTO(BaseDto):
    """转发消息DTO"""

    id: Optional[str] = None
    message_type: Optional[Literal["group", "friend"]] = None
    content: Optional[List[NodeDTO]] = None


# ==================== 富文本消息DTO ====================


@dataclass_dto
class XMLDTO(BaseDto):
    """XML消息DTO"""

    data: str


@dataclass_dto
class JsonDTO(BaseDto):
    """JSON消息DTO"""

    data: str


@dataclass_dto
class MarkdownDTO(BaseDto):
    """Markdown消息DTO"""

    content: str
