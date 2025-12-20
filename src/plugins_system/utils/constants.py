"""常量定义模块

包含插件系统的所有常量和功能开关定义
"""

from enum import Enum, auto
from typing import Final, Literal
from uuid import UUID

# 框架级常量
PROTOCOL_VERSION: Final[int] = 1
"""协议版本号"""

DEFAULT_MAX_WORKERS: Final[int | None] = None
"""默认最大工作线程数"""

DEFAULT_REQUEST_TIMEOUT: Final[float] = 10.0
"""默认请求超时时间（秒）"""

DEBUG_MODE: Final[bool] = True
"""调试模式开关"""

# UUID命名空间（用于确定性UUID生成）
# str2uuid = lambda s: __import__('uuid').UUID(__import__('hashlib').md5(s.encode('utf-8')).hexdigest())
# NAMESPACE = str2uuid("它穿越语言的边界，用一声轻喵，抵达她心底最柔软的故乡")
NAMESPACE = UUID("a980f9a7-09f1-91a8-61ba-20374cd0c393")
"""UUID命名空间常量"""


class FeatureFlags:
    """功能开关常量类

    控制插件系统的各种功能是否启用，便于在开发和部署时进行配置
    """

    # # TODO? 解决 os.chdir 进程级切换?我吗?喵?
    # ENABLE_RUN_IN_DATA_DIR: Final[bool] = False
    """是否启用数据目录执行功能

    当启用时，插件的事件处理器可以在插件的数据目录中执行，
    便于文件操作等需要特定工作目录的场景"""

    EVENT_BUS_IMPL: Final[
        Literal["SimpleEventBus", "NonBlockingEventBus", None]
    ] = "SimpleEventBus"

    INTERCEPTOR_SHORT_CIRCUIT: Final[bool] = False


class SystemEvents:
    """系统事件常量类

    包含所有系统级事件的事件名称
    """

    # 插件生命周期事件
    PLUGIN_LOADED = "system.plugin.loaded"
    """插件加载完成事件"""

    PLUGIN_UNLOADED = "system.plugin.unloaded"
    """插件卸载完成事件"""

    PLUGIN_STARTED = "system.plugin.started"
    """插件启动完成事件"""

    PLUGIN_STOPPED = "system.plugin.stopped"
    """插件停止完成事件"""

    # 管理器生命周期事件
    MANAGER_STARTING = "system.manager.starting"
    """管理器正在启动事件"""

    MANAGER_STARTED = "system.manager.started"
    """管理器启动完成事件"""

    MANAGER_STOPPING = "system.manager.stopping"
    """管理器正在停止事件"""

    # 插件有 on_unload 不需要关闭事件
    # MANAGER_STOPPED = "system.manager.stopped"
    # """管理器停止完成事件"""

    # 系统级事件
    ALL_PLUGINS_LOADED = "system.all_plugins_loaded"
    """所有插件加载完成事件"""

    DEPENDENCY_RESOLVED = "system.dependency_resolved"
    """依赖解析完成事件"""

    RELOAD_REQUESTED = "system.reload_requested"
    """重载请求事件"""

    # 错误事件
    LOAD_ERROR = "system.load_error"
    """加载错误事件"""

    RUNTIME_ERROR = "system.runtime_error"
    """运行时错误事件"""

    DEPENDENCY_ERROR = "system.dependency_error"
    """依赖错误事件"""

    # 功能相关事件
    FEATURE_FLAG_CHANGED = "system.feature_flag_changed"
    """功能开关变更事件"""


class PluginState(Enum):
    """插件状态枚举

    表示插件在其生命周期中可能处于的不同状态
    """

    LOADED = auto()
    """已加载状态"""

    RUNNING = auto()
    """运行中状态"""

    STOPPED = auto()
    """已停止状态"""

    FAILED = auto()
    """失败状态"""

    UNLOADED = auto()
    """已卸载状态"""


class PluginSourceType(Enum):
    """插件源类型枚举

    表示插件来源的不同类型
    """

    DIRECTORY = "directory"
    """目录类型插件源"""

    ZIP_PACKAGE = "zip"
    """ZIP包类型插件源"""

    FILE = "file"
    """文件类型插件源"""
