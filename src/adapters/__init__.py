"""
协议实现
"""
# 重新导出核心类型，方便用户导入
from ..core.IM import (
    User, Group, Me, Message,
    MessageContent, MessageNode,
    TextNode, ImageNode, FileNode, VoiceNode, VideoNode, AtNode, ReplyNode,
    UserInfo, GroupInfo, MessageInfo
)

from ..utils.typec import MessageType, MessageStatus, Sex, Role
from ..abc.api_base import APIBase

protocols = (
    'napcat',
)

__all__ = [
    # 工厂函数
    'create_client', 'register_protocol', 'get_available_protocols',
    
    # 核心类
    'IMClient', 'User', 'Group', 'Me', 'Message',
    
    # 枚举类型
    'MessageType', 'MessageStatus', 'Sex', 'Role',
    
    # 消息相关
    'MessageContent', 'MessageNode',
    'TextNode', 'ImageNode', 'FileNode', 'VoiceNode', 'VideoNode', 'AtNode', 'ReplyNode',
    
    # 信息类
    'UserInfo', 'GroupInfo', 'MessageInfo',
    
    # API 相关
    'APIBase',
]

import importlib
for p in protocols:
    importlib.import_module(f'.{p}', package=__package__)