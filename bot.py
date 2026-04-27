import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1003955162793  # <-- твой канал

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Отправь объявление — я опубликую его в канал 📢")


# 📢 ПУБЛИКАЦИЯ ОБЪЯВЛЕНИЯ
@dp.message()
async def publish(message: Message):
    text = message.text

    post = f"""
📢 НОВОЕ ОБЪЯВЛЕНИЕ

{text}

👤 @{message.from_user.username or 'без ника'}
"""

    await bot.send_message(CHANNEL_ID, post)
    await message.answer("✅ Объявление опубликовано")


async def main():
    print("БОТ СТАРТОВАЛ")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
