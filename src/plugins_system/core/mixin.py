"""
混入类模块
"""

from abc import ABC
from logging import Logger
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from .plugins import Plugin, PluginContext

T = TypeVar("T", bound="Plugin")


class PluginMixin(ABC):
    """插件混入类基类

    通过多重继承方式使用：class MyPlugin(Plugin, ServerMixin)

    NOTE: 请直接使用插件类属性
    TODO: 解决类型注释
    """

    context: "PluginContext"
    logger: Logger

    def __init__(self: T) -> T:
        pass

    # @property
    # def plugin(self) -> "Plugin":  # 兼容性设置，推荐直接使用self
    #     """获取宿主插件实例

    #     Returns:
    #         宿主插件实例

    #     Raises:
    #         RuntimeError: 当混入类尚未附加到插件时
    #     """
    #     if not hasattr(self, "_plugin") or self._plugin is None:
    #         raise RuntimeError("混入类尚未附加到插件")
    #     return self._plugin

    # def _set_plugin(self, value):
    #     """设置宿主插件实例

    #     Args:
    #         value: 插件实例
    #     """
    #     self._plugin = value

    async def on_mixin_load(self: T) -> T:
        """混入类加载时的回调

        可选实现，在插件加载时自动调用
        """
        pass

    async def on_mixin_unload(self: T) -> T:
        """混入类卸载时的回调

        可选实现，在插件卸载时自动调用
        """
        pass
