# FINAL VERSION V5 (fixed stop-words bug completely)

import asyncio
import logging
import os
import re
import json
from datetime import datetime

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
ADMIN_USERNAME = "blackberrySE"
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
# DB NAMES
# =========================

def load_db_names():
    try:
        with open("db_names.txt", "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except:
        return []

DB_NAMES = load_db_names()

# =========================
# STOP WORDS (V6 HARD FILTER)
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

    # заменяем похожие символы
    text = text.replace("0", "o").replace("1", "l").replace("3", "e")

    # оставляем латиницу + кириллицу + цифры
    text = re.sub(r"[^a-zа-я0-9]", "", text)

    return text


def build_pattern(word: str) -> str:
    """
    Превращает слово в regex, который ловит:
    f.u.c.k / f u c k / f-uck / f*ck
    """
    chars = list(word)
    pattern = r""

    for c in chars:
        pattern += re.escape(c) + r"[\W_]*"

    return pattern


# строим regex один раз
STOP_PATTERNS = []

for word in STOP_WORDS:
    w = normalize_text(word)

    if len(w) < 2:
        continue

    STOP_PATTERNS.append(re.compile(build_pattern(w)))


def contains_stop_word(text: str) -> bool:
    norm = normalize_text(text)

    if norm.isdigit():
        return False

    for pattern in STOP_PATTERNS:
        if pattern.search(norm):
            return True

    return False

# =========================
# ЛОГИКА
# =========================

def has_min_two_digits(text):
    return len(re.findall(r"\d", text)) >= 2


def matches_db(name):
    n = normalize_text(name)
    for item in DB_NAMES:
        ni = normalize_text(item)
        if ni in n or n in ni:
            return True
    return False


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

    if contains_stop_word(name):
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
    else:
        digits = ''.join(filter(str.isdigit, text))
        if not digits:
            await message.answer("❌ Ошибка")
            return
        price = f"{digits} грн"

    await state.update_data(price=price)
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

    data = await state.get_data()
    ads = load_ads()

    ad_id = generate_id(ads)

    now = datetime.now().strftime('%d.%m.%Y %H:%M')

    condition = data['condition'].replace("🆕 ", "").replace("♻️ ", "").lower()

    type_text = "📢 <b>ПРОДАМ</b>" if "Продам" in data['type'] else "💵 <b>КУПЛЮ</b>"

desc_text = f"\n📖 Доп. информация: {desc}" if desc else ""

text = (
    f"{type_text}\n\n"
    f"🧿 <b>{data['name']}</b>\n"
    f"🔢 Кол-во: {data['quantity']}\n"
    f"⚙️ Состояние: {condition}\n"
    f"💰 Цена: {data['price']}\n"
    f"📞 {data['phone']}"
    f"{desc_text}\n\n"
    f"🕒 {now}        {ad_id}"
)

    ads.append({**data, "id": ad_id, "desc": desc})
    save_ads(ads)

    read_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Читать", callback_data=f"read_{ad_id}")]
    ])

    if data.get("moderation"):
        mod_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{ad_id}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{ad_id}")]
        ])

        await bot.send_message(ADMIN_ID, text + "\n\n⏳ На модерации", reply_markup=mod_kb, parse_mode="HTML")
        await message.answer("⏳ На модерации", reply_markup=main_kb)
    else:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        await message.answer("✅ Опубликовано\n\nВыберите действие:", reply_markup=main_kb)

    await state.clear()

# =========================
# READ FULL DESCRIPTION
# =========================

@dp.callback_query(F.data.startswith("read_"))
async def read_more(callback: CallbackQuery):
    ad_id = callback.data.split("_", 1)[1]

    ads = load_ads()
    ad = next((a for a in ads if a.get("id") == ad_id), None)

    if not ad:
        await callback.answer("❌ Объявление не найдено", show_alert=True)
        return

    desc = ad.get("desc", "")

    if not desc:
        await callback.answer("ℹ️ Нет дополнительной информации", show_alert=True)
        return

    await callback.message.answer(f"📖 Доп. информация:\n\n{desc}")
    await callback.answer()

# =========================
# RUN
# =========================

async def main():
    print("БОТ СТАРТОВАЛ")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
