# from src import PluginBase
# from src.plugins_system.mixins.server import ServiceMixin, ServiceName, ServiceMeta, online_service
# from src.plugins_system.utils.types import PluginName, PluginVersion
# from logging import Logger

# class DemoSer(PluginBase, ServiceMixin):
#     name = "DemoSer_plugin"
#     version = "0.1.0"

#     async def on_load(self):
#         # self.register_service(ServiceName("demo_service"), self.bili_ck, event_mod=False)
#         self.logger.info("Service started")

#     @online_service("demo_service", event_mod=False)
#     async def bili_ck(self, meta: ServiceMeta):
#         print(type(meta))
#         return f"bili_ck called with demo data"

#     async def on_unload(self):
#         self.logger.info("Demo Service stopped")

# # __all__ = [
# #     'DemoSer'
# # ]
