import asyncio
import logging
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# 🔐 токен и канал
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1003955162793  # <-- твой канал

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 📌 Состояния
class Form(StatesGroup):
    type = State()
    name = State()
    quantity = State()
    condition = State()
    price = State()
    phone = State()

# 🔘 Главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Продам")],
        [KeyboardButton(text="🔍 Куплю")],
        [KeyboardButton(text="📊 Поиск")]
    ],
    resize_keyboard=True
)

# 🔘 Состояние товара
condition_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆕 Новый"), KeyboardButton(text="♻️ Б/У")]
    ],
    resize_keyboard=True
)

# ▶️ Старт
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_kb)

# 📦 Продам / Куплю
@dp.message(F.text.in_(["📦 Продам", "🔍 Куплю"]))
async def choose_type(message: Message, state: FSMContext):
    await state.update_data(type=message.text)
    await message.answer("📌 Введи наименование подшипника:")
    await state.set_state(Form.name)

# 📌 Наименование
@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📦 Введи количество:")
    await state.set_state(Form.quantity)

# 📦 Количество
@dp.message(Form.quantity)
async def get_quantity(message: Message, state: FSMContext):
    await state.update_data(quantity=message.text)
    await message.answer("⚙️ Выбери состояние:", reply_markup=condition_kb)
    await state.set_state(Form.condition)

# ⚙️ Состояние (только кнопки)
@dp.message(Form.condition, F.text.in_(["🆕 Новый", "♻️ Б/У"]))
async def get_condition(message: Message, state: FSMContext):
    await state.update_data(condition=message.text)
    await message.answer("💰 Введи цену (в гривнах):")
    await state.set_state(Form.price)

# 💰 Цена
@dp.message(Form.price)
async def get_price(message: Message, state: FSMContext):
    price_input = message.text.strip()

    digits = ''.join(filter(str.isdigit, price_input))

    if not digits:
        await message.answer("❌ Введи цену числом, например: 100")
        return

    price = f"{digits} грн"

    await state.update_data(price=price)

    # 👉 ПЕРЕХОД К ТЕЛЕФОНУ
    await message.answer("📞 Введи номер телефона (например: 0501234567)")
    await state.set_state(Form.phone)

# 📞 Телефон
@dp.message(Form.phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.text.strip()

    # проверка
    if not re.fullmatch(r"0\d{9}", phone):
        await message.answer("❌ Неверный формат!\nПример: 0501234567")
        return

    phone = "+38" + phone

    await state.update_data(phone=phone)
    data = await state.get_data()

    # 📢 формируем объявление
    text = (
        f"📢 Объявление\n\n"
        f"{data['type']}\n"
        f"📌 {data['name']}\n"
        f"📦 Кол-во: {data['quantity']}\n"
        f"⚙️ Состояние: {data['condition']}\n"
        f"💰 Цена: {data['price']}\n"
        f"📞 {phone}"
    )

    # отправка
    await bot.send_message(CHANNEL_ID, text)
    await message.answer("✅ Объявление опубликовано!", reply_markup=main_kb)

    await state.clear()

# 🚀 Запуск
async def main():
    print("БОТ СТАРТОВАЛ")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
