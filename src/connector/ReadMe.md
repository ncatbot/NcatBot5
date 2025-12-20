# AioHttpWebSocketClient 使用文档

## 概述

`AioHttpWebSocketClient` 是一个基于 aiohttp 的现代化 WebSocket 客户端，提供自动重连、消息队列、背压控制等生产级特性。

## 快速开始

### 安装依赖

```bash
pip install aiohttp
```

### 基础用法

```python
import asyncio
import logging
from your_websocket_client import AioHttpWebSocketClient, MessageType

async def main():
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建客户端
    async with AioHttpWebSocketClient(
        uri="wss://echo.websocket.org",
        heartbeat=30,
        reconnect_attempts=3
    ) as client:
        
        # 注册消息处理器
        async def message_handler(msg, msg_type):
            if msg_type == MessageType.TEXT:
                print(f"收到消息: {msg}")
        
        callback = await client.register_callback(message_handler)
        
        # 发送消息
        await client.send("Hello, WebSocket!")
        await asyncio.sleep(2)
        
        # 取消注册
        await client.unregister_callback(callback)

asyncio.run(main())
```

## 配置选项

### 连接配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `uri` | str | 必填 | WebSocket 服务器地址 |
| `headers` | Dict[str, str] | `{}` | 请求头 |
| `heartbeat` | float | `30.0` | 心跳间隔（秒） |
| `reconnect_attempts` | int | `5` | 最大重连次数 |
| `connect_timeout` | float | `20.0` | 连接超时时间 |
| `session_timeout` | float | `300.0` | 会话超时时间 |

### 队列配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `send_queue_size` | int | `1024` | 发送队列大小 |
| `command_queue_size` | int | `128` | 命令队列大小 |
| `backpressure_policy` | BackpressurePolicy | `EVICT_CONSUMER` | 背压策略 |

### 高级配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `backoff_base` | float | `1.0` | 重连退避基数 |
| `backoff_max` | float | `60.0` | 最大重连间隔 |
| `jitter_factor` | float | `0.5` | 重连抖动系数 |
| `compression` | int | `9` | 压缩级别 |
| `verify_ssl` | bool | `True` | SSL 验证 |
| `max_listeners` | int | `1000` | 最大监听器数量 |
| `enable_app_heartbeat` | bool | `False` | 启用应用层心跳 |
| `callback_execution_mode` | ExecutionMode | `ASYNC` | 回调执行模式 |
| `thread_pool_workers` | int | `4` | 线程池工作线程数 |

## 核心功能

### 1. 消息回调

```python
# 注册文本消息回调
async def text_handler(message, msg_type):
    if msg_type == MessageType.TEXT:
        print(f"文本消息: {message}")

callback = await client.register_callback(
    text_handler, 
    message_type=MessageType.TEXT
)

# 注册带过滤器的回调
async def json_handler(message, msg_type):
    data = json.loads(message)
    print(f"JSON消息: {data}")

callback = await client.register_callback(
    json_handler,
    filter_func=lambda msg: msg.startswith('{'),
    message_type=MessageType.TEXT
)
```

### 2. 请求-响应模式

```python
# 等待特定响应
try:
    response = await client.request(
        request={"type": "ping", "id": 123},
        response_matcher=lambda msg: (
            isinstance(msg, str) and 
            '"type":"pong"' in msg and 
            '"id":123' in msg
        ),
        timeout=5.0
    )
    print(f"收到响应: {response}")
except asyncio.TimeoutError:
    print("请求超时")
```

### 3. 消息流

```python
# 创建消息流
stream_id = await client.create_stream(buffer_size=50)

try:
    # 连续获取消息
    while True:
        message, msg_type = await client.get_stream_message(
            stream_id, 
            timeout=10.0
        )
        if message is not None:
            print(f"流消息: {message}")
        else:
            print("流消息超时")
            
except ListenerEvictedError:
    print("流被淘汰（背压策略）")
finally:
    await client.close_stream(stream_id)
```

### 4. 异步迭代器

```python
# 使用异步迭代器处理流消息
stream_id = await client.create_stream(buffer_size=50)

async for message, msg_type in client.messages.iter_stream(stream_id, timeout=5.0):
    if message is not None:
        print(f"迭代消息: {message}")
    # 可以随时 break 退出循环

await client.close_stream(stream_id)
```

## 背压策略

### DROP_OLD（丢弃旧消息）

```python
client = AioHttpWebSocketClient(
    uri="wss://example.com",
    backpressure_policy=BackpressurePolicy.DROP_OLD
)
# 适合实时数据场景，如股票行情
```

### DROP_NEW（丢弃新消息）

```python
client = AioHttpWebSocketClient(
    uri="wss://example.com", 
    backpressure_policy=BackpressurePolicy.DROP_NEW
)
# 适合关键数据场景，如交易指令
```

### EVICT_CONSUMER（淘汰消费者）

```python
client = AioHttpWebSocketClient(
    uri="wss://example.com",
    backpressure_policy=BackpressurePolicy.EVICT_CONSUMER
)
# 默认策略，保护系统稳定性
```

## 回调执行模式

### ASYNC 模式（默认）

```python
async def async_callback(message, msg_type):
    # 异步操作
    await process_message(message)

await client.register_callback(
    async_callback,
    execution_mode=ExecutionMode.ASYNC
)
```

### THREADED 模式

```python
def sync_callback(message, msg_type):
    # 同步阻塞操作
    time_consuming_processing(message)

await client.register_callback(
    sync_callback,
    execution_mode=ExecutionMode.THREADED
)
```

### SYNC 模式（谨慎使用）

```python
def light_callback(message, msg_type):
    # 轻量同步操作
    quick_processing(message)

await client.register_callback(
    light_callback, 
    execution_mode=ExecutionMode.SYNC
)
```

## 完整示例

### 股票行情客户端

```python
import asyncio
import json
import logging
from your_websocket_client import AioHttpWebSocketClient, MessageType

class StockClient:
    def __init__(self):
        self.client = AioHttpWebSocketClient(
            uri="wss://stock-api.example.com",
            heartbeat=10,
            reconnect_attempts=10,
            backpressure_policy=BackpressurePolicy.DROP_OLD,
            send_queue_size=5000
        )
        self.subscriptions = set()
    
    async def start(self):
        await self.client.start()
        
        # 注册行情处理器
        await self.client.register_callback(
            self._handle_quote,
            filter_func=lambda msg: 'price' in msg,
            execution_mode=ExecutionMode.THREADED
        )
    
    async def subscribe(self, symbol: str):
        self.subscriptions.add(symbol)
        await self.client.send({
            "action": "subscribe",
            "symbol": symbol
        })
    
    async def unsubscribe(self, symbol: str):
        self.subscriptions.discard(symbol)
        await self.client.send({
            "action": "unsubscribe", 
            "symbol": symbol
        })
    
    def _handle_quote(self, message, msg_type):
        # 在线程池中处理密集计算
        data = json.loads(message)
        if data.get('symbol') in self.subscriptions:
            # 处理行情数据
            print(f"价格更新: {data['symbol']} - {data['price']}")
    
    async def get_current_price(self, symbol: str, timeout: float = 5.0):
        # 请求当前价格
        return await self.client.request(
            request={"action": "get_price", "symbol": symbol},
            response_matcher=lambda msg: (
                symbol in msg and 'current_price' in msg
            ),
            timeout=timeout
        )
    
    async def stop(self):
        await self.client.stop()

async def main():
    stock_client = StockClient()
    await stock_client.start()
    
    try:
        await stock_client.subscribe("AAPL")
        await stock_client.subscribe("GOOGL")
        
        # 运行10分钟
        await asyncio.sleep(600)
        
    finally:
        await stock_client.stop()

asyncio.run(main())
```

### 聊天应用客户端

```python
import asyncio
import json
from your_websocket_client import AioHttpWebSocketClient, MessageType

class ChatClient:
    def __init__(self, room_id: str, user_id: str):
        self.room_id = room_id
        self.user_id = user_id
        self.client = AioHttpWebSocketClient(
            uri="wss://chat.example.com",
            headers={"User-ID": user_id},
            heartbeat=60,
            reconnect_attempts=5
        )
        self.message_stream = None
    
    async def connect(self):
        await self.client.start()
        
        # 加入聊天室
        await self.client.send({
            "type": "join",
            "room": self.room_id,
            "user": self.user_id
        })
        
        # 创建消息流
        self.message_stream = await self.client.create_stream(buffer_size=100)
        
        # 启动消息监听任务
        asyncio.create_task(self._listen_messages())
    
    async def send_message(self, text: str):
        await self.client.send({
            "type": "message",
            "room": self.room_id,
            "user": self.user_id,
            "text": text,
            "timestamp": int(time.time())
        })
    
    async def _listen_messages(self):
        try:
            async for message, msg_type in self.client.messages.iter_stream(
                self.message_stream, timeout=1.0
            ):
                if message and msg_type == MessageType.TEXT:
                    data = json.loads(message)
                    if data.get('type') == 'message':
                        print(f"{data['user']}: {data['text']}")
        except Exception as e:
            print(f"消息监听错误: {e}")
    
    async def wait_for_join_confirmation(self, timeout: float = 10.0):
        return await self.client.wait_for_message(
            filter_func=lambda msg: (
                'welcome' in msg and self.user_id in msg
            ),
            timeout=timeout
        )
    
    async def disconnect(self):
        if self.message_stream:
            await self.client.close_stream(self.message_stream)
        await self.client.stop()

# 使用示例
async def chat_example():
    chat = ChatClient("general", "user123")
    
    try:
        await chat.connect()
        
        # 等待加入确认
        welcome = await chat.wait_for_join_confirmation()
        print(f"加入成功: {welcome}")
        
        # 发送消息
        await chat.send_message("大家好！")
        
        # 运行一段时间
        await asyncio.sleep(30)
        
    finally:
        await chat.disconnect()

asyncio.run(chat_example())
```

## 监控和指标

### 获取运行指标

```python
# 获取客户端指标
metrics = client.get_metrics()
print(f"连接状态: {metrics['running']}")
print(f"发送消息数: {metrics['connection']['messages_sent']}")
print(f"接收消息数: {metrics['connection']['messages_received']}")
print(f"活跃回调数: {metrics['messages']['active_callbacks']}")
print(f"重连次数: {metrics['reconnection']['attempt_count']}")
```

### 健康检查

```python
async def health_check(client: AioHttpWebSocketClient) -> bool:
    metrics = client.get_metrics()
    
    # 检查连接状态
    if not metrics['running']:
        return False
    
    # 检查错误率
    total_operations = (
        metrics['connection']['messages_sent'] + 
        metrics['connection']['messages_received']
    )
    if total_operations > 0:
        error_rate = metrics['connection']['errors'] / total_operations
        if error_rate > 0.1:  # 错误率超过10%
            return False
    
    return True
```

## 故障排除

### 常见问题

1. **连接失败**
   - 检查 URI 格式（必须以 ws:// 或 wss:// 开头）
   - 验证网络连接和防火墙设置
   - 检查 SSL 证书验证设置

2. **消息丢失**
   - 调整背压策略为 `DROP_NEW`
   - 增大队列大小 `send_queue_size`
   - 检查回调函数是否抛出异常

3. **内存泄漏**
   - 确保正确取消注册回调
   - 及时关闭不再使用的消息流
   - 使用 `ExecutionMode.THREADED` 时注意线程资源

4. **重连频繁**
   - 调整 `backoff_base` 和 `backoff_max`
   - 检查服务器稳定性
   - 验证心跳间隔设置

### 调试模式

```python
import logging

# 启用详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s'
)

client = AioHttpWebSocketClient(
    uri="wss://example.com",
    logger=logging.getLogger("websocket_debug")
)
```

## 注意事项

1. **资源清理**: 始终使用 `async with` 或显式调用 `stop()` 来清理资源
2. **异常处理**: 在回调函数中妥善处理异常，避免影响其他消息处理
3. **性能考虑**: 根据业务场景选择合适的背压策略和执行模式
4. **内存管理**: 及时取消不需要的回调和关闭消息流，避免内存泄漏

这个文档涵盖了客户端的所有主要功能和使用方法，可以帮助用户快速上手并在生产环境中使用。
