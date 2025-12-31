"""
插件管理器默认实现模块

负责插件的生命周期管理和依赖解析
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

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
        reload_mode: Optional[str] = None,
        debounce_interval: float = 0.5,
    ) -> None:
        """初始化插件管理器

        Args:
            plugin_dirs: 插件目录列表
            config_base_dir: 配置基础目录
            data_base_dir: 数据基础目录
            event_bus: 事件总线实例
            dev_mode: 开发模式
            reload_mode: 重载模式（all|single|smart），默认取自 FeatureFlags.RELOAD_MODE
            debounce_interval: 文件变更防抖时间（秒）
        """
        self.plugin_dirs = plugin_dirs
        self.config_base_dir = config_base_dir
        self.data_base_dir = data_base_dir
        self.event_bus = event_bus
        self.dev_mode = dev_mode

        # 重载配置
        self.reload_mode = reload_mode or FeatureFlags.RELOAD_MODE
        self._debounce_interval = debounce_interval
        self._fs_event_lock = threading.Lock()
        self._pending_paths: Set[Path] = set()
        self._debounce_timer: Optional[threading.Timer] = None
        # 缓存: 源路径 -> 插件名集合（用于快速从文件路径映射到插件）
        self._path_to_plugin_cache: Dict[Path, Set[PluginName]] = {}

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

        # dev_mode下启用插件目录热重载（带防抖与智能映射）
        self._observer = None
        if self.dev_mode:

            class _PluginDirEventHandler(FileSystemEventHandler):
                def __init__(self, manager: "DefaultPluginManager"):
                    super().__init__()
                    self.manager = manager

                def on_any_event(self, event):
                    try:
                        src = Path(event.src_path)
                    except Exception:
                        return
                    dest = getattr(event, "dest_path", None)
                    paths = [src]
                    if dest:
                        try:
                            paths.append(Path(dest))
                        except Exception:
                            pass

                    for p in paths:
                        try:
                            # 非阻塞：收集文件变更并在防抖后处理
                            self.manager._on_fs_event(p, event.event_type)
                        except Exception:
                            logger.exception("处理文件系统事件时出错")

            self._observer = Observer()
            for plugin_dir in self.plugin_dirs:
                if plugin_dir.exists():
                    event_handler = _PluginDirEventHandler(self)
                    self._observer.schedule(
                        event_handler, str(plugin_dir), recursive=True
                    )
            self._observer.daemon = True
            self._observer.start()

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

        支持通过 event.data 提供以下字段：
        - plugin_name: 指定单个插件名重载
        - path / paths: 文件路径（或路径列表），触发基于文件的重载（遵循当前 reload_mode）
        - mode: 指定模式（all/single/smart），优先于管理器配置
        """
        data = event.data or {}
        plugin_name = data.get("plugin_name")
        mode = data.get("mode")
        paths = data.get("paths") or ([data.get("path")] if data.get("path") else None)

        logger.info(f"收到插件重载请求: {plugin_name or (mode or 'all')} | paths={paths}")

        if paths:
            try:
                mode_before = self.reload_mode
                if mode:
                    self.reload_mode = mode
                await self._process_fs_events(
                    {Path(p) for p in paths}, "external_request"
                )
            finally:
                if mode:
                    self.reload_mode = mode_before
            return

        if plugin_name:
            await self.reload_plugin(PluginName(plugin_name))
            return

        if (
            mode == ReloadModes.ALL
            or mode == ReloadModes.SINGLE
            or mode == ReloadModes.SMART
        ):
            if mode == ReloadModes.ALL:
                await self._reload_all_plugins()
                return

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

    def _on_fs_event(self, file_path: Path, event_type: str) -> None:
        """处理来自文件系统的单次事件（非阻塞）

        收集路径并启动防抖计时器，计时器触发后会统一处理所有收集到的路径。
        """
        with self._fs_event_lock:
            self._pending_paths.add(file_path)
            # restart debounce timer
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
        """防抖计时器线程回调，调用异步处理函数执行实际重载逻辑。"""
        with self._fs_event_lock:
            paths = set(self._pending_paths)
            self._pending_paths.clear()
            self._debounce_timer = None

        reason = f"文件变更: {', '.join([p.name for p in paths])}"
        try:
            asyncio.run(self._process_fs_events(paths, reason))
        except Exception as e:
            logger.exception(f"处理文件变更事件失败: {e}")

    async def _process_fs_events(self, paths: Set[Path], reason: str) -> None:
        """根据当前重载模式处理收集到的文件变更路径。"""
        if not paths or "__pycache__" in {p.name for p in paths}:
            return

        logger.info(
            f"开始处理文件变更（模式={self.reload_mode}）: {', '.join([str(p) for p in paths])}"
        )

        # 找出受影响的已加载插件，以及可能的新插件源
        impacted_plugins: Set[PluginName] = set()
        discovered_sources = []

        # 先从缓存/已加载模块中匹配
        for p in paths:
            # 匹配已加载模块
            for loaded_name, (_module_name, source) in list(
                self.loader._loaded_modules.items()
            ):
                try:
                    if source.contains_path(p):
                        impacted_plugins.add(loaded_name)
                except Exception:
                    continue

            # 通过查找器尝试识别插件源（包含新增的插件）
            try:
                src = self.plugin_finder.find_plugin_by_path(p)
                if src:
                    # 如果该source未被加载或不在_loaded_modules，记录为待发现
                    if not any(
                        str(s.path) == str(src.path)
                        for _m, s in self.loader._loaded_modules.values()
                    ):
                        discovered_sources.append(src)
            except Exception:
                continue

        # 根据模式采取不同策略
        mode = self.reload_mode

        if mode == ReloadModes.ALL:
            await self._send_system_event(
                SystemEvents.RELOAD_STARTED,
                {"mode": "all", "paths": [str(p) for p in paths]},
            )
            await self._reload_all_plugins()

            # 发现新增插件时，尝试加载
            for src in discovered_sources:
                try:
                    plugins = await self.loader.load_from_source(src)
                    for plugin in plugins:
                        with self._lock:
                            self._plugins[plugin.name] = plugin
                            self._plugin_status[plugin.name] = plugin.status
                        await self._send_plugin_event(
                            "loaded", plugin.name, plugin.meta
                        )
                        logger.info(f"新插件发现并加载: {plugin.name}")
                except Exception as e:
                    logger.exception(f"加载新插件 {src.path} 失败: {e}")

        elif mode == ReloadModes.SINGLE:
            await self._send_system_event(
                SystemEvents.RELOAD_STARTED,
                {"mode": "single", "paths": [str(p) for p in paths]},
            )
            if not impacted_plugins and discovered_sources:
                # 新增插件：尝试加载新插件
                for src in discovered_sources:
                    try:
                        plugins = await self.loader.load_from_source(src)
                        for plugin in plugins:
                            with self._lock:
                                self._plugins[plugin.name] = plugin
                                self._plugin_status[plugin.name] = plugin.status
                            await self._send_plugin_event(
                                "loaded", plugin.name, plugin.meta
                            )
                            logger.info(f"新插件发现并加载: {plugin.name}")
                    except Exception as e:
                        logger.exception(f"加载新插件 {src.path} 失败: {e}")
            else:
                # 只重载受影响的单个插件（每个独立处理）
                for name in list(impacted_plugins):
                    logger.info(f"[single-reload] 开始重载插件 {name}，原因: {reason}")
                    try:
                        await self.reload_plugin(PluginName(name))
                    except Exception as e:
                        logger.exception(f"[single-reload] 重载插件 {name} 失败: {e}")

        elif mode == ReloadModes.SMART:
            await self._send_system_event(
                SystemEvents.RELOAD_STARTED,
                {"mode": "smart", "paths": [str(p) for p in paths]},
            )
            # 收集依赖链上的所有受影响插件
            affected = set(impacted_plugins)

            # 构建反向依赖图（依赖 -> set(依赖者)）
            reverse_dep = {n: set() for n in self._plugins.keys()}
            for n, plugin in self._plugins.items():
                for dep in plugin.dependency.keys():
                    if dep in reverse_dep:
                        reverse_dep[dep].add(n)

            queue = list(impacted_plugins)
            while queue:
                cur = queue.pop()
                for dep in reverse_dep.get(cur, set()):
                    if dep not in affected:
                        affected.add(dep)
                        queue.append(dep)

            if not affected and discovered_sources:
                # 新增插件：尝试加载
                for src in discovered_sources:
                    try:
                        plugins = await self.loader.load_from_source(src)
                        for plugin in plugins:
                            with self._lock:
                                self._plugins[plugin.name] = plugin
                                self._plugin_status[plugin.name] = plugin.status
                            await self._send_plugin_event(
                                "loaded", plugin.name, plugin.meta
                            )
                            logger.info(f"新插件发现并加载: {plugin.name}")
                    except Exception as e:
                        logger.exception(f"加载新插件 {src.path} 失败: {e}")
            elif affected:
                logger.info(f"[smart-reload] 受影响插件集合: {affected}")
                await self._reload_plugin_set(affected, reason)

        else:
            # 保守做法：全部重载
            logger.warning(f"未知的重载模式 {mode}，执行全部重载")
            await self._reload_all_plugins()

        # 更新路径缓存
        try:
            self._refresh_path_cache()
        except Exception:
            pass

    def _refresh_path_cache(self) -> None:
        """从 loader._loaded_modules 中刷新路径->插件缓存映射"""
        cache: Dict[Path, Set[PluginName]] = {}
        for name, (_module_name, source) in self.loader._loaded_modules.items():
            cache.setdefault(source.path, set()).add(name)
        self._path_to_plugin_cache = cache

    def _map_paths_to_plugins(self, paths: Set[Path]) -> Set[PluginName]:
        """尝试将文件路径集合映射到插件名称集合（使用缓存与 loader 信息）。"""
        found: Set[PluginName] = set()
        for p in paths:
            # 先用缓存快速匹配
            for src_path, names in self._path_to_plugin_cache.items():
                try:
                    if (
                        src_path.is_relative_to(p)
                        or p.is_relative_to(src_path)
                        or src_path == p
                    ):
                        found.update(names)
                except Exception:
                    # is_relative_to可能抛出ValueError
                    try:
                        if str(p).startswith(str(src_path)) or str(src_path).startswith(
                            str(p)
                        ):
                            found.update(names)
                    except Exception:
                        continue

            # 精准匹配 loader 中的源
            for name, (_module_name, source) in self.loader._loaded_modules.items():
                try:
                    if source.contains_path(p):
                        found.add(name)
                except Exception:
                    continue

            # 最后尝试通过 finder 识别未知/新增的插件源，但不直接加载（由上层决定）
            try:
                src = self.plugin_finder.find_plugin_by_path(p)
                if src:
                    # 如果源对应已加载插件则添加
                    for name, (_m, s) in self.loader._loaded_modules.items():
                        if str(s.path) == str(src.path):
                            found.add(name)
            except Exception:
                pass

        return found

    async def _reload_plugin_set(
        self, plugin_names: Set[PluginName], reason: str
    ) -> None:
        """尝试按依赖顺序（先卸载依赖者）重载一组插件。"""
        # 先收集当前加载的插件对象，并记录对应的模块名以便重新加载
        current_plugins = []
        module_map: Dict[PluginName, str] = {}
        for name in plugin_names:
            p = self._plugins.get(name)
            if p:
                current_plugins.append(p)
                module_map[name] = getattr(p, "module_name", None)

        if not current_plugins:
            # 没有已加载的插件，直接尝试按单个处理（可能是新插件）
            for name in plugin_names:
                logger.info(f"[smart-reload] 重载（单插件）: {name}")
                try:
                    await self.reload_plugin(PluginName(name))
                except Exception as e:
                    logger.exception(f"[smart-reload] 插件 {name} 重新加载失败: {e}")
            return

        try:
            sorted_plugins = _topological_sort(current_plugins)
        except PluginDependencyError as e:
            logger.warning(f"依赖解析失败，退回到逐个重载: {e}")
            for name in plugin_names:
                try:
                    await self.reload_plugin(PluginName(name))
                except Exception as e:
                    logger.exception(f"重载插件 {name} 失败: {e}")
            return

        # 卸载：从依赖者到被依赖的顺序（反向）
        for p in reversed(sorted_plugins):
            try:
                logger.debug(f"[smart-reload] 卸载插件: {p.name}")
                await self.unload_plugin(p.name)
            except Exception as e:
                logger.exception(f"卸载插件 {p.name} 时出错: {e}")

        # 重新加载：按正向依赖顺序加载
        sources = await self.plugin_finder.find_plugins()
        for p in sorted_plugins:
            module_name = module_map.get(p.name)
            src = None
            if module_name:
                for s in sources:
                    if s.module_name == module_name:
                        src = s
                        break

            if src is None:
                logger.warning(f"未找到插件 {p.name} 的源，跳过加载")
                continue

            try:
                plugins = await self.loader.load_from_source(src)
                for plugin in plugins:
                    if plugin.name == p.name:
                        with self._lock:
                            self._plugins[plugin.name] = plugin
                            self._plugin_status[plugin.name] = plugin.status
                        logger.info(f"插件重载完成: {plugin.name}")
            except Exception as e:
                logger.exception(f"加载插件 {p.name} 时失败: {e}")

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
            if not self.dev_mode:
                raise
            else:
                # dev_mode下依赖失败不直接退出，返回空
                return []

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

                if not self.dev_mode:
                    if isinstance(e, (PluginVersionError, PluginDependencyError)):
                        raise
                    else:
                        raise PluginRuntimeError(str(e), plugin.name) from e
                # dev_mode下加载失败不直接退出，继续加载下一个插件
                continue

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

        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        if hasattr(self.event_bus, "close"):
            self.event_bus.close()

        # 插件有 on_unload 不需要关闭事件
        # await self._send_system_event(SystemEvents.MANAGER_STOPPED)

        logger.info("插件管理器已关闭")
