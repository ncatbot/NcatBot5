import functools
import inspect
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    get_type_hints,
)

from src.core.IM import Message, User
from src.plugins_system import Event

# ==============================
# 类型定义
# ==============================

Permission = str
CooldownUnit = Literal["second", "minute", "hour", "day"]
CommandHandler = Callable[[Any, Any], Any]  # (self, event/cmd) -> Any

# ==============================
# 命令解析结果
# ==============================


@dataclass
class CommandArgs:
    """命令解析结果，可以像列表一样索引参数"""

    event: Event[Message]
    args: List[str]

    def __init__(self, event: Event[Message], args: List[str]):
        self.event = event
        self.args = args
        self._msg = event.data

    def __getitem__(self, index: int) -> str:
        """通过索引获取参数"""
        return self.args[index]

    def __len__(self) -> int:
        """参数个数"""
        return len(self.args)

    def get(self, index: int, default: Any = None) -> Any:
        """安全获取参数"""
        try:
            return self.args[index]
        except IndexError:
            return default

    def get_int(self, index: int, default: int = 0) -> int:
        """获取整数参数"""
        try:
            return int(self.args[index])
        except (IndexError, ValueError):
            return default

    def get_float(self, index: int, default: float = 0.0) -> float:
        """获取浮点数参数"""
        try:
            return float(self.args[index])
        except (IndexError, ValueError):
            return default

    @property
    def text(self) -> str:
        """原始消息文本"""
        return str(self._msg) if self._msg else ""

    @property
    def sender_id(self) -> str:
        """发送者ID"""
        return self._msg.sender_id if self._msg else ""

    @property
    def group_id(self) -> Optional[str]:
        """群组ID"""
        return self._msg.group_id if self._msg else None

    @property
    def raw_args(self) -> str:
        """原始参数字符串"""
        return " ".join(self.args)

    def __repr__(self) -> str:
        return f"CommandArgs(args={self.args}, sender={self.sender_id})"


# ==============================
# 命令配置
# ==============================


@dataclass
class CommandConfig:
    """命令配置"""

    # 触发词
    name: str = ""
    aliases: List[str] = field(default_factory=list)
    description: str = ""

    # 参数传递模式
    raw: bool = False  # True: 传入原始event; False: 传入CommandArgs

    # 权限控制
    permission: Optional[Permission] = None
    admin_only: bool = False
    owner_only: bool = False
    root_only: bool = True

    # 冷却与限流
    cooldown: Optional[Union[int, float]] = None
    cooldown_unit: CooldownUnit = "second"
    rate_limit: Optional[int] = None
    rate_limit_window: int = 60

    # 上下文限制
    guild_only: bool = False
    private_only: bool = False

    # 状态控制
    enabled: bool = True
    hidden: bool = False

    # 参数信息（自动解析）
    params: List[Dict[str, Any]] = field(default_factory=list)

    def enable(self) -> None:
        """启用命令"""
        self.enabled = True

    def disable(self) -> None:
        """禁用命令"""
        self.enabled = False

    def set_permission(self, permission: Optional[Permission]) -> None:
        """设置权限"""
        self.permission = permission

    def add_alias(self, alias: str) -> None:
        """添加别名"""
        if alias not in self.aliases:
            self.aliases.append(alias)

    def remove_alias(self, alias: str) -> None:
        """移除别名"""
        if alias in self.aliases:
            self.aliases.remove(alias)


# ==============================
# 命令实例
# ==============================


class Command:
    """命令实例"""

    def __init__(self, instance: Any, handler: CommandHandler, config: CommandConfig):
        self.instance = instance  # Plugin实例
        self.handler = handler  # 原始处理器
        self.config = config
        self._original_handler = handler
        self._wrapped_handler = self._wrap_handler()

        # 冷却和限流存储
        self._cooldown_store: Dict[str, float] = {}
        self._rate_limit_store: Dict[str, List[float]] = {}

    def _get_user_key(self, event: Event[Message]) -> str:
        """获取用户标识键"""
        msg = event.data
        if not isinstance(msg, Message):
            return "unknown"
        return f"{self.config.name}:{msg.sender_id}"

    def _create_handler_wrapper(self) -> Callable[[Event[Message]], Any]:
        """创建处理器包装器，根据raw模式决定传入参数"""
        if self.config.raw:
            # raw=True: 传入原始event
            @functools.wraps(self.handler)
            def wrapper(event: Event[Message]) -> Any:
                return self.handler(self.instance, event)

        else:
            # raw=False: 传入CommandArgs
            @functools.wraps(self.handler)
            def wrapper(event: Event[Message]) -> Any:
                # 从事件元数据获取参数
                args = event.metadata.get("command_args", [])
                cmd_args = CommandArgs(event, args)
                return self.handler(self.instance, cmd_args)

        return wrapper

    def _wrap_handler(self) -> Callable[[Event[Message]], Any]:
        """包装处理器，添加各种检查"""
        handler = self._create_handler_wrapper()

        # 添加权限检查
        if (
            self.config.permission
            or self.config.admin_only
            or self.config.root_only
            or self.config.owner_only
        ):
            handler = self._wrap_permission_check(handler)

        # 添加上下文检查
        if self.config.guild_only or self.config.private_only:
            handler = self._wrap_context_check(handler)

        # 添加冷却检查
        if self.config.cooldown:
            handler = self._wrap_cooldown(handler)

        # 添加限流检查
        if self.config.rate_limit:
            handler = self._wrap_rate_limit(handler)

        # 添加启用状态检查
        handler = self._wrap_enabled_check(handler)

        return handler

    def _wrap_permission_check(self, handler: Callable) -> Callable:
        """包装权限检查"""

        @functools.wraps(handler)
        def wrapper(event: Event[Message]) -> Any:
            msg = event.data
            if not isinstance(msg, Message):
                return

            user = getattr(msg, "_sender_cache", None) or User(
                msg.sender_id, group_id=msg.group_id
            )

            # 检查权限
            if self.config.root_only and not user.has_role("Root"):
                return
            if self.config.admin_only and not user.has_role("Admin"):
                return
            if self.config.owner_only and not user.has_role("Owner"):
                return
            if self.config.permission and not user.can(self.config.permission):
                return

            return handler(event)

        return wrapper

    def _wrap_context_check(self, handler: Callable) -> Callable:
        """包装上下文检查"""

        @functools.wraps(handler)
        def wrapper(event: Event[Message]) -> Any:
            msg = event.data
            if not isinstance(msg, Message):
                return

            is_group = bool(msg.group_id)
            is_private = not is_group

            if self.config.guild_only and is_private:
                return
            if self.config.private_only and is_group:
                return

            return handler(event)

        return wrapper

    def _wrap_cooldown(self, handler: Callable) -> Callable:
        """包装冷却检查"""
        unit_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        cd_sec = self.config.cooldown * unit_map.get(self.config.cooldown_unit, 1)

        @functools.wraps(handler)
        def wrapper(event: Event[Message]) -> Any:
            key = self._get_user_key(event)
            now = time.time()

            if now - self._cooldown_store.get(key, 0) < cd_sec:
                return

            self._cooldown_store[key] = now
            return handler(event)

        return wrapper

    def _wrap_rate_limit(self, handler: Callable) -> Callable:
        """包装限流检查"""
        limit = self.config.rate_limit
        window = self.config.rate_limit_window

        @functools.wraps(handler)
        def wrapper(event: Event[Message]) -> Any:
            key = self._get_user_key(event)
            now = time.time()

            # 清理过期记录
            history = [
                t for t in self._rate_limit_store.get(key, []) if now - t <= window
            ]

            if len(history) >= limit:
                return

            history.append(now)
            self._rate_limit_store[key] = history
            return handler(event)

        return wrapper

    def _wrap_enabled_check(self, handler: Callable) -> Callable:
        """包装启用状态检查"""

        @functools.wraps(handler)
        def wrapper(event: Event[Message]) -> Any:
            if not self.config.enabled:
                return
            return handler(event)

        return wrapper

    async def __call__(self, event: Event[Message]) -> Any:
        """执行命令"""
        if inspect.iscoroutinefunction(self._wrapped_handler):
            return await self._wrapped_handler(event)
        return self._wrapped_handler(event)


# ==============================
# 命令路由器
# ==============================


class CommandRouter:
    """命令路由器"""

    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._alias_map: Dict[str, str] = {}
        self._prefixes: List[str] = []

    def set_prefixes(self, prefixes: List[str]) -> None:
        """设置命令前缀"""
        self._prefixes = prefixes

    def register(self, instance: Any, command: Command) -> None:
        """注册命令"""
        name = command.config.name

        # if name in self._commands:
        #     raise ValueError(f"命令 '{name}' 已注册")

        self._commands[name] = command

        # 注册别名
        for alias in command.config.aliases:
            if alias in self._alias_map:
                raise ValueError(
                    f"别名 '{alias}' 已被命令 '{self._alias_map[alias]}' 使用"
                )
            self._alias_map[alias] = name

        # 注册带前缀的触发词
        for prefix in self._prefixes:
            prefixed_name = f"{prefix}{name}"
            self._alias_map[prefixed_name] = name

            for alias in command.config.aliases:
                prefixed_alias = f"{prefix}{alias}"
                self._alias_map[prefixed_alias] = name

    def unregister(self, name: str) -> None:
        """注销命令"""
        if name not in self._commands:
            return

        self._commands.pop(name)

        # 清理别名
        aliases_to_remove = []
        for alias, cmd_name in self._alias_map.items():
            if cmd_name == name:
                aliases_to_remove.append(alias)

        for alias in aliases_to_remove:
            del self._alias_map[alias]

    def get_command(self, name: str) -> Optional[Command]:
        """获取命令"""
        # 尝试直接匹配
        if name in self._commands:
            return self._commands[name]

        # 尝试别名匹配
        if name in self._alias_map:
            real_name = self._alias_map[name]
            return self._commands.get(real_name)

        return None

    def parse_message(self, text: str) -> Tuple[Optional[Command], List[str]]:
        """解析消息，返回命令和参数"""
        text = text.strip()
        if not text:
            return None, []

        # 分割命令和参数
        parts = text.split(maxsplit=1)
        command_text = parts[0]
        args_text = parts[1] if len(parts) > 1 else ""

        # 获取命令
        command = self.get_command(command_text)
        if not command:
            return None, []

        # 解析参数
        args = args_text.split() if args_text else []

        return command, args

    async def handle_message(self, event: Event[Message]) -> Optional[Any]:
        """处理消息事件"""
        msg = event.data
        if not isinstance(msg, Message):
            return

        text = str(msg).strip()
        command, args = self.parse_message(text)

        if command:
            # 将参数存入元数据
            event.metadata["command_args"] = args
            event.metadata["command_name"] = command.config.name

            return await command.execute(event)

        return None


# ==============================
# 全局路由器和装饰器
# ==============================

# 全局路由器实例
_global_router = CommandRouter()


def get_router() -> CommandRouter:
    """获取全局路由器"""
    return _global_router


def set_global_prefixes(prefixes: List[str]) -> None:
    """设置全局前缀"""
    _global_router.set_prefixes(prefixes)


# ==============================
# 命令组（支持简洁的装饰器语法）
# ==============================


class CommandGroup:
    """
    命令组，支持简洁的装饰器语法

    示例：
        class Plugin:
            cmds = CommandGroup('test')

            # 方式1：直接装饰
            @cmds
            def echo(self, cmd: CommandArgs):
                return cmd[0]

            # 方式2：带参数的装饰器
            @cmds("help", description="帮助命令", raw=True)
            def help(self, event: Event):
                args = event.metadata.get("command_args", [])
                return f"帮助信息，参数: {args}"

            # 方式3：子组
            admin = cmds.subgroup("admin")

            @admin("add", admin_only=True)
            def add_admin(self, cmd: CommandArgs):
                if len(cmd) > 0:
                    return f"添加管理员: {cmd[0]}"
                return "请输入用户名"
    """

    def __init__(self, base_path: str = ""):
        self.base_path = base_path
        self._instance: Any = None  # 将绑定到Plugin实例
        self._commands: Dict[str, Command] = {}
        self._subgroups: Dict[str, "CommandGroup"] = {}

    def __set_name__(self, owner: type, name: str) -> None:
        """在描述符被分配给类属性时调用"""
        self._instance = None  # 将在__get__中设置

    def __get__(self, instance: Any, owner: type) -> "CommandGroup":
        """获取描述符时绑定实例"""
        if instance is None:
            return self

        # 创建绑定了实例的新CommandGroup
        bound_group = type(self)(self.base_path)
        bound_group._instance = instance

        # 重新绑定子组
        for name, subgroup in self._subgroups.items():
            bound_subgroup = type(subgroup)(subgroup.base_path)
            bound_subgroup._instance = instance
            bound_group._subgroups[name] = bound_subgroup

        return bound_group

    def __call__(self, *args, **kwargs):
        """
        装饰器用法：
        1. @group  # 不带括号
        2. @group("name")  # 带命令名
        3. @group("name", description="desc")  # 带命令名和配置
        """
        # 判断是直接装饰函数还是带参数装饰
        if len(args) == 1 and callable(args[0]):
            # @group 形式
            return self._register_command(args[0], **kwargs)
        else:
            # @group("name") 形式
            def decorator(func: Callable) -> Command:
                # 从位置参数中提取命令名
                cmd_name = None
                if args:
                    cmd_name = args[0]
                # 合并参数
                all_kwargs = kwargs.copy()
                if cmd_name:
                    all_kwargs["name"] = cmd_name
                return self._register_command(func, **all_kwargs)

            return decorator

    def _register_command(self, func: Callable, name: str = "", **kwargs) -> Command:
        """注册命令到组"""
        if self._instance is None:
            raise RuntimeError("CommandGroup必须在类实例中使用")

        # 解析函数签名获取参数信息
        sig = inspect.signature(func)
        params = []

        # 跳过self参数
        param_list = list(sig.parameters.values())
        if param_list and param_list[0].name == "self":
            param_list = param_list[1:]

        for param in param_list:
            param_info = {
                "name": param.name,
                "type": None,
                "required": param.default is inspect._empty,
                "default": (
                    param.default if param.default is not inspect._empty else None
                ),
            }

            # 获取类型注解
            try:
                type_hints = get_type_hints(func)
                if param.name in type_hints:
                    type_ann = type_hints[param.name]
                    param_info["type"] = (
                        type_ann.__name__
                        if hasattr(type_ann, "__name__")
                        else str(type_ann)
                    )
            except Exception:
                pass

            params.append(param_info)

        # 生成完整命令名
        if not name:
            name = func.__name__

        full_name = f"{self.base_path} {name}".strip() if self.base_path else name

        # 解析文档字符串
        doc_info = _parse_docstring(func.__doc__)

        # 创建配置
        config = CommandConfig(
            name=full_name,
            aliases=kwargs.get("aliases", []),
            description=kwargs.get("description") or doc_info.get("description", ""),
            raw=kwargs.get("raw", False),
            permission=kwargs.get("permission"),
            admin_only=kwargs.get("admin_only", False),
            root_only=kwargs.get("root_only", False),
            owner_only=kwargs.get("owner_only", False),
            cooldown=kwargs.get("cooldown"),
            cooldown_unit=kwargs.get("cooldown_unit", "second"),
            rate_limit=kwargs.get("rate_limit"),
            rate_limit_window=kwargs.get("rate_limit_window", 60),
            guild_only=kwargs.get("guild_only", False),
            private_only=kwargs.get("private_only", False),
            enabled=kwargs.get("enabled", True),
            hidden=kwargs.get("hidden", False),
            params=params,
        )

        # 创建命令实例
        cmd = Command(self._instance, func, config)

        # 注册到全局路由器
        _global_router.register(self._instance, cmd)

        # 存储命令
        self._commands[name] = cmd
        return cmd

    def subgroup(self, name: str) -> "CommandGroup":
        """创建子组"""
        if name in self._subgroups:
            return self._subgroups[name]

        base_path = f"{self.base_path} {name}".strip() if self.base_path else name
        subgroup = CommandGroup(base_path)
        self._subgroups[name] = subgroup
        return subgroup

    def get_command(self, name: str) -> Optional[Command]:
        """获取组内命令"""
        return self._commands.get(name)

    def enable_all(self) -> None:
        """启用所有命令"""
        for cmd in self._commands.values():
            cmd.config.enable()

    def disable_all(self) -> None:
        """禁用所有命令"""
        for cmd in self._commands.values():
            cmd.config.disable()


# ==============================
# 辅助函数
# ==============================


def _parse_docstring(doc: Optional[str]) -> Dict[str, Any]:
    """解析文档字符串"""
    if not doc:
        return {}

    lines = [line.strip() for line in doc.strip().splitlines()]
    if not lines:
        return {}

    result = {"description": lines[0]}

    # 简单解析示例和用法
    examples = []
    for line in lines[1:]:
        if line.startswith("例") or line.startswith("Example"):
            continue
        if line and not line.startswith(":"):
            examples.append(line)

    if examples:
        result["examples"] = examples

    return result


# ==============================
# 消息监听器集成
# ==============================


def create_command_listener(
    router: Optional[CommandRouter] = None,
) -> Callable[[Event[Message]], Any]:
    """
    创建命令监听器

    用法：
        @event_handler(re.compile(r".*"))
        async def on_message(event):
            return await create_command_listener()(event)
    """
    router = router or _global_router

    async def listener(event: Event[Message]) -> Any:
        return await router.handle_message(event)

    return listener


# ==============================
# 简化的全局命令装饰器（可选）
# ==============================


def command(name: str, **kwargs):
    """
    全局命令装饰器（支持与 @listener 配合使用）

    用法：
        @listener
        @command('echo', owner_only=True)
        def echo(self, c: CommandArgs):
            self.logger.info('echo %s', c)
    """

    def decorator(func: Callable) -> Callable:
        # 1. 准备配置
        config = CommandConfig(
            name=name,
            aliases=kwargs.get("aliases", []),
            description=kwargs.get("description", ""),
            raw=kwargs.get("raw", False),  # 默认 False，即传入 CommandArgs
            permission=kwargs.get("permission"),
            admin_only=kwargs.get("admin_only", False),
            root_only=kwargs.get("root_only", False),
            owner_only=kwargs.get("owner_only", False),
            cooldown=kwargs.get("cooldown"),
            cooldown_unit=kwargs.get("cooldown_unit", "second"),
            rate_limit=kwargs.get("rate_limit"),
            rate_limit_window=kwargs.get("rate_limit_window", 60),
            guild_only=kwargs.get("guild_only", False),
            private_only=kwargs.get("private_only", False),
            enabled=kwargs.get("enabled", True),
            hidden=kwargs.get("hidden", False),
        )

        # 2. 预计算匹配模式（名称和别名）
        triggers = {config.name}
        triggers.update(config.aliases)

        @functools.wraps(func)
        async def wrapper(self, event: Event[Message]) -> Optional[Any]:
            """
            包装器逻辑：
            1. 检查是否为消息事件
            2. 检查消息文本是否匹配命令触发词
            3. 如果匹配，初始化 Command 实例并执行
            """
            msg = event.data
            if not isinstance(msg, Message):
                return None

            text = str(msg).strip()
            if not text:
                return None

            # 解析消息文本，提取第一个词作为命令触发词
            parts = text.split(maxsplit=1)
            cmd_trigger = parts[0]
            args_text = parts[1] if len(parts) > 1 else ""
            args_list = args_text.split() if args_text else []

            # 检查是否匹配当前命令
            if cmd_trigger not in triggers:
                return None

            # 将解析出的参数存入 event.metadata，供 Command 类使用
            # 这与 CommandRouter.parse_message 的逻辑保持一致
            event.metadata["command_args"] = args_list
            event.metadata["command_name"] = config.name

            # 延迟初始化 Command 实例（绑定 self）
            # 使用 wrapper 的属性来缓存实例，避免每次调用都重新创建
            if not hasattr(wrapper, "_cmd_instance"):
                wrapper._cmd_instance = Command(self, func, config)

            # 执行命令（包含权限、冷却、参数解析等逻辑）
            # Command.__call__ 会处理 sync/async
            return await wrapper._cmd_instance(event)

        return wrapper

    return decorator
