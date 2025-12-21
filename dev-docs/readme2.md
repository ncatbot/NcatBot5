# Python Bot SDK

一个模块化、可扩展的 Python 机器人开发框架，支持多协议接入与插件化架构。

## 核心特性

- **协议抽象层**：统一的协议接口，支持快速接入不同 IM 平台
- **插件系统**：独立的事件驱动插件框架，支持热加载与依赖管理
- **异步架构**：基于 asyncio 的完全异步实现
- **类型安全**：完整的类型注解与数据校验
- **模块化设计**：核心组件可独立使用或集成

## 快速开始

```python
from src import Bot

bot = Bot(
    url="ws://localhost:3001",
    token="your-token",
    plugin_dir="./plugins"
)

bot.run()
```

## 项目结构

```
src/
├── abc/                    # 抽象接口定义
├── adapters/              # 协议实现（napcat等）
├── connector/             # WebSocket连接器（独立模块）
├── core/                  # IM核心实体与客户端
├── plugins_system/        # 插件系统（独立模块）
├── sys_plugin/            # 内置系统插件
└── utils/                 # 工具集
```

## 文档索引

- [架构设计](docs/architecture.md) - 系统整体架构与设计理念
- [插件系统](docs/plugin-system.md) - 插件开发与混入机制
- [适配器开发](docs/adapters.md) - 如何接入新协议
- [开发指南](docs/development.md) - 贡献代码与模块开发

## 开发状态

当前版本：`5.0.0-dev.0`

核心功能已完成，处于内部测试与文档完善阶段。

## 许可证

MIT License

```

---

## docs/architecture.md

```markdown
# 架构设计

## 核心原则

1. **分层架构**：严格分离关注点，各层通过抽象接口通信
2. **模块化**：核心组件可独立使用，`plugins_system` 与 `connector` 为独立包
3. **事件驱动**：插件系统基于事件总线实现解耦
4. **类型安全**：全程类型注解，关键数据类使用 dataclass

## 模块划分

### 1. 抽象层 (`abc/`)

定义系统契约，所有实现必须遵守：

- `api_base.py`：纯通信层抽象，`APIBase` 类自动包装所有异步方法
- `protocol_abc.py`：协议最小功能集，定义 `ProtocolABC` 接口

### 2. 连接器 (`connector/`)

**独立模块**，可单独发布：

- `wsclient.py`：异步 WebSocket 客户端，支持监听器模式与自动重连
- `abc.py`：WebSocket 抽象接口
- 特性：全异步/同步双形态、指数退避重连、可观测指标

### 3. 插件系统 (`plugins_system/`)

**独立框架**，不依赖 IM 功能：

- `core/`：事件、插件基类、混入类管理
- `implementations/`：默认实现（事件总线、插件加载器）
- `managers/`：配置与插件生命周期管理
- `mixins/`：可复用功能混入（如 ServiceMixin）

### 4. 适配器 (`adapters/`)

协议实现层，当前内置 `napcat`：

- 继承 `ProtocolABC` 实现具体协议
- 提供 `APIBase` 子类封装协议 API
- 实现消息/事件解析逻辑

### 5. 核心实体 (`core/`)

IM 领域模型：

- `IM.py`：User、Group、Message 等实体类
- `client.py`：`IMClient` 单例，封装协议操作
- `nodes.py`：消息节点系统（TextNode、ImageNode 等）

## 数据流

```

WebSocket 消息
    ↓
connector.wsclient (监听)
    ↓
protocol._parse_event (协议解析)
    ↓
EventBus.publish (事件发布)
    ↓
Plugin 事件处理器 (业务逻辑)
    ↓
IMClient API 调用
    ↓
protocol API 调用
    ↓
connector 发送

```

## 扩展点

- **新协议**：实现 `ProtocolABC` 与 `APIBase`
- **新功能**：通过 PluginMixin 扩展插件能力
- **事件总线**：实现 `EventBus` 接口可替换默认实现
- **插件加载**：自定义 `PluginFinder` 或 `PluginLoader`

## 关键设计决策

### 1. 监听器模式（WebSocket）

避免单线程消费瓶颈，支持多任务并行处理消息。

### 2. 插件元类（PluginMeta）

自动收集插件、验证元数据、生成确定性 UUID。

### 3. 延迟装饰器解析

插件加载时动态应用装饰器，支持跨模块功能注入。

### 4. 消息节点系统

将消息内容分解为类型安全节点，便于扩展与转换。
```

---

## docs/plugin-system.md

```markdown
# 插件系统

## 概述

`plugins_system` 是独立的事件驱动插件框架，不依赖 IM 功能，可用于任意 Python 项目。

## 核心概念

### 1. 插件基类 (`Plugin`)

所有插件必须继承自 `Plugin` 类：

```python
from plugins_system import Plugin

class MyPlugin(Plugin):
    name = "my_plugin"          # 必需：插件名
    version = "1.0.0"           # 必需：版本
    authors = ["developer"]     # 可选：作者

    async def on_load(self):
        """插件加载时调用，必需实现"""
        pass

    async def on_unload(self):
        """插件卸载时调用，可选"""
        pass
```

### 2. 事件总线 (`EventBus`)

插件间通信的核心：

```python
# 注册事件处理器
handler_id = self.register_handler("event.name", self.handler_func)

# 发布事件
self.publish_event("event.name", data={"key": "value"})

# 请求-响应模式
results = await self.request_event("event.name", data={}, timeout=10.0)
```

### 3. 插件上下文 (`PluginContext`)

提供插件运行环境：

```python
self.context.event_bus          # 事件总线
self.context.plugin_name        # 当前插件名
self.context.data_dir           # 插件数据目录
self.context.config_dir         # 插件配置目录
```

## 混入类（Mixin）开发

### 什么是混入类？

混入类是为插件提供可复用功能的基类，通过多重继承注入能力。

### 编写自定义混入类

继承 `PluginMixin`：

```python
from plugins_system import PluginMixin

class CacheMixin(PluginMixin):
    """为插件提供缓存能力"""

    async def on_mixin_load(self):
        """混入类加载时调用"""
        self.cache = {}
        self.logger.info("CacheMixin loaded")

    async def on_mixin_unload(self):
        """混入类卸载时清理资源"""
        self.cache.clear()

    def set_cache(self, key, value):
        self.cache[key] = value

    def get_cache(self, key):
        return self.cache.get(key)
```

### 在插件中使用混入类

```python
from plugins_system import Plugin
from my_mixins import CacheMixin

class MyPlugin(Plugin, CacheMixin):
    name = "my_plugin"

    async def on_load(self):
        self.set_cache("test", "value")  # 使用混入类功能
```

### 混入类生命周期

1. **插件实例化**：混入类被识别并存储在 `plugin._mixins`
2. **插件加载**：依次调用各混入类的 `on_mixin_load()`
3. **插件运行**：混入类方法可直接使用
4. **插件卸载**：依次调用各混入类的 `on_mixin_unload()`

## 服务混入类 (`ServiceMixin`)

内置强大功能混入，允许插件注册服务：

```python
from plugins_system.mixins.server import ServiceMixin, service

class MyPlugin(Plugin, ServiceMixin):
    name = "calculator"

    @service("add", description="加法服务")
    def add_service(self, a: int, b: int):
        return a + b

    async def on_load(self):
        # 服务自动注册，无需手动操作
        pass

# 其他插件调用
result = await self.call_service("add", data={"a": 1, "b": 2})
```

### 服务装饰器

- `@service(name, ...)`: 注册普通服务
- `@online_service(name, ...)`: 始终在线的服务
- `@toggleable_service(name, ...)`: 支持状态切换
- `@event_service(name, ...)`: 接收完整 Event 对象

## 延迟装饰器解析器

### 原理

在插件加载时动态扫描方法，应用装饰器，解决跨模块依赖问题。

### 创建解析器

```python
from plugins_system import LazyDecoratorResolver

class CronResolver(LazyDecoratorResolver):
    tag = "cron"                    # 装饰器标签
    space = "task"                  # 命名空间
    required_mixin = TimerMixin     # 依赖的混入类

    def handle(self, plugin, func, event_bus):
        """处理装饰逻辑"""
        cron_expr = self.kwd["expression"]
        # 注册定时任务
        plugin.register_cron_task(func, cron_expr)
        self.clear_cache()  # 清理临时数据
```

### 使用自定义装饰器

```python
class MyPlugin(Plugin, TimerMixin):
    @cron(expression="0 * * * *")
    async def hourly_task(self):
        """每小时执行"""
        pass
```

### 内置解析器：`ServiceResolver`

自动处理 `@service` 装饰器，将方法注册为事件总线处理器。

## 自定义插件系统实现

### 替换事件总线

```python
from plugins_system import EventBus

class CustomEventBus(EventBus):
    def register_handler(self, event, handler, plugin_name=None):
        # 自定义注册逻辑
        pass

    async def request(self, event, data, timeout=10.0):
        # 自定义请求响应逻辑
        pass

# 使用自定义总线
app = PluginApplication(
    plugin_dirs=["plugins"],
    event_bus=CustomEventBus()
)
```

### 自定义插件管理器

```python
from plugins_system import PluginManager

class CustomManager(PluginManager):
    async def load_plugins(self):
        # 自定义加载逻辑
        pass

    async def reload_plugin(self, name):
        # 自定义重载逻辑
        pass
```

### 自定义插件发现器

```python
from plugins_system import PluginFinder

class GitPluginFinder(PluginFinder):
    async def find_plugins(self):
        # 从 Git 仓库发现插件
        return [PluginSource(...)]
```

## 插件配置管理

配置自动加载与保存：

```yaml
# config/my_plugin/my_plugin.yaml
setting1: value1
setting2: value2
```

```python
class MyPlugin(Plugin):
    async def on_load(self):
        config = self.config  # 自动加载的 YAML/JSON 配置
        self.setting1 = config.get("setting1")
```

## 开发建议

1. **单一职责**：每个插件只做一件事
2. **依赖声明**：在 `dependency` 中声明插件依赖
3. **错误处理**：在 `on_load` 中捕获异常，设置为 FAILED 状态
4. **资源清理**：在 `on_unload` 中释放资源
5. **类型注解**：为服务方法添加完整类型注解，支持自动校验

```

---

## docs/adapters.md

```markdown
# 适配器开发指南

## 概述

适配器实现 `ProtocolABC` 接口，将 SDK 与具体 IM 协议（如 NapCat、OneBot 等）对接。

## 实现步骤

### 1. 创建适配器目录

```

adapters/
└── my_protocol/
    ├── **init**.py
    ├── protocol.py          # 主协议类
    ├── api.py               # API 封装
    ├── api_base.py          # API 基类
    ├── message.py           # 消息相关 API
    ├── user.py              # 用户相关 API
    └── group.py             # 群组相关 API

```

### 2. 实现 ProtocolABC

在 `protocol.py` 中：

```python
from abc.protocol_abc import ProtocolABC
from .api import MyAPI

class MyProtocol(ProtocolABC):
    protocol_name = "my_protocol"  # 必需：协议名称

    def __init__(self):
        self._api = MyAPI()
        self._self_id = ""

    @property
    def api(self) -> MyAPI:
        return self._api

    @property
    def self_id(self) -> str:
        return self._self_id

    # 核心消息发送
    async def send_group_message(self, gid: GroupID, content: MessageContent) -> RawMessage:
        segments = self._content_to_segments(content)
        return await self._api.group.send_group_msg(
            group_id=gid,
            message=segments
        )

    async def send_private_message(self, uid: UserID, content: MessageContent) -> RawMessage:
        segments = self._content_to_segments(content)
        return await self._api.user.send_private_msg(
            user_id=uid,
            message=segments
        )

    # 解析方法
    def _parse_event(self, raw: tuple[str, MessageType]) -> Event | None:
        data = json.loads(raw[0])
        # 解析为 Event 对象
        return Event(
            event=f"message.{data['type']}",
            data=data,
            source="my_protocol"
        )

    def _parse_message(self, raw: RawMessage) -> Message:
        # 转换原始消息为 Message 对象
        return Message(...)

    # 其他必需方法...
```

### 3. 实现 APIBase

在 `api_base.py` 中：

```python
from abc.api_base import APIBase, ApiRequest
from connector import AsyncWebSocketClient

class MyAPIBase(APIBase):
    protocol_name = "my_protocol"
    client: AsyncWebSocketClient

    def __init__(self):
        super().__init__()

    async def invoke(self, request: ApiRequest) -> Any:
        """核心通信方法"""
        # 转换 ApiRequest 为协议格式
        payload = {
            "action": request.activity,
            "params": request.data,
            "echo": str(uuid.uuid4())
        }

        # 发送并等待响应
        listener = await self.client.create_listener()
        await self.client.send(payload)

        while True:
            msg, _ = await self.client.get_message(listener)
            resp = json.loads(msg)
            if resp.get("echo") == payload["echo"]:
                return resp

    # 子类 API 方法返回 ApiRequest 或 (activity, data) 元组
```

### 4. 实现具体 API 分组

```python
# message.py
class MyAPIMessage(MyAPIBase):
    async def send_msg(self, user_id: UserID, message: list) -> tuple[str, dict]:
        return ("send_msg", {
            "user_id": user_id,
            "message": message
        })
```

### 5. 消息格式转换

实现内容节点与协议格式的互转：

```python
# protocol.py
def _content_to_segments(self, content: MessageContent) -> list[dict]:
    """SDK MessageContent -> 协议消息段"""
    segments = []
    for node in content.nodes:
        if isinstance(node, TextNode):
            segments.append({"type": "text", "data": {"text": node.content}})
        elif isinstance(node, ImageNode):
            segments.append({"type": "image", "data": {"url": node.uri}})
        # ... 其他节点类型
    return segments

def _parse_message_content(self, segments: list[dict]) -> MessageContent:
    """协议消息段 -> SDK MessageContent"""
    nodes = []
    for seg in segments:
        if seg["type"] == "text":
            nodes.append(TextNode(content=seg["data"]["text"]))
        # ... 其他类型
    return MessageContent(nodes=nodes)
```

## 注册适配器

在 `adapters/__init__.py` 中：

```python
protocols = ("my_protocol", "napcat")

import importlib
for p in protocols:
    importlib.import_module(f".{p}", package=__package__)
```

## 测试适配器

```python
from src import Bot

bot = Bot(
    url="ws://localhost:3001",
    protocol="my_protocol"
)

@bot.event_bus.register_handler("message.private")
async def on_private_message(event):
    print(event.data)

bot.run()
```

## 适配器能力范围

### 必需实现

- **消息收发**：`send_group_message`, `send_private_message`
- **实体获取**：`fetch_user`, `fetch_group`, `fetch_friends`, `fetch_groups`
- **消息操作**：`recall_message`, `fetch_message`
- **事件解析**：`_parse_event` 必须能解析所有推送事件

### 可选实现

- **好友管理**：`add_friend`, `delete_friend`, `block_user`（协议不支持返回 False）
- **群管理**：`kick_group_member`, `set_group_name` 等
- **个人资料**：`set_self_nickname` 等

### 协议差异处理

- 不支持的功能：方法返回 `False` 或抛 `NotImplementedError`
- 参数差异：在方法内适配，保持接口签名一致
- 响应格式：在 `invoke` 层统一转换为标准格式

## 最佳实践

1. **分层实现**：`api*.py` 只封装通信，`protocol.py` 处理业务逻辑
2. **错误处理**：API 调用失败时返回 `None` 或抛异常，不要静默忽略
3. **日志记录**：每个适配器使用独立 logger：`logging.getLogger("Protocol.MyProtocol")`
4. **类型转换**：严格校验输入类型，返回数据尽量转换为 Python 原生类型
5. **文档注释**：每个 API 方法注明协议文档链接与参数说明

```

---

## docs/development.md

```markdown
# 开发指南

## 环境要求

- Python >= 3.10
- 异步环境支持（asyncio）

## 项目结构

```

src/
├── abc/                    # 抽象接口
│   ├── api_base.py        # 通信层抽象
│   └── protocol_abc.py    # 协议抽象
├── adapters/              # 协议适配器
│   └── napcat/           # NapCat 协议实现
├── connector/             # WebSocket 连接器（独立模块）
│   ├── abc.py
│   └── wsclient.py
├── core/                  # IM 核心
│   ├── IM.py             # 实体类（User/Group/Message）
│   ├── client.py         # IMClient 单例
│   ├── nodes.py          # 消息节点系统
│   └── plugin.py         # PluginBase（兼容 plugins_system）
├── plugins_system/        # 插件系统（独立模块）
│   ├── abc/              # 抽象接口
│   ├── core/             # 核心实现
│   ├── implementations/  # 默认实现
│   ├── managers/         # 管理器
│   ├── mixins/           # 混入类
│   └── utils/            # 工具
├── sys_plugin/           # 内置系统插件
│   └── demo.py
└── utils/                # 通用工具
    ├── logger.py
    ├── typec.py
    └── helper.py

```

## 模块独立性说明

### 1. `plugins_system` 独立包

可单独复制到其他项目使用：

```python
# 独立使用示例
from plugins_system import PluginApplication

app = PluginApplication(plugin_dirs=["./plugins"])
await app.start()
```

**依赖**：仅依赖 Python 标准库 + `pyyaml`（配置加载）

### 2. `connector` 独立包

WebSocket 客户端可独立使用：

```python
from connector import AsyncWebSocketClient

client = AsyncWebSocketClient("ws://echo.websocket.org")
await client.start()
listener = await client.create_listener()
await client.send({"msg": "hello"})
msg, _ = await client.get_message(listener)
```

**依赖**：`aiohttp`

### 3. `sys_plugin` 内置插件

随框架启动自动加载，位于 `src/sys_plugin/`：

- `demo.py`：示例插件（默认禁用）
- 可添加系统级功能插件，如监控、日志聚合等

**注意**：系统插件目录硬编码在 `Bot.__init__` 中：

```python
plugin_dirs = [Path(__file__).resolve().parent / "sys_plugin"]
```

## 开发规范

### 代码风格

- 遵循 PEP 8
- 类型注解：公共 API 必须完整注解，私有方法建议注解
- 异步方法：使用 `async def`，避免混合同步/异步调用

### 日志规范

```python
# 正确：使用模块级 logger
logger = logging.getLogger("Module.Name")
logger.info("message")

# 错误：不要使用 print
print("debug info")  # 禁止
```

### 异常处理

- 自定义异常继承自 `SDKError` 或 `PluginError`
- 捕获异常后使用 `logger.exception()` 记录完整堆栈
- 不要静默捕获异常，除非明确知道可恢复

## 测试

### 单元测试

```python
# 测试插件
import pytest
from plugins_system import Plugin

class TestPlugin(Plugin):
    name = "test"
    version = "1.0"

    async def on_load(self):
        pass

@pytest.mark.asyncio
async def test_plugin_load():
    plugin = TestPlugin(context=..., config={})
    await plugin._internal_on_load()
    assert plugin.status.state == PluginState.RUNNING
```

### 集成测试

```python
# 测试完整流程
from src import Bot

async def test_bot_flow():
    bot = Bot(url="ws://mock", protocol="napcat")
    await bot.run_async()

    # 模拟消息
    event = Event("message.private", data={"user_id": "123", "message": "hi"})
    bot.event_bus.publish_event(event)

    await bot.stop()
```

## 贡献流程

1. **Fork 仓库**
2. **创建特性分支**：`git checkout -b feature/new-adapter`
3. **编写代码**：遵循上述规范
4. **添加测试**：覆盖核心逻辑
5. **更新文档**：修改相关 `.md` 文件
6. **提交 PR**：描述改动与测试情况

## 发布准备

### 版本管理

- 版本号格式：`{major}.{minor}.{patch}-dev.{build}`
- 稳定版移除 `-dev` 后缀
- 在 `meta.py` 中更新 `__version__`

### 依赖管理

- 生产依赖：写入 `pyproject.toml`
- 开发依赖：写入 `requirements-dev.txt`
- 独立模块依赖：在模块内注明

### 打包独立模块

```bash
# 打包 connector
cd src/connector
cp -r ../utils/logger ../utils/color .  # 复制依赖
# 创建 setup.py 并发布
```

## 常见问题

### Q1: 如何实现插件热重载？

当前版本未完全实现热重载。建议方案：

- 监听插件目录文件变动
- 调用 `plugin_manager.reload_plugin(name)`
- 注意清理旧插件的定时任务与句柄

### Q2: 插件间如何共享数据？

**推荐**：通过 `ServiceMixin` 注册服务
**不推荐**：直接操作其他插件实例（强耦合）

### Q3: 如何处理长时间运行的任务？

```python
class MyPlugin(Plugin):
    async def on_load(self):
        self._task = asyncio.create_task(self._background_task())

    async def _background_task(self):
        while True:
            await asyncio.sleep(60)
            # do work

    async def on_unload(self):
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
```

### Q4: `connector` 监听器泄漏？

确保调用 `remove_listener()`，或使用上下文管理器：

```python
listener = await client.create_listener()
try:
    # use listener
finally:
    await client.remove_listener(listener)
```

## Roadmap

- [ ] 完善热重载机制
- [ ] 支持更多协议（OneBot v12、Discord）
- [ ] 插件市场与依赖自动安装
- [ ] Web UI 管理界面
- [ ] 性能监控与指标暴露（Prometheus）
