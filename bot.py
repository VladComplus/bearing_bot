import asyncio
import logging
import os
import re
import json

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# 🔐 токен и канал
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1003955162793
DB_FILE = "ads.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =========================
# 📦 БАЗА (JSON)
# =========================

def load_ads():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_ad(ad):
    ads = load_ads()
    ads.append(ad)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(ads, f, ensure_ascii=False, indent=2)

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

CHAR_MAP = str.maketrans({
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х",
    "A": "а", "E": "е", "O": "о", "P": "р", "C": "с", "Y": "у", "X": "х"
})

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.translate(CHAR_MAP)
    text = re.sub(r"[^а-я0-9]", "", text)
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
    search = State()

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
        await message.answer(
            "❌ Максимум 32 символа\n\n"
            "🔁 Повторите ввод\n"
            "📌 Введите наименование:"
        )
        return

    if contains_stop_word(name):
        await message.answer(
            "❌ Запрещённые слова\n\n"
            "🔁 Повторите ввод\n"
            "📌 Введите наименование:"
        )
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
        await message.answer(
            "❌ Только цифры\n\n"
            "🔁 Повторите ввод\n"
            "🔢 Введите количество:"
        )
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
        await message.answer("💰 Введи цену (в гривнах):")

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
            await message.answer(
                "❌ Введи цену цифрами\n\n"
                "🔁 Повторите ввод\n"
                "💰 Введите цену:"
            )
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
        await message.answer(
            "❌ Неверный формат\n\n"
            "🔁 Повторите ввод\n"
            "📞 Введите номер (0501234567):"
        )
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

    # 💾 сохраняем в базу
    ad = {
        "type": title,
        "name": data['name'],
        "quantity": data['quantity'],
        "condition": condition,
        "price": data['price'],
        "phone": phone
    }

    save_ad(ad)

    # 📢 публикуем
    await bot.send_message(CHANNEL_ID, text)
    await message.answer("✅ Опубликовано", reply_markup=main_kb)

    await state.clear()

# =========================
# 🔍 ПОИСК
# =========================

@dp.message(F.text == "📊 Поиск")
async def search_start(message: Message, state: FSMContext):
    await message.answer("🔍 Введи что ищешь:")
    await state.set_state(Form.search)

@dp.message(Form.search)
async def search_ads(message: Message, state: FSMContext):
    query = message.text.strip()
    query_norm = normalize_text(query)

    ads = load_ads()
    results = []

    for ad in ads:
        combined = f"{ad['name']} {ad['type']} {ad['condition']} {ad['price']}"
        combined_norm = normalize_text(combined)

        if query_norm in combined_norm:
            results.append(ad)

    if not results:
        await message.answer(
            "❌ Ничего не найдено\n\n"
            "🔁 Попробуйте другой запрос"
        )
        return

    results = results[:5]

    await message.answer(f"🔍 Найдено: {len(results)}")

    for ad in results:
        text = (
            f"{ad['type']}\n\n"
            f"📦 {ad['name']}\n"
            f"🔢 Кол-во: {ad['quantity']}\n"
            f"⚙️ Состояние: {ad['condition']}\n"
            f"💰 Цена: {ad['price']}\n"
            f"📞 {ad['phone']}"
        )
        await message.answer(text)

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
