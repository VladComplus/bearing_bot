import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

TOKEN = "8759403185:AAHZmN6hWzexMB_Ph5W8AZ6iBmhhMT7Bkrk"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Бот запущен 🚀")

async def main():
    print("БОТ СТАРТОВАЛ")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
