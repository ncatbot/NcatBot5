from __future__ import annotations

from typing import Any, Dict

from . import PluginMixin


class DictProxy(dict):
    """继承 dict，仅对 Python 层能走到的方法做覆盖。"""

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._log: list[tuple[str, Any, Any]] = []

    # ---------- 拦截 ----------
    def __setitem__(self, key: Any, value: Any) -> None:
        self._log.append(("SET", key, value))
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self._log.append(("DEL", key))
        super().__delitem__(key)

    def pop(self, key: Any, *default: Any) -> Any:
        self._log.append(("POP", key))
        return super().pop(key, *default)

    # ---------- 辅助 ----------
    def to_dict(self) -> Dict[str, Any]:
        """返回纯 dict，方便序列化。"""
        return dict(self)


class ConfigerMixin(PluginMixin):
    def __init__(self):
        super().__init__()
        self._config = DictProxy()

    # ---------- 只读访问 ----------
    @property
    def config(self) -> DictProxy:
        return self._config

    # ---------- 整表替换 ----------
    @config.setter
    def config(self, val: Dict[str, Any] | DictProxy) -> None:
        if not getattr(self, "_config", None):
            self._config = DictProxy()
        if isinstance(val, dict):
            self._config = DictProxy(val)
        elif isinstance(val, DictProxy):
            self._config = val
        else:
            raise ValueError("未知的字典设置类型")
