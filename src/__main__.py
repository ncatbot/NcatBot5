import asyncio
import logging
from pathlib import Path
from typing import Optional, Self

from .abc.protocol_abc import ProtocolABC, ProtocolMeta
from .connector import AsyncWebSocketClient
from .core.client import IMClient
from .plugins_system import Event, EventBus, PluginApplication
from .utils.constants import DefaultSetting, ProtocolName

log = logging.getLogger("Bot")
One_Mod = True


class Router:
    def __init__(self):
        pass


class Bot:
    """机器人框架统一入口"""

    # --- 类级状态 ---
    running: bool = False  # 是否有实例在运行

    # --- 实例级属性 ---
    plugin_sys: PluginApplication
    _ws: AsyncWebSocketClient
    _protocol: ProtocolABC
    _im_client: IMClient
    _stop_event: asyncio.Event

    def __init__(
        self,
        url: str,
        token: Optional[str] = None,
        plugin_dir: Optional[Path | str] = None,
        protocol: ProtocolName = "napcat",
        config_dir: Path | str = "config",
        data_dir: Path | str = "data",
    ):
        # 插件系统
        plugin_dirs = [Path(__file__).resolve().parent / "sys_plugin"]
        if plugin_dir:
            plugin_dirs.append(plugin_dir)

        self.plugin_sys = PluginApplication(
            plugin_dirs=plugin_dirs,
            config_dir=config_dir,
            data_dir=data_dir,
            dev_mode=DefaultSetting.debug,  # NOTE 热重载
            event_bus=DefaultSetting.event_bus,
        )
        self.event_bus: EventBus = self.plugin_sys.event_bus

        protocol_class = ProtocolMeta.get_protocol(protocol)
        self._protocol: ProtocolABC = protocol_class()

        # 停止信号
        self._stop_event = asyncio.Event()

        self.token = token
        self.url = url

    # ---------- 公开属性 ----------
    @property
    def protocol(self) -> ProtocolABC:
        return self._protocol

    # ---------- 同步入口 ----------
    def run(self) -> None:
        """阻塞式启动，直到 Bot 退出"""

        async def _():
            await self.run_async()
            while not Bot.running:
                await asyncio.sleep(0.1)

        try:
            asyncio.run(_())
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log.exception(f"Bot 运行异常: {e}")
        finally:
            Bot.running = False

    # ---------- 异步入口 ----------
    async def run_async(self) -> None:
        # NOTE 独立使用你最好主动 await asyncio.sleep(...) 以便连接完成

        if Bot.running and One_Mod:
            raise RuntimeError("Bot 实例已经在运行，不允许重复启动")
        Bot.running = True
        self._stop_event.clear()

        # NOTE 用了会变的不幸
        # # 注册系统信号，支持 docker / 终端 kill
        # for sig in (signal.SIGINT, signal.SIGTERM):
        #     asyncio.get_running_loop().add_signal_handler(sig, self._request_shutdown)

        try:
            # 握手 / 登录
            self.ws: AsyncWebSocketClient = await self.protocol.login(
                self.url, self.token
            )
            log.info("Bot登录成功")

            # 监听器
            self.listener = await self.ws.create_listener()

            # 实例化 IMClient
            self._im_client = IMClient(self.protocol)

            # 启动插件
            await self.plugin_sys.start()
            log.info("插件系统启动完成")

            log.info("IMClient 启动完成，Bot 开始工作 ...")

            while not self._stop_event.is_set():
                await self._cat()
            # await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            await self.stop()
        except Exception as e:
            log.error(e)
            await self.stop()
        finally:
            Bot.running = False

    # ---------- 内部运行 ----------
    async def _cat(self) -> None:
        ws = self.ws
        protocol = self.protocol
        event_bus = self.event_bus
        listener_id = self.listener

        raw = await ws.get_message(listener_id)
        if raw:
            event = protocol._parse_event(raw)
            if isinstance(event, Event):
                await protocol.print_event(event)
                event_bus.publish_event(event)

    # ---------- 优雅退出 ----------
    async def stop(self) -> None:
        log.info("Bot 正在退出 ...")
        tasks = []

        # 关闭插件系统
        tasks.append(
            asyncio.create_task(
                self._safe_coro("plugin_sys.stop", self.plugin_sys.stop())
            )
        )

        await self.protocol.logout()

        # 等待所有清理任务完成（超时 5s）
        await asyncio.wait(tasks, timeout=5)
        self._stop_event.set()

        log.info("Bot 已完全停止")
        raise KeyboardInterrupt()

    # ---------- 工具 ----------
    def _request_shutdown(self) -> None:
        """信号处理器：请求停止"""
        if not self._stop_event.is_set():
            self._stop_event.set()

    async def _safe_coro(self, name: str, coro) -> None:
        """捕获并记录清理阶段的异常，避免掩盖主异常"""
        try:
            await coro
        except Exception as exc:
            log.error(f"清理阶段 {name} 异常: {exc}", exc_info=True)

    async def __aenter__(self) -> Self:
        return await self.run_async()

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()


# 在文件末尾追加
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="bot", description="机器人框架 CLI：启动、停止、查看状态等。")
    sub = parser.add_subparsers(dest="cmd", help="子命令")

    # start
    p_start = sub.add_parser("start", help="启动 Bot")
    p_start.add_argument("-u", "--url", required=True, help="WebSocket 地址")
    p_start.add_argument("-t", "--token", help="鉴权 token")
    p_start.add_argument("-p", "--protocol", default="napcat", help="协议类型")
    p_start.add_argument("--plugin-dir", type=Path, help="额外插件目录")
    p_start.add_argument("--config-dir", type=Path, default="config", help="配置目录")
    p_start.add_argument("--data-dir", type=Path, default="data", help="数据目录")

    # stop / status / reload 等可后续扩展
    # p_stop = sub.add_parser("stop", help="停止 Bot（暂未实现）")
    # p_status = sub.add_parser("status", help="查看运行状态（暂未实现）")

    args = parser.parse_args()

    if args.cmd == "start":
        bot = Bot(
            url=args.url,
            token=args.token,
            protocol=args.protocol,
            plugin_dir=args.plugin_dir,
            config_dir=args.config_dir,
            data_dir=args.data_dir,
        )
        try:
            bot.run()
        except KeyboardInterrupt:
            sys.exit(0)
    # elif args.cmd == "stop":
    #     print("stop 功能待实现")
    # elif args.cmd == "status":
    #     print("status 功能待实现")
    else:
        parser.print_help()
