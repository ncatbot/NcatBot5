"""
协议实现
"""
import importlib

from ..abc.api_base import APIBase
from ..abc.builder import MessageBuilder
from ..abc.nodes import MessageNode
from ..core.client import IMClient

# 重新导出核心类型，方便协议导入
from ..core.IM import Group, GroupInfo, Me, Message, MessageInfo, User, UserInfo

protocols = ("napcat",)

for p in protocols:
    importlib.import_module(f".{p}", package=__package__)


__all__ = [
    # 核心类
    "IMClient",
    "User",
    "Group",
    "Me",
    "Message",
    # 消息相关
    "MessageNode",
    "MessageBuilder",
    # 信息类
    "UserInfo",
    "GroupInfo",
    "MessageInfo",
    # API 相关
    "APIBase",
]
