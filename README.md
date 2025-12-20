# 插件系统

> 一个现代化、高可扩展的 Python 插件框架

---

## 核心特性

### 完全可定制架构

- **插件管理器** - 可替换的插件生命周期管理
- **事件总线** - 支持自定义实现，满足不同性能需求
- **插件加载器** - 灵活的插件发现和加载机制
- **配置系统** - 可扩展的配置管理方案

### 企业级功能

- **依赖解析** - 自动拓扑排序，循环依赖检测
- **热重载** - 运行时插件更新，无需重启
- **状态跟踪** - 完整的插件状态监控
- **错误隔离** - 插件间错误隔离，避免级联故障

### 开发体验

- **声明式编程** - 基于装饰器的简洁API
- **混入类系统** - 通过多重继承扩展功能
- **类型提示** - 完整的类型注解支持
- **调试支持** - 详细的日志和错误信息

---

## 快速开始

### 基础用法

```python
from pack.plugins_system.app import PluginApplication
import asyncio

# 创建应用实例
app = PluginApplication(
    plugin_dirs=["./plugins"],
    config_dir="./config", 
    data_dir="./data"
)

# 启动应用
async def main():
    async with app:
        print("插件系统已启动")
        await asyncio.sleep(3600)

asyncio.run(main())
```

### 创建简单插件

```python
from pack.plugins_system.core.plugins import Plugin

class BasicPlugin(Plugin):
    """基础插件示例"""
    
    name = "basic_plugin"
    version = "1.0.0"
    authors = ["开发者"]
    
    async def on_load(self):
        self.logger.info("插件已加载")
        self.register_handler("test.message", self.handle_message)
    
    async def handle_message(self, event):
        return {"response": "消息已处理", "data": event.data}
```

---

## 高度自定义

### 自定义事件总线

```python
from pack.plugins_system.abc.events import EventBus
import redis.asyncio as redis

class CustomEventBus(EventBus):
    """完全自定义的事件总线实现"""
    
    def __init__(self, redis_url: str, max_queue_size: int = 1000):
        self.redis = redis.from_url(redis_url)
        self.max_queue_size = max_queue_size
        self._handlers = {}
    
    def register_handler(self, event, handler, plugin_name=None):
        # 自定义注册逻辑
        handler_id = str(uuid.uuid4())
        self._handlers[handler_id] = {
            'event': event,
            'handler': handler, 
            'plugin': plugin_name
        }
        return handler_id
    
    async def publish(self, event: str, data: Any = None, **kwargs):
        # 自定义发布逻辑
        message = {
            'event': event,
            'data': data,
            'timestamp': time.time()
        }
        await self.redis.publish('plugin_events', json.dumps(message))
    
    # 实现其他抽象方法...
```

### 自定义插件管理器

```python
from pack.plugins_system.abc.plugins import PluginManager

class CustomPluginManager(PluginManager):
    """自定义插件管理器"""
    
    def __init__(self, plugin_dirs, config_dir, data_dir, event_bus):
        self.plugin_dirs = plugin_dirs
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.event_bus = event_bus
        
        # 自定义初始化逻辑
        self._plugins = {}
        self._dependency_graph = {}
    
    async def load_plugins(self):
        # 自定义加载逻辑
        plugins = await self._discover_plugins()
        sorted_plugins = self._resolve_dependencies(plugins)
        
        for plugin in sorted_plugins:
            await self._load_single_plugin(plugin)
        
        return list(self._plugins.values())
    
    # 实现其他抽象方法...
```

### 常量配置系统

```python
# 在 pack/plugins_system/utils/constants.py 中定义

# 系统常量
PROTOCOL_VERSION = 3
NAMESPACE = uuid.UUID('12345678-1234-5678-1234-567812345678')

# 插件状态
class PluginState:
    LOADED = "loaded"
    RUNNING = "running" 
    STOPPED = "stopped"
    FAILED = "failed"
    UNLOADED = "unloaded"

# 特性开关
class FeatureFlags:
    EVENT_BUS_IMPL = 'NonBlockingEventBus'
    ENABLE_RUN_IN_DATA_DIR = False
    DEBUG_MODE = True

# 系统事件
class SystemEvents:
    MANAGER_STARTING = "system.manager.starting"
    MANAGER_STOPPING = "system.manager.stopping"
    PLUGIN_LOADED = "system.plugin.loaded"
    PLUGIN_UNLOADED = "system.plugin.unloaded"
    RELOAD_REQUESTED = "system.reload.requested"
```

### 使用自定义常量

```python
from pack.plugins_system.utils.constants import (
    PluginState, SystemEvents, FeatureFlags, PROTOCOL_VERSION
)

class AdvancedPlugin(Plugin):
    async def on_load(self):
        # 使用系统常量
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("协议版本不兼容")
        
        # 使用特性开关
        if FeatureFlags.DEBUG_MODE:
            self.logger.debug("调试模式已启用")
        
        # 发布系统事件
        self.publish_event(SystemEvents.PLUGIN_LOADED, self.meta)
```

---

## 混入类开发

### 基础混入类

```python
from pack.plugins_system.core.mixin import PluginMixin

class DatabaseMixin(PluginMixin):
    """数据库混入类"""
    
    async def on_mixin_load(self):
        self.db_connection = await self._create_connection()
        self.logger.info("数据库连接已建立")
    
    async def on_mixin_unload(self):
        if hasattr(self, 'db_connection'):
            await self.db_connection.close()
            self.logger.info("数据库连接已关闭")
    
    async def execute_query(self, query, params=None):
        return await self.db_connection.execute(query, params)

class CacheMixin(PluginMixin):
    """缓存混入类"""
    
    async def on_mixin_load(self):
        self.cache_client = await self._setup_cache()
    
    async def get_cached(self, key):
        return await self.cache_client.get(key)
    
    async def set_cached(self, key, value, ttl=3600):
        await self.cache_client.set(key, value, ex=ttl)
```

### 使用混入类

```python
class UserServicePlugin(Plugin, DatabaseMixin, CacheMixin):
    """使用多个混入类的插件"""
    
    name = "user_service"
    version = "2.0.0"
    
    async def on_load(self):
        # 混入类的on_mixin_load会自动调用
        await super().on_load()
        
        # 直接使用混入类提供的方法
        self.register_handler("user.get", self.get_user)
    
    async def get_user(self, event):
        user_id = event.data['user_id']
        
        # 先尝试从缓存获取
        cached_user = await self.get_cached(f"user:{user_id}")
        if cached_user:
            return cached_user
        
        # 缓存未命中，查询数据库
        user = await self.execute_query(
            "SELECT * FROM users WHERE id = ?", 
            (user_id,)
        )
        
        # 写入缓存
        await self.set_cached(f"user:{user_id}", user)
        
        return user
```

---

## 配置管理

### 环境变量配置

```bash
# 日志系统配置
LOG_LEVEL=INFO
FILE_LOG_LEVEL=DEBUG
LOG_FILE_PATH=./logs
LOG_FILE_NAME=app_%Y%m%d.log
BACKUP_COUNT=7

# 插件系统配置  
PLUGIN_SYSTEM_DEBUG=false
EVENT_BUS_MAX_WORKERS=10
LOG_REDIRECT_RULES='{"database": "db.log", "api": "api.log"}'

# 自定义常量（可在constants.py中设置）
DEFAULT_TIMEOUT=30
MAX_RETRY_ATTEMPTS=3
```

### 插件配置

```yaml
# config/my_plugin/my_plugin.yaml
database:
  host: "localhost"
  port: 5432
  username: "admin"
  password: "secret"

api:
  base_url: "https://api.example.com"
  timeout: 30
  retry_attempts: 3

features:
  enable_caching: true
  cache_ttl: 3600
```

```python
class ConfigurablePlugin(Plugin):
    async def on_load(self):
        # 访问配置
        db_config = self.config.get('database', {})
        api_config = self.config.get('api', {})
        
        # 使用配置值
        self.db_host = db_config.get('host', 'localhost')
        self.api_timeout = api_config.get('timeout', 30)
        
        # 特性开关
        if self.config.get('features', {}).get('enable_caching', False):
            self.setup_caching()
```

---

## 事件系统

### 多种事件模式

```python
class EventDrivenPlugin(Plugin):
    async def on_load(self):
        # 精确字符串匹配
        self.register_handler("user.created", self.handle_user_created)
        
        # 正则表达式匹配
        self.register_handler("re:order\..*", self.handle_order_events)
        
        # 批量注册
        event_handlers = {
            "payment.completed": self.handle_payment,
            "invoice.generated": self.handle_invoice,
            "notification.sent": self.handle_notification
        }
        self.register_handlers(event_handlers)
    
    async def handle_user_created(self, event):
        user_data = event.data
        
        # 发布后续事件
        self.publish_event("user.welcome_email", {
            "email": user_data['email'],
            "username": user_data['username']
        })
        
        self.publish_event("user.analytics", {
            "user_id": user_data['id'],
            "signup_source": user_data.get('source', 'direct')
        })
    
    async def send_notification(self, user_id, message):
        # 请求-响应模式
        results = await self.request_event(
            "notification.send",
            {
                "user_id": user_id,
                "message": message,
                "channels": ["email", "push"]
            },
            timeout=10.0
        )
        return results
```

---

## 重要警告

### 工作目录切换注意事项

```python
# 警告：在插件中使用 os.chdir 会影响整个进程
# 建议使用相对路径或绝对路径代替目录切换

class SafePathPlugin(Plugin):
    async def on_load(self):
        # 不推荐：会改变整个进程的工作目录
        # os.chdir(self.data_dir)
        
        # 推荐：使用绝对路径
        config_path = self.data_dir / "config.json"
        await self.load_config(config_path)
        
        # 或者使用上下文管理器（如果启用）
        # async with self.working_directory():
        #     # 在此块内工作目录已切换
        #     await self.process_files()
    
    async def load_config(self, config_path):
        # 使用绝对路径，不依赖当前工作目录
        if config_path.exists():
            async with aiofiles.open(config_path, 'r') as f:
                return json.loads(await f.read())
        return {}
```

### 资源管理最佳实践

```python
class ResourceAwarePlugin(Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resources = []
    
    async def on_load(self):
        try:
            # 初始化资源
            self._resources.append(await self.create_database_pool())
            self._resources.append(await self.create_http_client())
            self._resources.append(await self.create_cache_client())
            
            self.logger.info("所有资源已初始化")
        except Exception as e:
            await self._cleanup_resources()
            raise
    
    async def on_unload(self):
        await self._cleanup_resources()
        self.logger.info("所有资源已清理")
    
    async def _cleanup_resources(self):
        for resource in self._resources:
            try:
                if hasattr(resource, 'close'):
                    await resource.close()
                elif hasattr(resource, 'shutdown'):
                    await resource.shutdown()
            except Exception as e:
                self.logger.error(f"资源清理失败: {e}")
        self._resources.clear()
```

---

## 项目结构

```
plugin_system/
├── app.py                    # 应用入口点
├── abc/                      # 抽象接口
│   ├── events.py            # 事件总线接口
│   └── plugins.py           # 插件管理接口
├── core/                    # 核心实现
│   ├── plugins.py           # 插件基类与元类
│   ├── events.py            # 事件模型
│   ├── mixin.py             # 混入类系统
│   └── lazy_resolver.py     # 延迟装饰器解析
├── implementations/         # 默认实现
│   ├── event_bus.py         # 事件总线实现
│   ├── plugin_loader.py     # 插件加载器
│   └── plugin_finder.py     # 插件查找器
├── managers/               # 管理器
│   ├── plugin_manager.py    # 插件管理器
│   └── config_manager.py    # 配置管理器
├── mixins/                 # 内置混入类
│   └── server.py           # 服务器混入类
└── utils/                  # 工具类
    ├── color.py            # 终端颜色支持
    ├── constants.py        # 系统常量定义
    ├── helpers.py          # 辅助函数
    └── types.py            # 类型定义
```

---

## 故障排除

### 常见问题

**插件未加载**

- 检查插件类是否继承自 `Plugin`
- 验证 `name` 和 `version` 属性是否正确设置
- 确认插件目录配置正确

**依赖解析失败**

- 检查依赖插件是否可用
- 验证版本约束语法是否正确
- 查看是否存在循环依赖

**事件未触发**

- 确认事件名称匹配（大小写敏感）
- 检查处理器是否正确定义为异步函数
- 验证事件发布时数据格式

### 调试技巧

```python
# 启用调试模式
app = PluginApplication(
    plugin_dirs=["./plugins"],
    dev_mode=True  # 启用详细日志输出
)

# 检查插件状态
plugin_manager = app.get_plugin_manager()
status = plugin_manager.list_plugins_with_status()
for name, status in status.items():
    print(f"{name}: {status.state}")

# 手动触发事件
await app.get_event_bus().publish("debug.test", {"message": "测试事件"})
```

---

## 扩展建议

### 性能优化

- 对于高频率事件，使用 `NonBlockingEventBus`
- 合理设置 `max_workers` 参数平衡性能
- 在生产环境关闭调试模式

### 安全考虑

- 验证插件来源和签名
- 限制插件文件系统访问
- 使用沙箱环境运行不可信插件

### 监控集成

- 集成应用性能监控(APM)工具
- 添加健康检查端点
- 实现插件指标收集

---

## 许可证

Fcatbot 使用许可协议

## 支持

- 邮箱: Fish-LP <fish.zh@outlook.com>

---

*本文档由 AI 编写，旨在提供参考*
