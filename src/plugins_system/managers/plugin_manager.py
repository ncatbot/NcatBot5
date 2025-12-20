"""
插件管理器默认实现模块

负责插件的生命周期管理和依赖解析
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..abc.events import EventBus
from ..abc.plugins import PluginManager
from ..core.events import Event
from ..core.plugins import Plugin, PluginState, PluginStatus
from ..exceptions import PluginDependencyError, PluginRuntimeError, PluginVersionError
from ..implementations.plugin_finder import DefaultPluginFinder
from ..implementations.plugin_loader import DefaultPluginLoader
from ..utils.constants import DEBUG_MODE, PROTOCOL_VERSION, SystemEvents
from ..utils.helpers import _version_satisfies
from ..utils.types import PluginName
from .config_manager import ConfigManager

logger = logging.getLogger("PluginsSys")


def _topological_sort(plugins: List[Plugin]) -> List[Plugin]:
    """对插件进行拓扑排序

    Args:
        plugins: 要排序的插件列表

    Returns:
        拓扑排序后的插件列表

    Raises:
        PluginDependencyError: 当存在循环依赖或缺失依赖时
    """
    name_to_plugin: Dict[PluginName, Plugin] = {p.name: p for p in plugins}
    graph: Dict[PluginName, Set[PluginName]] = {p.name: set() for p in plugins}
    in_degree: Dict[PluginName, int] = {p.name: 0 for p in plugins}

    for p in plugins:
        for dep_name, version_spec in p.dependency.items():
            if dep_name not in name_to_plugin:
                raise PluginDependencyError(
                    f"插件 {p.name} 依赖缺失: {dep_name} {version_spec}", plugin_name=p.name
                )
            dep_plugin = name_to_plugin[dep_name]
            if not _version_satisfies(dep_plugin.version, version_spec):
                raise PluginDependencyError(
                    f"插件 {p.name} 需要 {dep_name} {version_spec}, 但找到的是 {dep_plugin.version}",
                    plugin_name=p.name,
                )
            graph[dep_name].add(p.name)
            in_degree[p.name] += 1

    queue = [name for name, deg in in_degree.items() if deg == 0]
    sorted_names: List[PluginName] = []

    while queue:
        cur = queue.pop(0)
        sorted_names.append(cur)
        for neighbor in graph[cur]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_names) != len(plugins):
        remaining = [name for name in in_degree if in_degree[name] > 0]
        raise PluginDependencyError(
            f"插件之间存在循环依赖: {remaining}", plugin_name=remaining[0] if remaining else None
        )

    return [name_to_plugin[n] for n in sorted_names]


class DefaultPluginManager(PluginManager):
    """默认插件管理器

    提供完整的插件生命周期管理功能

    Attributes:
        plugin_dirs: 插件目录列表
        config_base_dir: 配置基础目录
        data_base_dir: 数据基础目录
        event_bus: 事件总线实例
        dev_mode: 开发模式
        _plugins: 插件映射
        _plugin_status: 插件状态映射
        _shutdown: 是否已关闭
        _lock: 线程锁
    """

    def __init__(
        self,
        plugin_dirs: List[Path],
        config_base_dir: Path,
        data_base_dir: Path,
        event_bus: Optional[EventBus] = None,
        dev_mode: bool = DEBUG_MODE,
    ) -> None:
        """初始化插件管理器

        Args:
            plugin_dirs: 插件目录列表
            config_base_dir: 配置基础目录
            data_base_dir: 数据基础目录
            event_bus: 事件总线实例
            dev_mode: 开发模式
        """
        self.plugin_dirs = plugin_dirs
        self.config_base_dir = config_base_dir
        self.data_base_dir = data_base_dir
        self.event_bus = event_bus
        self.dev_mode = dev_mode

        self.config_manager = ConfigManager(config_base_dir)
        self.plugin_finder = DefaultPluginFinder(plugin_dirs)
        # 更新插件加载器初始化，传入config_base_dir
        self.loader = DefaultPluginLoader(
            self.event_bus,
            self.config_manager,
            data_base_dir,
            config_base_dir,  # 传入配置基础目录
            dev_mode,
        )

        self._plugins: Dict[PluginName, Plugin] = {}
        self._plugin_status: Dict[PluginName, PluginStatus] = {}
        self._shutdown = False
        self._lock = threading.RLock()

        self._register_system_event_handlers()

    def _register_system_event_handlers(self) -> None:
        """注册系统性事件处理器"""
        self.event_bus.register_handler(
            SystemEvents.MANAGER_STARTING, self._handle_manager_starting
        )
        self.event_bus.register_handler(
            SystemEvents.MANAGER_STOPPING, self._handle_manager_stopping
        )
        self.event_bus.register_handler(
            SystemEvents.RELOAD_REQUESTED, self._handle_reload_requested
        )
        self.event_bus.register_handler(
            SystemEvents.LOAD_ERROR, self._handle_load_error
        )
        self.event_bus.register_handler(
            SystemEvents.RUNTIME_ERROR, self._handle_runtime_error
        )

    async def _handle_manager_starting(self, event: Event) -> None:
        """处理管理器启动事件"""
        logger.info("插件管理器正在启动...")

    async def _handle_manager_stopping(self, event: Event) -> None:
        """处理管理器停止事件"""
        logger.info("插件管理器正在停止...")

    async def _handle_reload_requested(self, event: Event) -> None:
        """处理重载请求事件

        Args:
            event: 重载请求事件
        """
        plugin_name = event.data.get("plugin_name") if event.data else None
        logger.info(f"收到插件重载请求: {plugin_name or 'all'}")

        if plugin_name:
            await self.reload_plugin(PluginName(plugin_name))
        else:
            await self._reload_all_plugins()

    async def _handle_load_error(self, event: Event) -> None:
        """处理加载错误事件

        Args:
            event: 加载错误事件
        """
        logger.error(f"插件加载错误: {event.data}")

    async def _handle_runtime_error(self, event: Event) -> None:
        """处理运行时错误事件

        Args:
            event: 运行时错误事件
        """
        logger.error(f"插件运行时错误: {event.data}")

    async def _reload_all_plugins(self) -> None:
        """重载所有插件"""
        logger.info("开始重载所有插件...")

        plugin_states = {
            name: plugin.status.state for name, plugin in self._plugins.items()
        }

        plugin_names = self.list_plugins()
        for plugin_name in reversed(plugin_names):
            await self.unload_plugin(plugin_name)

        await self.load_plugins()

        for plugin_name, state in plugin_states.items():
            plugin = self.get_plugin(plugin_name)
            if plugin:
                if (
                    state == PluginState.RUNNING
                    and plugin.status.state != PluginState.RUNNING
                ):
                    await self.start_plugin(plugin_name)

        logger.info("所有插件重载完成")

    async def _send_system_event(self, event: str, data: Any = None) -> None:
        """发送系统性事件

        Args:
            event: 事件名称
            data: 事件数据
        """
        self.event_bus.publish(event, data, source="PluginManager")

    async def _send_plugin_event(
        self, event_suffix: str, plugin_name: PluginName, data: Any = None
    ) -> None:
        """发送插件事件

        Args:
            event_suffix: 事件后缀
            plugin_name: 插件名称
            data: 事件数据
        """
        event_name = f"plugin.{plugin_name}.{event_suffix}"
        self.event_bus.publish(
            event_name, data, source="PluginManager", target=plugin_name
        )

    async def load_plugins(self) -> List[Plugin]:
        """加载所有插件

        Returns:
            成功加载的插件列表

        Raises:
            RuntimeError: 当插件管理器已关闭时
            PluginDependencyError: 当依赖解析失败时
            PluginRuntimeError: 当插件运行时发生错误时
        """
        if self._shutdown:
            raise RuntimeError("插件管理器已关闭")

        await self._send_system_event(SystemEvents.MANAGER_STARTING)

        sources = await self.plugin_finder.find_plugins()
        all_plugins = []

        for source in sources:
            try:
                plugins = await self.loader.load_from_source(source)
                all_plugins.extend(plugins)

                for plugin in plugins:
                    await self._send_plugin_event(
                        "discovered", plugin.name, plugin.meta
                    )

            except Exception as e:
                logger.error(f"加载插件失败 {source.path}:\n{e}")
                plugin_name = source.module_name
                await self._send_system_event(
                    SystemEvents.LOAD_ERROR,
                    {
                        "plugin": plugin_name,
                        "source": str(source.path),
                        "error": str(e),
                    },
                )

        if not all_plugins:
            logger.warning("未找到任何插件")
            return []

        try:
            sorted_plugins = _topological_sort(all_plugins)
            await self._send_system_event(
                SystemEvents.DEPENDENCY_RESOLVED,
                {"sorted_plugins": [p.name for p in sorted_plugins]},
            )
        except PluginDependencyError as e:
            logger.error(f"插件依赖解析失败:\n{e}")
            await self._send_system_event(
                SystemEvents.DEPENDENCY_ERROR,
                {"error": str(e), "plugin": e.plugin_name},
            )
            raise

        success_plugins: List[Plugin] = []

        for plugin in sorted_plugins:
            if plugin.name in self._plugins:
                logger.debug(f"插件 {plugin.name} 已加载，跳过")
                continue

            try:
                if plugin.protocol_version != PROTOCOL_VERSION:
                    raise PluginVersionError(f"插件 {plugin.name} 协议版本不兼容", plugin.name)

                await self._send_plugin_event("loading", plugin.name, plugin.meta)

                await plugin._internal_on_load()

                with self._lock:
                    self._plugins[plugin.name] = plugin
                    self._plugin_status[plugin.name] = plugin.status

                success_plugins.append(plugin)
                logger.info(f"插件已加载: {plugin.name}@{plugin.version}")

                await self._send_plugin_event("loaded", plugin.name, plugin.meta)
                await self._send_system_event(
                    SystemEvents.PLUGIN_LOADED,
                    {"plugin": plugin.name, "version": plugin.version},
                )

            except Exception as e:
                plugin._set_status(PluginState.FAILED, e)
                logger.exception(f"插件 {plugin.name} 加载失败")

                await self._send_plugin_event("load_failed", plugin.name, str(e))
                await self._send_system_event(
                    SystemEvents.LOAD_ERROR, {"plugin": plugin.name, "error": str(e)}
                )

                for loaded_plugin in reversed(success_plugins):
                    try:
                        await self.unload_plugin(loaded_plugin.name)
                    except Exception as unload_error:
                        logger.exception(
                            f"卸载插件 {loaded_plugin.name} 时出错: {unload_error}"
                        )

                if isinstance(e, (PluginVersionError, PluginDependencyError)):
                    raise
                else:
                    raise PluginRuntimeError(str(e), plugin.name) from e

        if success_plugins:
            await self._send_system_event(
                SystemEvents.ALL_PLUGINS_LOADED,
                {
                    "loaded_plugins": [p.name for p in success_plugins],
                    "total_count": len(success_plugins),
                },
            )

            for plugin in success_plugins:
                await self._send_plugin_event(
                    "ready",
                    plugin.name,
                    {"loaded_plugins": [p.name for p in success_plugins]},
                )

        await self._send_system_event(
            SystemEvents.MANAGER_STARTED, {"loaded_count": len(success_plugins)}
        )

        return success_plugins

    async def unload_plugin(self, plugin_name: PluginName) -> bool:
        """卸载指定插件

        Args:
            plugin_name: 要卸载的插件名称

        Returns:
            如果成功卸载返回True，否则返回False
        """
        with self._lock:
            plugin = self._plugins.pop(plugin_name, None)
            if plugin is None:
                return False

        try:
            await self._send_plugin_event("unloading", plugin_name)

            await plugin._internal_on_unload()

            if hasattr(self.event_bus, "unregister_plugin_handlers"):
                self.event_bus.unregister_plugin_handlers(plugin_name)

            plugin.context.close()

            await self.loader.unload_plugin_module(plugin_name)

            with self._lock:
                self._plugin_status[plugin_name] = plugin.status

            logger.info(f"卸载插件: {plugin_name}")

            await self._send_plugin_event("unloaded", plugin_name)
            await self._send_system_event(
                SystemEvents.PLUGIN_UNLOADED, {"plugin": plugin_name}
            )

            return True

        except Exception as e:
            logger.exception(f"卸载插件 {plugin_name} 时出错:\n{e}")
            plugin._set_status(PluginState.FAILED, e)

            await self._send_system_event(
                SystemEvents.RUNTIME_ERROR,
                {"plugin": plugin_name, "operation": "unload", "error": str(e)},
            )

            return False

    async def start_plugin(self, plugin_name: PluginName) -> bool:
        """启动指定插件

        Args:
            plugin_name: 要启动的插件名称

        Returns:
            如果成功启动返回True，否则返回False
        """
        plugin = self.get_plugin(plugin_name)
        if plugin is None:
            return False

        if plugin.status.state == PluginState.STOPPED:
            try:
                await self._send_plugin_event("starting", plugin_name)

                await plugin._internal_on_load()

                with self._lock:
                    self._plugin_status[plugin_name] = plugin.status

                await self._send_plugin_event("started", plugin_name)
                await self._send_system_event(
                    SystemEvents.PLUGIN_STARTED, {"plugin": plugin_name}
                )

                return True

            except Exception as e:
                plugin._set_status(PluginState.FAILED, e)
                logger.exception(f"启动插件 {plugin_name} 失败")

                await self._send_plugin_event("start_failed", plugin_name, str(e))
                await self._send_system_event(
                    SystemEvents.RUNTIME_ERROR,
                    {"plugin": plugin_name, "operation": "start", "error": str(e)},
                )

                return False

        return plugin.status.state == PluginState.RUNNING

    async def stop_plugin(self, plugin_name: PluginName) -> bool:
        """停止指定插件

        Args:
            plugin_name: 要停止的插件名称

        Returns:
            如果成功停止返回True，否则返回False
        """
        plugin = self.get_plugin(plugin_name)
        if plugin is None:
            return False

        if plugin.status.state == PluginState.RUNNING:
            try:
                await self._send_plugin_event("stopping", plugin_name)

                await plugin._internal_on_unload()
                plugin._set_status(PluginState.STOPPED)

                with self._lock:
                    self._plugin_status[plugin_name] = plugin.status

                await self._send_plugin_event("stopped", plugin_name)
                await self._send_system_event(
                    SystemEvents.PLUGIN_STOPPED, {"plugin": plugin_name}
                )

                return True

            except Exception as e:
                plugin._set_status(PluginState.FAILED, e)
                logger.exception(f"停止插件 {plugin_name} 失败")

                await self._send_plugin_event("stop_failed", plugin_name, str(e))
                await self._send_system_event(
                    SystemEvents.RUNTIME_ERROR,
                    {"plugin": plugin_name, "operation": "stop", "error": str(e)},
                )

                return False

        return plugin.status.state == PluginState.STOPPED

    async def reload_plugin(self, plugin_name: PluginName) -> bool:
        """重载指定插件

        Args:
            plugin_name: 要重载的插件名称

        Returns:
            如果成功重载返回True，否则返回False
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return False

        logger.info(f"开始重载插件: {plugin_name}")

        was_running = plugin.status.state == PluginState.RUNNING

        if was_running:
            await self.stop_plugin(plugin_name)

        await self.unload_plugin(plugin_name)

        sources = await self.plugin_finder.find_plugins()
        for source in sources:
            if source.module_name == plugin.module_name:
                plugins = await self.loader.load_from_source(source)
                for new_plugin in plugins:
                    if new_plugin.name == plugin_name:
                        await new_plugin._internal_on_load()

                        with self._lock:
                            self._plugins[new_plugin.name] = new_plugin
                            self._plugin_status[new_plugin.name] = new_plugin.status

                        logger.info(f"插件重载完成: {plugin_name}")
                        return True

        logger.warning(f"未找到插件的源文件: {plugin_name}")
        return False

    def get_plugin(self, plugin_name: PluginName) -> Optional[Plugin]:
        """获取指定插件实例

        Args:
            plugin_name: 插件名称

        Returns:
            插件实例，如果不存在则返回None
        """
        with self._lock:
            return self._plugins.get(plugin_name)

    def list_plugins(self, cls: bool = False) -> List[PluginName | Plugin]:
        """获取所有插件名称列表

        Returns:
            插件名称列表
        """
        with self._lock:
            if cls:
                return self._plugins.values()
            else:
                return list(self._plugins.keys())

    def list_plugins_with_status(self) -> Dict[PluginName, PluginStatus]:
        """获取插件状态映射

        Returns:
            插件名称到状态的映射
        """
        with self._lock:
            return self._plugin_status.copy()

    async def close(self) -> None:
        """关闭插件管理器"""
        if self._shutdown:
            return

        self._shutdown = True

        await self._send_system_event(SystemEvents.MANAGER_STOPPING)

        plugin_names = self.list_plugins()
        for plugin_name in reversed(plugin_names):
            if not await self.unload_plugin(plugin_name):
                logger.error(f"关闭插件时发生错误: {plugin_name}")

        if hasattr(self.event_bus, "close"):
            self.event_bus.close()

        # 插件有 on_unload 不需要关闭事件
        # await self._send_system_event(SystemEvents.MANAGER_STOPPED)

        logger.info("插件管理器已关闭")
