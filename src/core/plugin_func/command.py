import ast
import functools
import inspect
import re
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Concatenate,
    Dict,
    List,
    Literal,
    NewType,
    Optional,
    ParamSpec,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from src.core.IM import Message, User
from src.plugins_system import Event, LazyDecoratorResolver
from src.plugins_system.core.lazy_resolver import create_namespaced_decorator
from src.plugins_system.core.mixin import PluginMixin

# ==============================
# 类型定义
# ==============================

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

Permission = NewType("Permission", str)
CooldownUnit = Literal["second", "minute", "hour", "day"]

# ==============================
# AST 辅助函数
# ==============================


def _ast_parse_signature(func: Callable) -> Dict[str, Any]:
    """
    使用 AST 解析函数签名，获取参数信息、默认值和返回类型。
    这比 inspect 更静态，不依赖于函数是否可调用。
    """
    try:
        source = inspect.getsource(func)
        tree = ast.parse(source)

        # 查找对应的 FunctionDef
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func.__name__:
                func_node = node
                break

        if not func_node:
            return {}

        args_info = []
        # 跳过 'self' (index 0)
        args = func_node.args.args[1:]
        defaults = func_node.args.defaults

        # 处理默认值对齐
        defaults_offset = len(args) - len(defaults)

        for i, arg in enumerate(args):
            arg_name = arg.arg
            arg_type = ast.unparse(arg.annotation) if arg.annotation else None
            has_default = i >= defaults_offset

            default_val = None
            if has_default:
                default_node = defaults[i - defaults_offset]
                default_val = (
                    ast.literal_eval(default_node)
                    if isinstance(
                        default_node, (ast.Constant, ast.Num, ast.Str, ast.NameConstant)
                    )
                    else ast.unparse(default_node)
                )

            args_info.append(
                {
                    "name": arg_name,
                    "type": arg_type,
                    "default": default_val,
                    "required": not has_default,
                }
            )

        return_type = ast.unparse(func_node.returns) if func_node.returns else None

        return {"args": args_info, "return_type": return_type}
    except Exception:
        # 如果 AST 解析失败（例如动态生成的函数），回退到空字典
        return {}


# ==============================
# 配置与节点
# ==============================


@dataclass
class CommandConfig:
    """命令配置数据类"""

    # 触发路径: ["mcp", "server"] -> 触发词 "mcp server"
    path: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    permission: Optional[Permission] = None

    # 冷却与限流
    cooldown: Optional[Union[int, float]] = None
    cooldown_unit: CooldownUnit = "second"
    rate_limit: Optional[int] = None
    rate_limit_window: int = 60

    # 文本信息
    description: Optional[str] = None
    usage: Optional[str] = None
    examples: List[str] = field(default_factory=list)

    # AST 解析出的参数信息
    params: List[Dict[str, Any]] = field(default_factory=list)

    # 开关与限制
    hidden: bool = False
    disabled: bool = False
    guild_only: bool = False
    private_only: bool = False

    # 权限快捷方式
    admin_only: bool = False
    superuser_only: bool = False
    owner_only: bool = False

    @property
    def trigger(self) -> str:
        """将路径列表拼接为触发字符串"""
        return " ".join(self.path)

    def to_dict(self) -> dict:
        return {
            "trigger": self.trigger,
            "aliases": self.aliases,
            "permission": self.permission,
            "params": self.params,
            "description": self.description,
            "usage": self.usage,
            "examples": self.examples,
            "hidden": self.hidden,
            "disabled": self.disabled,
        }


class CommandNode:
    """
    命令节点，代表 Trie 树中的一个节点。
    """

    def __init__(self):
        self.children: Dict[str, "CommandNode"] = {}
        self.handler: Optional[Callable] = None
        self.config: Optional[CommandConfig] = None


class CommandTrie:
    """
    命令前缀树

    用于高效匹配命令路径，支持任意层级的子命令。
    """

    def __init__(self):
        self.root = CommandNode()
        # 别名扁平映射：alias_string -> CommandNode
        # 这样可以避免在 Trie 中插入不规则的别名，保持 Trie 结构的纯洁性
        self.alias_map: Dict[str, CommandNode] = {}

    def insert(
        self,
        path: List[str],
        handler: Callable,
        config: CommandConfig,
        aliases: List[str],
    ):
        """插入命令到 Trie"""
        node = self.root
        for segment in path:
            if segment not in node.children:
                node.children[segment] = CommandNode()
            node = node.children[segment]

        node.handler = handler
        node.config = config

        # 注册别名：直接映射到该节点
        for alias in aliases:
            self.alias_map[alias] = node

    def match(
        self, text: str
    ) -> Tuple[Optional[Callable], Optional[CommandConfig], List[str]]:
        """
        匹配文本
        返回:
        """
        segments = text.strip().split()

        # 1. 尝试在 Trie 中精确匹配路径
        node = self.root
        matched_depth = 0

        for seg in segments:
            if seg in node.children:
                node = node.children[seg]
                matched_depth += 1
            else:
                break

        if node.handler and matched_depth == len(segments):
            # 完全匹配
            return node.handler, node.config, []

        # 2. 如果 Trie 没完全匹配，尝试匹配别名
        # 注意：这里假设别名是全词匹配，或者用户输入的就是别名本身
        # 简单起见，我们检查输入文本是否完全等于某个别名
        if text in self.alias_map:
            alias_node = self.alias_map[text]
            return alias_node.handler, alias_node.config, []

        # 如果是部分匹配（如输入 "mcp"，匹配到 mcp 节点，但该节点无 handler）
        # 可以在此处扩展逻辑，比如返回可能的子命令列表
        return None, None, []


# ==============================
# 全局路由器
# ==============================


class CommandRouter:
    """全局命令路由器 - 单例模式"""

    _instance: Optional["CommandRouter"] = None
    _is_registered: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._trie = CommandTrie()
        return cls._instance

    def register(self, path: List[str], handler: Callable, config: CommandConfig):
        """注册命令路径"""
        if not path:
            raise ValueError("Command path cannot be empty")

        self._trie.insert(path, handler, config, config.aliases)

    def setup_listener(self, event_bus):
        """注册全局监听器"""
        if self._is_registered:
            return
        event_bus.register_handler(re.compile(r".*"), self._dispatch, "CommandRouter")
        self._is_registered = True

    async def _dispatch(self, event: Event[Message]):
        msg = event.data
        if not isinstance(msg, Message):
            return

        text = str(msg).strip()
        if not text:
            return

        handler, config, _ = self._trie.match(text)

        if handler and config:
            # 执行包装后的处理器
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        # else: 无匹配，忽略


# ==============================
# 包装器逻辑
# ==============================


class CommandFunc:
    """命令函数包装器"""

    _cooldown_store: Dict[str, float] = {}
    _rate_limit_store: Dict[str, List[float]] = {}

    def __init__(self, func: Callable, config: CommandConfig):
        self.original_func = func
        self.config = config
        self.is_async = inspect.iscoroutinefunction(func)

    def _get_user_key(self, event: Event[Message]) -> str:
        msg = event.data
        if not isinstance(msg, Message):
            return "unknown"
        return f"{self.config.trigger}:{msg.sender_id}"

    def build(self) -> Callable:
        func = self.original_func

        if self.config.guild_only or self.config.private_only:
            func = self._wrap_context_check(func)
        if (
            self.config.admin_only
            or self.config.superuser_only
            or self.config.owner_only
            or self.config.permission
        ):
            func = self._wrap_permission_check(func)
        if self.config.cooldown:
            func = self._wrap_cooldown(func)
        if self.config.rate_limit:
            func = self._wrap_rate_limit(func)

        if self.is_async:
            return self._async_final_wrapper(func)
        else:
            return self._sync_to_async_final_wrapper(func)

    def _wrap_context_check(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ev: Event[Message]):
            msg = ev.data
            if not isinstance(msg, Message):
                return
            is_group = bool(msg.group_id)
            is_private = not is_group
            if self.config.guild_only and is_private:
                return
            if self.config.private_only and is_group:
                return

            return await func(ev) if self.is_async else func(ev)

        return wrapper

    def _wrap_permission_check(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ev: Event[Message]):
            msg = ev.data
            if not isinstance(msg, Message):
                return
            user = User(msg.sender_id, group_id=msg.group_id)

            if self.config.superuser_only and not user.has_role("Root"):
                return
            if self.config.admin_only and not user.has_role("Admin"):
                return
            if self.config.owner_only and not user.has_role("Owner"):
                return
            if self.config.permission and not user.can(self.config.permission):
                return

            return await func(ev) if self.is_async else func(ev)

        return wrapper

    def _wrap_cooldown(self, func: Callable) -> Callable:
        unit_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        cd_sec = self.config.cooldown * unit_map.get(self.config.cooldown_unit, 1)

        @functools.wraps(func)
        async def wrapper(ev: Event):
            key = self._get_user_key(ev)
            now = time.time()
            if now - CommandFunc._cooldown_store.get(key, 0) < cd_sec:
                return
            CommandFunc._cooldown_store[key] = now
            return await func(ev) if self.is_async else func(ev)

        return wrapper

    def _wrap_rate_limit(self, func: Callable) -> Callable:
        limit = self.config.rate_limit
        window = self.config.rate_limit_window

        @functools.wraps(func)
        async def wrapper(ev: Event):
            key = self._get_user_key(ev)
            now = time.time()
            history = [
                t
                for t in CommandFunc._rate_limit_store.get(key, [])
                if now - t <= window
            ]

            if len(history) >= limit:
                return
            history.append(now)
            CommandFunc._rate_limit_store[key] = history

            return await func(ev) if self.is_async else func(ev)

        return wrapper

    def _async_final_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ev: Event):
            if self.config.disabled:
                return
            return await func(ev)

        return wrapper

    def _sync_to_async_final_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ev: Event):
            if self.config.disabled:
                return
            return func(ev)

        return wrapper


# ==============================
# 命令组与装饰器
# ==============================


class CommandGroup:
    """
    命令组，支持任意嵌套和路径定义

    Example:
        group = CommandGroup("bot", "admin")

        @group.command("user") # 触发词: "bot admin user"
        def add_user(): ...
    """

    def __init__(self, *path_segments: str):
        # 存储路径片段
        self.path: List[str] = list(path_segments)

    def command(self, *sub_segments: str, **kwargs):
        """
        定义子命令

        Args:
            *sub_segments: 子命令路径片段
            **kwargs: 其他 CommandConfig 参数
        """

        def _decorator(f: Callable):
            # 合并路径：Group路径 + 装饰器参数路径
            full_path = self.path + list(sub_segments)

            # 如果没有提供 name，尝试从函数名获取（作为路径的最后一段，除非 sub_segments 已提供）
            if not full_path:
                func_name = getattr(f, "__name__", None)
                if not func_name:
                    raise ValueError("Command must have a valid name or path segments")
                full_path.append(func_name)

            kwargs["path"] = full_path
            return command(**kwargs)(f)

        return _decorator

    def group(self, *sub_segments: str) -> "CommandGroup":
        """创建子组"""
        return CommandGroup(*(self.path + list(sub_segments)))


@overload
def command(func: Callable[Concatenate[T, P], R]) -> Callable[Concatenate[T, P], R]: ...


@overload
def command(
    *path_segments: str,
    aliases: Optional[List[str]] = None,
    permission: Optional[Permission] = None,
    cooldown: Optional[Union[int, float]] = None,
    cooldown_unit: CooldownUnit = "second",
    rate_limit: Optional[int] = None,
    rate_limit_window: int = 60,
    description: Optional[str] = None,
    usage: Optional[str] = None,
    examples: Optional[List[str]] = None,
    hidden: bool = False,
    disabled: bool = False,
    guild_only: bool = False,
    private_only: bool = False,
    admin_only: bool = False,
    superuser_only: bool = False,
    owner_only: bool = False,
) -> Callable[[Callable[Concatenate[T, P], R]], Callable[Concatenate[T, P], R]]: ...


def command(
    func_or_path: Union[Callable, str] = None,
    *path_segments: str,
    aliases: Optional[List[str]] = None,
    permission: Optional[Permission] = None,
    cooldown: Optional[Union[int, float]] = None,
    cooldown_unit: CooldownUnit = "second",
    rate_limit: Optional[int] = None,
    rate_limit_window: int = 60,
    description: Optional[str] = None,
    usage: Optional[str] = None,
    examples: Optional[List[str]] = None,
    hidden: bool = False,
    disabled: bool = False,
    guild_only: bool = False,
    private_only: bool = False,
    admin_only: bool = False,
    superuser_only: bool = False,
    owner_only: bool = False,
) -> Union[Callable, Callable[[Callable], Callable]]:
    """
    命令装饰器

    支持多种定义方式:
    1. @command -> 使用函数名
    2. @command("trigger") -> 使用 "trigger"
    3. @command("a", "b") -> 使用 "a b"
    """

    # 处理第一个参数可能是函数的情况（无参数调用）
    if callable(func_or_path):
        # 此时 func_or_path 是函数，path_segments 为空
        func = func_or_path
        return _create_decorator(
            func,
            [],
            {
                "aliases": aliases,
                "permission": permission,
                "cooldown": cooldown,
                "cooldown_unit": cooldown_unit,
                "rate_limit": rate_limit,
                "rate_limit_window": rate_limit_window,
                "description": description,
                "usage": usage,
                "examples": examples,
                "hidden": hidden,
                "disabled": disabled,
                "guild_only": guild_only,
                "private_only": private_only,
                "admin_only": admin_only,
                "superuser_only": superuser_only,
                "owner_only": owner_only,
            },
        )

    # 否则，func_or_path 是第一个路径片段
    current_path = [func_or_path] + list(path_segments) if func_or_path else []

    def _decorator(f: Callable) -> Callable:
        kwargs = {
            "aliases": aliases,
            "permission": permission,
            "cooldown": cooldown,
            "cooldown_unit": cooldown_unit,
            "rate_limit": rate_limit,
            "rate_limit_window": rate_limit_window,
            "description": description,
            "usage": usage,
            "examples": examples,
            "hidden": hidden,
            "disabled": disabled,
            "guild_only": guild_only,
            "private_only": private_only,
            "admin_only": admin_only,
            "superuser_only": superuser_only,
            "owner_only": owner_only,
        }
        return _create_decorator(f, current_path, kwargs)

    return _decorator


def _create_decorator(f: Callable, path: List[str], kwargs: Dict) -> Callable:
    """内部工厂函数，负责构建配置和元数据"""

    # 1. 解析 Docstring
    doc_info = _parse_docstring(f.__doc__)

    # 2. 如果 path 为空，回退到函数名
    if not path:
        func_name = getattr(f, "__name__", None)
        if not func_name:
            raise ValueError("Command must have a valid name or explicit path segments")
        path = [func_name]

    # 3. 使用 AST 解析参数信息
    ast_info = _ast_parse_signature(f)
    params = ast_info.get("args", [])

    # 4. 构建 Config
    config_args = {
        "path": path,
        "aliases": kwargs.get("aliases") or [],
        "permission": kwargs.get("permission"),
        "cooldown": kwargs.get("cooldown"),
        "cooldown_unit": kwargs.get("cooldown_unit", "second"),
        "rate_limit": kwargs.get("rate_limit"),
        "rate_limit_window": kwargs.get("rate_limit_window", 60),
        "description": kwargs.get("description") or doc_info.get("description"),
        "usage": kwargs.get("usage") or doc_info.get("usage"),
        "examples": kwargs.get("examples") or doc_info.get("examples"),
        "params": params,  # 注入 AST 解析结果
        "hidden": kwargs.get("hidden", False),
        "disabled": kwargs.get("disabled", False),
        "guild_only": kwargs.get("guild_only", False),
        "private_only": kwargs.get("private_only", False),
        "admin_only": kwargs.get("admin_only", False),
        "superuser_only": kwargs.get("superuser_only", False),
        "owner_only": kwargs.get("owner_only", False),
    }

    # 5. 写入元数据
    # 我们将整个 config 字典存入，Resolver 负责实例化 CommandConfig
    decorator = create_namespaced_decorator("command", "command", **config_args)
    return decorator()(f)


def _parse_docstring(doc: Optional[str]) -> Dict[str, Any]:
    if not doc:
        return {}
    lines = [line.strip() for line in doc.strip().splitlines()]
    if not lines:
        return {}

    result = {"description": lines[0], "usage": None, "examples": []}
    current_section, buffer = None, []

    for line in lines[1:]:
        if line.lower().startswith("args:"):
            current_section = "args"
            continue
        elif line.lower().startswith("examples:"):
            if buffer:
                result["usage"] = "\n".join(buffer).strip()
            current_section = "examples"
            buffer = []
            continue

        if current_section == "args":
            buffer.append(line)
        elif current_section == "examples":
            if line:
                result["examples"].append(re.sub(r"^\s*[\d\-\*]+\.\s*", "", line))

    if current_section == "args" and buffer:
        result["usage"] = "\n".join(buffer).strip()
    return result


# ==============================
# 混入与解析器
# ==============================


class CommandMixin(PluginMixin):
    def __init__(self: T) -> T:
        self._commands: Dict[str, CommandConfig] = {}  # name -> config
        return self

    def register_command(self, name: str, handler: Callable, config: CommandConfig):
        self._commands[name] = config
        router = CommandRouter()
        router.register(config.path, handler, config)


class CommandResolver(LazyDecoratorResolver):
    tag = "command"
    space = "command"
    required_mixin = CommandMixin

    def handle(self, plugin: CommandMixin, func: Callable, event_bus):
        router = CommandRouter()
        router.setup_listener(event_bus)

        data = self.get_kwd(func)
        if not data:
            return

        config = CommandConfig(**data)
        cmd_func = CommandFunc(func, config)
        handler = cmd_func.build()

        # name 依然需要唯一标识，用于插件内部管理
        name = config.trigger.replace(" ", "_")
        plugin.register_command(name, handler, config)
