import sqlite3
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("ads.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    condition TEXT,
    price TEXT,
    city TEXT,
    contact TEXT
)
""")
conn.commit()

kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(KeyboardButton("Разместить"), KeyboardButton("Поиск"))

user_data = {}

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Бот объявлений", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Разместить")
async def add_ad(msg: types.Message):
    user_data[msg.from_user.id] = {}
    await msg.answer("Введите наименование:")

@dp.message_handler()
async def process(msg: types.Message):
    uid = msg.from_user.id

    if uid in user_data:
        data = user_data[uid]

        if "name" not in data:
            data["name"] = msg.text
            await msg.answer("Состояние (новый/б/у):")
        elif "condition" not in data:
            data["condition"] = msg.text
            await msg.answer("Цена:")
        elif "price" not in data:
            data["price"] = msg.text
            await msg.answer("Город:")
        elif "city" not in data:
            data["city"] = msg.text
            await msg.answer("Контакт:")
        elif "contact" not in data:
            data["contact"] = msg.text

            cursor.execute(
                "INSERT INTO ads (name, condition, price, city, contact) VALUES (?, ?, ?, ?, ?)",
                (data["name"], data["condition"], data["price"], data["city"], data["contact"])
            )
            conn.commit()

            await msg.answer("Объявление добавлено ✅")
            del user_data[uid]

    elif msg.text == "Поиск":
        await msg.answer("Введите запрос:")

    else:
        cursor.execute("SELECT * FROM ads WHERE name LIKE ?", ('%' + msg.text + '%',))
        results = cursor.fetchall()

        if results:
            text = ""
            for r in results:
                text += f"{r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]}\n"
            await msg.answer(text)
        else:
            await msg.answer("Ничего не найдено")

if __name__ == "__main__":
    executor.start_polling(dp)