from typing import Any, Dict, TypeVar

DtoT = TypeVar("DtoT", bound="BaseDto")


class BaseDto:
    # 纯占位用了, 不然动态注入会导致ide识别不到

    def to_dict(
        self, exclude_none: bool = False, exclude_unset: bool = False
    ) -> Dict[str, Any]:
        pass

    def to_json(self, indent: int = 2, exclude_none: bool = False, **kwargs) -> str:
        """将DTO转换为JSON字符串"""
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = True) -> DtoT:
        """从字典创建DTO实例"""
        pass

    def copy(self, **changes):
        """创建DTO的副本，可选择更新某些字段"""
        pass

    def validate(self) -> bool:
        """验证DTO的所有字段"""
        pass
