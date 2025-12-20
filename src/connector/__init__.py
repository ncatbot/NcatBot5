'''
连接器，用于与服务提供者连接
'''
from abc import ABC, abstractmethod
from typing import Any, NoReturn
from .wsclient import SyncWebSocketClient, AsyncWebSocketClient, MessageType
from logging import Logger, getLogger

class BaseWsClient(ABC):
    def __init__(self, uri: str, headers: str = None, ssl: bool = False, logger: Logger = getLogger('WsClient')):
        super().__init__()
        client = AsyncWebSocketClient(
            uri=uri,
            headers=headers,
            verify_ssl=ssl,
            logger=logger
        )
        self.logger = logger
        self.client = client
        self.listener = client.create_listener()

    async def run(self) -> NoReturn:
        client = self.client
        listener = self.listener
        try:
            await client.start()
            while True:
                try:
                    msg, msg_type = await client.get_message(listener)
                except Exception as exc:
                    self.logger.exception("接收消息时出错: %s", exc)
                    break

                match msg_type:
                    case MessageType.Text:
                        await self.on_message(msg)
                    case MessageType.Close:
                        await self.on_close(msg)
                    case MessageType.Error:
                        await self.on_error(msg)
                    case unhandled:
                        self.logger.warning("未处理的消息类型: %s", unhandled)
        finally:
            await client.stop()
    
    @abstractmethod
    async def on_message(self, data: Any) -> Any: ...
    @abstractmethod
    async def on_close(self, data: Any) -> Any: ...
    @abstractmethod
    async def on_error(self, data: Any) -> Any: ...