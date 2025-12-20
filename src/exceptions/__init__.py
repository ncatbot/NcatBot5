"""
# 异常
包含SDK使用的所有自定义异常类
"""

class SDKError(Exception):
    
    def __init__(self, message: str):
        """初始化插件异常
        
        Args:
            message: 异常消息
            plugin_name: 相关的插件名称
        """
        super().__init__(message)
        
    def add_note(self, note: str) -> None:
        """添加异常说明
        
        Args:
            note: 要添加的说明文本
        """
        if hasattr(super(), 'add_note'):
            super().add_note(note)
