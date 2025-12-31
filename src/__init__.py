from .__main__ import Bot
from .abc.api_base import APIBase
from .abc.builder import MessageBuilder
from .abc.nodes import MessageNode
from .abc.protocol_abc import APIBaseT, ProtocolABC
from .adapters import protocols  # 加载协议
from .core.client import IMClient
from .core.IM import Group, Me, Message, User
from .core.plugin import PluginBase
from .utils.logger import setup_logging

setup_logging()


def get_protocol() -> ProtocolABC:
    return IMClient.get_current().protocol


def get_msg_builder() -> MessageBuilder:
    return IMClient.get_current().protocol.msg_builder


def get_api() -> APIBaseT:
    return IMClient.get_current().protocol.api


__all__ = [
    # 核心类
    "IMClient",
    "User",
    "Group",
    "Me",
    "Message",
    # 消息相关
    "MessageContent",
    "MessageNode",
    # 信息类
    "UserInfo",
    "GroupInfo",
    "MessageInfo",
    # 其他·
    "Bot",
    "IMClient",
    "APIBase",
    "protocols",
    "PluginBase",
    # 奇怪的东西
    "get_protocol",
    "get_msg_builder",
]
