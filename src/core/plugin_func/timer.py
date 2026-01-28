# from typing import Callable, Optional

# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from . import PluginMixin

# class CrontabMixin(PluginMixin):
#     """
#     定时任务混入类

#     为插件提供一个独立的任务调度器，插件卸载时自动关闭所有任务。
#     """

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # 每个 Mixin 实例维护自己的调度器
#         self._scheduler: Optional[AsyncIOScheduler] = None

#     async def on_mixin_load(self) -> None:
#         await super().on_mixin_load()
#         self._scheduler = AsyncIOScheduler()
#         self._scheduler.start()
#         self.plugin.logger.info("[CrontabMixin] 调度器已启动")

#     async def on_mixin_unload(self) -> None:
#         await super().on_mixin_unload()
#         if self._scheduler:
#             self._scheduler.shutdown(wait=False)
#             self.plugin.logger.info("[CrontabMixin] 调度器已关闭")

#     def schedule_task(
#         self,
#         func: Callable,
#         trigger: str = "interval",
#         **trigger_args
#     ) -> None:
#         """
#         添加定时任务

#         Example:
#             self.schedule_task(self.my_job, "interval", seconds=10)
#         """
#         if not self._scheduler:
#             raise RuntimeError("调度器未初始化")

#         # 包装一下，确保日志能关联到插件
#         def wrapped_func(*args, **kwargs):
#             self.plugin.logger.debug(f"执行定时任务: {func.__name__}")
#             return func(*args, **kwargs)

#         self._scheduler.add_job(wrapped_func, trigger, **trigger_args)
