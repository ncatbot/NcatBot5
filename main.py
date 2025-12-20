import asyncio
from src import Bot, IMClient

bot = Bot(
    url='ws://192.168.3.20:3003'
)

bot.run()