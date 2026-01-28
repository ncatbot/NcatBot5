from __future__ import annotations

import dataclasses
import functools
import inspect
import ipaddress
import json
import re
import typing
from datetime import date, datetime
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Set,
    Tuple,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from urllib.parse import urlparse
from uuid import UUID

# ========== 自定义网络格式类型 ==========


class Email(str):
    """邮箱地址类型"""

    _pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    @classmethod
    def validate(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        return bool(cls._pattern.match(value))

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"Email expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid email address format: {value}")
        return super().__new__(cls, value)


class URL(str):
    """URL地址类型"""

    _allowed_schemes = {"http", "https", "ftp", "ftps", "ws", "wss"}

    @classmethod
    def validate(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        try:
            result = urlparse(value)
            return bool(
                result.scheme
                and result.netloc
                and result.scheme in cls._allowed_schemes
            )
        except Exception:
            return False

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"URL expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid URL format: {value}")
        return super().__new__(cls, value)


class IPv4Address(str):
    """IPv4地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool:
        try:
            ipaddress.IPv4Address(value)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"IPv4Address expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid IPv4 address format: {value}")
        return super().__new__(cls, value)


class IPv6Address(str):
    """IPv6地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool:
        try:
            ipaddress.IPv6Address(value)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"IPv6Address expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid IPv6 address format: {value}")
        return super().__new__(cls, value)


class IPAddress(str):
    """IP地址类型（IPv4或IPv6）"""

    @classmethod
    def validate(cls, value: str) -> bool:
        return IPv4Address.validate(value) or IPv6Address.validate(value)

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"IPAddress expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid IP address format: {value}")
        return super().__new__(cls, value)


class DomainName(str):
    """域名类型"""

    _pattern = re.compile(
        r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
    )

    @classmethod
    def validate(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        return bool(cls._pattern.match(value))

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"DomainName expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid domain name format: {value}")
        return super().__new__(cls, value)


class PhoneNumber(str):
    """电话号码类型（默认中国+86）"""

    @classmethod
    def validate(cls, value: str, country_code: str = "+86") -> bool:
        if not isinstance(value, str):
            return False
        digits = re.sub(r"\D", "", value)

        if country_code in ("+86", "86"):
            return (
                len(digits) == 11 and digits.startswith("1") and digits[1] in "3456789"
            )
        return 7 <= len(digits) <= 15

    def __new__(cls, value: str, country_code: str = "+86"):
        if not isinstance(value, str):
            raise TypeError(f"PhoneNumber expects str, got {type(value).__name__}")
        if not cls.validate(value, country_code):
            raise ValueError(f"Invalid phone number format: {value}")
        return super().__new__(cls, value)


class UUIDString(str):
    """UUID字符串类型"""

    @classmethod
    def validate(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        try:
            UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"UUIDString expects str, got {type(value).__name__}")
        if not cls.validate(value):
            raise ValueError(f"Invalid UUID format: {value}")
        return super().__new__(cls, value)


# ========== 类型工具函数 ==========


def _is_optional(t: Any) -> bool:
    """检查是否为 Optional[T] 或 Union[T, None]"""
    origin = get_origin(t)
    if origin is Union:
        args = get_args(t)
        return type(None) in args and len(args) == 2
    return False


def _unwrap_optional(t: Any) -> Any:
    """从 Optional[T] 中提取 T"""
    args = get_args(t)
    return next(arg for arg in args if arg is not type(None))


def _is_list_type(t: Any) -> bool:
    """检查是否为列表类型（支持 List, list, Sequence 等）"""
    origin = get_origin(t)
    return origin in (list, List) or (
        isinstance(origin, type) and issubclass(origin, list)
    )


def _is_dict_type(t: Any) -> bool:
    """检查是否为字典类型"""
    origin = get_origin(t)
    return origin in (dict, Dict) or (
        isinstance(origin, type) and issubclass(origin, dict)
    )


def _is_set_type(t: Any) -> bool:
    """检查是否为集合类型"""
    origin = get_origin(t)
    return origin in (set, Set) or (
        isinstance(origin, type) and issubclass(origin, set)
    )


def _is_tuple_type(t: Any) -> bool:
    """检查是否为元组类型"""
    origin = get_origin(t)
    return origin in (tuple, Tuple) or (
        isinstance(origin, type) and issubclass(origin, tuple)
    )


# ========== DTO 装饰器核心 ==========


def dataclass_dto(cls=None, *, strict: bool = True, frozen: bool = False):
    """
    装饰器：将 dataclass 转换为 DTO，提供序列化、验证、转换等功能

    Args:
        strict: 是否启用严格类型检查（构造和赋值时）
        frozen: 是否创建不可变对象
    """

    def decorator(cls):
        # 应用 dataclass 装饰器
        dc_cls = dataclasses.dataclass(frozen=frozen)(cls)

        # 添加类型检查
        dc_cls = _add_type_checking(dc_cls, strict)

        # 添加 DTO 功能
        dc_cls = _add_dto_features(dc_cls)

        return dc_cls

    if cls is None:
        return decorator
    return decorator(cls)


def _add_type_checking(cls, strict: bool):
    """为类添加类型检查功能"""
    original_init = cls.__init__
    type_hints = get_type_hints(cls)

    @functools.wraps(original_init)
    def __init__(self, *args, **kwargs):
        # 调用原始初始化
        original_init(self, *args, **kwargs)

        # 严格模式下验证所有字段
        if strict:
            errors = []
            for field in dataclasses.fields(self):
                field_name = field.name
                field_value = getattr(self, field_name)

                # 跳过缺失值
                if field_value is dataclasses.MISSING:
                    continue

                if field_name in type_hints:
                    expected_type = type_hints[field_name]
                    try:
                        converted = _try_convert_value(
                            field_value, expected_type, field_name
                        )
                        if converted is not field_value:
                            object.__setattr__(self, field_name, converted)
                        _check_type_and_value(converted, expected_type, field_name)
                    except (TypeError, ValueError) as e:
                        errors.append(str(e))

            if errors:
                raise TypeError(
                    f"Validation failed for {cls.__name__}: {'; '.join(errors)}"
                )

    cls.__init__ = __init__

    # 修复：正确处理 frozen 和 strict 的组合
    if strict:
        dc_params = getattr(cls, "__dataclass_params__", None)
        is_frozen = dc_params.frozen if dc_params else False

        if not is_frozen:
            # 保存原始 setattr
            original_setattr = cls.__setattr__

            def __setattr__(self, name, value):
                if name in type_hints:
                    expected_type = type_hints[name]
                    try:
                        converted = _try_convert_value(value, expected_type, name)
                        _check_type_and_value(converted, expected_type, name)
                        value = converted
                    except (TypeError, ValueError) as e:
                        raise type(e)(f"In {cls.__name__}.{name}: {e}") from e

                original_setattr(self, name, value)

            cls.__setattr__ = __setattr__
            cls._original_setattr = original_setattr

    cls._type_hints = type_hints
    cls._type_check_enabled = strict
    return cls


def _check_type_and_value(value: Any, expected_type: Any, name: str = "") -> None:
    """递归检查类型和值（支持嵌套泛型、Literal）"""
    # 处理 Any
    if expected_type is Any:
        return

    # 处理 Literal（必须在 Optional/Union 之前，因为是具体的值匹配）
    if _is_literal(expected_type):
        allowed_values = get_args(expected_type)
        if value not in allowed_values:
            raise ValueError(
                f"Field '{name}' expects one of {allowed_values!r}, "
                f"got {value!r} ({type(value).__name__})"
            )
        return

    # 处理 Optional[T]
    if _is_optional(expected_type):
        if value is None:
            return
        expected_type = _unwrap_optional(expected_type)
        return _check_type_and_value(value, expected_type, name)

    # 处理 Union（非 Optional）
    origin = get_origin(expected_type)
    if origin is Union:
        args = get_args(expected_type)
        for arg in args:
            try:
                _check_type_and_value(value, arg, name)
                return
            except (TypeError, ValueError):
                continue
        raise TypeError(
            f"Field '{name}' expects one of {args}, got {type(value).__name__}"
        )

    # 处理列表（支持嵌套如 List[List[int]]）
    if _is_list_type(expected_type):
        if not isinstance(value, list):
            raise TypeError(f"Field '{name}' expects list, got {type(value).__name__}")

        args = get_args(expected_type)
        if args:
            item_type = args[0]
            for i, item in enumerate(value):
                _check_type_and_value(item, item_type, f"{name}[{i}]")
        return

    # 处理字典（支持嵌套如 Dict[str, List[int]]）
    if _is_dict_type(expected_type):
        if not isinstance(value, dict):
            raise TypeError(f"Field '{name}' expects dict, got {type(value).__name__}")

        args = get_args(expected_type)
        if len(args) >= 2:
            key_type, val_type = args[0], args[1]
            for k, v in value.items():
                _check_type_and_value(k, key_type, f"{name}.key")
                _check_type_and_value(v, val_type, f"{name}[{k!r}]")
        return

    # 处理集合
    if _is_set_type(expected_type):
        if not isinstance(value, set):
            raise TypeError(f"Field '{name}' expects set, got {type(value).__name__}")

        args = get_args(expected_type)
        if args:
            item_type = args[0]
            for item in value:
                _check_type_and_value(item, item_type, f"{name}.item")
        return

    # 处理元组（支持定长如 Tuple[int, str] 和变长如 Tuple[int, ...]）
    if _is_tuple_type(expected_type):
        if not isinstance(value, tuple):
            raise TypeError(f"Field '{name}' expects tuple, got {type(value).__name__}")

        args = get_args(expected_type)
        if not args:
            return

        # 处理 Tuple[T, ...] 变长元组
        if len(args) == 2 and args[1] is Ellipsis:
            item_type = args[0]
            for i, item in enumerate(value):
                _check_type_and_value(item, item_type, f"{name}[{i}]")
            return

        # 处理定长元组
        if len(args) != len(value):
            raise TypeError(
                f"Field '{name}' expects tuple of length {len(args)}, got {len(value)}"
            )

        for i, (item, item_type) in enumerate(zip(value, args)):
            _check_type_and_value(item, item_type, f"{name}[{i}]")
        return

    # 处理自定义字符串类型（Email, URL 等）
    if inspect.isclass(expected_type) and issubclass(expected_type, str):
        if isinstance(value, expected_type):
            return
        if isinstance(value, str):
            # 尝试构造以验证格式
            try:
                expected_type(value)
                return
            except ValueError as e:
                raise ValueError(f"Field '{name}' has invalid value: {e}")
        raise TypeError(
            f"Field '{name}' expects {expected_type.__name__} or str, got {type(value).__name__}"
        )

    # 基本类型检查
    if not isinstance(value, expected_type):
        raise TypeError(
            f"Field '{name}' expects {expected_type.__name__}, got {type(value).__name__}"
        )


def _is_literal(t: Any) -> bool:
    """检查是否为 Literal 类型"""
    origin = get_origin(t)
    if origin is None:
        return False
    # 兼容不同 Python 版本：检查 origin 是否为 Literal
    return origin is getattr(typing, "Literal", None) or str(origin) == "typing.Literal"


def _try_convert_value(value: Any, expected_type: Any, name: str = "") -> Any:
    """尝试将值转换为期望类型（支持嵌套泛型、Literal）"""
    # 处理 None 和 Any
    if value is None or expected_type is Any:
        return value

    if value is dataclasses.MISSING:
        return value

    # 处理 Literal - 值必须精确匹配，不做类型转换，仅验证
    if _is_literal(expected_type):
        allowed_values = get_args(expected_type)
        if value not in allowed_values:
            raise ValueError(
                f"Field '{name}' expects one of {allowed_values!r}, "
                f"got {value!r} ({type(value).__name__})"
            )
        return value

    # 处理 Optional[T]
    if _is_optional(expected_type):
        if value is None:
            return None
        return _try_convert_value(value, _unwrap_optional(expected_type), name)

    # 处理 Union（按顺序尝试每个类型）
    origin = get_origin(expected_type)
    if origin is Union:
        last_error = None
        for arg in get_args(expected_type):
            if arg is type(None):
                continue
            try:
                return _try_convert_value(value, arg, name)
            except (TypeError, ValueError) as e:
                last_error = e
        if last_error:
            raise last_error
        raise TypeError(
            f"Field '{name}' cannot convert to any of {get_args(expected_type)}"
        )

    # 处理列表（支持从 JSON 字符串解析和嵌套转换）
    if _is_list_type(expected_type):
        # 从 JSON 字符串解析
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if not isinstance(parsed, list):
                    raise TypeError(
                        f"Field '{name}' expects list, got {type(value).__name__}"
                    )
                value = parsed
            except json.JSONDecodeError:
                raise TypeError(
                    f"Field '{name}' expects list or JSON array string, got {type(value).__name__}"
                )

        if not isinstance(value, list):
            raise TypeError(f"Field '{name}' expects list, got {type(value).__name__}")

        args = get_args(expected_type)
        if args:
            item_type = args[0]
            return [
                _try_convert_value(item, item_type, f"{name}[{i}]")
                for i, item in enumerate(value)
            ]
        return value

    # 处理字典（支持嵌套）
    if _is_dict_type(expected_type):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if not isinstance(parsed, dict):
                    raise TypeError(
                        f"Field '{name}' expects dict, got {type(value).__name__}"
                    )
                value = parsed
            except json.JSONDecodeError:
                raise TypeError(
                    f"Field '{name}' expects dict or JSON object string, got {type(value).__name__}"
                )

        if not isinstance(value, dict):
            raise TypeError(f"Field '{name}' expects dict, got {type(value).__name__}")

        args = get_args(expected_type)
        if len(args) >= 2:
            key_type, val_type = args[0], args[1]
            return {
                _try_convert_value(k, key_type, f"{name}.key"): _try_convert_value(
                    v, val_type, f"{name}[{k!r}]"
                )
                for k, v in value.items()
            }
        return value

    # 处理集合
    if _is_set_type(expected_type):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    value = set(parsed)
                else:
                    raise TypeError(
                        f"Field '{name}' expects set, got {type(value).__name__}"
                    )
            except json.JSONDecodeError:
                raise TypeError(
                    f"Field '{name}' expects set or JSON array string, got {type(value).__name__}"
                )
        elif isinstance(value, (list, tuple)):
            value = set(value)

        if not isinstance(value, set):
            raise TypeError(f"Field '{name}' expects set, got {type(value).__name__}")

        args = get_args(expected_type)
        if args:
            item_type = args[0]
            return {
                _try_convert_value(item, item_type, f"{name}.item") for item in value
            }
        return value

    # 处理元组（支持从 list/JSON 转换）
    if _is_tuple_type(expected_type):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    value = tuple(parsed)
                else:
                    raise TypeError(
                        f"Field '{name}' expects tuple, got {type(value).__name__}"
                    )
            except json.JSONDecodeError:
                raise TypeError(
                    f"Field '{name}' expects tuple, got {type(value).__name__}"
                )
        elif isinstance(value, list):
            value = tuple(value)

        if not isinstance(value, tuple):
            raise TypeError(f"Field '{name}' expects tuple, got {type(value).__name__}")

        args = get_args(expected_type)
        if not args:
            return value

        # 处理变长元组 Tuple[T, ...]
        if len(args) == 2 and args[1] is Ellipsis:
            item_type = args[0]
            return tuple(
                _try_convert_value(item, item_type, f"{name}[{i}]")
                for i, item in enumerate(value)
            )

        # 处理定长元组
        if len(args) != len(value):
            raise TypeError(
                f"Field '{name}' expects tuple of length {len(args)}, got {len(value)}"
            )

        return tuple(
            _try_convert_value(item, item_type, f"{name}[{i}]")
            for i, (item, item_type) in enumerate(zip(value, args))
        )

    # 处理 dataclass（支持从 dict 自动转换）
    if inspect.isclass(expected_type) and dataclasses.is_dataclass(expected_type):
        if isinstance(value, dict):
            # 递归使用 from_dict，保持 strict 一致性
            if hasattr(expected_type, "from_dict"):
                return expected_type.from_dict(value, strict=False)
        elif isinstance(value, expected_type):
            return value
        raise TypeError(
            f"Field '{name}' expects {expected_type.__name__} or dict, got {type(value).__name__}"
        )

    # 处理自定义字符串类型
    if inspect.isclass(expected_type) and issubclass(expected_type, str):
        if isinstance(value, expected_type):
            return value
        if not isinstance(value, str):
            value = str(value)
        return expected_type(value)  # 让构造器验证格式

    # 处理 UUID
    if expected_type is UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except Exception as e:
                raise ValueError(f"Field '{name}' has invalid UUID: {e}") from e
        raise TypeError(
            f"Field '{name}' expects UUID or str, got {type(value).__name__}"
        )

    # 处理 datetime
    if expected_type is datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception as e:
                raise ValueError(f"Field '{name}' has invalid datetime: {e}") from e
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        raise TypeError(
            f"Field '{name}' expects datetime, str or number, got {type(value).__name__}"
        )

    # 处理 date
    if expected_type is date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except Exception as e:
                raise ValueError(f"Field '{name}' has invalid date: {e}") from e
        if isinstance(value, datetime):
            return value.date()
        raise TypeError(
            f"Field '{name}' expects date or str, got {type(value).__name__}"
        )

    # 处理 Decimal
    if expected_type is Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception as e:
            raise ValueError(f"Field '{name}' has invalid Decimal: {e}") from e

    # 处理 bool（注意：必须放在 int 之前，因为 bool 是 int 的子类）
    if expected_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes", "y", "t", "on"):
                return True
            if v in ("false", "0", "no", "n", "f", "off"):
                return False
            raise ValueError(f"Field '{name}' has invalid boolean: {value}")
        if isinstance(value, (int, float)):
            return bool(value)
        raise TypeError(
            f"Field '{name}' expects bool, str or number, got {type(value).__name__}"
        )

    # 处理 int（排除 bool）
    if expected_type is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as e:
                raise ValueError(f"Field '{name}' has invalid int: {e}") from e
        if isinstance(value, float) and value.is_integer():
            return int(value)
        raise TypeError(f"Field '{name}' expects int, got {type(value).__name__}")

    # 处理 float
    if expected_type is float:
        if isinstance(value, float):
            return value
        if isinstance(value, (int, str)):
            try:
                return float(value)
            except ValueError as e:
                raise ValueError(f"Field '{name}' has invalid float: {e}") from e
        raise TypeError(f"Field '{name}' expects float, got {type(value).__name__}")

    # 其他类型：检查是否是实例
    if isinstance(value, expected_type):
        return value

    raise TypeError(
        f"Field '{name}' expects {expected_type}, got {type(value).__name__}"
    )


# ========== DTO 功能扩展 ==========


def _add_dto_features(cls):
    """为 DTO 类添加序列化和反序列化功能"""

    def to_dict(
        self, exclude_none: bool = False, exclude_unset: bool = False
    ) -> Dict[str, Any]:
        """将 DTO 转换为字典（递归处理嵌套 DTO）"""
        result = {}

        for field in dataclasses.fields(self):
            value = getattr(self, field.name)

            # 处理 exclude_unset：跳过默认值
            if exclude_unset:
                if field.default is not dataclasses.MISSING and value == field.default:
                    continue
                if field.default_factory is not dataclasses.MISSING:
                    try:
                        if value == field.default_factory():
                            continue
                    except Exception:
                        pass

            # 处理 exclude_none
            if exclude_none and value is None:
                continue

            # 序列化逻辑
            field_name = field.name
            result[field_name] = _serialize_value(value, exclude_none, exclude_unset)

        return result

    def to_json(self, indent: int = 2, exclude_none: bool = False, **kwargs) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(
            self.to_dict(exclude_none=exclude_none),
            indent=indent,
            default=_json_serializer,
            **kwargs,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = True):
        """从字典创建 DTO 实例（支持嵌套和类型转换）"""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")

        type_hints = getattr(cls, "_type_hints", {})
        processed = {}

        for field in dataclasses.fields(cls):
            field_name = field.name

            if field_name not in data:
                # 缺失字段：使用默认值或报错
                if field.default is not dataclasses.MISSING:
                    processed[field_name] = field.default
                elif field.default_factory is not dataclasses.MISSING:
                    processed[field_name] = field.default_factory()
                elif strict:
                    raise ValueError(f"Missing required field: {field_name}")
                continue

            value = data[field_name]

            # 类型转换
            if field_name in type_hints:
                expected_type = type_hints[field_name]
                try:
                    value = _try_convert_value(value, expected_type, field_name)
                except (TypeError, ValueError):
                    if strict:
                        raise

            processed[field_name] = value

        return cls(**processed)

    def copy(self, **changes):
        """创建副本并更新指定字段"""
        return dataclasses.replace(self, **changes)

    def validate(self) -> bool:
        """验证所有字段"""
        type_hints = getattr(self, "_type_hints", {})
        try:
            for field_name, expected_type in type_hints.items():
                value = getattr(self, field_name)
                _check_type_and_value(value, expected_type, field_name)
            return True
        except (TypeError, ValueError):
            return False

    def _type_check_context_manager(self):
        """上下文管理器：临时禁用类型检查（用于批量修改）"""

        class TypeCheckContext:
            def __init__(self, instance):
                self.instance = instance
                self.cls = type(instance)
                self.original_setattr = None

            def __enter__(self):
                # 临时替换为 object.__setattr__ 绕过检查
                self.original_setattr = self.cls.__setattr__
                self.cls.__setattr__ = object.__setattr__
                return self.instance

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.cls.__setattr__ = self.original_setattr
                if exc_type is None:
                    # 退出时验证
                    self.instance.validate()

        return TypeCheckContext(self)

    # 绑定方法到类
    cls.to_dict = to_dict
    cls.to_json = to_json
    cls.from_dict = from_dict
    cls.copy = copy
    cls.validate = validate
    cls.type_check_context = property(_type_check_manager)

    return cls


def _serialize_value(value: Any, exclude_none: bool, exclude_unset: bool) -> Any:
    """递归序列化值"""
    if value is None:
        return None

    # 处理自定义字符串类型
    if isinstance(
        value,
        (
            Email,
            URL,
            IPv4Address,
            IPv6Address,
            IPAddress,
            DomainName,
            PhoneNumber,
            UUIDString,
        ),
    ):
        return str(value)

    # 处理嵌套 DTO
    if dataclasses.is_dataclass(value):
        return value.to_dict(exclude_none, exclude_unset)

    # 处理列表
    if isinstance(value, list):
        return [_serialize_value(item, exclude_none, exclude_unset) for item in value]

    # 处理字典
    if isinstance(value, dict):
        return {
            k: _serialize_value(v, exclude_none, exclude_unset)
            for k, v in value.items()
        }

    # 处理集合（转为列表）
    if isinstance(value, set):
        return [_serialize_value(item, exclude_none, exclude_unset) for item in value]

    # 处理元组（转为列表以便 JSON 序列化）
    if isinstance(value, tuple):
        return [_serialize_value(item, exclude_none, exclude_unset) for item in value]

    return value


def _json_serializer(obj: Any) -> Any:
    """JSON 序列化器"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(
        obj,
        (
            Email,
            URL,
            IPv4Address,
            IPv6Address,
            IPAddress,
            DomainName,
            PhoneNumber,
            UUIDString,
        ),
    ):
        return str(obj)
    if dataclasses.is_dataclass(obj):
        return obj.to_dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _type_check_manager(self):
    """属性 getter，返回上下文管理器"""

    class TypeCheckContext:
        def __init__(self, instance):
            self.instance = instance
            self.cls = type(instance)
            self.original = None

        def __enter__(self):
            self.original = getattr(self.cls, "_original_setattr", None)
            if self.original:
                self.cls.__setattr__ = object.__setattr__
            return self.instance

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.original:
                self.cls.__setattr__ = self.original
            if exc_type is None:
                self.instance.validate()

    return TypeCheckContext(self)
