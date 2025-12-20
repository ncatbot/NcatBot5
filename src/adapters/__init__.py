"""
协议实现
"""
from ..abc.api_base import APIBase

# 重新导出核心类型，方便协议导入
from ..core.IM import (
    Group,
    GroupInfo,
    Me,
    Message,
    MessageContent,
    MessageInfo,
    MessageNode,
    User,
    UserInfo,
)
from ..core.nodes import (
    AtNode,
    FileNode,
    ImageNode,
    ReplyNode,
    TextNode,
    VideoNode,
    VoiceNode,
)
from ..utils.typec import MessageStatus, MessageType, Role, Sex

protocols = ("napcat",)

import importlib  # noqa: E402

for p in protocols:
    importlib.import_module(f".{p}", package=__package__)


__all__ = [
    # 工厂函数
    "create_client",
    "register_protocol",
    "get_available_protocols",
    # 核心类
    "IMClient",
    "User",
    "Group",
    "Me",
    "Message",
    # 枚举类型
    "MessageType",
    "MessageStatus",
    "Sex",
    "Role",
    # 消息相关
    "MessageContent",
    "MessageNode",
    "TextNode",
    "ImageNode",
    "FileNode",
    "VoiceNode",
    "VideoNode",
    "AtNode",
    "ReplyNode",
    # 信息类
    "UserInfo",
    "GroupInfo",
    "MessageInfo",
    # API 相关
    "APIBase",
]
