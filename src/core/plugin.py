from ..plugins_system import Plugin, PluginContext
from ..plugins_system.core.plugins import PluginState
from .client import IMClient


class PluginBase(Plugin):
    
    def __init__(self, context, config, debug = False):
        super().__init__(context, config, debug)
    
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
    def api(self):
        return self.client.api

    @property
    def protocol(self):
        return self.client.protocol