# ========== 消息节点 ==========
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MessageNode(ABC):
    """消息节点抽象基类 - 所有消息节点的父类"""

    @abstractmethod
    def __str__(self) -> str:
        """获取节点的字符串表示"""
        pass

    def __repr__(self) -> str:
        """获取节点的调试表示"""
        attrs = []
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                # 截断长字符串以便显示
                if isinstance(value, str) and len(value) > 50:
                    value = f"{value[:50]}..."
                attrs.append(f"{key}={value!r}")

        class_name = self.__class__.__name__
        if attrs:
            return f"{class_name}({', '.join(attrs)})"
        return f"{class_name}()"

    @property
    @abstractmethod
    def node_type(self) -> str:
        """节点类型标识符（如：text, image, audio等）"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """将节点转换为字典表示"""
        result = {"type": self.type}

        # 只包含非私有属性
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                result[key] = value

        return result

    def to_json(self) -> str:
        """将节点转换为JSON字符串"""
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False)

    def __eq__(self, other: Any) -> bool:
        """比较两个节点是否相等"""
        if not isinstance(other, MessageNode):
            return False

        # 比较类型和所有属性
        if self.type != other.type:
            return False

        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        """计算节点的哈希值"""
        return hash((self.type, tuple(sorted(self.__dict__.items()))))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["MessageNode"]:
        """从字典创建节点（工厂方法）"""
        # 这是一个通用工厂方法，需要子类实现具体逻辑
        # 或者可以由一个注册表来处理

        # NODE_REGISTRY  # 假设有一个节点注册表

        # node_type = data.get("type")
        # if node_type in NODE_REGISTRY:
        #     node_class = NODE_REGISTRY[node_type]
        #     # 创建节点实例，传入剩余的参数
        #     return node_class(**{k: v for k, v in data.items() if k != "type"})

        return None
