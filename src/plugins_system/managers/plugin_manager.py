"""
插件管理器默认实现模块（最终修正版）

负责插件的生命周期管理和依赖解析，修复了重载失败后的残留模块导致死循环的问题。
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer, ObserverType

from ..abc.events import EventBus
from ..abc.plugins import PluginManager
from ..core.events import Event
from ..core.plugins import Plugin, PluginState, PluginStatus
from ..exceptions import PluginDependencyError, PluginRuntimeError, PluginVersionError
from ..implementations.plugin_finder import DefaultPluginFinder
from ..implementations.plugin_loader import DefaultPluginLoader
from ..utils.constants import (
    DEBUG_MODE,
    PROTOCOL_VERSION,
    FeatureFlags,
    ReloadModes,
    SystemEvents,
)
from ..utils.helpers import _version_satisfies
from ..utils.types import PluginName
from .config_manager import ConfigManager

logger = logging.getLogger("PluginsSys")


def _topological_sort(plugins: List[Plugin]) -> List[Plugin]:
    """对插件进行拓扑排序"""
    name_to_plugin: Dict[PluginName, Plugin] = {p.name: p for p in plugins}
    graph: Dict[PluginName, Set[PluginName]] = {p.name: set() for p in plugins}
    in_degree: Dict[PluginName, int] = {p.name: 0 for p in plugins}

    for p in plugins:
        for dep_name, version_spec in p.dependency.items():
            if dep_name not in name_to_plugin:
                raise PluginDependencyError(
                    f"插件 {p.name} 依赖缺失: {dep_name} {version_spec}",
                    plugin_name=p.name,
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
            f"插件之间存在循环依赖: {remaining}",
            plugin_name=remaining[0] if remaining else None,
        )

    return [name_to_plugin[n] for n in sorted_names]


class DefaultPluginManager(PluginManager):
    """默认插件管理器"""

    def __init__(
        self,
        plugin_dirs: List[Path],
        config_base_dir: Path,
        data_base_dir: Path,
        event_bus: Optional[EventBus] = None,
        dev_mode: bool = DEBUG_MODE,
        reload_mode: Optional[str] = None,
        debounce_interval: float = 0.5,
    ) -> None:
        self.plugin_dirs = plugin_dirs
        self.config_base_dir = config_base_dir
        self.data_base_dir = data_base_dir
        self.event_bus = event_bus
        self.dev_mode = dev_mode

        self.reload_mode = reload_mode or FeatureFlags.RELOAD_MODE
        self._debounce_interval = debounce_interval
        self._fs_event_lock = threading.Lock()
        self._pending_paths: Set[Path] = set()
        self._debounce_timer: Optional[threading.Timer] = None
        self._path_to_plugin_cache: Dict[Path, Set[PluginName]] = {}

        self.config_manager = ConfigManager(config_base_dir)
        self.plugin_finder = DefaultPluginFinder(plugin_dirs)
        self.loader = DefaultPluginLoader(
            self.event_bus,
            self.config_manager,
            data_base_dir,
            config_base_dir,
            dev_mode,
        )

        self._plugins: Dict[PluginName, Plugin] = {}
        self._plugin_status: Dict[PluginName, PluginStatus] = {}
        self._shutdown = False
        self._lock = threading.RLock()

        self._register_system_event_handlers()
        self._observer: Optional[ObserverType] = None
        if self.dev_mode:
            self._setup_watcher()

    def _setup_watcher(self) -> None:
        class _PluginDirEventHandler(FileSystemEventHandler):
            def __init__(self, manager: "DefaultPluginManager"):
                super().__init__()
                self.manager = manager

            def on_any_event(self, event):
                try:
                    src = Path(event.src_path)
                except Exception:
                    return
                paths = [src]
                dest = getattr(event, "dest_path", None)
                if dest:
                    try:
                        paths.append(Path(dest))
                    except Exception:
                        pass
                for p in paths:
                    self.manager._on_fs_event(p, event.event_type)

        self._observer = Observer()
        for plugin_dir in self.plugin_dirs:
            if plugin_dir.exists():
                self._observer.schedule(
                    _PluginDirEventHandler(self), str(plugin_dir), recursive=True
                )
        self._observer.daemon = True
        self._observer.start()

    def _register_system_event_handlers(self) -> None:
        handlers = {
            SystemEvents.MANAGER_STARTING: self._handle_manager_starting,
            SystemEvents.MANAGER_STOPPING: self._handle_manager_stopping,
            SystemEvents.RELOAD_REQUESTED: self._handle_reload_requested,
            SystemEvents.LOAD_ERROR: self._handle_load_error,
            SystemEvents.RUNTIME_ERROR: self._handle_runtime_error,
        }
        for event_name, handler in handlers.items():
            self.event_bus.register_handler(event_name, handler)

    # ==================== 事件处理 ====================

    async def _handle_manager_starting(self, event: Event) -> None:
        logger.info("插件管理器正在启动...")

    async def _handle_manager_stopping(self, event: Event) -> None:
        logger.info("插件管理器正在停止...")

    async def _handle_reload_requested(self, event: Event) -> None:
        data = event.data or {}
        plugin_name = data.get("plugin_name")
        mode = data.get("mode")
        paths = data.get("paths") or ([data.get("path")] if data.get("path") else None)

        logger.info(
            f"收到插件重载请求: plugin={plugin_name}, mode={mode}, paths={paths}"
        )

        if paths:
            try:
                original_mode = self.reload_mode
                if mode:
                    self.reload_mode = mode
                await self._process_fs_events(
                    {Path(p) for p in paths}, "external_request"
                )
            finally:
                if mode:
                    self.reload_mode = original_mode
            return

        if plugin_name:
            await self.reload_plugin(PluginName(plugin_name))
            return

        if mode in (ReloadModes.ALL, ReloadModes.SINGLE, ReloadModes.SMART):
            if mode == ReloadModes.ALL:
                await self._reload_all_plugins()
                return
        await self._reload_all_plugins()

    async def _handle_load_error(self, event: Event) -> None:
        logger.error(f"插件加载错误: {event.data}")

    async def _handle_runtime_error(self, event: Event) -> None:
        logger.error(f"插件运行时错误: {event.data}")

    async def _send_system_event(self, event: str, data: Any = None) -> None:
        self.event_bus.publish(event, data, source="PluginManager")

    async def _send_plugin_event(
        self, event_suffix: str, plugin_name: PluginName, data: Any = None
    ) -> None:
        event_name = f"plugin.{plugin_name}.{event_suffix}"
        self.event_bus.publish(
            event_name, data, source="PluginManager", target=plugin_name
        )

    # ==================== 生命周期管理 ====================

    async def load_plugins(self) -> List[Plugin]:
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
                logger.error(f"加载插件源失败 {source.path}:\n{e}")
                await self._send_system_event(
                    SystemEvents.LOAD_ERROR,
                    {
                        "plugin": source.module_name,
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
            if not self.dev_mode:
                raise
            return []

        success_plugins: List[Plugin] = []
        for plugin in sorted_plugins:
            if plugin.name in self._plugins:
                logger.debug(f"插件 {plugin.name} 已加载，跳过")
                continue

            try:
                self._check_protocol_version(plugin)

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

                if not self.dev_mode:
                    if isinstance(e, (PluginVersionError, PluginDependencyError)):
                        raise
                    raise PluginRuntimeError(str(e), plugin.name) from e
                continue

        if success_plugins:
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
            await self.config_manager.save_config(plugin.module_name, plugin.config)
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
        plugin = self.get_plugin(plugin_name)
        if not plugin:
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
        plugin = self.get_plugin(plugin_name)
        if not plugin:
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
        """
        重载指定插件
        修复：加载失败时清理 Loader 中的残留模块，防止死循环。
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return False

        logger.info(f"开始重载插件: {plugin_name}")
        was_running = plugin.status.state == PluginState.RUNNING

        try:
            if was_running:
                ok = await self.stop_plugin(plugin_name)
                if not ok:
                    raise RuntimeError("stop_plugin 返回 False")
            ok = await self.unload_plugin(plugin_name)
            if not ok:
                raise RuntimeError("unload_plugin 返回 False")
        except Exception as e:
            logger.exception(f"重载插件 {plugin_name} 时“停/卸”阶段失败")
            raise PluginRuntimeError(f"重载失败（停/卸阶段）: {e}", plugin_name) from e

        sources = await self.plugin_finder.find_plugins()
        target_source = None
        for source in sources:
            if source.module_name == plugin.module_name:
                target_source = source
                break

        if not target_source:
            self._plugins.pop(plugin_name, None)
            self._plugin_status.pop(plugin_name, None)
            logger.warning(f"未找到插件的源文件: {plugin_name}，已回滚到未加载状态")
            return False

        try:
            plugins = await self.loader.load_from_source(target_source)
            for new_plugin in plugins:
                if new_plugin.name == plugin_name:
                    await new_plugin._internal_on_load()
                    await new_plugin.on_reload()

                    with self._lock:
                        self._plugins[new_plugin.name] = new_plugin
                        self._plugin_status[new_plugin.name] = new_plugin.status

                    if was_running:
                        await self.start_plugin(plugin_name)

                    logger.info(f"插件重载完成: {plugin_name}")
                    return True
        except Exception as e:
            # 关键修复：清理 Loader 中的模块，避免残留导致后续重载死循环
            logger.exception(f"重载插件 {plugin_name} 时“装”阶段失败，执行回滚清理")
            try:
                await self.loader.unload_plugin_module(plugin_name)
            except Exception:
                pass

            self._plugins.pop(plugin_name, None)
            self._plugin_status.pop(plugin_name, None)
            raise PluginRuntimeError(f"重载失败（装阶段）: {e}", plugin_name) from e

        return False

    async def close(self) -> None:
        if self._shutdown:
            return

        self._shutdown = True
        await self._send_system_event(SystemEvents.MANAGER_STOPPING)

        plugin_names = self.list_plugins()
        for plugin_name in reversed(plugin_names):
            if not await self.unload_plugin(plugin_name):
                logger.error(f"关闭插件时发生错误: {plugin_name}")

        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        if hasattr(self.event_bus, "close"):
            self.event_bus.close()

        logger.info("插件管理器已关闭")

    # ==================== 查询接口 ====================

    def get_plugin(self, plugin_name: PluginName) -> Optional[Plugin]:
        with self._lock:
            return self._plugins.get(plugin_name)

    def list_plugins(self, cls: bool = False) -> List[PluginName | Plugin]:
        with self._lock:
            if cls:
                return list(self._plugins.values())
            else:
                return list(self._plugins.keys())

    def list_plugins_with_status(self) -> Dict[PluginName, PluginStatus]:
        with self._lock:
            return self._plugin_status.copy()

    # ==================== 热重载与文件监控 ====================

    def _check_protocol_version(self, plugin: Plugin) -> None:
        if plugin.protocol_version != PROTOCOL_VERSION:
            raise PluginVersionError(f"插件 {plugin.name} 协议版本不兼容", plugin.name)

    def _on_fs_event(self, file_path: Path, event_type: str) -> None:
        with self._fs_event_lock:
            self._pending_paths.add(file_path)
            if self._debounce_timer is not None:
                try:
                    self._debounce_timer.cancel()
                except Exception:
                    pass

            self._debounce_timer = threading.Timer(
                self._debounce_interval, self._debounce_timer_handler
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _debounce_timer_handler(self) -> None:
        with self._fs_event_lock:
            paths = set(self._pending_paths)
            self._pending_paths.clear()
            self._debounce_timer = None

        try:
            asyncio.run(self._process_fs_events(paths, "file_change"))
        except Exception as e:
            logger.exception(f"处理文件变更事件失败: {e}")

    def _refresh_path_cache(self) -> None:
        cache: Dict[Path, Set[PluginName]] = {}
        for name, (_module_name, source) in self.loader._loaded_modules.items():
            cache.setdefault(source.path, set()).add(name)
        self._path_to_plugin_cache = cache

    async def _process_fs_events(self, paths: Set[Path], reason: str) -> None:
        if not paths or any(p.name == "__pycache__" for p in paths):
            return

        logger.info(
            f"开始处理文件变更|{self.reload_mode} : {', '.join([str(p) for p in paths])}"
        )

        impacted_plugins, discovered_sources = self._analyze_fs_changes(paths)

        await self._send_system_event(
            SystemEvents.RELOAD_STARTED,
            {"mode": self.reload_mode, "paths": [str(p) for p in paths]},
        )

        if self.reload_mode == ReloadModes.ALL:
            await self._reload_all_plugins()
            await self._load_new_sources(discovered_sources)

        elif self.reload_mode == ReloadModes.SINGLE:
            if not impacted_plugins and discovered_sources:
                await self._load_new_sources(discovered_sources)
            else:
                for name in list(impacted_plugins):
                    try:
                        logger.info(f"[single-reload] 重载插件 {name}, 原因: {reason}")
                        await self.reload_plugin(PluginName(name))
                    except Exception as e:
                        logger.exception(f"[single-reload] 重载插件 {name} 失败: {e}")

        elif self.reload_mode == ReloadModes.SMART:
            if not impacted_plugins and discovered_sources:
                await self._load_new_sources(discovered_sources)
            elif impacted_plugins:
                affected_set = self._calculate_dependent_set(impacted_plugins)
                logger.info(f"[smart-reload] 受影响插件集合: {affected_set}")
                await self._reload_plugin_set(affected_set, reason)
        else:
            logger.warning(f"未知的重载模式 {self.reload_mode}，执行全部重载")
            await self._reload_all_plugins()

        self._refresh_path_cache()

    def _analyze_fs_changes(
        self, paths: Set[Path]
    ) -> tuple[Set[PluginName], List[Any]]:
        impacted: Set[PluginName] = set()
        discovered = []

        for p in paths:
            try:
                for loaded_name, (_module_name, source) in list(
                    self.loader._loaded_modules.items()
                ):
                    if source.contains_path(p):
                        impacted.add(loaded_name)
            except Exception:
                pass

            try:
                src = self.plugin_finder.find_plugin_by_path(p)
                if src:
                    is_new = True
                    for _m, s in self.loader._loaded_modules.values():
                        if str(s.path) == str(src.path):
                            is_new = False
                            break
                    if is_new:
                        discovered.append(src)
            except Exception:
                pass

        return impacted, discovered

    def _calculate_dependent_set(
        self, initial_names: Set[PluginName]
    ) -> Set[PluginName]:
        affected = set(initial_names)
        reverse_dep = {n: set() for n in self._plugins.keys()}

        for n, plugin in self._plugins.items():
            for dep in plugin.dependency.keys():
                if dep in reverse_dep:
                    reverse_dep[dep].add(n)

        queue = list(initial_names)
        while queue:
            cur = queue.pop()
            for dep_user in reverse_dep.get(cur, set()):
                if dep_user not in affected:
                    affected.add(dep_user)
                    queue.append(dep_user)

        return affected

    async def _load_new_sources(self, sources: List[Any]) -> None:
        for src in sources:
            try:
                plugins = await self.loader.load_from_source(src)
                for plugin in plugins:
                    await plugin._internal_on_load()
                    await plugin.on_reload()
                    with self._lock:
                        self._plugins[plugin.name] = plugin
                        self._plugin_status[plugin.name] = plugin.status
                    await self._send_plugin_event("loaded", plugin.name, plugin.meta)
                    logger.info(f"新插件发现并加载: {plugin.name}")
            except Exception as e:
                logger.exception(f"加载新插件 {src.path} 失败: {e}")

    async def _reload_all_plugins(self) -> None:
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
            if (
                plugin
                and state == PluginState.RUNNING
                and plugin.status.state != PluginState.RUNNING
            ):
                await self.start_plugin(plugin_name)

        logger.info("所有插件重载完成")

    async def _reload_plugin_set(
        self, plugin_names: Set[PluginName], reason: str
    ) -> None:
        """按依赖顺序重载指定的一组插件"""
        current_plugins = []
        module_map: Dict[PluginName, str] = {}

        for name in plugin_names:
            p = self._plugins.get(name)
            if p:
                current_plugins.append(p)
                module_map[name] = getattr(p, "module_name", None)

        if not current_plugins:
            # 如果插件名存在但 _plugins 中不存在，说明上次失败已清理，
            # 且 loader 中的模块可能已被清理（或在当前逻辑中视为新插件）。
            # 此时不再做特殊处理，让后续的文件变更事件通过“新插件发现”流程恢复。
            logger.debug("[smart-reload] 插件集合为空，可能已被清理，跳过")
            return

        try:
            sorted_plugins = _topological_sort(current_plugins)
        except PluginDependencyError as e:
            logger.warning(f"依赖解析失败，退回到逐个重载: {e}")
            for name in plugin_names:
                try:
                    await self.reload_plugin(PluginName(name))
                except Exception:
                    pass
            return

        # 卸载
        for p in reversed(sorted_plugins):
            try:
                logger.debug(f"[smart-reload] 卸载插件: {p.name}")
                await self.unload_plugin(p.name)
            except Exception as e:
                logger.exception(f"卸载插件 {p.name} 时出错: {e}")

        # 重新加载
        sources = await self.plugin_finder.find_plugins()
        for p in sorted_plugins:
            module_name = module_map.get(p.name)
            src = next((s for s in sources if s.module_name == module_name), None)

            if not src:
                logger.warning(f"未找到插件 {p.name} 的源，跳过")
                continue

            try:
                plugins = await self.loader.load_from_source(src)
                for plugin in plugins:
                    if plugin.name == p.name:
                        await plugin._internal_on_load()
                        await plugin.on_reload()

                        with self._lock:
                            self._plugins[plugin.name] = plugin
                            self._plugin_status[plugin.name] = plugin.status
                        logger.info(f"插件重载完成: {plugin.name}")
            except Exception:
                # 关键修复：加载失败时清理 Loader 中的模块
                logger.exception(f"加载插件 {p.name} 时失败，执行回滚清理")
                try:
                    await self.loader.unload_plugin_module(p.name)
                except Exception:
                    pass

                self._plugins.pop(p.name, None)
                self._plugin_status.pop(p.name, None)
