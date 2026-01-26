from .__main__ import Bot
from .abc.api_base import APIBase
from .abc.builder import MessageBuilder
from .abc.nodes import MessageNode
from .abc.protocol_abc import APIBaseT, ProtocolABC
from .adapters import protocols  # 加载协议
from .core.client import IMClient
from .core.IM import (
    Group,
    GroupInfo,
    Me,
    Message,
    MessageChain,
    MessageInfo,
    User,
    UserInfo,
)
from .core.plugin import PluginBase
from .meta import __version__
from .plugins_system import Event, EventBus
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
    "Event",
    # 消息相关
    "MessageNode",
    "MessageChain",
    "get_msg_builder",
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
    "EventBus",
    # 奇怪的东西
    "get_protocol",
    "get_api",
    "__version__",
]
