"""
插件查找器默认实现模块

包含插件的目录扫描和发现功能
"""

import zipfile
from pathlib import Path
from typing import AsyncIterable, List

import aiofiles.os

from ..abc.plugins import PluginFinder
from ..core.plugins import PluginSource, PluginSourceType
from ..logger import logger


class DefaultPluginFinder(PluginFinder):
    """默认插件查找器

    在指定目录中扫描并发现可用的插件

    Attributes:
        plugin_dirs: 插件目录列表
    """

    def __init__(self, plugin_dirs: List[Path]) -> None:
        """初始化插件查找器

        Args:
            plugin_dirs: 插件目录列表
        """
        self.plugin_dirs = plugin_dirs

    async def find_plugins(self) -> List[PluginSource]:
        """查找所有可用插件

        Returns:
            插件源列表
        """
        sources: List[PluginSource] = []

        for plugin_dir in self.plugin_dirs:
            print(plugin_dir)
            print(not await aiofiles.os.path.exists(plugin_dir))
            if not await aiofiles.os.path.exists(plugin_dir):
                continue

            async for entry in self._scan_directory(plugin_dir):
                sources.append(entry)

        return sources

    async def _scan_directory(self, directory: Path) -> AsyncIterable[PluginSource]:
        """扫描目录查找插件

        Args:
            directory: 要扫描的目录

        Yields:
            插件源对象
        """
        try:
            entries = await aiofiles.os.scandir(directory)
            for entry in entries:
                if entry.is_dir():
                    init_file = Path(entry.path) / "__init__.py"
                    if await aiofiles.os.path.exists(init_file):
                        yield PluginSource(
                            PluginSourceType.DIRECTORY, Path(entry.path), entry.name
                        )

                elif entry.is_file():
                    if entry.name.endswith(".zip"):
                        module_name = entry.name[:-4]
                        if await self._is_valid_zip_plugin(Path(entry.path)):
                            yield PluginSource(
                                PluginSourceType.ZIP_PACKAGE,
                                Path(entry.path),
                                module_name,
                            )

                    elif entry.name.endswith(".py") and entry.name != "__init__.py":
                        module_name = entry.name[:-3]
                        yield PluginSource(
                            PluginSourceType.FILE, Path(entry.path), module_name
                        )
        except OSError as e:
            logger.warning(f"扫描目录 {directory} 失败:\n{e}")

    async def _is_valid_zip_plugin(self, zip_path: Path) -> bool:
        """检查ZIP文件是否为有效的插件

        Args:
            zip_path: ZIP文件路径

        Returns:
            如果是有效插件返回True，否则返回False
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                return any(name.endswith("__init__.py") for name in zf.namelist())
        except (zipfile.BadZipFile, OSError):
            return False
