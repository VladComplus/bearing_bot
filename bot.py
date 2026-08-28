# FINAL VERSION V5 (fixed stop-words bug completely)

import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

from aiogram.filters import Command
import sqlite3

@dp.message(Command("db"))
async def db_view(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return

    text = message.text.strip().split()

    # если просто /db → список
    if len(text) == 1:
        conn = sqlite3.connect("ads.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT id, name, price, phone, archived, created_at
        FROM ads
        ORDER BY created_at DESC
        LIMIT 20
        """)

        rows = cursor.fetchall()
        conn.close()

        msg = "📦 Последние объявления:\n\n"

        for r in rows:
            status = "🔒 архив" if r[4] == 1 else "🟢 актив"
            msg += f"{r[0]} | {r[1]} | {r[2]} \n{status}\n\n"

        await message.answer(msg)
        return

    # если /db IDxxxx → одно объявление
    ad_id = text[1]

    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, name, quantity, condition, price, phone, desc, archived, created_at, channel_message_id
    FROM ads
    WHERE id = ?
    """, (ad_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        await message.answer("❌ Объявление не найдено")
        return

    status = "🔒 АРХИВ" if row[7] == 1 else "🟢 АКТИВ"

    desc_text = f"\n📖 {row[6]}" if row[6] else ""

    msg = (
        f"📦 <b>{row[1]}</b>\n"
        f"🔢 Кол-во: {row[2]}\n"
        f"⚙️ Состояние: {row[3]}\n"
        f"💰 Цена: {row[4]}\n"
        f"📞 {row[5]}\n"
        f"{status}"
        f"{desc_text}\n\n"
        f"🆔 {row[0]}\n"
        f"📨 MSG_ID: {row[9]}"
    )

    await message.answer(msg)

# ===========Подлежит удалению после теста до conn.close==============
@dp.message(Command("upgrade"))
async def upgrade_db(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return

    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
        ALTER TABLE ads
        ADD COLUMN channel_message_id INTEGER
        """)

        conn.commit()

        await message.answer("✅ Колонка channel_message_id добавлена")

    except Exception as e:
        await message.answer(f"⚠️ {e}")

    conn.close()
# ===========Подлежит удалению до conn.close==============

@dp.message(Command("db_tables"))
async def db_tables(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("board.db")
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    text = "📦 Таблицы базы:\n\n"

    for table in tables:
        text += f"{table[0]}\n"

    conn.close()

    await message.answer(text)

# =========================
# БАЗА
# =========================

def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id TEXT PRIMARY KEY,
        type TEXT,
        name TEXT,
        quantity TEXT,
        condition TEXT,
        price TEXT,
        phone TEXT,
        desc TEXT,
        user_id INTEGER,
        created_at TEXT,
        expires_at TEXT,
        archived INTEGER DEFAULT 0,
        channel_message_id INTEGER
    )
    """)

       
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    position INTEGER NOT NULL
    )
    """)

    conn.commit()
    conn.close()

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


def generate_id():
    today = datetime.now().strftime("%Y%m%d")

    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM ads WHERE id LIKE ?", (f"ID{today}-%",))
    count = cursor.fetchone()[0]

    conn.close()

    return f"ID{today}-{count+1}"

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
    photos = State()
    search = State()

# =========================
# UI
# =========================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Продам"), KeyboardButton(text="💵 Куплю")],
        [KeyboardButton(text="🔍 Поиск")]
    ],
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

photo_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Готово")],
        [KeyboardButton(text="⏭ Пропустить")]
    ],
    resize_keyboard=True
)
# =========================
# START
# =========================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_kb)

@dp.message(Command("testdb"))
async def test_db(message: Message):
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM ads")
    count = cursor.fetchone()[0]

    conn.close()

    await message.answer(f"В базе объявлений: {count}")

# =========================
# FLOW
# =========================

@dp.message(F.text.in_(["📢 Продам", "💵 Куплю"]))
async def choose_type(message: Message, state: FSMContext):
    await state.update_data(type=message.text)
    await message.answer("Введите наименование:")
    await state.set_state(Form.name)
    
@dp.message(F.text == "🔍 Поиск")
async def search_start(message: Message, state: FSMContext):
    await state.set_state(Form.search)
    await message.answer("Введите номер подшипника или текст для поиска:")
    
@dp.message(Form.search)
async def search_ads(message: Message, state: FSMContext):
    query = message.text.strip()

    search_query = (
        query.lower()
        .replace("-", "")
        .replace(" ", "")
        .replace(".", "")
    )

    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, type, name, quantity, condition,
           price, phone, desc, created_at, archived
    FROM ads
    ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    found = []

    for row in rows:
        db_name = (
            row[2].lower()
            .replace("-", "")
            .replace(" ", "")
            .replace(".", "")
        )

        if search_query in db_name:
            found.append(row)

    if not found:
        await message.answer(
            "❌ Ничего не найдено\n\nВыберите действие:",
            reply_markup=main_kb
        )
        await state.clear()
        return

    for row in found[:10]:
        ad_id = row[0]

        type_text = "📢 <b>ПРОДАМ</b>" if "Продам" in row[1] else "💵 <b>КУПЛЮ</b>"

        condition = row[4].replace("🆕 ", "").replace("♻️ ", "").lower()

        now = datetime.fromisoformat(row[8]).strftime('%d.%m.%Y %H:%M')

        is_archived = row[9] == 1

        if is_archived:
            text = (
                f"{type_text}\n\n"
                f"🧿 <b>{row[2]}</b>\n"
                f"🔢 Кол-во: {row[3]}\n"
                f"⚙️ Состояние: {condition}\n"
                f"💰 Цена: {row[5]}\n\n"
                f"🔒 Архивное объявление\n"
                f"📩 Связь через администратора\n\n"
                f"🕒 {now}        {ad_id}"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📩 Связаться с админом",
                    url=f"https://t.me/{ADMIN_USERNAME}"
                )]
            ])

            await message.answer(text, reply_markup=kb, parse_mode="HTML")

        else:
            desc_text = f"\n📖 Доп. информация: {row[7]}" if row[7] else ""

            text = (
                f"{type_text}\n\n"
                f"🧿 <b>{row[2]}</b>\n"
                f"🔢 Кол-во: {row[3]}\n"
                f"⚙️ Состояние: {condition}\n"
                f"💰 Цена: {row[5]}\n"
                f"📞 {row[6]}"
                f"{desc_text}\n\n"
                f"🕒 {now}        {ad_id}"
            )

            await message.answer(text, parse_mode="HTML")

    await message.answer("Выберите действие:", reply_markup=main_kb)

    await state.clear()

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

    if desc and contains_stop_word(desc):
        await message.answer("❌ Ошибка ввод")
        return

    await state.update_data(desc=desc, photos=[])

    await message.answer(
        "📷 Загрузите до 4 фотографий.\n\n"
        "Можно отправлять фотографии по одной.\n"
        "После загрузки нажмите «✅ Готово».\n"
        "Если фотографии не нужны — нажмите «⏭ Пропустить».",
        reply_markup=photo_kb
    )

    await state.set_state(Form.photos)


# =========================
# PHOTOS
# =========================


# =========================
# READ FULL DESCRIPTION
# =========================

@dp.callback_query(F.data.startswith("read_"))
async def read_more(callback: CallbackQuery):
    ad_id = callback.data.split("_", 1)[1]

   

    desc = "временно недоступно"

    if not desc:
        await callback.answer("ℹ️ Нет дополнительной информации", show_alert=True)
        return

    await callback.message.answer(f"📖 Доп. информация:\n\n{desc}")
    await callback.answer()

# =========================
# MODERATION HANDLERS
# =========================

@dp.callback_query(F.data.startswith("approve_"))
async def approve_ad(callback: CallbackQuery):
    ad_id = callback.data.split("_", 1)[1]

    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()

    cursor.execute("""
SELECT id, name, quantity, condition, price, phone, desc,
archived, created_at, channel_message_id
FROM ads
WHERE id = ?
""", (ad_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        await callback.answer("❌ Не найдено", show_alert=True)
        return

    is_archived = row[8] == 1

    condition = row[3].replace("🆕 ", "").replace("♻️ ", "").lower()

    type_text = "📢 <b>ПРОДАМ</b>" if "Продам" in row[0] else "💵 <b>КУПЛЮ</b>"
    desc_text = f"\n📖 Доп. информация: {row[6]}" if row[6] else ""

    now = datetime.fromisoformat(row[7]).strftime('%d.%m.%Y %H:%M')

    if is_archived:
        text = (
            f"{type_text}\n\n"
            f"🧿 <b>{row[1]}</b>\n"
            f"🔢 Кол-во: {row[2]}\n"
            f"⚙️ Состояние: {condition}\n"
            f"💰 Цена: {row[4]}\n\n"
            f"🔒 Контакты скрыты\n"
            f"📩 Связь через администратора\n\n"
            f"🕒 {now}        {ad_id}"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 Связаться с админом", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])

        await bot.send_message(CHANNEL_ID, text, reply_markup=kb, parse_mode="HTML")

    else:
        text = (
            f"{type_text}\n\n"
            f"🧿 <b>{row[1]}</b>\n"
            f"🔢 Кол-во: {row[2]}\n"
            f"⚙️ Состояние: {condition}\n"
            f"💰 Цена: {row[4]}\n"
            f"📞 {row[5]}"
            f"{desc_text}\n\n"
            f"🕒 {now}        {ad_id}"
        )

        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

    await callback.message.edit_text("✅ Одобрено")
    await callback.answer()


@dp.callback_query(F.data.startswith("reject_"))
async def reject_ad(callback: CallbackQuery):
    ad_id = callback.data.split("_", 1)[1]

    await callback.message.edit_text("❌ Отклонено")
    await callback.answer()

# =========================
# RUN
# =========================
async def archive_old_ads():
    while True:
        
        print("ARCHIVE CHECK RUN11")  
        
        conn = sqlite3.connect("ads.db")
        cursor = conn.cursor()

        now = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
        SELECT id, name, quantity, condition, price, created_at, channel_message_id
        FROM ads
        WHERE expires_at < ?
        AND archived = 0
        AND channel_message_id IS NOT NULL
        """, (now,))

        rows = cursor.fetchall()

        for row in rows:
            ad_id = row[0]

            try:
                text = (
                    f"🔒 <b>АРХИВНОЕ ОБЪЯВЛЕНИЕ</b>\n\n"
                    f"🧿 <b>{row[1]}</b>\n"
                    f"🔢 Кол-во: {row[2]}\n"
                    f"⚙️ Состояние: {row[3]}\n"
                    f"💰 Цена: {row[4]}\n\n"
                    f"📩 Связаться с администратором"
                )

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📩 Написать администратору",
                        url=f"https://t.me/{ADMIN_USERNAME}"
                    )]
                ])

                await bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=row[6],
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )

                cursor.execute("""
                UPDATE ads
                SET archived = 1
                WHERE id = ?
                """, (ad_id,))

                conn.commit()

            except Exception as e:
                print(f"Archive error {ad_id}: {e}")

        conn.close()

        await asyncio.sleep(3600)
        
async def main():
    print("БОТ СТАРТОВАЛ")
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(archive_old_ads())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
