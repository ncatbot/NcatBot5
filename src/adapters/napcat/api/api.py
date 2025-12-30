from ....connector import AsyncWebSocketClient
from .api_base import NCAPIBase
from .group import NCAPIGroup
from .message import NCAPIMessage
from .system import NCAPISystem
from .user import NCAPIUser


class NCAPI(NCAPIBase):
    """napcatAPI封装"""

    def __init__(self):
        super().__init__()
        # 创建子 API 实例
        self.user = NCAPIUser()
        self.group = NCAPIGroup()
        self.system = NCAPISystem()
        self.message = NCAPIMessage()

    def set_client(self, client: AsyncWebSocketClient):
        """设置 WebSocket 客户端并共享给所有子 API"""
        self.client = client
        self.user.client = client
        self.group.client = client
        self.system.client = client
        self.message.client = client
