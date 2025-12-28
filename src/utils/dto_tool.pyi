from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
    runtime_checkable,
)

from typing_extensions import Self

# ========== 自定义网络格式类型 ==========

class Email(str):
    """邮箱地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> Email: ...

class URL(str):
    """URL地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> URL: ...

class IPv4Address(str):
    """IPv4地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> IPv4Address: ...

class IPv6Address(str):
    """IPv6地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> IPv6Address: ...

class IPAddress(str):
    """IP地址类型（IPv4或IPv6）"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> IPAddress: ...

class DomainName(str):
    """域名类型"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> DomainName: ...

class PhoneNumber(str):
    """电话号码类型"""

    @classmethod
    def validate(cls, value: str, country_code: str = "+86") -> bool: ...
    def __new__(cls, value: str, country_code: str = "+86") -> PhoneNumber: ...

class UUIDString(str):
    """UUID字符串类型"""

    @classmethod
    def validate(cls, value: str) -> bool: ...
    def __new__(cls, value: str) -> UUIDString: ...

# ========== DTO协议 ==========

_T = TypeVar("_T")
_DataType = Dict[str, Any]

@runtime_checkable
class DTOProtocol(Protocol):
    """DTO协议，所有DTO类都应该实现这些方法"""

    # 动态属性
    _type_hints: Dict[str, Any]
    _type_check_enabled: bool

    @property
    def type_check_context(self) -> _TypeCheckContext: ...

    # 序列化方法
    def to_dict(
        self, exclude_none: bool = False, exclude_unset: bool = False
    ) -> Dict[str, Any]: ...
    def to_json(self, indent: int = 2, exclude_none: bool = False, **kwargs) -> str: ...
    @classmethod
    def from_dict(cls: Type[_T], data: _DataType, strict: bool = True) -> _T: ...

    # 其他功能
    def copy(self, **changes) -> Self: ...
    def validate(self) -> bool: ...

# ========== 上下文管理器 ==========

class _TypeCheckContext:
    """类型检查上下文管理器"""

    def __init__(self, instance: DTOProtocol) -> None: ...
    def __enter__(self) -> DTOProtocol: ...
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> Optional[bool]: ...

# ========== 装饰器重载 ==========

@overload
def dataclass_dto(cls: Type[_T]) -> Type[_T | DTOProtocol]: ...
@overload
def dataclass_dto(
    *, strict: bool = True, frozen: bool = False
) -> Callable[[Type[_T]], Type[_T | DTOProtocol]]: ...
def dataclass_dto(
    cls: Optional[Type[_T]] = None, *, strict: bool = True, frozen: bool = False
) -> Union[Type[_T | DTOProtocol], Callable[[Type[_T]], Type[_T | DTOProtocol]]]:
    """
    装饰器：将dataclass转换为DTO，提供序列化、验证、转换等功能

    Args:
        cls: 要装饰的类
        strict: 是否启用严格类型检查
        frozen: 是否创建不可变对象（类似元组）

    Returns:
        装饰后的DTO类，具有序列化和验证功能
    """
    ...

# ========== 辅助函数类型提示 ==========

def _check_type_and_value(value: Any, expected_type: Any, name: str = "") -> None:
    """
    检查类型和值，正确抛出TypeError或ValueError

    Args:
        value: 要检查的值
        expected_type: 期望的类型
        name: 字段名，用于错误信息

    Raises:
        TypeError: 当值不是期望的类型时
        ValueError: 当值是正确的类型但格式/内容不合法时
    """
    ...

def _add_type_checking(cls: Type[_T], strict: bool) -> Type[_T]: ...
def _add_dto_features(cls: Type[_T]) -> Type[_T | DTOProtocol]: ...

# ========== 类型别名 ==========

# 常用类型别名
StrTypes = Union[
    str,
    Email,
    URL,
    IPv4Address,
    IPv6Address,
    IPAddress,
    DomainName,
    PhoneNumber,
    UUIDString,
]

# JSON序列化支持的类型
JsonSerializable = Union[
    str,
    int,
    float,
    bool,
    None,
    List["JsonSerializable"],
    Dict[str, "JsonSerializable"],
    datetime,
    date,
    Decimal,
    Email,
    URL,
    IPv4Address,
    IPv6Address,
    IPAddress,
    DomainName,
    PhoneNumber,
    UUIDString,
    DTOProtocol,
]

# DTO字段支持的完整类型
DTOField = Union[
    JsonSerializable,
    List[JsonSerializable],
    Dict[str, JsonSerializable],
    Set[JsonSerializable],
    Tuple[JsonSerializable, ...],
    Optional["DTOField"],
]
