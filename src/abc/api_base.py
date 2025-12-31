# api_base.py
"""
纯通信层 - 只负责发送和自动包装，不定义具体接口
"""
import asyncio
import functools
import inspect
from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


@dataclass
class ApiRequest(Generic[T]):
    """API请求定义"""

    activity: str  # 操作名称
    data: Dict[str, Any]  # 请求数据
    headers: Optional[Dict[str, str]] = None  # 可选的请求头


class ApiMeta(ABCMeta):
    """API元类 - 自动包装所有方法到invoke"""

    abc = True

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # 跳过抽象基类
        if cls.abc:
            return cls

        assert isinstance(namespace, dict)

        # 自动包装所有公共的异步方法
        for attr_name, attr_value in namespace.items():
            assert isinstance(attr_name, str)

            # 跳过特殊方法本身
            if attr_name in ("invoke", "call"):
                continue

            if attr_name.startswith("_"):
                continue

            if asyncio.iscoroutinefunction(attr_value):
                # 创建包装器
                def make_wrapper(original_method):
                    @functools.wraps(original_method)
                    async def wrapper(self, *args, **kwargs):
                        assert isinstance(self, APIBase)

                        # 调用原始方法获取请求定义
                        original_result = await original_method(self, *args, **kwargs)

                        # 处理不同类型的返回值
                        if isinstance(original_result, ApiRequest):
                            # 直接使用ApiRequest
                            return await self.invoke(original_result)
                        elif (
                            isinstance(original_result, tuple)
                            and len(original_result) == 2
                        ):
                            # 返回 (activity, data) 元组
                            activity, data = original_result
                            return await self.invoke(ApiRequest(activity, data))
                        else:
                            # 原始方法已经处理了请求，直接返回结果
                            return original_result

                    return wrapper

                setattr(cls, attr_name, make_wrapper(attr_value))

        return cls


class APIBase(ABC, metaclass=ApiMeta):
    """
    纯通信层基类
    只负责两件事
    1. 实现invoke方法进行实际通信
    2. 自动包装所有方法到invoke调用

    不定义任何具体接口，协议开发者可以自由定义方法
    """

    # ========== 底层方法 ==========
    @abstractmethod
    async def invoke(self, request: ApiRequest[Any]) -> Any:
        """
        执行API调用 - 子类必须实现
        这是唯一的强制要求

        Args:
            request: API请求
        Returns:
            API响应数据
        """
        pass

    async def call(self, activity: str, **kwargs) -> Any:
        """直接调用activity"""
        return await self.invoke(ApiRequest(activity, kwargs))

    # ========== 自动发现API方法 ==========

    def list_api_methods(self) -> List[str]:
        """列出所有API方法"""
        methods = []
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if not name.startswith("_") and asyncio.iscoroutinefunction(method):
                methods.append(name)
        return methods

    def __getattr__(self, name: str):
        """动态调用任意API方法"""  # 如果没有定义

        async def dynamic_method(*args, **kwargs):
            if args:  # 只要出现位置参数就报错
                raise TypeError(
                    f"{name} 仅接受关键字参数，请使用 key=value 形式调用，避免桥接 API 时参数顺序与远端不一致"
                )
            # 纯关键字参数
            return await self.invoke(ApiRequest[Any](name, kwargs))

        return dynamic_method
