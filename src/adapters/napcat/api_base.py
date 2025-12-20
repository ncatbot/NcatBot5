import asyncio
import json
import logging
import uuid
from typing import Any, Dict

from src.abc.api_base import APIBase, ApiRequest
from src.connector import AsyncWebSocketClient, MessageType

log = logging.getLogger("NCAPI")


class NCAPIBase(APIBase):
    """napcatAPI基类"""

    protocol_name = "napcat"
    client: AsyncWebSocketClient

    def __init__(self):
        super().__init__()

    # 将 ApiRequest 转换为napcat标准字典格式
    def to_dict(self, request: ApiRequest) -> Dict[str, Any]:
        result = {"action": request.activity, "params": request.data}
        if request.headers:
            result["headers"] = request.headers
        return result

    async def invoke(self, request: ApiRequest) -> Any:
        """调用 NapCat API 并返回响应数据"""
        if not getattr(self, "client", None):
            raise RuntimeError("WebSocket 客户端未初始化，请先调用 login")

        if not self.client.running:
            await self.client.start()
            await asyncio.sleep(0.1)
            while self.client.connection.is_connected():
                await asyncio.sleep(0.1)

        listener_id = await self.client.create_listener()
        echo = str(uuid.uuid4())
        request_data = self.to_dict(request) | {"echo": echo}
        await self.client.send(request_data)

        while True:
            message, t = await self.client.get_message(listener_id, timeout=10)
            match t:
                case MessageType.Text:
                    try:
                        resp: dict = json.loads(message)
                    except json.JSONDecodeError as e:
                        log.error("解析错误: %s", e)
                        return None
                    if resp.get("echo") == echo:
                        return resp  # 正常路径直接返回
                case _:
                    log.error("未知类型返回: %s", request.activity)
                    return None
