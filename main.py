from src import Bot

bot = Bot(
    url="ws://192.168.3.20:3003",
    plugin_dir="plugins",
)

try:
    bot.run()
except KeyboardInterrupt:
    pass
