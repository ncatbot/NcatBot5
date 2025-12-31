from src import PluginBase, User
from src.plugins_system.mixins.server import ServiceMeta, ServiceMixin, online_service


class DemoSer(PluginBase, ServiceMixin):
    name = "DemoSer_plugin"
    version = "0.1.0"

    async def on_load(self):
        # self.register_service(ServiceName("demo_service"), self.bili_ck, event_mod=False)
        self.logger.info("Service started")
        await User("3123651157").send_text("DemoSer_plugin loaded")

    @online_service("demo_service", event_mod=False)
    async def bili_ck(self, meta: ServiceMeta):
        print(type(meta))
        return "bili_ck called with demo data"

    async def on_unload(self):
        self.logger.info("Demo Service stopped")


# __all__ = [
#     'DemoSer'
# ]
