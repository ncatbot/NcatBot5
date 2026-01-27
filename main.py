from src import Bot

bot = Bot(
    root_id="3123651157",  # Bot所有者id
    url="ws://192.168.3.20:3003",  # Bot后端ws接口
    plugin_dir="./plugins",  # 用户插件文件夹目录
    # token='',                       # Bot后端w连接token
    debug=True,  # debug模式
)

try:
    bot.run()
except KeyboardInterrupt:
    pass
