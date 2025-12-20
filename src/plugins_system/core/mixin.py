"""
混入类模块
"""

from abc import ABC
from logging import Logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .plugins import Plugin, PluginContext


class PluginMixin(ABC):
    """插件混入类基类

    通过多重继承方式使用：class MyPlugin(Plugin, ServerMixin)

    Attributes:
        _plugin: 宿主插件实例（自动设置）
    """

    context: "PluginContext"
    logger: Logger

    def __init__(self, *args, **kwargs):
        """初始化混入类

        注意：混入类的__init__应该调用super()来确保所有基类正确初始化
        """
        super().__init__(*args, **kwargs)
        # _plugin 会在 Plugin 基类中设置

        # 魔↗术↘技↘巧↗
        if TYPE_CHECKING:
            assert issubclass(self, Plugin)

    @property
    def plugin(self) -> "Plugin":  # 兼容性设置，推荐直接使用self
        """获取宿主插件实例

        Returns:
            宿主插件实例

        Raises:
            RuntimeError: 当混入类尚未附加到插件时
        """
        if not hasattr(self, "_plugin") or self._plugin is None:
            raise RuntimeError("混入类尚未附加到插件")
        return self._plugin

    # @property
    # def context(self) -> "PluginContext":
    #     """获取宿主插件上下文

    #     Returns:
    #         插件上下文实例
    #     """
    #     return self.plugin.context

    # @context.setter
    # def context(self, value: "PluginContext") -> None:
    #     """获取宿主插件上下文

    #     Returns:
    #         插件上下文实例
    #     """
    #     self.plugin.context = value

    # @property
    # def logger(self):
    #     """获取宿主插件上下文

    #     Returns:
    #         插件上下文实例
    #     """
    #     return self.plugin.logger

    def _set_plugin(self, value):
        """设置宿主插件实例

        Args:
            value: 插件实例
        """
        self._plugin = value

    async def on_mixin_load(self) -> None:
        """混入类加载时的回调

        可选实现，在插件加载时自动调用
        """
        pass

    async def on_mixin_unload(self) -> None:
        """混入类卸载时的回调

        可选实现，在插件卸载时自动调用
        """
        pass
