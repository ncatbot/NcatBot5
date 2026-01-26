from src import PluginBase
from src.core.IM import Message
from src.plugins_system import Event

# from src.core.IM import User


class DemoSer(PluginBase):
    name = "DemoSer_plugin"
    version = "0.1.0"

    async def on_load(self):
        # self.register_service(ServiceName("demo_service"), self.bili_ck, event_mod=False)
        self.logger.info("Service started")
        if "loaded" in self.config:
            self.config["loaded"] += 1
        else:
            self.config["loaded"] = 1
        # self.logger.info(self.__dict__)
        self.logger.info("hi")

        # await User("3123651157").send_text("DemoSer_plugin loaded successfully")
        # self.register_handlers({
        #     're:.*': self.p
        # })

    async def on_reload(self):
        # raise ValueError()

        # self.logger.info(self.__dict__)
        self.logger.info("reload")

    def on_config_reloaded(self):
        # print("配置文件重载:")
        print(self.config)

    # @online_service("demo_service", event_mod=False)
    # async def bili_ck(self, meta: ServiceMeta):
    #     print(type(meta))
    #     return "bili_ck called with demo data"

    async def on_unload(self):
        self.logger.info("Demo Service stopped")

    def p(self, e: Event[Message]):
        if not isinstance(e.data, Message):
            return
        msg = e.data
        print(msg.raw["raw_message"])


# __plugin__ = [
#     'DemoSer'
# ]

# __all__ = [
#     'DemoSer'
# ]
