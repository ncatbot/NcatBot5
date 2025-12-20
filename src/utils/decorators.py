# decorators.py
"""
依赖注入装饰器 - 简化版本
"""
import functools
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class ClientNotBoundError(ValueError):
    """客户端未绑定错误"""

    pass


def requires_client(func: F) -> F:
    """检查对象是否绑定了客户端"""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_client") or self._client is None:
            raise ClientNotBoundError(
                f"{self.__class__.__name__} 未绑定 IMClient，无法执行 {func.__name__} 操作"
            )
        return await func(self, *args, **kwargs)

    return wrapper
