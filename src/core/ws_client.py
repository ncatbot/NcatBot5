# '''
# 连接器，用于与服务提供者连接
# '''
# from logging import getLogger
# from ..plugins_system.abc.events import EventBus
# from ..plugins_system.core.plugins import Plugin
# from ..plugins_system import DefaultPluginManager

# from ..abc.apiabc import ApiBase
# from ..utils.constants import DefaultSetting

# from typing import List, Optional
# from ..connector import BaseWsClient

# logger = getLogger('WsClient')

# class WsClient(BaseWsClient):
#     def __init__(self,
#             uri: str,
#             token: Optional[str]=None,
#             ssl: bool=False,
#             debug: bool=False,
#             protocol: str = 'napcat'
#             ):
        
#         if protocol not in ApiBase._registry:
#             raise ValueError(f"未知通信协议: {protocol}")
#         self._api = ApiBase._registry[protocol]
        
#         self.plugin_manage=DefaultPluginManager(
#             plugin_dirs=DefaultSetting.plugin_dirs,
#             config_base_dir=DefaultSetting.config_dir,
#             event_bus=DefaultSetting.event_bus,
#             dev_mode=debug or DefaultSetting.debug
#         )
#         self.plugins: List[Plugin] = []
        
#         super().__init__(
#             uri=uri,
#             headers=f"Authorization: Bearer {token}" if token else None,
#             ssl=ssl,
#             logger=logger
#         )
        
#         self._debug = debug

#     async def on_close(self, data):
#         self.logger.info("连接关闭: %s", data)

#     async def on_error(self, data):
#         self.logger.info("通信错误: %s", data)

#     @property
#     def event_but(self) -> EventBus:
#         return self.plugin_manage.event_bus

#     @property
#     def debug(self) -> bool:
#         return self._debug

#     async def load_plugins(self):
#         self.plugins = await self.plugin_manage.load_plugins()
    
#     async def link_ws_server(self):
#         await self.run()
    
#     async def run(self):
#         await self.link_ws_server()
#         await self.load_plugins()
#         await super().run()