from abc import abstractmethod

from ..plugins_system import Plugin
from .client import IMClient


class PluginBase(Plugin):
    def __init__(self, context, config, debug=False):
        super().__init__(context, config, debug)
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
    def api(self):
        return self.client.api

    @property
    def protocol(self):
        return self.client.protocol
