"""应用程序模块

提供插件系统的顶层接口和便捷使用方法
"""

from pathlib import Path
from typing import List, Union, Optional
import logging

from .abc.plugins import PluginName
from .abc.events import EventBus
from .abc.plugins import PluginManager
from .implementations.event_bus import SimpleEventBus, NonBlockingEventBus
from .managers.plugin_manager import DefaultPluginManager
from .utils.constants import DEFAULT_MAX_WORKERS, DEBUG_MODE, FeatureFlags




logger = logging.getLogger("PluginApplication")

class PluginApplication:
    """插件应用程序
    
    提供插件系统的顶层接口，简化系统初始化和使用
    
    Attributes:
        plugin_dirs: 插件目录列表
        config_dir: 配置目录
        data_dir: 数据目录
        event_bus: 事件总线实例
        plugin_manager: 插件管理器实例
        _running: 运行状态
    """
    
    def __init__(
        self,
        plugin_dirs: List[Union[Path, str]],
        config_dir: Union[Path, str] = "config",
        data_dir: Union[Path, str] = "data",
        event_bus: Optional[EventBus] = None,
        plugin_manager: Optional[PluginManager] = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
        dev_mode: bool = DEBUG_MODE
    ):
        """初始化插件应用程序
        
        Args:
            plugin_dirs: 插件目录列表
            config_dir: 配置目录
            data_dir: 数据目录
            event_bus: 事件总线实例
            plugin_manager: 插件管理器实例
            max_workers: 最大工作线程数
            dev_mode: 开发模式
        """
        self.plugin_dirs = [Path(d).expanduser().resolve() for d in plugin_dirs]
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir)
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        if event_bus:
            self.event_bus = event_bus
        else:
            match FeatureFlags.EVENT_BUS_IMPL:
                case 'SimpleEventBus':
                    self.event_bus = SimpleEventBus(max_workers=max_workers)
                case 'NonBlockingEventBus':
                    queue_maxsize = 50 if DEBUG_MODE else 1_00_00
                    self.event_bus = NonBlockingEventBus(max_workers=max_workers, queue_maxsize=queue_maxsize)
                case None:
                    raise ValueError("没有选择有效默认事件总线且没有自定义事件总线传入")
        self.plugin_manager = plugin_manager or DefaultPluginManager(
            self.plugin_dirs,
            self.config_dir,
            self.data_dir,
            self.event_bus,
            dev_mode
        )
        self._running = False
    
    async def start(self) -> None:
        """启动插件应用程序
        
        Raises:
            Exception: 当启动过程中发生错误时
        """
        if self._running:
            return
        
        logger.info("正在启动插件应用程序...")
        
        try:
            await self.plugin_manager.load_plugins()
            self._running = True
            logger.info("插件应用程序已启动")
        except Exception as e:
            logger.error(f"启动插件应用程序失败:\n{e}")
            raise
    
    async def stop(self) -> None:
        """停止插件应用程序"""
        if not self._running:
            return
        
        logger.info("正在停止插件应用程序...")
        await self.plugin_manager.close()
        self._running = False
        logger.info("插件应用程序已停止")
    
    def is_running(self) -> bool:
        """检查应用程序是否正在运行
        
        Returns:
            如果正在运行返回True，否则返回False
        """
        return self._running
    
    def get_plugin_manager(self) -> PluginManager:
        """获取插件管理器实例
        
        Returns:
            插件管理器实例
        """
        return self.plugin_manager
    
    def get_event_bus(self) -> EventBus:
        """获取事件总线实例
        
        Returns:
            事件总线实例
        """
        return self.event_bus
    
    async def reload_plugins(self) -> bool:
        """重载所有插件
        
        Returns:
            如果成功重载返回True，否则返回False
        """
        if not self._running:
            return False
        
        return await self.plugin_manager.reload_plugin(PluginName("all"))
    
    async def __aenter__(self):
        """异步上下文管理器入口
        
        Returns:
            应用程序实例
        """
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
        """
        await self.stop()