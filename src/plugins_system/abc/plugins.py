"""
插件相关抽象基类

定义插件管理器、加载器和查找器的接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from ..utils.types import PluginName
from ..core.plugins import Plugin, PluginSource, PluginStatus


class PluginManager(ABC):
    """插件管理器抽象基类
    
    负责插件的生命周期管理
    """
    
    @abstractmethod
    async def load_plugins(self) -> List[Plugin]:
        """加载所有插件
        
        Returns:
            成功加载的插件列表
        """
        pass
    
    @abstractmethod
    async def unload_plugin(self, plugin_name: PluginName) -> bool:
        """卸载指定插件
        
        Args:
            plugin_name: 要卸载的插件名称
            
        Returns:
            如果成功卸载返回True，否则返回False
        """
        pass
    
    @abstractmethod
    async def start_plugin(self, plugin_name: PluginName) -> bool:
        """启动指定插件
        
        Args:
            plugin_name: 要启动的插件名称
            
        Returns:
            如果成功启动返回True，否则返回False
        """
        pass
    
    @abstractmethod
    async def stop_plugin(self, plugin_name: PluginName) -> bool:
        """停止指定插件
        
        Args:
            plugin_name: 要停止的插件名称
            
        Returns:
            如果成功停止返回True，否则返回False
        """
        pass
    
    @abstractmethod
    async def reload_plugin(self, plugin_name: PluginName) -> bool:
        """重载指定插件
        
        Args:
            plugin_name: 要重载的插件名称
            
        Returns:
            如果成功重载返回True，否则返回False
        """
        pass
    
    @abstractmethod
    def get_plugin(self, plugin_name: PluginName) -> Optional[Plugin]:
        """获取指定插件实例
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件实例，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    def list_plugins(self, cls: bool = False) -> List[PluginName | Plugin]:
        """获取所有插件名称列表
        
        Returns:
            插件名称列表
        """
        pass
    
    @abstractmethod
    def list_plugins_with_status(self) -> Dict[PluginName, 'PluginStatus']:
        """获取插件状态映射
        
        Returns:
            插件名称到状态的映射
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭插件管理器"""
        pass


class PluginLoader(ABC):
    """插件加载器抽象基类
    
    负责从不同源加载插件
    """
    
    @abstractmethod
    async def load_from_source(self, source: PluginSource) -> List[Plugin]:
        """从源加载插件
        
        Args:
            source: 插件源
            
        Returns:
            加载的插件列表
        """
        pass
    
    @abstractmethod
    async def unload_plugin_module(self, plugin_name: PluginName) -> bool:
        """卸载插件模块
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            如果成功卸载返回True，否则返回False
        """
        pass


class PluginFinder(ABC):
    """插件查找器抽象基类
    
    负责在指定目录中查找插件
    """
    
    @abstractmethod
    async def find_plugins(self) -> List[PluginSource]:
        """查找所有可用插件
        
        Returns:
            插件源列表
        """
        pass