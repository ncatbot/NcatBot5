from src.plugins_system import PluginMixin  # noqa: F401

from .command import CommandArgs, command
from .listener import listener

__all__ = [
    # 监听器装饰器
    "listener",
    # 命令装饰器
    "command",
    "CommandArgs",
]
