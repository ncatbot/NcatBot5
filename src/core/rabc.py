# -*- coding: utf-8 -*-
"""
RBAC（Role-Based Access Control）权限系统
支持：
1. 角色继承
2. 通配符 / 正则 权限匹配
3. 用户黑白名单
4. JSON 持久化与恢复
5. 权限树可视化
"""

import json
import re
from logging import getLogger
from typing import Any, Dict, List, Optional, Set

logger = getLogger("RBAC")


# ------------------------------------------------------
# 权限匹配器：支持三种模式
# 1. 显式字符串        system.config
# 2. 通配符            *.config  /  **.log
# 3. 正则表达式        [regex_here]
# ------------------------------------------------------
class PermissionMatcher:
    @staticmethod
    def match(pattern: str, target: str) -> bool:
        """
        检查目标权限字符串是否匹配给定的模式

        Args:
            pattern: 权限模式，支持字符串、通配符或正则表达式
            target: 要检查的目标权限字符串

        Returns:
            bool: 如果匹配返回True，否则返回False
        """
        # 若被 [] 包裹，则整体当正则处理
        if pattern.startswith("[") and pattern.endswith("]"):
            regex_content = pattern[1:-1]
            try:
                return re.fullmatch(regex_content, target) is not None
            except re.error:
                return False

        # 其余情况先转义，再做通配符替换
        regex_pattern = re.escape(pattern)
        # ** 匹配任意深度（含点）
        regex_pattern = regex_pattern.replace(r"\*\*", ".*")
        # *  匹配单段（不含点）
        regex_pattern = regex_pattern.replace(r"\*", "[^.]*")
        return re.match(f"^{regex_pattern}$", target) is not None


# ------------------------------------------------------
# 管理器：集中管理所有角色与用户
# 负责：创建、查找、序列化、反序列化
# ------------------------------------------------------
class RBACManager:
    def __init__(self, name: str = "default") -> None:
        """
        初始化RBAC管理器

        Args:
            name: 管理器名称
        """
        self.name: str = name
        self._users: Dict[str, "User"] = {}
        self._roles: Dict[str, "Role"] = {}

    # ---------- 快捷创建 ----------
    def create_user(self, username: str) -> "User":
        """
        创建新用户

        Args:
            username: 用户名

        Returns:
            User: 新创建的用户对象
        """
        user = User(self, username)
        self._users[username] = user
        return user

    def create_role(self, rolename: str) -> "Role":
        """
        创建新角色

        Args:
            rolename: 角色名

        Returns:
            Role: 新创建的角色对象
        """
        role = Role(self, rolename)
        self._roles[rolename] = role
        return role

    # ---------- 快捷查找 ----------
    def get_user(self, name: str) -> Optional["User"]:
        """
        根据用户名获取用户

        Args:
            name: 用户名

        Returns:
            Optional[User]: 用户对象，如果不存在则返回None
        """
        return self._users.get(name)

    def get_role(self, name: str) -> Optional["Role"]:
        """
        根据角色名获取角色

        Args:
            name: 角色名

        Returns:
            Optional[Role]: 角色对象，如果不存在则返回None
        """
        return self._roles.get(name)

    # --------------------------------------------------
    # 序列化：把当前整个系统压成纯字典，方便 JSON 保存
    # --------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """
        将管理器状态转换为字典

        Returns:
            Dict[str, Any]: 包含所有角色和用户信息的字典
        """
        return {
            "manager_name": self.name,
            "roles": [
                {
                    "name": r.name,
                    "permissions": list(r._permissions),  # 自身权限
                    "parents": [p.name for p in r._parents],  # 继承哪些角色
                }
                for r in self._roles.values()
            ],
            "users": [
                {
                    "name": u.name,
                    "roles": [r.name for r in u._roles],  # 绑定哪些角色
                    "whitelist": list(u._whitelist),  # 白名单
                    "blacklist": list(u._blacklist),  # 黑名单
                }
                for u in self._users.values()
            ],
        }

    # --------------------------------------------------
    # 保存到文件
    # --------------------------------------------------
    def save_to_file(self, filepath: str) -> None:
        """
        将管理器状态保存到JSON文件

        Args:
            filepath: 文件路径
        """
        data = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # print(f"已成功保存 RBAC 数据到 {filepath}")

    # --------------------------------------------------
    # 类方法：从文件重建整个系统
    # 分三遍处理，避免依赖顺序问题
    # --------------------------------------------------
    @classmethod
    def load_from_file(cls, filepath: str) -> "RBACManager":
        """
        从JSON文件加载RBAC管理器状态

        Args:
            filepath: 文件路径

        Returns:
            RBACManager: 加载后的RBAC管理器

        Raises:
            AssertionError: 如果文件格式不正确
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
            assert isinstance(data, dict)

        # 1. 先建管理器壳子
        manager = cls(data.get("manager_name", "loaded"))

        # 2. 第一遍：把所有 Role / User 对象造出来（不连关系）
        role_map: Dict[str, Role] = {}  # 名字 -> Role 对象
        for r_data in data.get("roles", []):
            assert isinstance(r_data, dict)
            role = manager.create_role(r_data["name"])
            for perm in r_data.get("permissions", []):
                role.add_permission(perm)
            role_map[role.name] = role

        # 3. 第二遍：建立角色之间的继承
        for r_data in data.get("roles", []):
            assert isinstance(r_data, dict)
            role = role_map[r_data["name"]]
            for parent_name in r_data.get("parents", []):
                parent_role = role_map.get(parent_name)
                if parent_role:
                    role.inherit_from(parent_role)

        # 4. 第三遍：恢复用户及其角色、黑白名单
        for u_data in data.get("users", []):
            user = manager.create_user(u_data["name"])
            for perm in u_data.get("whitelist", []):
                user.permit(perm)
            for perm in u_data.get("blacklist", []):
                user.deny(perm)
            for role_name in u_data.get("roles", []):
                role = role_map.get(role_name)
                if role:
                    user.add_role(role)

        print(f"已成功从 {filepath} 加载 RBAC 数据")
        return manager


# ------------------------------------------------------
# 基类：给 Role 与 User 提供"同一管理器"安全检查
# ------------------------------------------------------
class ManagedEntity:
    def __init__(self, manager: RBACManager) -> None:
        """
        初始化受管理实体

        Args:
            manager: 所属的RBAC管理器
        """
        self._manager: RBACManager = manager

    def _check_manager_compatibility(self, other: "ManagedEntity") -> None:
        """
        检查两个实体是否属于同一个管理器

        Args:
            other: 另一个实体

        Raises:
            RuntimeError: 如果两个实体不属于同一个管理器
        """
        # 防止跨管理器操作，避免权限污染
        if self._manager is not other._manager:
            raise RuntimeError("安全错误：不允许跨管理器交互！")


# ------------------------------------------------------
# 角色：拥有权限 + 可继承父角色
# ------------------------------------------------------
class Role(ManagedEntity):
    def __init__(self, manager: RBACManager, name: str) -> None:
        """
        初始化角色

        Args:
            manager: 所属的RBAC管理器
            name: 角色名称
        """
        super().__init__(manager)
        self.name: str = name
        self._permissions: Set[str] = set()  # 自身权限
        self._parents: Set[Role] = set()  # 父角色

    def add_permission(self, perm_str: str) -> None:
        """给角色增加一条权限字符串

        Args:
            perm_str: 权限字符串
        """
        self._permissions.add(perm_str)

    def inherit_from(self, parent_role: "Role") -> None:
        """继承另一个角色（支持多继承）

        Args:
            parent_role: 要继承的父角色

        Raises:
            RuntimeError: 如果父角色不属于同一个管理器
        """
        self._check_manager_compatibility(parent_role)
        self._parents.add(parent_role)

    def has_permission(
        self, perm_str: str, checked_roles: Optional[Set["Role"]] = None
    ) -> bool:
        """
        递归判断角色是否拥有某权限（含继承链）

        Args:
            perm_str: 要检查的权限字符串
            checked_roles: 已检查的角色集合，用于防止循环继承

        Returns:
            bool: 如果角色拥有该权限返回True，否则返回False
        """
        if checked_roles is None:
            _checked_roles: Set[Role] = set()
        else:
            _checked_roles = checked_roles

        if self in _checked_roles:
            return False
        _checked_roles.add(self)

        # 先看自身权限
        for p in self._permissions:
            if PermissionMatcher.match(p, perm_str):
                return True
        # 再看父角色
        for parent in self._parents:
            if parent.has_permission(perm_str, _checked_roles):
                return True
        return False

    def get_permission_tree(self) -> Dict[str, Any]:
        """
        把角色权限转成多级字典，方便前端树形展示
        例如：system.config.read -> {'system': {'config': {'read': {}}}}

        Returns:
            Dict[str, Any]: 权限树字典
        """
        tree: Dict[str, Any] = {}
        for perm in self._permissions:
            # 正则权限当成一整段
            parts = (
                [perm]
                if (perm.startswith("[") and perm.endswith("]"))
                else perm.split(".")
            )
            curr = tree
            for part in parts:
                if part not in curr:
                    curr[part] = {}
                curr = curr[part]
        return tree


# ------------------------------------------------------
# 用户：绑定角色 + 黑白名单
# 权限判断顺序：黑名单 > 白名单 > 角色
# ------------------------------------------------------
class User(ManagedEntity):
    def __init__(self, manager: RBACManager, name: str) -> None:
        """
        初始化用户

        Args:
            manager: 所属的RBAC管理器
            name: 用户名
        """
        super().__init__(manager)
        self.name: str = name
        self._roles: Set[Role] = set()
        self._whitelist: Set[str] = set()
        self._blacklist: Set[str] = set()

    def add_role(self, role: Role) -> None:
        """给用户绑定一个角色

        Args:
            role: 要绑定的角色

        Raises:
            RuntimeError: 如果角色不属于同一个管理器
        """
        self._check_manager_compatibility(role)
        self._roles.add(role)

    def permit(self, p: str) -> None:
        """用户级白名单

        Args:
            p: 要添加到白名单的权限字符串
        """
        self._whitelist.add(p)

    def deny(self, p: str) -> None:
        """用户级黑名单

        Args:
            p: 要添加到黑名单的权限字符串
        """
        self._blacklist.add(p)

    def can(self, perm_str: str) -> bool:
        """
        判断用户是否拥有某权限
        优先级：黑名单 → 白名单 → 角色（含继承）

        Args:
            perm_str: 要检查的权限字符串

        Returns:
            bool: 如果用户拥有该权限返回True，否则返回False
        """
        # 1. 黑名单一票否决
        for p in self._blacklist:
            if PermissionMatcher.match(p, perm_str):
                return False
        # 2. 白名单直接通过
        for p in self._whitelist:
            if PermissionMatcher.match(p, perm_str):
                return True
        # 3. 遍历所有绑定角色（含继承）
        checked: Set[Role] = set()
        for r in self._roles:
            if r not in checked and r.has_permission(perm_str):
                return True
            checked.add(r)
        return False

    def get_permission_tree(self) -> Dict[str, Any]:
        """
        合并所有角色、黑白名单，生成一颗完整的权限树
        __status__ = True / False  表示最终允许或拒绝

        Returns:
            Dict[str, Any]: 权限树字典，包含权限状态信息
        """
        tree: Dict[str, Any] = {}

        def insert(perm: str, status: bool) -> None:
            """向树中插入权限及其状态"""
            parts = (
                [perm]
                if (perm.startswith("[") and perm.endswith("]"))
                else perm.split(".")
            )
            d = tree
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            last = parts[-1]
            if last not in d:
                d[last] = {}
            d[last]["__status__"] = status

        # 收集所有角色权限（含继承）
        all_perms: Set[str] = set()
        role_queue: List[Role] = list(self._roles)
        visited_roles: Set[Role] = set(self._roles)
        while role_queue:
            r = role_queue.pop(0)
            all_perms.update(r._permissions)
            for p in r._parents:
                if p not in visited_roles:
                    visited_roles.add(p)
                    role_queue.append(p)

        # 插入权限
        for perm in all_perms:
            insert(perm, True)
        for perm in self._whitelist:
            insert(perm, True)
        for perm in self._blacklist:
            insert(perm, False)

        return tree
