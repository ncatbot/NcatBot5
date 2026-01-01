import asyncio
import hashlib
import io
import logging
import mimetypes
import os
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, BinaryIO, Dict, Literal, Optional, Union
from urllib.parse import urlparse

import aiofiles
import aiohttp

# 配置常量
DEFAULT_CACHE_DIR = tempfile.gettempdir() + "/resource_cache"
DEFAULT_MAX_CACHE_SIZE = 128 * 1024 * 1024  # 128MB
DEFAULT_CACHE_TTL = 3600  # 1小时
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_TIMEOUT = 30

# 特殊常量：忽略缓存大小限制
IGNORE_CACHE_LIMIT = False

# 日志
logger = logging.getLogger(__name__)


class CachePolicy(Enum):
    """缓存策略"""

    DEFAULT = "default"  # 默认策略，受大小限制
    IGNORE_LIMIT = "ignore_limit"  # 忽略大小限制
    NO_CACHE = "no_cache"  # 不缓存


class CacheManager:
    """改进的缓存管理器"""

    def __init__(
        self,
        cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR,
        max_size: int = DEFAULT_MAX_CACHE_SIZE,
        ttl: int = DEFAULT_CACHE_TTL,
        ignore_limit: bool = IGNORE_CACHE_LIMIT,
    ):
        self.cache_dir = Path(cache_dir)
        self.max_size = max_size
        self.ttl = ttl
        self.ignore_limit = ignore_limit

        # 创建缓存目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 初始化访问时间记录
        self.access_times = {}
        self._load_access_times()

        logger.info(
            f"CacheManager initialized: dir={self.cache_dir}, max_size={self._format_size(max_size)}, ignore_limit={ignore_limit}"
        )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化字节大小为可读字符串"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"

    def _load_access_times(self):
        """加载访问时间记录"""
        access_file = self.cache_dir / ".access_times"
        if access_file.exists():
            try:
                with open(access_file, "r") as f:
                    for line in f:
                        if ":" in line:
                            key, timestamp = line.strip().split(":", 1)
                            self.access_times[key] = float(timestamp)
            except Exception as e:
                logger.warning(f"Failed to load access times: {e}")

    def _save_access_times(self):
        """保存访问时间记录"""
        access_file = self.cache_dir / ".access_times"
        try:
            with open(access_file, "w") as f:
                for key, timestamp in self.access_times.items():
                    f.write(f"{key}:{timestamp}\n")
        except Exception as e:
            logger.warning(f"Failed to save access times: {e}")

    def _get_cache_key(self, url: str) -> str:
        """生成缓存键"""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cache_path(self, key: str, filename: Optional[str] = None) -> Path:
        """获取缓存文件路径"""
        if filename:
            # 清理文件名中的非法字符
            safe_filename = "".join(
                c for c in filename if c.isalnum() or c in ("-", "_", ".")
            )
            return self.cache_dir / f"{key}_{safe_filename}"
        return self.cache_dir / key

    def get(self, url: str) -> Optional[Path]:
        """获取缓存文件路径"""
        key = self._get_cache_key(url)

        # 查找匹配的文件
        for file in self.cache_dir.glob(f"{key}*"):
            if file.is_file():
                # 检查是否过期
                if self._is_expired(file, key):
                    try:
                        file.unlink()
                        if key in self.access_times:
                            del self.access_times[key]
                    except Exception as e:
                        logger.debug(f"Failed to delete expired cache: {e}")
                    return None

                # 更新访问时间
                self.access_times[key] = time.time()
                self._save_access_times()
                return file
        return None

    def _is_expired(self, file: Path, key: str) -> bool:
        """检查缓存是否过期"""
        # 检查TTL
        file_mtime = file.stat().st_mtime
        if time.time() - file_mtime > self.ttl:
            return True

        # 检查访问时间
        if key in self.access_times:
            if time.time() - self.access_times[key] > self.ttl:
                return True

        return False

    async def aput(
        self,
        url: str,
        data: bytes,
        filename: Optional[str] = None,
        cache_policy: CachePolicy = CachePolicy.DEFAULT,
    ) -> Optional[Path]:
        """
        异步保存到缓存

        Args:
            url: 资源URL
            data: 数据
            filename: 文件名
            cache_policy: 缓存策略

        Returns:
            缓存路径或None（如果未缓存）
        """
        data_size = len(data)

        # 检查是否应该缓存
        if cache_policy == CachePolicy.NO_CACHE:
            logger.debug(f"Skipping cache for {url} (NO_CACHE policy)")
            return None

        # 检查单文件是否超过缓存限制（除非忽略限制）
        if cache_policy != CachePolicy.IGNORE_LIMIT and data_size > self.max_size:
            logger.warning(
                f"File too large to cache: {self._format_size(data_size)} "
                f"> max cache size {self._format_size(self.max_size)}. URL: {url}"
            )
            return None

        key = self._get_cache_key(url)
        cache_path = self._get_cache_path(key, filename)

        # 检查是否需要清理空间
        if cache_policy != CachePolicy.IGNORE_LIMIT:
            if not self._ensure_space(data_size):
                logger.warning(f"Insufficient cache space for {url}")
                return None

        try:
            # 写入文件
            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(data)

            # 更新访问时间
            self.access_times[key] = time.time()
            self._save_access_times()

            logger.debug(f"Cached {self._format_size(data_size)} to {cache_path}")
            return cache_path

        except Exception as e:
            logger.error(f"Failed to cache {url}: {e}")
            # 如果写入失败，删除可能损坏的文件
            try:
                if cache_path.exists():
                    cache_path.unlink()
            except Exception:
                pass
            return None

    def _ensure_space(self, required_size: int) -> bool:
        """
        确保有足够的缓存空间

        Returns:
            True如果有足够空间，False否则
        """
        current_size = self._get_cache_size()

        if current_size + required_size <= self.max_size:
            return True

        # 需要清理空间
        return self._cleanup_space(required_size)

    def _get_cache_size(self) -> int:
        """获取缓存总大小"""
        total = 0
        for file in self.cache_dir.glob("*"):
            if file.is_file() and not file.name.startswith("."):
                try:
                    total += file.stat().st_size
                except OSError:
                    continue
        return total

    def _cleanup_space(self, required_size: int) -> bool:
        """清理缓存空间"""
        current_size = self._get_cache_size()

        # 即使清空所有缓存也不够
        if required_size > self.max_size:
            return False

        # 收集文件信息
        files_with_info = []
        for file in self.cache_dir.glob("*"):
            if file.is_file() and not file.name.startswith("."):
                try:
                    file_size = file.stat().st_size
                    file_mtime = file.stat().st_mtime
                    # 提取key
                    key = file.name.split("_")[0] if "_" in file.name else file.name
                    access_time = self.access_times.get(key, file_mtime)
                    files_with_info.append(
                        {
                            "path": file,
                            "size": file_size,
                            "access_time": access_time,
                            "mtime": file_mtime,
                        }
                    )
                except OSError:
                    continue

        # 按访问时间排序（最久未访问的先删除）
        files_with_info.sort(key=lambda x: x["access_time"])

        # 删除最旧的文件直到有足够空间
        for file_info in files_with_info:
            if current_size + required_size <= self.max_size:
                break

            try:
                file_info["path"].unlink()
                current_size -= file_info["size"]

                # 从访问时间记录中删除
                key = (
                    file_info["path"].name.split("_")[0]
                    if "_" in file_info["path"].name
                    else file_info["path"].name
                )
                if key in self.access_times:
                    del self.access_times[key]

                logger.debug(
                    f"Cleaned cache file: {file_info['path'].name} ({self._format_size(file_info['size'])})"
                )
            except Exception as e:
                logger.warning(f"Failed to delete cache file {file_info['path']}: {e}")

        self._save_access_times()

        # 检查清理后是否足够
        current_size = self._get_cache_size()
        if current_size + required_size <= self.max_size:
            return True
        else:
            logger.warning(
                f"Failed to free enough space. Current: {self._format_size(current_size)}, "
                f"Required: {self._format_size(required_size)}, "
                f"Max: {self._format_size(self.max_size)}"
            )
            return False

    def clear(self):
        """清空缓存"""
        try:
            deleted_count = 0
            deleted_size = 0

            for file in self.cache_dir.glob("*"):
                if file.is_file():
                    try:
                        file_size = file.stat().st_size
                        file.unlink()
                        deleted_count += 1
                        deleted_size += file_size
                    except Exception:
                        pass

            self.access_times.clear()
            self._save_access_times()

            logger.info(
                f"Cache cleared: {deleted_count} files, {self._format_size(deleted_size)}"
            )

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_size = 0
        file_count = 0
        oldest_access = None
        newest_access = None

        for file in self.cache_dir.glob("*"):
            if file.is_file() and not file.name.startswith("."):
                try:
                    total_size += file.stat().st_size
                    file_count += 1
                except OSError:
                    continue

        if self.access_times:
            timestamps = list(self.access_times.values())
            if timestamps:
                oldest_access = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(min(timestamps))
                )
                newest_access = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(max(timestamps))
                )

        return {
            "total_size": total_size,
            "total_size_formatted": self._format_size(total_size),
            "file_count": file_count,
            "max_size": self.max_size,
            "max_size_formatted": self._format_size(self.max_size),
            "usage_percentage": (
                (total_size / self.max_size * 100) if self.max_size > 0 else 0
            ),
            "ttl": self.ttl,
            "ttl_formatted": f"{self.ttl // 3600}h {(self.ttl % 3600) // 60}m",
            "oldest_access": oldest_access,
            "newest_access": newest_access,
            "ignore_limit": self.ignore_limit,
            "cache_dir": str(self.cache_dir),
        }


@dataclass
class ResourceInfo:
    """资源信息"""

    uri: str
    filename: Optional[str] = None
    mimetype: Optional[str] = None
    size: Optional[int] = None
    cached: bool = False
    cache_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Resource:
    """资源类，类似文件对象"""

    def __init__(
        self,
        uri: str,
        mode: Literal["rb", "r"] = "rb",
        session: Optional[aiohttp.ClientSession] = None,
        cache_manager: Optional[CacheManager] = None,
        use_cache: bool = True,
        cache_policy: CachePolicy = CachePolicy.DEFAULT,
        timeout: int = DEFAULT_TIMEOUT,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        """
        初始化资源

        Args:
            uri: 资源URI（URL或文件路径）
            mode: 打开模式（'rb'为二进制读取，'r'为文本读取）
            session: aiohttp会话
            cache_manager: 缓存管理器
            use_cache: 是否使用缓存（仅对URL有效）
            cache_policy: 缓存策略
            timeout: 超时时间（秒）
            chunk_size: 块大小
        """
        self.uri = uri
        self.mode = mode
        self.session = session
        self.cache_manager = cache_manager
        self.use_cache = use_cache
        self.cache_policy = cache_policy
        self.timeout = timeout
        self.chunk_size = chunk_size

        self._info: Optional[ResourceInfo] = None
        self._file_obj: Optional[BinaryIO] = None
        self._async_file_obj = None
        self._should_close_session = False
        self._is_url = self._is_url_resource()
        self._local_file_path: Optional[Path] = None

        logger.debug(
            f"Resource initialized: uri={uri}, is_url={self._is_url}, use_cache={use_cache}, cache_policy={cache_policy}"
        )

    def _is_url_resource(self) -> bool:
        """判断是否为URL资源"""
        parsed = urlparse(self.uri)
        return bool(parsed.scheme and parsed.netloc)

    def _get_filename_from_url(self, url: str) -> str:
        """从URL提取文件名"""
        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = os.path.basename(path)
            if filename:
                return filename
        return "download.bin"

    def _guess_mimetype(self, filename: Optional[str]) -> str:
        """猜测MIME类型"""
        if not filename:
            return "application/octet-stream"
        mimetype, _ = mimetypes.guess_type(filename)
        return mimetype or "application/octet-stream"

    async def _fetch_from_url(self) -> ResourceInfo:
        """从URL获取资源"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            self._should_close_session = True

        # 检查缓存
        cache_path = None
        if self.use_cache and self.cache_manager:
            cache_path = self.cache_manager.get(self.uri)
            if cache_path:
                logger.debug(f"Using cached resource: {self.uri}")
                size = cache_path.stat().st_size
                # 从缓存文件名中提取原始文件名
                cache_filename = cache_path.name
                if "_" in cache_filename:
                    # 格式: {key}_{filename}
                    filename = "_".join(cache_filename.split("_")[1:])
                else:
                    filename = cache_filename

                mimetype = self._guess_mimetype(filename)

                return ResourceInfo(
                    uri=self.uri,
                    filename=filename,
                    mimetype=mimetype,
                    size=size,
                    cached=True,
                    cache_path=cache_path,
                    metadata={"source": "cache"},
                )

        # 从网络获取
        async with self.session.get(self.uri, timeout=self.timeout) as response:
            response.raise_for_status()

            # 获取文件名
            filename = self._get_filename_from_url(self.uri)

            # 从Content-Disposition获取文件名
            content_disposition = response.headers.get("Content-Disposition", "")
            if "filename=" in content_disposition:
                import re

                match = re.search(
                    r'filename=["\']?([^"\']+)["\']?', content_disposition
                )
                if match:
                    filename = match.group(1)

            # 获取MIME类型
            mimetype = response.headers.get("Content-Type", "").split(";")[0]
            if not mimetype:
                mimetype = self._guess_mimetype(filename)

            # 读取数据
            data = await response.read()
            size = len(data)

            # 保存到缓存（只缓存网络资源）
            if self.use_cache and self.cache_manager:
                cache_path = await self.cache_manager.aput(
                    self.uri, data, filename, cache_policy=self.cache_policy
                )
                if cache_path:
                    logger.debug(f"Cached resource: {self.uri} ({size} bytes)")
                else:
                    logger.debug(f"Resource not cached: {self.uri}")

            metadata = {
                "source": "network",
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
                "status_code": response.status,
                "headers": dict(response.headers),
            }

            return ResourceInfo(
                uri=self.uri,
                filename=filename,
                mimetype=mimetype,
                size=size,
                cached=False,
                cache_path=cache_path,
                metadata=metadata,
            )

    async def _open_file(self) -> ResourceInfo:
        """打开文件资源（不缓存本地文件）"""
        path = Path(self.uri)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {self.uri}")

        size = path.stat().st_size
        mimetype = self._guess_mimetype(path.name)

        # 记住本地文件路径，用于后续打开
        self._local_file_path = path

        return ResourceInfo(
            uri=self.uri,
            filename=path.name,
            mimetype=mimetype,
            size=size,
            cached=False,
            cache_path=path,  # 本地文件路径，但不是缓存
            metadata={"source": "local"},
        )

    async def __aenter__(self):
        """异步上下文管理器入口"""
        # 获取资源信息
        if self._is_url:
            self._info = await self._fetch_from_url()
        else:
            self._info = await self._open_file()

        # 打开文件对象
        if self._info.cached and self._info.cache_path:
            # 从缓存打开
            self._async_file_obj = aiofiles.open(self._info.cache_path, self.mode)
            self._file_obj = await self._async_file_obj.__aenter__()
        elif self._local_file_path:
            # 打开本地文件（不缓存）
            self._async_file_obj = aiofiles.open(self._local_file_path, self.mode)
            self._file_obj = await self._async_file_obj.__aenter__()
        else:
            # 对于未缓存的网络资源，使用BytesIO
            data = await self._fetch_data()
            self._file_obj = io.BytesIO(data)

        return self

    async def _fetch_data(self) -> bytes:
        """获取资源数据（用于未缓存的情况）"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            self._should_close_session = True

        async with self.session.get(self.uri, timeout=self.timeout) as response:
            response.raise_for_status()
            return await response.read()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        # 关闭文件对象
        if self._async_file_obj:
            await self._async_file_obj.__aexit__(exc_type, exc_val, exc_tb)

        # 关闭会话
        if self._should_close_session and self.session:
            await self.session.close()
            self.session = None

    async def read(self, size: int = -1) -> bytes:
        """读取数据"""
        if isinstance(self._file_obj, io.BytesIO):
            return self._file_obj.read(size)
        elif hasattr(self._file_obj, "read"):
            if size == -1:
                return await self._file_obj.read()
            else:
                return await self._file_obj.read(size)
        else:
            raise ValueError("File object not available")

    async def read_chunk(self) -> bytes:
        """读取一个块"""
        return await self.read(self.chunk_size)

    async def readline(self) -> bytes:
        """读取一行"""
        if isinstance(self._file_obj, io.BytesIO):
            return self._file_obj.readline()
        elif hasattr(self._file_obj, "readline"):
            return await self._file_obj.readline()
        else:
            # 模拟读取行
            data = b""
            while True:
                chunk = await self.read(1)
                if not chunk:
                    break
                data += chunk
                if chunk == b"\n":
                    break
            return data

    async def readlines(self) -> list:
        """读取所有行"""
        lines = []
        while True:
            line = await self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """异步迭代器"""
        while True:
            chunk = await self.read_chunk()
            if not chunk:
                break
            yield chunk

    @property
    def info(self) -> ResourceInfo:
        """获取资源信息"""
        if self._info is None:
            raise ValueError("Resource not opened. Use 'async with' context manager.")
        return self._info

    @property
    def filename(self) -> Optional[str]:
        """获取文件名"""
        return self._info.filename if self._info else None

    @property
    def size(self) -> Optional[int]:
        """获取文件大小"""
        return self._info.size if self._info else None

    @property
    def mimetype(self) -> Optional[str]:
        """获取MIME类型"""
        return self._info.mimetype if self._info else None

    @property
    def cached(self) -> bool:
        """是否来自缓存"""
        return self._info.cached if self._info else False


# 工厂函数
async def resource_open(
    uri: str,
    mode: str = "rb",
    session: Optional[aiohttp.ClientSession] = None,
    cache_manager: Optional[CacheManager] = None,
    use_cache: bool = True,
    cache_policy: CachePolicy = CachePolicy.DEFAULT,
    timeout: int = DEFAULT_TIMEOUT,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Resource:
    """
    打开资源（类似open()函数）

    Args:
        uri: 资源URI
        mode: 打开模式
        session: aiohttp会话
        cache_manager: 缓存管理器
        use_cache: 是否使用缓存
        cache_policy: 缓存策略
        timeout: 超时时间
        chunk_size: 块大小

    Returns:
        Resource对象
    """
    return Resource(
        uri, mode, session, cache_manager, use_cache, cache_policy, timeout, chunk_size
    )


# 批量获取工具
class ResourceFetcher:
    """批量资源获取工具"""

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        max_concurrent: int = 5,
        default_timeout: int = DEFAULT_TIMEOUT,
        default_cache_policy: CachePolicy = CachePolicy.DEFAULT,
    ):
        self.cache_manager = cache_manager
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.default_cache_policy = default_cache_policy
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch(
        self,
        uris: list,
        use_cache: bool = True,
        cache_policy: Optional[CachePolicy] = None,
    ) -> list:
        """批量获取资源"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        cache_policy = cache_policy or self.default_cache_policy

        async def fetch_one(uri):
            async with semaphore:
                try:
                    async with await resource_open(
                        uri,
                        session=self.session,
                        cache_manager=self.cache_manager,
                        use_cache=use_cache,
                        cache_policy=cache_policy,
                        timeout=self.default_timeout,
                    ) as res:
                        data = await res.read()
                        return {
                            "uri": uri,
                            "data": data,
                            "info": res.info,
                            "error": None,
                        }
                except Exception as e:
                    logger.error(f"Failed to fetch {uri}: {e}")
                    return {"uri": uri, "data": None, "info": None, "error": str(e)}

        tasks = [fetch_one(uri) for uri in uris]
        return await asyncio.gather(*tasks)
