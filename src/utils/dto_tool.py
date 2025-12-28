from __future__ import annotations

import dataclasses
import inspect
import ipaddress
import json
import re
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

# NOTE TypeError:  当值不是期望的类型时
# NOTE ValueError: 当值是正确的类型但格式/内容不合法时
# ========== 自定义网络格式类型 ==========


class Email(str):
    """邮箱地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool:
        """验证邮箱格式"""
        if not isinstance(value, str):
            raise TypeError(f"Email expects str, got {type(value).__name__}")

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, value):
            return False
        return True

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"Email expects str, got {type(value).__name__}")

        if not cls.validate(value):
            raise ValueError(f"Invalid email address format: {value}")
        return super().__new__(cls, value)


class URL(str):
    """URL地址类型"""

    @classmethod
    def validate(cls, value: str) -> bool:
        """验证URL格式"""
        if not isinstance(value, str):
            raise TypeError(f"URL expects str, got {type(value).__name__}")

        try:
            result = urlparse(value)
            if not result.scheme or not result.netloc:
                return False
            if result.scheme not in ("http", "https", "ftp", "ftps", "ws", "wss"):
                return False
            return True
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
        """验证IPv4地址格式"""
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
        """验证IPv6地址格式"""
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
        """验证IP地址格式（支持IPv4和IPv6）"""
        return IPv4Address.validate(value) or IPv6Address.validate(value)

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"IPAddress expects str, got {type(value).__name__}")

        if not cls.validate(value):
            raise ValueError(f"Invalid IP address format: {value}")
        return super().__new__(cls, value)


class DomainName(str):
    """域名类型"""

    @classmethod
    def validate(cls, value: str) -> bool:
        """验证域名格式"""
        if not isinstance(value, str):
            raise TypeError(f"DomainName expects str, got {type(value).__name__}")

        pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
        if not re.match(pattern, value):
            return False
        return True

    def __new__(cls, value: str):
        if not isinstance(value, str):
            raise TypeError(f"DomainName expects str, got {type(value).__name__}")

        if not cls.validate(value):
            raise ValueError(f"Invalid domain name format: {value}")
        return super().__new__(cls, value)


class PhoneNumber(str):
    """电话号码类型"""

    @classmethod
    def validate(cls, value: str, country_code: str = "+86") -> bool:
        """验证电话号码格式"""
        if not isinstance(value, str):
            raise TypeError(f"PhoneNumber expects str, got {type(value).__name__}")

        digits = re.sub(r"\D", "", value)

        if country_code in ("+86", "86"):
            if len(digits) != 11 or not digits.startswith("1"):
                return False
            if digits[1] not in "3456789":
                return False
            return True

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
        """验证UUID格式"""
        if not isinstance(value, str):
            raise TypeError(f"UUIDString expects str, got {type(value).__name__}")

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


# ========== 修复类型检查装饰器 ==========


def dataclass_dto(cls=None, *, strict: bool = True, frozen: bool = False):
    """
    装饰器：将dataclass转换为DTO，提供序列化、验证、转换等功能

    Args:
        strict: 是否启用严格类型检查
        frozen: 是否创建不可变对象（类似元组）
    """

    def decorator(cls):
        # 首先应用dataclass装饰器
        dc_cls = dataclasses.dataclass(frozen=frozen)(cls)

        # 添加类型检查功能
        dc_cls = _add_type_checking(dc_cls, strict)

        # 添加DTO功能
        dc_cls = _add_dto_features(dc_cls)

        return dc_cls

    if cls is None:
        return decorator
    return decorator(cls)


def _add_type_checking(cls, strict: bool):
    """添加类型检查功能 - 修复版"""
    original_init = cls.__init__
    type_hints = get_type_hints(cls)

    def __init__(self, *args, **kwargs):
        # 调用原始初始化
        original_init(self, *args, **kwargs)

        # 初始化后检查所有字段的类型
        if strict:
            for field in dataclasses.fields(self):
                field_name = field.name
                field_value = getattr(self, field_name)

                # 跳过默认工厂的特殊标记
                if field_value is dataclasses.MISSING or (
                    hasattr(field_value, "__class__")
                    and field_value.__class__.__name__ == "_MISSING_TYPE"
                ):
                    continue

                if field_name in type_hints:
                    expected_type = type_hints[field_name]
                    try:
                        _check_type_and_value(field_value, expected_type, field_name)
                    except TypeError as e:
                        raise TypeError(f"In {cls.__name__}.__init__: {e}") from e

    cls.__init__ = __init__

    # 如果需要严格模式，包装setattr
    if (
        strict
        and not dataclasses.is_dataclass(cls)
        or not getattr(cls, "__dataclass_params__").frozen
    ):
        # 保存原始__setattr__
        if not hasattr(cls, "_original_setattr"):
            cls._original_setattr = cls.__setattr__

        def __setattr__(self, name, value):
            if name in type_hints:
                expected_type = type_hints[name]
                try:
                    _check_type_and_value(value, expected_type, name)
                except TypeError as e:
                    raise TypeError(f"In {cls.__name__}.{name}: {e}") from e

            # 调用原始__setattr__
            object.__setattr__(self, name, value)

        cls.__setattr__ = __setattr__

    cls._type_hints = type_hints
    # 添加类型检查开关
    cls._type_check_enabled = strict

    return cls


def _check_type_and_value(value, expected_type, name: str = ""):
    """
    检查类型和值，正确抛出TypeError或ValueError
    """
    # 处理特殊标记
    if value is dataclasses.MISSING or (
        hasattr(value, "__class__") and value.__class__.__name__ == "_MISSING_TYPE"
    ):
        return

    # 处理Any类型
    if expected_type is Any:
        return

    # 处理Optional
    origin = get_origin(expected_type)
    if origin is Union:
        args = get_args(expected_type)
        if type(None) in args:
            # 这是Optional类型
            if value is None:
                return
            # 从Union中移除None，检查其他类型
            non_none_args = [arg for arg in args if arg is not type(None)]
            for arg_type in non_none_args:
                try:
                    _check_type_and_value(value, arg_type, name)
                    return
                except TypeError:
                    continue
                except ValueError:
                    raise
            raise TypeError(
                f"Field '{name}' expects one of {non_none_args}, got {type(value).__name__}"
            )

    # 处理泛型容器
    if origin in (list, List):
        if not isinstance(value, list):
            raise TypeError(f"Field '{name}' expects list, got {type(value).__name__}")

        if get_args(expected_type):
            item_type = get_args(expected_type)[0]
            for i, item in enumerate(value):
                try:
                    _check_type_and_value(item, item_type, f"{name}[{i}]")
                except TypeError as e:
                    raise TypeError(f"List item error: {e}")
                except ValueError as e:
                    raise ValueError(f"List item error: {e}")
        return

    elif origin in (dict, Dict):
        if not isinstance(value, dict):
            raise TypeError(f"Field '{name}' expects dict, got {type(value).__name__}")

        args = get_args(expected_type)
        if len(args) >= 2:
            key_type, val_type = args[:2]
            for key, val in value.items():
                try:
                    _check_type_and_value(key, key_type, f"{name}.key")
                    _check_type_and_value(val, val_type, f"{name}[{key!r}]")
                except TypeError as e:
                    raise TypeError(f"Dict entry error: {e}")
                except ValueError as e:
                    raise ValueError(f"Dict entry error: {e}")
        return

    elif origin in (set, Set):
        if not isinstance(value, set):
            raise TypeError(f"Field '{name}' expects set, got {type(value).__name__}")

        if get_args(expected_type):
            item_type = get_args(expected_type)[0]
            for item in value:
                try:
                    _check_type_and_value(item, item_type, f"{name}.item")
                except TypeError as e:
                    raise TypeError(f"Set item error: {e}")
                except ValueError as e:
                    raise ValueError(f"Set item error: {e}")
        return

    elif origin in (tuple, Tuple):
        if not isinstance(value, tuple):
            raise TypeError(f"Field '{name}' expects tuple, got {type(value).__name__}")

        args = get_args(expected_type)
        if args:
            if len(args) != len(value):
                raise TypeError(
                    f"Field '{name}' expects tuple of length {len(args)}, "
                    f"got {len(value)}"
                )
            for i, (item, item_type) in enumerate(zip(value, args)):
                try:
                    _check_type_and_value(item, item_type, f"{name}[{i}]")
                except TypeError as e:
                    raise TypeError(f"Tuple item error: {e}")
                except ValueError as e:
                    raise ValueError(f"Tuple item error: {e}")
        return

    # 处理自定义字符串类型
    if inspect.isclass(expected_type) and issubclass(expected_type, str):
        if not isinstance(value, expected_type):
            try:
                if isinstance(value, str):
                    expected_type(value)
                    return
                else:
                    raise TypeError(
                        f"Field '{name}' expects {expected_type.__name__} or str, got {type(value).__name__}"
                    )
            except ValueError as e:
                raise ValueError(f"Field '{name}' has invalid value: {e}")
            except TypeError:
                raise TypeError(
                    f"Field '{name}' expects {expected_type.__name__} or str, got {type(value).__name__}"
                )

    # 基本类型检查
    if not isinstance(value, expected_type):
        raise TypeError(
            f"Field '{name}' expects {expected_type.__name__}, got {type(value).__name__}"
        )


# ========== DTO功能 ==========


def _add_dto_features(cls):
    """为DTO类添加额外功能"""

    def to_dict(
        self, exclude_none: bool = False, exclude_unset: bool = False
    ) -> Dict[str, Any]:
        """将DTO转换为字典"""
        result = {}
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)

            if (
                exclude_unset
                and field.default != dataclasses.MISSING
                and value == field.default
            ):
                continue
            if exclude_unset and field.default_factory != dataclasses.MISSING:
                try:
                    default_value = field.default_factory()
                    if value == default_value:
                        continue
                except Exception:
                    pass

            if exclude_none and value is None:
                continue

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
                result[field.name] = str(value)
            elif dataclasses.is_dataclass(value):
                result[field.name] = value.to_dict(exclude_none, exclude_unset)
            elif isinstance(value, list):
                result[field.name] = [
                    item.to_dict(exclude_none, exclude_unset)
                    if dataclasses.is_dataclass(item)
                    else item
                    for item in value
                ]
            elif isinstance(value, dict):
                result[field.name] = {
                    k: v.to_dict(exclude_none, exclude_unset)
                    if dataclasses.is_dataclass(v)
                    else v
                    for k, v in value.items()
                }
            else:
                result[field.name] = value

        return result

    cls.to_dict = to_dict

    def to_json(self, indent: int = 2, exclude_none: bool = False, **kwargs) -> str:
        """将DTO转换为JSON字符串"""

        def default_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return str(obj)
            elif isinstance(
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
            elif dataclasses.is_dataclass(obj):
                return obj.to_dict(exclude_none=exclude_none)
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        return json.dumps(
            self.to_dict(exclude_none=exclude_none),
            indent=indent,
            default=default_serializer,
            **kwargs,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = True):
        """从字典创建DTO实例"""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")

        processed_data = {}
        # type_hints = getattr(cls, "_type_hints", {})

        for field in dataclasses.fields(cls):
            field_name = field.name

            if field_name not in data:
                if field.default != dataclasses.MISSING:
                    processed_data[field_name] = field.default
                elif field.default_factory != dataclasses.MISSING:
                    processed_data[field_name] = field.default_factory()
                elif strict:
                    raise ValueError(f"Missing required field: {field_name}")
                continue

            value = data[field_name]
            processed_data[field_name] = value

        return cls(**processed_data)

    cls.to_json = to_json
    cls.from_dict = from_dict

    def copy(self, **changes):
        """创建DTO的副本，可选择更新某些字段"""
        return dataclasses.replace(self, **changes)

    def validate(self) -> bool:
        """验证DTO的所有字段"""
        type_hints = getattr(self, "_type_hints", {})
        for field_name, expected_type in type_hints.items():
            value = getattr(self, field_name)
            try:
                _check_type_and_value(value, expected_type, field_name)
            except (TypeError, ValueError):
                return False
        return True

    cls.copy = copy
    cls.validate = validate

    # 修复上下文管理器
    def _type_check_context(self):
        """返回类型检查上下文管理器"""

        class TypeCheckContext:
            def __init__(self, instance):
                self.instance = instance
                self.original_method = None

            def __enter__(self):
                # 保存当前__setattr__方法
                self.original_method = self.instance.__setattr__
                # 临时替换为object.__setattr__来禁用类型检查
                self.instance.__setattr__ = object.__setattr__
                return self.instance

            def __exit__(self, exc_type, exc_val, exc_tb):
                # 恢复原来的__setattr__方法
                self.instance.__setattr__ = self.original_method
                if exc_type is None:
                    # 如果没有异常，验证所有字段
                    self.instance.validate()

        return TypeCheckContext(self)

    cls.type_check_context = property(_type_check_context)

    return cls
