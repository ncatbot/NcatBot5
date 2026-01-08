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
from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("RBAC")


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
        """
        logger.debug("权限匹配: 模式=%r, 目标=%r", pattern, target)

        # 若被 [] 包裹，则整体当正则处理
        if pattern.startswith("[") and pattern.endswith("]"):
            regex_content = pattern[1:-1]
            try:
                matched = re.fullmatch(regex_content, target) is not None
                logger.debug("正则表达式匹配: 模式=%r, 结果=%s", regex_content, matched)
                return matched
            except re.error:
                logger.debug("无效的正则表达式: %r", regex_content)
                return False

        # 其余情况先转义，再做通配符替换
        regex_pattern = re.escape(pattern)
        regex_pattern = regex_pattern.replace(r"\*\*", ".*")  # ** 匹配任意深度（含点）
        regex_pattern = regex_pattern.replace(r"\*", "[^.]*")  # *  匹配单段（不含点）
        matched = re.match(f"^{regex_pattern}$", target) is not None
        logger.debug(
            "通配符匹配: 原模式=%r, 转换后=%r, 结果=%s", pattern, regex_pattern, matched
        )
        return matched


# ------------------------------------------------------
# 管理器：集中管理所有角色与用户
# ------------------------------------------------------
class RBACManager:
    def __init__(self, name: str = "default") -> None:
        self.name: str = name
        self._users: Dict[str, "User"] = {}
        self._roles: Dict[str, "Role"] = {}
        logger.debug("RBAC管理器<%s> 已创建", name)

    # ---------- 快捷创建 ----------
    def create_user(self, username: str) -> "User":
        if username in self._users:
            raise ValueError(f"用户<{username}> 已存在（禁止覆盖）")
        user = User(self, username)
        self._users[username] = user
        logger.info("用户<%s> 已创建", username)
        return user

    def create_role(self, rolename: str) -> "Role":
        if rolename in self._roles:
            raise ValueError(f"角色<{rolename}> 已存在（禁止覆盖）")
        role = Role(self, rolename)
        self._roles[rolename] = role
        logger.info("角色<%s> 已创建", rolename)
        return role

    # -------------- 显式删除 --------------
    def delete_user(self, username: str) -> None:
        """
        删除用户，若不存在抛 KeyError。
        可选：若检测到外部强引用可拒绝删除（安全模式）。
        """
        if username not in self._users:
            raise KeyError(f"用户<{username}> 不存在")
        user = self._users[username]

        # 因为 _users 里的是强引用，所以引用计数 >=2 说明外部仍持有。
        if sys.getrefcount(user) > 2:
            raise RuntimeError(f"用户<{username}> 仍被外部引用（安全检查）")

        del self._users[username]
        logger.info("用户<%s> 已删除", username)

    def delete_role(self, rolename: str) -> None:
        """
        删除角色，若不存在抛 KeyError。
        额外检查：仍有用户继承该角色时拒绝删除（可解除继承后再删）。
        """
        if rolename not in self._roles:
            raise KeyError(f"角色<{rolename}> 不存在")
        role = self._roles[rolename]

        # 检查是否还有用户依赖
        dependent_users = [u.name for u in self._users.values() if role in u._roles]
        if dependent_users:
            raise RuntimeError(f"角色<{rolename}> 仍被以下用户使用: {dependent_users}")

        # 检查是否还被别的角色继承
        dependent_roles = [r.name for r in self._roles.values() if role in r._parents]
        if dependent_roles:
            raise RuntimeError(f"角色<{rolename}> 仍被以下角色继承: {dependent_roles}")

        del self._roles[rolename]
        logger.info("角色<%s> 已删除", rolename)

    # ---------- 快捷查找 ----------
    def get_user(self, name: str) -> Optional["User"]:
        return self._users.get(name)

    def get_role(self, name: str) -> Optional["Role"]:
        return self._roles.get(name)

    # --------------------------------------------------
    # 序列化：把当前整个系统压成纯字典，方便 JSON 保存
    # --------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
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
        data = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("RBAC数据已保存到 %s", filepath)

    # --------------------------------------------------
    # 类方法：从文件重建整个系统
    # --------------------------------------------------
    @classmethod
    def load_from_file(cls, filepath: str) -> "RBACManager":
        with open(filepath, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
            assert isinstance(data, dict)

        # 1. 先建管理器壳子
        manager = cls(data.get("manager_name", "loaded"))
        logger.info("正在从 %s 加载RBAC数据", filepath)

        # 2. 第一遍：把所有 Role / User 对象造出来（不连关系）
        role_map: Dict[str, Role] = {}
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

        logger.info("RBAC数据已从 %s 加载完成", filepath)
        return manager


# ------------------------------------------------------
# 基类：给 Role 与 User 提供"同一管理器"安全检查
# ------------------------------------------------------
class ManagedEntity:
    def __init__(self, manager: RBACManager) -> None:
        self._manager: RBACManager = manager

    def _check_manager_compatibility(self, other: "ManagedEntity") -> None:
        # 防止跨管理器操作，避免权限污染
        if self._manager is not other._manager:
            raise RuntimeError("安全错误：不允许跨管理器交互！")


# ------------------------------------------------------
# 角色：拥有权限 + 可继承父角色
# ------------------------------------------------------
class Role(ManagedEntity):
    def __init__(self, manager: RBACManager, name: str) -> None:
        super().__init__(manager)
        self.name: str = name
        self._permissions: Set[str] = set()
        self._parents: Set["Role"] = set()

    def add_permission(self, perm_str: str) -> None:
        self._permissions.add(perm_str)
        logger.info("角色<%s> 添加权限: %r", self.name, perm_str)

    def inherit_from(self, parent_role: "Role") -> None:
        self._check_manager_compatibility(parent_role)
        self._parents.add(parent_role)
        logger.info("角色<%s> 继承自角色<%s>", self.name, parent_role.name)

    def has_permission(
        self, perm_str: str, checked_roles: Optional[Set["Role"]] = None
    ) -> bool:
        if checked_roles is None:
            _checked_roles: Set["Role"] = set()
        else:
            _checked_roles = checked_roles

        if self in _checked_roles:
            return False
        _checked_roles.add(self)

        # 先看自身权限
        for p in self._permissions:
            if PermissionMatcher.match(p, perm_str):
                logger.debug("角色<%s> 自身权限匹配: %r", self.name, perm_str)
                return True
        # 再看父角色
        for parent in self._parents:
            if parent.has_permission(perm_str, _checked_roles):
                logger.debug(
                    "角色<%s> 通过父角色<%s> 继承匹配权限: %r",
                    self.name,
                    parent.name,
                    perm_str,
                )
                return True
        logger.debug("角色<%s> 缺少权限: %r", self.name, perm_str)
        return False

    def get_permission_tree(self) -> Dict[str, Any]:
        tree: Dict[str, Any] = {}
        for perm in self._permissions:
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
        logger.debug("角色<%s> 权限树: %s", self.name, tree)
        return tree


# ------------------------------------------------------
# 用户：绑定角色 + 黑白名单
# 权限判断顺序：黑名单 > 白名单 > 角色
# ------------------------------------------------------
class User(ManagedEntity):
    def __init__(self, manager: RBACManager, name: str) -> None:
        super().__init__(manager)
        self.name: str = name
        self._roles: Set[Role] = set()
        self._whitelist: Set[str] = set()
        self._blacklist: Set[str] = set()
        logger.info("用户<%s> 已创建", name)

    def add_role(self, role: Role) -> None:
        self._check_manager_compatibility(role)
        self._roles.add(role)
        logger.info("用户<%s> 添加角色<%s>", self.name, role.name)

    def permit(self, p: str) -> None:
        self._whitelist.add(p)
        logger.info("用户<%s> 白名单添加: %r", self.name, p)

    def deny(self, p: str) -> None:
        self._blacklist.add(p)
        logger.info("用户<%s> 黑名单添加: %r", self.name, p)

    def can(self, perm_str: str) -> bool:
        logger.debug("用户<%s> 检查权限: %r", self.name, perm_str)
        # 1. 黑名单一票否决
        for p in self._blacklist:
            if PermissionMatcher.match(p, perm_str):
                logger.warning("用户<%s> 权限被黑名单拒绝: 模式=%r", self.name, p)
                return False
        # 2. 白名单直接通过
        for p in self._whitelist:
            if PermissionMatcher.match(p, perm_str):
                logger.debug("用户<%s> 权限被白名单允许: 模式=%r", self.name, p)
                return True
        # 3. 遍历所有绑定角色（含继承）
        checked: Set[Role] = set()
        for r in self._roles:
            if r not in checked and r.has_permission(perm_str):
                logger.debug("用户<%s> 权限通过角色<%s> 允许", self.name, r.name)
                return True
            checked.add(r)
        logger.warning("用户<%s> 权限最终拒绝: %r", self.name, perm_str)
        return False

    @classmethod
    def quick_can(cls, user: "User", perm: str, *extra: "Role") -> bool:
        """
        快捷权限检查：除了用户自身角色外，还可以额外传入一些临时角色进行检查
        """
        # 合并临时角色到单次检查
        checked: set["Role"] = set()
        for r in (*user._roles, *extra):
            if r not in checked and r.has_permission(perm):
                return True
            checked.add(r)
        return False

    def get_permission_tree(self) -> Dict[str, Any]:
        tree: Dict[str, Any] = {}

        def insert(perm: str, status: bool) -> None:
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

        for perm in all_perms:
            insert(perm, True)
        for perm in self._whitelist:
            insert(perm, True)
        for perm in self._blacklist:
            insert(perm, False)

        logger.debug("用户<%s> 合并权限树: %s", self.name, tree)
        return tree
