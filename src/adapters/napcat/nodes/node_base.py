from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, TypeVar

from ....abc.nodes import MessageNode

if TYPE_CHECKING:
    from .dto.dto_base import BaseDto

logger = getLogger(__name__)

NodeT = TypeVar("NodeT", bound="BaseNode")


class BaseNode(MessageNode):
    _str_exclude = {""}  # 排除在str中的属性集合
    _node_type: str = ""

    def get_core_properties_str(self) -> str:
        excludes = set(getattr(self, "_repr_exclude", ()))
        props = {
            k: v
            for k, v in vars(self).items()
            if not k.startswith("_") and k not in excludes
        }
        parts = [f"{k}={repr(v)}" for k, v in props.items()]
        return ", ".join(parts)

    @property
    def node_type(self) -> str:
        return self._node_type

    def to_dict(self) -> Dict[str, Any]:
        """将节点转换为符合OneBot协议的字典表示 {type, data: {...}}"""
        data = {}

        # 只包含非私有属性
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                data[key] = value

        return {"type": self.node_type, "data": data}

    def get_summary(self) -> str:
        """获取节点摘要，子类可覆写"""
        return f"[{self._node_type}]"

    @classmethod
    def from_dto(cls, data: "BaseDto") -> "BaseNode":
        data_dict = data.to_dict()
        logger.debug(f"节点字典: {data} -> {data_dict}")
        return cls(**data_dict)

    def __str__(self):
        return self.get_summary()
