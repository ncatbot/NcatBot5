# adapters/napcat/builder.py
"""
Napcat协议消息构建器
提供流畅的API来构建各种类型的消息节点和消息链
"""
from typing import Any, Dict, List, Optional, Union

from src.core.IM import Message, MessageChain

from .nodes import (
    XML,
    Anonymous,
    At,
    AtAll,
    Contact,
    Dice,
    Face,
    File,
    Forward,
    Image,
    Json,
    Location,
    Markdown,
    Music,
    Node,
    Poke,
    Record,
    Reply,
    Rps,
    Shake,
    Share,
    Text,
    Video,
)


class MessageBuilder:
    """Napcat协议消息构建器

    提供流畅的API来构建各种类型的消息节点和消息链
    支持链式调用和批量操作
    """

    def __init__(self):
        self._nodes: List[Union[str, Any]] = []
        self._current_chain: Optional[MessageChain] = None

    # ==================== 基础构建方法 ====================

    def text(self, content: str) -> "MessageBuilder":
        """添加文本节点

        Args:
            content: 文本内容

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Text(text=content))
        return self

    def face(
        self, face_id: Union[str, int], face_text: str = "[表情]"
    ) -> "MessageBuilder":
        """添加表情节点

        Args:
            face_id: 表情ID
            face_text: 表情描述文本

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Face(id=str(face_id), face_text=face_text))
        return self

    def at(
        self, user_id: Union[str, int], display_name: Optional[str] = None
    ) -> "MessageBuilder":
        """添加@用户节点

        Args:
            user_id: 用户ID
            display_name: 显示名称（可选）

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(At(qq=str(user_id)))
        if display_name:
            self._nodes.append(Text(text=f"({display_name})"))
        return self

    def at_all(self) -> "MessageBuilder":
        """添加@全体成员节点

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(AtAll())
        return self

    # ==================== 媒体消息方法 ====================

    def image(
        self,
        file: Optional[str] = None,
        url: Optional[str] = None,
        file_id: Optional[str] = None,
        summary: str = "[图片]",
        sub_type: int = 0,
        image_type: Optional[str] = None,
    ) -> "MessageBuilder":
        """添加图片节点

        Args:
            file: 本地文件路径
            url: 网络图片URL
            file_id: 文件ID
            summary: 图片摘要
            sub_type: 子类型 (0: 一般图片; 1: 动画表情)
            image_type: 图片类型 ("flash" 表示闪照)

        Returns:
            MessageBuilder实例，支持链式调用
        """
        image_node = Image(
            file=file,
            url=url,
            file_id=file_id,
            summary=summary,
            sub_type=sub_type,
            type=image_type,
        )
        self._nodes.append(image_node)
        return self

    def file(
        self,
        file: Optional[str] = None,
        url: Optional[str] = None,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_type: Optional[str] = None,
    ) -> "MessageBuilder":
        """添加文件节点

        Args:
            file: 本地文件路径
            url: 网络文件URL
            file_id: 文件ID
            file_name: 文件名
            file_size: 文件大小
            file_type: 文件类型

        Returns:
            MessageBuilder实例，支持链式调用
        """
        file_node = File(
            file=file,
            url=url,
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
        )
        self._nodes.append(file_node)
        return self

    def record(
        self,
        file: Optional[str] = None,
        url: Optional[str] = None,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> "MessageBuilder":
        """添加语音节点

        Args:
            file: 本地文件路径
            url: 网络语音URL
            file_id: 文件ID
            file_name: 文件名
            file_size: 文件大小

        Returns:
            MessageBuilder实例，支持链式调用
        """
        record_node = Record(
            file=file,
            url=url,
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
        )
        self._nodes.append(record_node)
        return self

    def video(
        self,
        file: Optional[str] = None,
        url: Optional[str] = None,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> "MessageBuilder":
        """添加视频节点

        Args:
            file: 本地文件路径
            url: 网络视频URL
            file_id: 文件ID
            file_name: 文件名
            file_size: 文件大小

        Returns:
            MessageBuilder实例，支持链式调用
        """
        video_node = Video(
            file=file,
            url=url,
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
        )
        self._nodes.append(video_node)
        return self

    # ==================== 互动消息方法 ====================

    def poke(
        self, user_id: Union[str, int], poke_type: str = "poke"
    ) -> "MessageBuilder":
        """添加戳一戳节点

        Args:
            user_id: 目标用户ID
            poke_type: 戳一戳类型

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Poke(id=str(user_id), type=poke_type))
        return self

    def shake(self) -> "MessageBuilder":
        """添加抖动节点

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Shake())
        return self

    def rps(self) -> "MessageBuilder":
        """添加猜拳节点

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Rps())
        return self

    def dice(self) -> "MessageBuilder":
        """添加骰子节点

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Dice())
        return self

    # ==================== 分享消息方法 ====================

    def share(
        self,
        url: str,
        title: str = "分享",
        content: Optional[str] = None,
        image: Optional[str] = None,
    ) -> "MessageBuilder":
        """添加分享节点

        Args:
            url: 分享链接
            title: 分享标题
            content: 分享内容
            image: 分享图片

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Share(url=url, title=title, content=content, image=image))
        return self

    def contact(
        self, contact_type: str, contact_id: Union[str, int]
    ) -> "MessageBuilder":
        """添加联系人分享节点

        Args:
            contact_type: 联系人类型 ("qq" 或 "group")
            contact_id: 联系人ID

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Contact(type=contact_type, id=str(contact_id)))
        return self

    def location(
        self,
        latitude: float,
        longitude: float,
        title: str = "位置分享",
        content: Optional[str] = None,
    ) -> "MessageBuilder":
        """添加位置节点

        Args:
            latitude: 纬度
            longitude: 经度
            title: 位置标题
            content: 位置描述

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(
            Location(lat=latitude, lon=longitude, title=title, content=content)
        )
        return self

    def music(
        self,
        music_type: str,
        music_id: Optional[str] = None,
        url: Optional[str] = None,
        audio: Optional[str] = None,
        title: Optional[str] = None,
        content: Optional[str] = None,
        image: Optional[str] = None,
    ) -> "MessageBuilder":
        """添加音乐节点

        Args:
            music_type: 音乐类型 ("qq", "163", "custom")
            music_id: 音乐ID
            url: 音乐链接
            audio: 音频链接
            title: 音乐标题
            content: 音乐描述
            image: 音乐封面

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(
            Music(
                type=music_type,
                id=music_id,
                url=url,
                audio=audio,
                title=title,
                content=content,
                image=image,
            )
        )
        return self

    # ==================== 回复和转发方法 ====================

    def reply(
        self, message_id: Union[str, int], text: Optional[str] = None
    ) -> "MessageBuilder":
        """添加回复节点

        Args:
            message_id: 要回复的消息ID
            text: 回复文本（可选）

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Reply(id=str(message_id)))
        if text:
            self._nodes.append(Text(text=text))
        return self

    def forward(self, forward_id: str, message_type: str = "group") -> "MessageBuilder":
        """添加转发节点

        Args:
            forward_id: 转发消息ID
            message_type: 消息类型 ("group" 或 "friend")

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Forward(id=forward_id, message_type=message_type))
        return self

    def node(
        self, user_id: Union[str, int], nickname: str, content: List[Any]
    ) -> "MessageBuilder":
        """添加消息节点（用于转发消息）

        Args:
            user_id: 用户ID
            nickname: 用户昵称
            content: 消息内容列表

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(
            Node(user_id=str(user_id), nickname=nickname, content=content)
        )
        return self

    # ==================== 富文本方法 ====================

    def xml(self, data: str) -> "MessageBuilder":
        """添加XML节点

        Args:
            data: XML数据

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(XML(data=data))
        return self

    def json(self, data: str) -> "MessageBuilder":
        """添加JSON节点

        Args:
            data: JSON数据

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Json(data=data))
        return self

    def markdown(self, content: str) -> "MessageBuilder":
        """添加Markdown节点

        Args:
            content: Markdown内容

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Markdown(content=content))
        return self

    # ==================== 特殊消息方法 ====================

    def anonymous(self) -> "MessageBuilder":
        """添加匿名节点

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.append(Anonymous())
        return self

    # ==================== 批量操作方法 ====================

    def add_texts(self, *texts: str) -> "MessageBuilder":
        """批量添加文本节点

        Args:
            *texts: 多个文本内容

        Returns:
            MessageBuilder实例，支持链式调用
        """
        for text in texts:
            self.text(text)
        return self

    def add_images(self, *image_urls: str) -> "MessageBuilder":
        """批量添加图片节点

        Args:
            *image_urls: 多个图片URL

        Returns:
            MessageBuilder实例，支持链式调用
        """
        for url in image_urls:
            self.image(url=url)
        return self

    def add_ats(self, *user_ids: Union[str, int]) -> "MessageBuilder":
        """批量添加@用户节点

        Args:
            *user_ids: 多个用户ID

        Returns:
            MessageBuilder实例，支持链式调用
        """
        for user_id in user_ids:
            self.at(user_id)
        return self

    # ==================== 构建和转换方法 ====================

    def build_chain(self) -> MessageChain:
        """构建消息链

        Returns:
            MessageChain实例
        """
        self._current_chain = MessageChain(nodes=self._nodes.copy())
        return self._current_chain

    def build_message(
        self,
        sender_id: Union[str, int],
        group_id: Optional[Union[str, int]] = None,
        message_type: str = "normal",
    ) -> Message:
        """构建完整消息

        Args:
            sender_id: 发送者ID
            group_id: 群组ID（可选）
            message_type: 消息类型

        Returns:
            Message实例
        """
        chain = self.build_chain()
        return Message.create(
            content=chain,
            sender_id=str(sender_id),
            group_id=str(group_id) if group_id else None,
            message_type=message_type,
        )

    def to_segments(self) -> List[Dict[str, Any]]:
        """转换为Napcat消息段格式

        Returns:
            Napcat协议消息段列表
        """
        segments = []
        for node in self._nodes:
            if hasattr(node, "to_dict"):
                segments.append(node.to_dict())
            else:
                segments.append({"type": "text", "data": {"text": str(node)}})
        return segments

    def clear(self) -> "MessageBuilder":
        """清空当前构建的消息

        Returns:
            MessageBuilder实例，支持链式调用
        """
        self._nodes.clear()
        self._current_chain = None
        return self

    def copy(self) -> "MessageBuilder":
        """创建当前构建器的副本

        Returns:
            新的MessageBuilder实例
        """
        new_builder = MessageBuilder()
        new_builder._nodes = self._nodes.copy()
        return new_builder

    # ==================== 快捷方法 ====================

    def __str__(self) -> str:
        """字符串表示"""
        if self._current_chain:
            return str(self._current_chain)
        return "".join(str(node) for node in self._nodes)

    def __len__(self) -> int:
        """节点数量"""
        return len(self._nodes)

    def __bool__(self) -> bool:
        """是否有节点"""
        return bool(self._nodes)

    # ==================== 上下文管理器支持 ====================

    def __enter__(self) -> "MessageBuilder":
        """进入上下文"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，自动清理"""
        self.clear()


# ==================== 快捷构建函数 ====================


def build_text_message(text: str) -> MessageChain:
    """快速构建文本消息

    Args:
        text: 文本内容

    Returns:
        MessageChain实例
    """
    return MessageBuilder().text(text).build_chain()


def build_image_message(image_url: str, text: Optional[str] = None) -> MessageChain:
    """快速构建图片消息

    Args:
        image_url: 图片URL
        text: 附加文本（可选）

    Returns:
        MessageChain实例
    """
    builder = MessageBuilder()
    if text:
        builder.text(text)
    return builder.image(url=image_url).build_chain()


def build_at_message(
    user_id: Union[str, int], text: Optional[str] = None
) -> MessageChain:
    """快速构建@消息

    Args:
        user_id: 用户ID
        text: 附加文本（可选）

    Returns:
        MessageChain实例
    """
    builder = MessageBuilder().at(user_id)
    if text:
        builder.text(text)
    return builder.build_chain()


def build_forward_message(messages: List[Dict[str, Any]]) -> MessageChain:
    """快速构建转发消息

    Args:
        messages: 消息列表，每个消息包含user_id, nickname, content

    Returns:
        MessageChain实例
    """
    builder = MessageBuilder()
    for msg in messages:
        builder.node(
            user_id=msg["user_id"], nickname=msg["nickname"], content=msg["content"]
        )
    return builder.build_chain()
