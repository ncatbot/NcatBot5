"""
延迟装饰器解析器模块
"""

from __future__ import annotations

import threading
from abc import ABC, ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from ..abc.events import EventBus
    from .plugins import Plugin


class _LazyResolverMeta(ABCMeta):
    """元类，用于自动注册解析器子类"""

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if not hasattr(cls, "_resolvers"):
            cls._resolvers = []
        if ABC not in bases and name != "LazyDecoratorResolver":
            cls._resolvers.append(cls)


class LazyDecoratorResolver(ABC, metaclass=_LazyResolverMeta):
    """
    增强的延迟装饰器解析器基类

    新特性：
    1. 支持隐式命名空间：通过 tag 和 space 类变量自动检查
    2. 提供 kwd 属性快捷访问命名空间数据
    3. 自动混入类检查
    """

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _resolved: ClassVar[List[TypeVar["LazyDecoratorResolver"]]] = []
    _resolvers: ClassVar[List[TypeVar["LazyDecoratorResolver"]]] = []

    # 子类可以覆盖这些类变量
    tag: ClassVar[Union[str, Set[str]]] = None  # 装饰器标签
    space: ClassVar[str] = None  # 命名空间
    required_mixin: ClassVar[Type] = None  # 需要的混入类

    def __init__(self, attr_name: str = "__mate__") -> None:
        self.attr_name = attr_name
        self._current_func: Optional[Callable] = None
        self._current_kwd: Optional[Dict[str, Any]] = None

    @classmethod
    def get_all_resolvers(cls) -> List[TypeVar["LazyDecoratorResolver"]]:
        """获取所有注册的解析器实例"""
        with cls._lock:
            if not cls._resolved:
                cls._resolved = [resolver() for resolver in cls._resolvers]
            return cls._resolved.copy()

    def check(self, plugin: Plugin, func: Callable, event_bus: EventBus) -> bool:
        """
        默认的检查方法 - 支持隐式命名空间检查
        """
        # NOTE 不要操作数据，这会导致检查副作用
        # 获取原始函数（处理绑定方法）
        original_func = func
        if hasattr(func, "__func__"):
            original_func = func.__func__

        mate_data = self.get_mate_data(original_func)
        if not mate_data:
            return False

        # 检查标签匹配
        if not self._check_tags(mate_data):
            return False

        # 检查命名空间存在
        if self.space and self.space not in mate_data:
            return False

        # 检查混入类要求
        if self.required_mixin and not plugin.has_mixin(self.required_mixin):
            return False

        # 缓存当前函数和命名空间数据用于后续处理
        self._current_func = func
        self._current_kwd = mate_data.get(self.space, {}) if self.space else mate_data

        return True

    def _check_tags(self, mate_data: Dict[str, Any]) -> bool:
        """检查标签匹配"""
        tags = mate_data.get("tag", set())

        if self.tag is None:
            # 没有指定标签，匹配任何有标签的函数
            return bool(tags)

        if isinstance(self.tag, str):
            # 单个标签匹配
            return self.tag in tags
        elif isinstance(self.tag, set):
            # 多个标签匹配（需要全部匹配）
            return self.tag.issubset(tags)

        return False

    @property
    def kwd(self) -> Dict[str, Any]:
        """
        快捷访问当前函数的命名空间数据

        使用示例：
            service_name = self.kwd['service_name']
            state_checker = self.kwd.get('state_checker')
        """
        if self._current_kwd is None:
            return {}
        return self._current_kwd

    def get_kwd(self, func: Optional[Callable] = None) -> Dict[str, Any]:
        """
        获取指定函数的命名空间数据

        Args:
            func: 目标函数，如果为None则使用当前缓存的函数

        Returns:
            命名空间数据字典
        """
        if func is None:
            return self.kwd

        # 获取原始函数
        original_func = func
        if hasattr(func, "__func__"):
            original_func = func.__func__

        mate_data = self.get_mate_data(original_func)
        if not mate_data:
            return {}

        return mate_data.get(self.space, {}) if self.space else mate_data

    @staticmethod
    def has_all_attrs(data: Dict[str, Any], *specs: Tuple[str, Type]) -> bool:
        """增强的属性检查工具"""
        return all(k in data and type(data[k]) is t for k, t in specs)

    def get_mate_data(self, func: Callable) -> Optional[Dict[str, Any]]:
        """安全获取装饰器元数据"""
        return getattr(func, self.attr_name, None)

    def clear_cache(self) -> None:
        """清理当前缓存"""
        self._current_func = None
        self._current_kwd = None

    @abstractmethod
    def handle(self, plugin: Plugin, func: Callable, event_bus: EventBus) -> None:
        """执行延迟绑定逻辑"""


# -------------------- 基础设施 --------------------
def tagged_decorator(
    tag: str, *, space: str = "default", **meta
) -> Callable[[Callable], Callable]:
    """
    增强的标签装饰器工厂

    创建具有隐式命名空间的装饰器，元数据组织为：
    {
        'tag': {tag, ...},           # 标签集合
        space: {**meta},             # 命名空间数据
        ...                          # 其他命名空间
    }
    """

    def _marker(func: Callable) -> Callable:
        if not hasattr(func, "__mate__"):
            setattr(func, "__mate__", {"tag": set()})

        mate: Dict[str, Any] = getattr(func, "__mate__")
        mate["tag"].add(tag)

        if space not in mate:
            mate[space] = {}
        mate[space].update(meta)

        return func

    return _marker


# -------------------- 快捷装饰器创建工具 --------------------
def create_namespaced_decorator(
    tag: str,
    space: str,
    **default_meta: Any,
) -> Callable[..., Callable]:
    """
    创建具有命名空间的装饰器工厂

    Args:
        tag: 装饰器标签
        space: 命名空间
        resolver_class: 对应的解析器类
        default_meta: 默认元数据

    Returns:
        装饰器工厂函数
    """

    def decorator_factory(**meta) -> Callable[[Callable], Callable]:
        # 合并默认元数据和用户提供的元数据
        combined_meta = {**default_meta, **meta}
        return tagged_decorator(tag, space=space, **combined_meta)

    return decorator_factory
