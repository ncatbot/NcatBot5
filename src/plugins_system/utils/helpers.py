"""
工具函数

包含插件系统中使用的各种工具函数
"""

import functools
import logging
import uuid
import re
import asyncio
from typing import Union, Pattern, Tuple, Any, Callable
from functools import partial


from .constants import NAMESPACE

from ..logger import logger


def handler_to_uuid(func: Callable) -> uuid.UUID:
    """将处理器函数转换为确定性UUID
    
    通过处理器的模块名和限定名生成唯一的确定性UUID
    
    Args:
        func: 要转换的处理器函数
        
    Returns:
        生成的UUID
        
    Raises:
        ValueError: 当函数嵌套partial超过32层时
    """
    for _ in range(32):
        if isinstance(func, functools.partial):
            func = func.func
        else:
            break
    else:
        raise ValueError("函数嵌套partial超过32层")
    
    mod = getattr(func, "__module__", "")
    qual = getattr(func, "__qualname__", None) or getattr(func, "__name__", "<unknown>")
    name = f"{mod}.{qual}"
    return uuid.uuid5(NAMESPACE, name)


def compile_event_pattern(event_pattern: Union[str, Pattern[str]]) -> Tuple[Union[str, Pattern[str]], bool]:
    """编译事件模式
    
    支持普通字符串模式和正则表达式模式（以're:'开头）
    
    Args:
        event_pattern: 事件模式字符串或已编译的正则表达式
        
    Returns:
        元组，包含编译后的事件模式和是否为正则表达式的标志
    """
    if isinstance(event_pattern, Pattern):
        return event_pattern, True
    
    # 检查是否是正则表达式模式
    if event_pattern.startswith('re:'):
        pattern_str = event_pattern[3:]
        try:
            compiled_pattern = re.compile(pattern_str)
            return compiled_pattern, True
        except re.error as e:
            logger.warning(f"无效的正则表达式模式 '{pattern_str}': {e}, 将作为普通字符串处理")
            return event_pattern, False
    
    # 普通字符串模式
    return event_pattern, False


def _get_current_task_name() -> str | None:
    """获取当前asyncio任务的名称
    
    Returns:
        当前任务名称，如果不在事件循环中则返回None
    """
    try:
        task = asyncio.current_task()
        if task is None:
            return None
        name_getter = getattr(task, 'get_name', None)
        if callable(name_getter):
            return name_getter()
        return str(task)
    except RuntimeError:
        return None


async def run_any(func: Callable, *args, **kwargs) -> Any:
    """运行任意函数（同步或异步）
    
    自动检测函数类型并选择合适的执行方式
    
    Args:
        func: 要执行的函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        函数的执行结果
    """
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    loop = asyncio.get_running_loop()
    bound = partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, bound)


def _version_satisfies(found: str, version_spec: str) -> bool:
    """检查版本是否满足规范
    
    Args:
        found: 发现的版本号
        version_spec: 版本规范字符串
        
    Returns:
        如果版本满足规范则返回True，否则返回False
        
    Raises:
        PluginValidationError: 当版本或规范格式无效时
    """
    from packaging.version import Version, InvalidVersion
    from packaging.specifiers import SpecifierSet, InvalidSpecifier
    
    try:
        if version_spec.strip() and not any(c in version_spec for c in "<>!=~"):
            version_spec = "==" + version_spec
        specifier = SpecifierSet(version_spec)
        found_version = Version(found)
        return specifier.contains(found_version)
    except (InvalidVersion, InvalidSpecifier) as e:
        from ..exceptions import PluginValidationError
        raise PluginValidationError(f"无效的版本: found={found}, spec={version_spec}, error={e}")