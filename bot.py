# FULL BOT WITH MODERATION BUTTONS

import asyncio
import logging
import os
import re
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1003955162793
ADMIN_ID = 1833282667  # <-- ВСТАВЬ СВОЙ ID
DB_FILE = "ads.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =========================
# БАЗА
# =========================

def load_ads():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_ads(ads):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(ads, f, ensure_ascii=False, indent=2)

# =========================
# СЛОВА
# =========================

def load_list(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except:
        return []

STOP_WORDS = load_list("stop_words.txt")
DB_NAMES = load_list("db_names.txt")

CHAR_MAP = str.maketrans({
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х",
})


def normalize_text(text):
    text = text.lower().translate(CHAR_MAP)
    return re.sub(r"[^а-я0-9]", "", text)


def clean_name(text):
    return re.sub(r"[^A-Za-zА-Яа-яЁё0-9]+", "", text)


def contains_stop_word(text):
    n = normalize_text(text)
    for w in STOP_WORDS:
        w = normalize_text(w)
        if not w:
            continue
        if w in n:
            return True
    return False


def has_min_two_digits(text):
    return len(re.findall(r"\d", text)) >= 2


def in_db_names(text):
    text = text.lower()
    return any(name in text for name in DB_NAMES)

# =========================
# FSM
# =========================

class Form(StatesGroup):
    type = State()
    name = State()
    quantity = State()
    condition = State()
    price = State()
    phone = State()

# =========================
# UI
# =========================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Продам")],
        [KeyboardButton(text="💵 Куплю")]
    ], resize_keyboard=True
)

condition_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🆕 Новый"), KeyboardButton(text="♻️ Б/У")]],
    resize_keyboard=True
)

# =========================
# START
# =========================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_kb)

# =========================
# FLOW
# =========================

@dp.message(F.text.in_(["📢 Продам", "💵 Куплю"]))
async def choose_type(message: Message, state: FSMContext):
    await state.update_data(type=message.text)
    await message.answer("Введите наименование:")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    name = clean_name(message.text)

    if not has_min_two_digits(name):
        await message.answer("❌ Ошибка ввода")
        return

    if contains_stop_word(name):
        await message.answer("❌ Ошибка ввода")
        return

    status = "approved" if in_db_names(name) else "moderation"

    await state.update_data(name=name, status=status)
    await message.answer("Количество:")
    await state.set_state(Form.quantity)

@dp.message(Form.quantity)
async def get_qty(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Ошибка")
        return

    await state.update_data(quantity=message.text)
    await message.answer("Состояние:", reply_markup=condition_kb)
    await state.set_state(Form.condition)

@dp.message(Form.condition)
async def get_cond(message: Message, state: FSMContext):
    await state.update_data(condition=message.text)
    await message.answer("Цена:")
    await state.set_state(Form.price)

@dp.message(Form.price)
async def get_price(message: Message, state: FSMContext):
    digits = ''.join(filter(str.isdigit, message.text))
    if not digits:
        await message.answer("❌ Ошибка")
        return

    await state.update_data(price=f"{digits} грн", price_value=int(digits))
    await message.answer("Телефон:")
    await state.set_state(Form.phone)

@dp.message(Form.phone)
async def get_phone(message: Message, state: FSMContext):
    if not re.fullmatch(r"0\d{9}", message.text):
        await message.answer("❌ Ошибка")
        return

    data = await state.get_data()
    phone = "+38" + message.text
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    text = (
        f"{data['type']}\n\n"
        f"📦 {data['name']}\n"
        f"🔢 {data['quantity']}\n"
        f"⚙️ {data['condition']}\n"
        f"💰 {data['price']}\n"
        f"📞 {phone}\n"
        f"🕒 {now}"
    )

    ads = load_ads()
    ad_id = len(ads)

    ad = {**data, "phone": phone, "date": now, "id": ad_id}
    ads.append(ad)
    save_ads(ads)

    if data["status"] == "approved":
        await bot.send_message(CHANNEL_ID, text)
        await message.answer("✅ Опубликовано")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"ok_{ad_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no_{ad_id}")
            ]
        ])

        await bot.send_message(ADMIN_ID, f"МОДЕРАЦИЯ:\n\n{text}", reply_markup=kb)
        await message.answer("⏳ На модерации")

    await state.clear()

# =========================
# CALLBACKS
# =========================

@dp.callback_query(F.data.startswith("ok_"))
async def approve(callback: CallbackQuery):
    ad_id = int(callback.data.split("_")[1])
    ads = load_ads()

    ad = ads[ad_id]

    text = (
        f"{ad['type']}\n\n"
        f"📦 {ad['name']}\n"
        f"🔢 {ad['quantity']}\n"
        f"⚙️ {ad['condition']}\n"
        f"💰 {ad['price']}\n"
        f"📞 {ad['phone']}\n"
        f"🕒 {ad['date']}"
    )

    await bot.send_message(CHANNEL_ID, text)
    await callback.message.edit_text("✅ Опубликовано")

@dp.callback_query(F.data.startswith("no_"))
async def reject(callback: CallbackQuery):
    await callback.message.edit_text("❌ Отклонено")

# =========================
# RUN
# =========================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

