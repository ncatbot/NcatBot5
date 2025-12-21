# 灰度测试快速上手（临时文档）

> 本文档仅用于灰度测试，接口可能变动，请随时关注群内通知。

---

## 1. 安装 & 启动

```bash
# 解压灰度包
unzip dist-5.0.0-dev.0.zip
cd bot-sdk

# 安装依赖（仅需一次）
pip install -r requirements.txt

# 启动
python -m src \
  -u ws://localhost:3001 \
  -t <你的token> \
  -p napcat \
  --plugin-dir ./plugins
```

---

## 2. IM.py 是什么

`IM.py` 是**用户面向的对象层**，已帮你把协议细节封装成直观类：

| 类 | 作用 | 常用示例 |
|---|---|---|
| `User` | 任何用户 | `user.send_text("hello")` |
| `Group` | 任何群 | `group.send_text("@all 开工")` |
| `Message` | 单条消息 | `msg.reply_text("收到")` |
| `MessageContent` | 富文本容器 | 见下方“发富文本” |

这些对象**只在事件回调里拿到**，不要自己 `new`。

---

## 3. 5 分钟写插件

### ① 新建文件

`plugins/demo.py`

```python
from src.plugins_system import Plugin
from src import Event                        # 事件对象

class DemoPlugin(Plugin):
    name = "demo"
    version = "0.1"

    async def on_load(self):
        # 注册事件：群消息
        self.register_handler("message.group", self.on_group_msg)

    async def on_group_msg(self, event: Event):
        data = event.data
        text: str = data["message"][0]["data"]["text"]

        if text == "你好":
            # 拿到群对象
            from src import IMClient
            client = IMClient.get_current()
            group = await client.get_group(data["group_id"])
            await group.send_text("你好，灰度测试！")
```

### ② 放回插件目录

把 `demo.py` 丢进启动时 `--plugin-dir` 指定的文件夹即可，**无需重启**会自动加载。

---

## 4. 常用代码片段

| 场景 | 代码 |
|---|---|
| 回复文本 | `await msg.reply_text("ok")` |
| 发富文本 | `await user.send_message(MessageContent([TextNode("文字"), ImageNode("http://i.jpg")]))` |
| 获取发送者 | `sender = await msg.get_sender()` |
| 取好友列表 | `friends = await client.get_friends()` |
| 撤回自己消息 | `await msg.recall()` |

---

## 5. 快速调试

1. 打开 `logs/bot.log` 看实时日志。
2. 插件里任意地方打印：

   ```python
   self.logger.info("任意信息")
   ```

3. 改完代码保存即热重载（灰度版已开 dev 模式）。

---

## 6. 限制 & 注意

- 仅支持 `napcat` 协议。
- 灰度阶段 **API 可能 breaking**，请锁定版本号。
- 可以直接实例化 `User`/`Group` 使用

---
