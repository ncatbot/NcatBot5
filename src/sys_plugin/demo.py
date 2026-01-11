from src import PluginBase

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
        self.logger.info(self.__dict__)
        self.logger.info("hi")

        # await User("3123651157").send_text("DemoSer_plugin loaded successfully")

    async def on_reload(self):
        # raise ValueError()

        self.logger.info(self.__dict__)
        self.logger.info("reload")

    # @online_service("demo_service", event_mod=False)
    # async def bili_ck(self, meta: ServiceMeta):
    #     print(type(meta))
    #     return "bili_ck called with demo data"

    async def on_unload(self):
        self.logger.info("Demo Service stopped")


# __plugin__ = [
#     'DemoSer'
# ]

# __all__ = [
#     'DemoSer'
# ]
