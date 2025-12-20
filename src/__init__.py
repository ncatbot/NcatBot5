from .core.IM import *
from .core.client import IMClient

from .utils.typec import MessageType, MessageStatus, Sex, Role
from .abc.api_base import APIBase
from .__main__ import Bot

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
    
    'Bot', 'IMClient',
]

# 加载协议
from .adapters import protocols