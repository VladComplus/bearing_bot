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
CHANNEL_ID = -1003955162793

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =========================
# 🔒 СТОП-СЛОВА + АНТИ-ОБХОД
# =========================

def load_stop_words():
    try:
        with open("stop_words.txt", "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except:
        return []

STOP_WORDS = load_stop_words()

# 🔄 замена похожих символов (обходы)
CHAR_MAP = str.maketrans({
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х",
    "A": "а", "E": "е", "O": "о", "P": "р", "C": "с", "Y": "у", "X": "х"
})

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.translate(CHAR_MAP)
    text = re.sub(r"[^а-я0-9]", "", text)  # убираем символы типа *, -, пробелы
    return text

def contains_stop_word(text: str) -> bool:
    normalized = normalize_text(text)

    for word in STOP_WORDS:
        if normalize_text(word) in normalized:
            return True
    return False

# =========================
# 📌 FSM
# =========================

class Form(StatesGroup):
    type = State()
    name = State()
    quantity = State()
    condition = State()
    price = State()
    phone = State()

# =========================
# 🔘 КЛАВИАТУРЫ
# =========================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Продам")],
        [KeyboardButton(text="💵 Куплю")],
        [KeyboardButton(text="📊 Поиск")]
    ],
    resize_keyboard=True
)

condition_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆕 Новый"), KeyboardButton(text="♻️ Б/У")]
    ],
    resize_keyboard=True
)

price_kb_buy = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Договорная")]
    ],
    resize_keyboard=True
)

# =========================
# ▶️ СТАРТ
# =========================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_kb)

# =========================
# 📢 / 💵
# =========================

@dp.message(F.text.in_(["📢 Продам", "💵 Куплю"]))
async def choose_type(message: Message, state: FSMContext):
    await state.update_data(type=message.text)
    await message.answer("📌 Введи наименование (до 32 символов):")
    await state.set_state(Form.name)

# =========================
# 📌 НАИМЕНОВАНИЕ
# =========================

@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name) > 32:
        await message.answer("❌ Максимум 32 символа")
        return

    if contains_stop_word(name):
        await message.answer("❌ Запрещённые слова")
        return

    await state.update_data(name=name)
    await message.answer("🔢 Введи количество:")
    await state.set_state(Form.quantity)

# =========================
# 🔢 КОЛИЧЕСТВО
# =========================

@dp.message(Form.quantity)
async def get_quantity(message: Message, state: FSMContext):
    qty = message.text.strip()

    if not qty.isdigit():
        await message.answer("❌ Только цифры")
        return

    await state.update_data(quantity=qty)
    await message.answer("⚙️ Выбери состояние:", reply_markup=condition_kb)
    await state.set_state(Form.condition)

# =========================
# ⚙️ СОСТОЯНИЕ
# =========================

@dp.message(Form.condition, F.text.in_(["🆕 Новый", "♻️ Б/У"]))
async def get_condition(message: Message, state: FSMContext):
    await state.update_data(condition=message.text)

    data = await state.get_data()

    if "Куплю" in data['type']:
        await message.answer("💰 Введи цену или выбери:", reply_markup=price_kb_buy)
    else:
        await message.answer("💰 Введи цену (в грн):")

    await state.set_state(Form.price)

# =========================
# 💰 ЦЕНА
# =========================

@dp.message(Form.price)
async def get_price(message: Message, state: FSMContext):
    price_input = message.text.strip()

    if price_input == "💰 Договорная":
        price = "договорная"
    else:
        digits = ''.join(filter(str.isdigit, price_input))

        if not digits:
            await message.answer("❌ Введи цену цифрами")
            return

        price = f"{digits} грн"

    await state.update_data(price=price)

    await message.answer("📞 Введи номер (0501234567)")
    await state.set_state(Form.phone)

# =========================
# 📞 ТЕЛЕФОН
# =========================

@dp.message(Form.phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.text.strip()

    if not re.fullmatch(r"0\d{9}", phone):
        await message.answer("❌ Формат: 0501234567")
        return

    phone = "+38" + phone

    await state.update_data(phone=phone)
    data = await state.get_data()

    title = "📢 ПРОДАМ" if "Продам" in data['type'] else "💵 КУПЛЮ"

    condition = data['condition'].replace("🆕 ", "").replace("♻️ ", "").lower()

    text = (
        f"{title}\n\n"
        f"📦 {data['name']}\n"
        f"🔢 Кол-во: {data['quantity']}\n"
        f"⚙️ Состояние: {condition}\n"
        f"💰 Цена: {data['price']}\n"
        f"📞 {phone}"
    )

    await bot.send_message(CHANNEL_ID, text)
    await message.answer("✅ Опубликовано", reply_markup=main_kb)

    await state.clear()

# =========================
# 🚀 ЗАПУСК
# =========================

async def main():
    print("БОТ СТАРТОВАЛ")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
