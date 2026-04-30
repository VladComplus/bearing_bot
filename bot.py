# FINAL VERSION V3 (fixed UX + moderation)

import asyncio
import logging
import os
import re
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardRemove
)
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1003955162793
ADMIN_ID = 1833282667
DB_FILE = "ads.json"
ADMIN_USERNAME = "blackberrySE"

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
# СПРАВОЧНИК
# =========================

def load_db_names():
    try:
        with open("db_names.txt", "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except:
        return []

DB_NAMES = load_db_names()

# =========================
# УТИЛИТЫ
# =========================

def normalize(text):
    return re.sub(r"[^a-z0-9а-яё]", "", text.lower())


def has_min_two_digits(text):
    return len(re.findall(r"\d", text)) >= 2


def matches_db(name):
    n = normalize(name)
    return any(normalize(x) in n or n in normalize(x) for x in DB_NAMES)


def contains_link(text):
    return any(x in text.lower() for x in ["http", "www", ".com", ".ru", ".net"])


def generate_id(ads):
    today = datetime.now().strftime("%Y%m%d")
    today_ads = [a for a in ads if a.get("id", "").startswith(f"ID{today}")]
    return f"ID{today}-{len(today_ads)+1}"

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
    desc = State()

# =========================
# UI
# =========================

main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📢 Продам")],[KeyboardButton(text="💵 Куплю")]],
    resize_keyboard=True
)

condition_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🆕 Новый"), KeyboardButton(text="♻️ Б/У")]],
    resize_keyboard=True
)

price_kb_buy = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💰 Договорная")]],
    resize_keyboard=True
)

skip_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏭ Пропустить")]],
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
    name = message.text.strip()

    if not has_min_two_digits(name):
        await message.answer("❌ Ошибка ввод")
        return

    await state.update_data(name=name)

    if not matches_db(name):
        await state.update_data(moderation=True)
    else:
        await state.update_data(moderation=False)

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
    data = await state.get_data()

    if "Куплю" in data['type']:
        await message.answer("Цена:", reply_markup=price_kb_buy)
    else:
        await message.answer("Цена в грн:", reply_markup=ReplyKeyboardRemove())

    await state.set_state(Form.price)

@dp.message(Form.price)
async def get_price(message: Message, state: FSMContext):
    text = message.text.strip()

    if text == "💰 Договорная":
        price = "договорная"
        price_value = 0
    else:
        digits = ''.join(filter(str.isdigit, text))
        if not digits:
            await message.answer("❌ Ошибка")
            return
        price = f"{digits} грн"
        price_value = int(digits)

    await state.update_data(price=price, price_value=price_value)
    await message.answer("Телефон:")
    await state.set_state(Form.phone)

@dp.message(Form.phone)
async def get_phone(message: Message, state: FSMContext):
    if not re.fullmatch(r"0\d{9}", message.text):
        await message.answer("❌ Ошибка")
        return

    await state.update_data(phone="+38"+message.text)
    await message.answer("Доп. информация (до 250 символов):", reply_markup=skip_kb)
    await state.set_state(Form.desc)

@dp.message(Form.desc)
async def get_desc(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        desc = ""
    else:
        desc = message.text.strip()

    if desc and len(desc) > 250:
        await message.answer("❌ Слишком длинный текст")
        return

    if contains_link(desc):
        await message.answer("❌ Ссылки запрещены")
        return

    data = await state.get_data()
    ads = load_ads()

    ad_id = generate_id(ads)

    now = datetime.now()

    condition = data['condition'].replace("🆕 ", "").replace("♻️ ", "").lower()

    short_desc = desc.split("\n")[0] if desc else ""

    text = (
        f"{data['type']}\n\n"
        f"📦 {data['name']}\n"
        f"🔢 Кол-во: {data['quantity']}\n"
        f"⚙️ Состояние: {condition}\n"
        f"💰 Цена: {data['price']}\n"
        f"📞 {data['phone']}\n"
    )

    if short_desc:
        text += f"📄 {short_desc}...\n"

    text += f"🕒 {now.strftime('%d.%m.%Y %H:%M')}        {ad_id}"

    ad = {**data, "desc": desc, "id": ad_id}

    ads.append(ad)
    save_ads(ads)

    # КНОПКИ МОДЕРАЦИИ
    mod_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{ad_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{ad_id}")]
    ])

    read_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Читать", callback_data=f"read_{ad_id}")]
    ])

    if data.get("moderation"):
        await bot.send_message(ADMIN_ID, text + "\n\n⏳ На модерации", reply_markup=mod_kb)
        await message.answer("⏳ На модерации", reply_markup=ReplyKeyboardRemove())
    else:
        await bot.send_message(CHANNEL_ID, text, reply_markup=read_kb)
        await message.answer("✅ Опубликовано", reply_markup=ReplyKeyboardRemove())

    await state.clear()

# =========================
# MODERATION ACTIONS
# =========================

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    ad_id = callback.data.split("_")[1]
    ads = load_ads()

    for ad in ads:
        if ad["id"] == ad_id:
            text = f"📢 Продам\n\n📦 {ad['name']}\n🔢 Кол-во: {ad['quantity']}\n⚙️ Состояние: {ad['condition']}\n💰 Цена: {ad['price']}\n📞 {ad['phone']}\n🕒 {ad_id}"

            await bot.send_message(CHANNEL_ID, text)

    await callback.message.edit_text("✅ Одобрено")

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    await callback.message.edit_text("❌ Отклонено")

# =========================
# READ
# =========================

@dp.callback_query(F.data.startswith("read_"))
async def read(callback: CallbackQuery):
    ad_id = callback.data.split("_")[1]
    ads = load_ads()

    for ad in ads:
        if ad["id"] == ad_id:
            text = f"📄 {ad['desc']}" if ad['desc'] else "Нет описания"

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍💼 Связаться", url=f"https://t.me/{ADMIN_USERNAME}")]
            ])

            await callback.message.answer(text, reply_markup=kb)

# =========================
# RUN
# =========================

async def main():
    print("БОТ СТАРТОВАЛ")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





