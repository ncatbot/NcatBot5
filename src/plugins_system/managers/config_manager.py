"""
配置管理器

负责插件的配置加载和保存
"""

import json
from pathlib import Path
from typing import Dict, Any
import aiofiles
import aiofiles.os
import yaml

from ..logger import logger
from ..utils.types import PluginName




class ConfigManager:
    """配置管理器
    
    负责管理插件的配置文件
    
    Attributes:
        config_base_dir: 配置基础目录
    """
    
    def __init__(self, config_base_dir: Path) -> None:
        """初始化配置管理器
        
        Args:
            config_base_dir: 配置基础目录
        """
        self.config_base_dir = config_base_dir
    
    async def load_config(self, plugin_name: PluginName) -> Dict[str, Any]:
        """加载插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件配置字典
        """
        plugin_config_dir = self.config_base_dir / plugin_name
        config_files = [
            plugin_config_dir / f"{plugin_name}.yaml",
            plugin_config_dir / f"{plugin_name}.yml",
            plugin_config_dir / f"{plugin_name}.json",
        ]
        
        for config_file in config_files:
            if await aiofiles.os.path.exists(config_file):
                try:
                    async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if config_file.suffix in ('.yaml', '.yml'):
                            return yaml.safe_load(content) or {}
                        else:
                            return json.loads(content) or {}
                except Exception as e:
                    logger.warning(f"加载配置 {config_file} 失败:\n{e}")
        
        return {}
    
    async def save_config(self, plugin_name: PluginName, config: Dict[str, Any]) -> bool:
        """保存插件配置
        
        Args:
            plugin_name: 插件名称
            config: 配置字典
            
        Returns:
            如果成功保存返回True，否则返回False
        """
        try:
            plugin_config_dir = self.config_base_dir / plugin_name
            await aiofiles.os.makedirs(plugin_config_dir, exist_ok=True)
            
            config_file = plugin_config_dir / f"{plugin_name}.yaml"
            async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(config, default_flow_style=False, allow_unicode=True))
            
            return True
        except Exception as e:
            logger.error(f"保存配置失败 {plugin_name}:\n{e}")
            return False