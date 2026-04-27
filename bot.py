import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1003955162793

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()


# 📌 Состояния
class Form(StatesGroup):
    type = State()
    name = State()
    qty = State()
    condition = State()
    price = State()
    phone = State()


# 📌 Клавиатура
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Продам"), KeyboardButton(text="Куплю")],
        [KeyboardButton(text="Поиск")]
    ],
    resize_keyboard=True
)


# ▶️ Старт
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Выбери действие:", reply_markup=menu)


# 🔘 Продам / Куплю
@dp.message(F.text.in_(["Продам", "Куплю"]))
async def choose_type(message: Message, state: FSMContext):
    await state.update_data(type=message.text)
    await message.answer("📦 Введи наименование:")
    await state.set_state(Form.name)


# 📦 Наименование
@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🔢 Введи количество:")
    await state.set_state(Form.qty)


# 🔢 Количество
@dp.message(Form.qty)
async def get_qty(message: Message, state: FSMContext):
    await state.update_data(qty=message.text)
    await message.answer("⚙️ Состояние (новый / б/у):")
    await state.set_state(Form.condition)


# ⚙️ Состояние
@dp.message(Form.condition)
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

    # 👉 ВАЖНО: переход к следующему шагу
    await message.answer("📞 Введи номер телефона (например: 0501234567)")
    await state.set_state(Form.phone)
    data = await state.get_data()

    post = f"""
📢 {data['type'].upper()}

📦 {data['name']}
🔢 Кол-во: {data['qty']}
⚙️ Состояние: {data['condition']}
💰 Цена: {data['price']}

👤 @{message.from_user.username or 'без ника'}
"""

    await bot.send_message(CHANNEL_ID, post)
    await message.answer("✅ Объявление опубликовано", reply_markup=menu)

    await state.clear()


# 🔍 Поиск (пока заглушка)
@dp.message(F.text == "Поиск")
async def search(message: Message):
    await message.answer("🔍 Поиск скоро добавим")


async def main():
    print("БОТ СТАРТОВАЛ")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
