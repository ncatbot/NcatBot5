from abc import abstractmethod

from ..abc.protocol_abc import APIBaseT, ProtocolABC
from ..plugins_system import Plugin
from .client import IMClient
from .plugin_mixin.config import ReloadableConfigerMixin


class PluginBase(
    Plugin,
    ReloadableConfigerMixin,
):
    """Base"""

    def __init__(self, context, debug=False):
        super().__init__(context, debug)
        self._client = None

    @abstractmethod
    async def on_load(self) -> None:
        """插件加载时的回调 - 子类必须实现"""
        pass

    async def on_unload(self) -> None:
        """插件卸载时的回调 - 子类可以覆盖"""
        self.logger.info(f"插件 {self.name} 正在关闭...")

    @property
    def client(self) -> IMClient:
        if isinstance(self._client, IMClient):
            return self._client

        current = IMClient.get_current()
        if current is None:
            raise RuntimeError("IM 服务未启动")
        self._client = current
        return current

    @property
    def api(self) -> APIBaseT:
        return self.client.api

    @property
    def protocol(self) -> ProtocolABC:
        return self.client.protocol

    def on_config_reloaded(self):
        """配置文件重载时触发"""
        pass
