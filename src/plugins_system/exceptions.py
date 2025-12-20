"""
# 异常
包含插件系统中使用的所有自定义异常类
"""

from typing import Optional
from .utils.types import PluginName


class PluginError(Exception):
    """插件基础异常类
    
    Attributes:
        plugin_name: 相关的插件名称
    """
    
    def __init__(self, message: str, plugin_name: Optional[PluginName] = None):
        """初始化插件异常
        
        Args:
            message: 异常消息
            plugin_name: 相关的插件名称
        """
        self.plugin_name = plugin_name
        super().__init__(message)
        
    def add_note(self, note: str) -> None:
        """添加异常说明
        
        Args:
            note: 要添加的说明文本
        """
        if hasattr(super(), 'add_note'):
            super().add_note(note)


class PluginDependencyError(PluginError):
    """插件依赖异常
    
    当插件依赖解析失败时抛出
    """
    pass


class PluginVersionError(PluginError):
    """插件版本异常
    
    当插件版本不兼容时抛出
    """
    pass


class PluginValidationError(PluginError):
    """插件验证异常
    
    当插件配置或元数据验证失败时抛出
    """
    pass


class PluginNotFound(PluginError):
    """插件未发现
    
    当在模块中没有找到插件时抛出
    """
    pass


class PluginRuntimeError(PluginError):
    """插件运行时异常
    
    当插件在运行时发生错误时抛出
    """
    pass