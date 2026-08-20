import asyncio
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)


# =========================================================
# SOZLAMALAR
# =========================================================

TOKEN = "BOT_TOKENINGIZNI_BU_YERGA_YOZING"

# O'Z TELEGRAM IDINGIZNI YOZING
ADMIN_ID = 123456789


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    phone TEXT,
    status TEXT DEFAULT 'pending',
    workspace_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    table_number INTEGER NOT NULL,
    price_per_hour REAL NOT NULL,
    is_active INTEGER DEFAULT 0,
    start_time TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS active_extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    table_id INTEGER NOT NULL,
    extra_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    table_number INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    table_money REAL NOT NULL,
    extras_money REAL NOT NULL,
    total_money REAL NOT NULL
)
""")

# Eski bot bazasida workspace_id bo'lmasa qo'shamiz.
try:
    cursor.execute("ALTER TABLE users ADD COLUMN workspace_id INTEGER")
except sqlite3.OperationalError:
    pass

cursor.execute("UPDATE users SET workspace_id=user_id WHERE workspace_id IS NULL")
db.commit()

# Bog'langan foydalanuvchilar uchun tezkor workspace cache.
workspace_cache = {}
cursor.execute("SELECT user_id, COALESCE(workspace_id, user_id) FROM users")
for _uid, _workspace in cursor.fetchall():
    workspace_cache[_uid] = _workspace

def workspace_id(user_id):
    return workspace_cache.get(user_id, user_id)


# SQL ichidan workspace_id(user_id) ni chaqirish uchun.
db.create_function("workspace", 1, workspace_id)



# =========================================================
# BOT
# =========================================================

bot = Bot(TOKEN)
dp = Dispatcher()

user_state = {}


# =========================================================
# ASOSIY MENU
# =========================================================

def main_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🪑 Stol qo‘shish"),
                KeyboardButton(text="➖ Stol ayirish")
            ],
            [
                KeyboardButton(text="🪑 Stollar"),
                KeyboardButton(text="▶️ Vaqtni boshlash")
            ],
            [
                KeyboardButton(text="⏹ Vaqtni to‘xtatish"),
                KeyboardButton(text="📊 Hisobot")
            ],
            [
                KeyboardButton(text="🥤 Qo‘shimcha qo‘shish"),
                KeyboardButton(text="📦 Qo‘shimchalar")
            ],
            [
                KeyboardButton(text="🔗 Ulanish"),
                KeyboardButton(text="📅 Kunlik hisobot")
            ]
        ],
        resize_keyboard=True
    )


# =========================================================
# ORQAGA
# ENG MUHIM HANDLER
# =========================================================

@dp.message(F.text == "🔙 Orqaga")
async def back_button(message: Message):

    user_id = message.from_user.id

    # Hamma vaqtinchalik holatni o'chirish
    user_state.pop(user_id, None)

    await message.answer(
        "🏠 Asosiy menyu:",
        reply_markup=main_keyboard()
    )


# =========================================================
# ULanish / WORKSPACE
# =========================================================

@dp.message(F.text == "🔗 Ulanish")
async def connect_start(message: Message):
    user_id = message.from_user.id
    user_state[user_id] = {"action": "link_user_id"}
    await message.answer(
        "🔗 Ulanish\n\n"
        "Ulanmoqchi bo‘lgan foydalanuvchining Telegram ID sini yuboring.\n\n"
        "Masalan: 123456789\n\n"
        "🔙 Orqaga — bekor qilish"
    )


@dp.message(
    lambda m: m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "link_user_id"
)
async def connect_user_id(message: Message):
    requester_id = message.from_user.id

    try:
        target_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("❌ Telegram ID faqat raqamlardan iborat bo‘ladi.")
        return

    if target_id == requester_id:
        await message.answer("❌ O‘zingiz bilan ulana olmaysiz.")
        return

    cursor.execute("SELECT name, status, COALESCE(workspace_id, user_id) FROM users WHERE user_id=?", (target_id,))
    target = cursor.fetchone()

    if not target:
        await message.answer("❌ Bu ID bilan foydalanuvchi topilmadi.")
        return

    target_name, target_status, target_workspace = target

    if target_status != "approved":
        await message.answer("❌ Bu foydalanuvchi hali botda tasdiqlanmagan.")
        return

    requester_workspace = workspace_id(requester_id)

    if target_workspace == requester_workspace:
        await message.answer("✅ Sizlar allaqachon ulangan ekansiz.")
        user_state.pop(requester_id, None)
        return

    # Bir xil stol raqami bo‘lsa, birlashtirish noaniq bo‘lib qolmasligi uchun rad qilamiz.
    cursor.execute("SELECT table_number FROM tables WHERE user_id=?", (requester_workspace,))
    own_tables = {r[0] for r in cursor.fetchall()}
    cursor.execute("SELECT table_number FROM tables WHERE user_id=?", (target_workspace,))
    target_tables = {r[0] for r in cursor.fetchall()}
    duplicates = own_tables & target_tables

    if duplicates:
        nums = ", ".join(map(str, sorted(duplicates)))
        await message.answer(
            f"❌ Ulanib bo‘lmaydi. Ikkalangizda ham bir xil stol raqami bor: {nums}.\n"
            "Avval ulardan birini o‘zgartiring yoki o‘chiring."
        )
        return

    user_state.pop(requester_id, None)

    await bot.send_message(
        target_id,
        "🔗 ULanish so‘rovi\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"🆔 ID: {requester_id}\n\n"
        "Bu foydalanuvchi bilan qo‘shilasizmi?\n\n"
        "Ulangandan keyin stollar, narxlar, qo‘shimchalar va hisobotlar umumiy bo‘ladi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ HA", callback_data=f"link_yes:{requester_id}"),
                InlineKeyboardButton(text="❌ YO‘Q", callback_data=f"link_no:{requester_id}")
            ]
        ])
    )

    await message.answer("📨 So‘rov yuborildi. Ikkinchi foydalanuvchi tasdiqlashini kuting.", reply_markup=main_keyboard())


@dp.callback_query(F.data.startswith("link_yes:"))
async def connect_accept(callback: CallbackQuery):
    target_id = callback.from_user.id
    requester_id = int(callback.data.split(":")[1])

    cursor.execute("SELECT COALESCE(workspace_id, user_id) FROM users WHERE user_id=?", (target_id,))
    target_row = cursor.fetchone()
    cursor.execute("SELECT COALESCE(workspace_id, user_id) FROM users WHERE user_id=?", (requester_id,))
    requester_row = cursor.fetchone()

    if not target_row or not requester_row:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    target_workspace = target_row[0]
    requester_workspace = requester_row[0]

    if target_workspace == requester_workspace:
        await callback.answer("Sizlar allaqachon ulangan.")
        return

    # Ikkala workspace ma'lumotlarini requester workspace'iga birlashtiramiz.
    cursor.execute("UPDATE tables SET user_id=? WHERE user_id=?", (requester_workspace, target_workspace))
    cursor.execute("UPDATE extras SET user_id=? WHERE user_id=?", (requester_workspace, target_workspace))
    cursor.execute("UPDATE active_extras SET user_id=? WHERE user_id=?", (requester_workspace, target_workspace))
    cursor.execute("UPDATE sessions SET user_id=? WHERE user_id=?", (requester_workspace, target_workspace))
    cursor.execute("UPDATE users SET workspace_id=? WHERE user_id IN (?, ?)", (requester_workspace, requester_id, target_id))
    db.commit()

    workspace_cache[requester_id] = requester_workspace
    workspace_cache[target_id] = requester_workspace

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ ULANDI"
    )

    await bot.send_message(
        requester_id,
        "🎉 Ulanish tasdiqlandi!\n\n"
        "Endi stollar, narxlar, qo‘shimchalar va hisobotlar ikkalangizda ham umumiy.",
        reply_markup=main_keyboard()
    )

    await callback.answer("Ulanish tasdiqlandi ✅")


@dp.callback_query(F.data.startswith("link_no:"))
async def connect_reject(callback: CallbackQuery):
    requester_id = int(callback.data.split(":")[1])
    target_id = callback.from_user.id

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ RAD ETILDI"
    )

    await bot.send_message(
        requester_id,
        "❌ Ulanish so‘rovingiz rad etildi."
    )

    await callback.answer("So‘rov rad etildi ❌")


# =========================================================
# TELEFON TUGMASI
# =========================================================

def phone_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📞 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# ADMIN INLINE TUGMALARI
# =========================================================

def approval_keyboard(user_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ HA",
                    callback_data=f"approve:{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ YO‘Q",
                    callback_data=f"reject:{user_id}"
                )
            ]
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    user_id = message.from_user.id

    cursor.execute(
        "SELECT status FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    # BLOKLANGAN
    if result and result[0] == "blocked":

        await message.answer(
            "🚫 Siz botdan foydalanish uchun bloklangansiz."
        )
        return

    # TASDIQLANGAN
    if result and result[0] == "approved":

        await message.answer(
            "🏠 Asosiy menyu:",
            reply_markup=main_keyboard()
        )
        return

    # PENDING
    if result and result[0] == "pending":

        await message.answer(
            "⏳ Sizning so‘rovingiz admin tomonidan "
            "ko‘rib chiqilmoqda.\n\n"
            "Iltimos, kuting."
        )
        return

    # YANGI USER

    cursor.execute("""
        INSERT INTO users
        (user_id, name, username, status, workspace_id)
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        user_id,
        message.from_user.full_name,
        message.from_user.username,
        user_id
    ))

    db.commit()
    workspace_cache[user_id] = user_id

    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        "Botdan foydalanish uchun telefon "
        "raqamingizni yuboring.",
        reply_markup=phone_keyboard()
    )


# =========================================================
# TELEFON QABUL QILISH
# =========================================================

@dp.message(F.contact)
async def receive_contact(message: Message):

    user_id = message.from_user.id

    if message.contact.user_id != user_id:

        await message.answer(
            "❌ Iltimos, o‘zingizning telefon raqamingizni yuboring."
        )
        return

    phone = message.contact.phone_number
    name = message.from_user.full_name
    username = message.from_user.username

    cursor.execute("""
        UPDATE users
        SET name=?, username=?, phone=?, status='pending'
        WHERE user_id=?
    """, (
        name,
        username,
        phone,
        user_id
    ))

    db.commit()

    username_text = (
        f"@{username}"
        if username
        else "Username yo‘q"
    )

    admin_text = (
        "🔔 YANGI FOYDALANUVCHI\n\n"
        f"👤 Ism: {name}\n"
        f"🔗 Username: {username_text}\n"
        f"🆔 ID: {user_id}\n"
        f"📞 Telefon: {phone}\n\n"
        "Bu odamni taniysizmi?"
    )

    await bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=approval_keyboard(user_id)
    )

    await message.answer(
        "✅ Ma'lumotlaringiz adminga yuborildi.\n\n"
        "⏳ Admin tasdiqlashini kuting.",
        reply_markup=ReplyKeyboardRemove()
    )


# =========================================================
# ADMIN — HA
# =========================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_user(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Siz admin emassiz.",
            show_alert=True
        )
        return

    user_id = int(
        callback.data.split(":")[1]
    )

    cursor.execute("""
        UPDATE users
        SET status='approved'
        WHERE user_id=?
    """, (user_id,))

    db.commit()

    await callback.message.edit_text(
        callback.message.text +
        "\n\n✅ NATIJA: TASDIQLANDI"
    )

    await bot.send_message(
        user_id,
        "🎉 Siz tasdiqlandingiz!\n\n"
        "Endi botdan foydalanishingiz mumkin.",
        reply_markup=main_keyboard()
    )

    await callback.answer(
        "Foydalanuvchi tasdiqlandi ✅"
    )


# =========================================================
# ADMIN — YO‘Q
# =========================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_user(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Siz admin emassiz.",
            show_alert=True
        )
        return

    user_id = int(
        callback.data.split(":")[1]
    )

    cursor.execute("""
        UPDATE users
        SET status='blocked'
        WHERE user_id=?
    """, (user_id,))

    db.commit()

    await callback.message.edit_text(
        callback.message.text +
        "\n\n🚫 NATIJA: BLOKLANDI"
    )

    await bot.send_message(
        user_id,
        "🚫 Siz botdan foydalanish uchun bloklandingiz.",
        reply_markup=ReplyKeyboardRemove()
    )

    await callback.answer(
        "Foydalanuvchi bloklandi ❌"
    )


# =========================================================
# STOL QO‘SHISH
# =========================================================

@dp.message(F.text == "🪑 Stol qo‘shish")
async def add_table(message: Message):

    user_state[message.from_user.id] = {
        "action": "table_number"
    }

    await message.answer(
        "🪑 Stol raqamini kiriting.\n\n"
        "Masalan: 5\n\n"
        "🔙 Orqaga — bekor qilish"
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id]["action"] == "table_number"
)
async def table_number(message: Message):

    user_id = message.from_user.id

    try:
        number = int(message.text)

        if number <= 0:
            raise ValueError

    except ValueError:

        await message.answer(
            "❌ Stol raqamini to‘g‘ri kiriting."
        )
        return

    cursor.execute("""
        SELECT id
        FROM tables
        WHERE user_id=workspace(?) AND table_number=?
    """, (
        user_id,
        number
    ))

    if cursor.fetchone():

        await message.answer(
            "❌ Bu stol allaqachon mavjud."
        )
        return

    user_state[user_id] = {
        "action": "table_price",
        "table_number": number
    }

    await message.answer(
        f"🪑 Stol №{number}\n\n"
        "💰 1 soatlik narxini kiriting.\n\n"
        "Masalan: 10000"
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id]["action"] == "table_price"
)
async def table_price(message: Message):

    user_id = message.from_user.id

    try:
        price = float(message.text)

        if price <= 0:
            raise ValueError

    except ValueError:

        await message.answer(
            "❌ Narxni to‘g‘ri kiriting."
        )
        return

    number = user_state[user_id]["table_number"]

    cursor.execute("""
        INSERT INTO tables
        (user_id, table_number, price_per_hour)
        VALUES (workspace(?), ?, ?)
    """, (
        user_id,
        number,
        price
    ))

    db.commit()

    user_state.pop(user_id)

    await message.answer(
        f"✅ Stol qo‘shildi!\n\n"
        f"🪑 Stol №{number}\n"
        f"💰 1 soat: {price:.0f} so‘m",
        reply_markup=main_keyboard()
    )


# =========================================================
# STOLLAR
# =========================================================

@dp.message(F.text == "🪑 Stollar")
async def show_tables(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT table_number,
               price_per_hour,
               is_active,
               start_time
        FROM tables
        WHERE user_id=workspace(?)
        ORDER BY table_number
    """, (user_id,))

    tables = cursor.fetchall()

    if not tables:

        await message.answer(
            "❌ Sizda hali stol mavjud emas.",
            reply_markup=main_keyboard()
        )
        return

    text = "🪑 STOLLAR\n\n"

    for number, price, active, start_time in tables:

        if active:

            start = datetime.fromisoformat(start_time)
            now = datetime.now()

            seconds = int(
                (now - start).total_seconds()
            )

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            money = seconds / 3600 * price

            text += (
                f"🟢 Stol №{number}\n"
                f"⏱ {hours} soat "
                f"{minutes} daqiqa "
                f"{secs} soniya\n"
                f"💰 {money:.0f} so‘m\n\n"
            )

        else:

            text += (
                f"⚪ Stol №{number}\n"
                f"💰 1 soat: {price:.0f} so‘m\n"
                f"Holati: Bo‘sh\n\n"
            )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# VAQT BOSHLASH
# =========================================================

@dp.message(F.text == "▶️ Vaqtni boshlash")
async def start_timer(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, table_number
        FROM tables
        WHERE user_id=workspace(?)
        ORDER BY table_number
    """, (user_id,))

    tables = cursor.fetchall()

    if not tables:

        await message.answer(
            "❌ Avval stol qo‘shing."
        )
        return

    buttons = []

    for table_id, number in tables:

        buttons.append([
            KeyboardButton(
                text=f"🪑 Stol {number}"
            )
        ])

    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    user_state[user_id] = {
        "action": "start_table"
    }

    await message.answer(
        "▶️ Qaysi stolning vaqtini boshlaymiz?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id]["action"] == "start_table"
)
async def start_selected_table(message: Message):

    user_id = message.from_user.id

    if not message.text.startswith("🪑 Stol "):

        await message.answer(
            "❌ Stolni tugmadan tanlang."
        )
        return

    number = int(
        message.text.replace("🪑 Stol ", "")
    )

    cursor.execute("""
        SELECT id,
               price_per_hour,
               is_active
        FROM tables
        WHERE user_id=workspace(?)
        AND table_number=?
    """, (
        user_id,
        number
    ))

    result = cursor.fetchone()

    if not result:

        await message.answer(
            "❌ Stol topilmadi."
        )
        return

    table_id, price, active = result

    if active:

        await message.answer(
            "⚠️ Bu stol allaqachon ishlayapti."
        )
        return

    now = datetime.now()

    cursor.execute("""
        UPDATE tables
        SET is_active=1,
            start_time=?
        WHERE id=?
    """, (
        now.isoformat(),
        table_id
    ))

    db.commit()

    user_state.pop(user_id)

    await message.answer(
        f"▶️ VAQT BOSHLANDI!\n\n"
        f"🪑 Stol №{number}\n"
        f"💰 1 soat: {price:.0f} so‘m\n"
        f"🕐 Boshlangan vaqt: "
        f"{now.strftime('%H:%M:%S')}\n\n"
        f"⏱ Hisoblash boshlandi.",
        reply_markup=main_keyboard()
    )


# =========================================================
# VAQT TO‘XTATISH
# =========================================================

@dp.message(F.text == "⏹ Vaqtni to‘xtatish")
async def stop_timer(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id,
               table_number
        FROM tables
        WHERE user_id=workspace(?)
        AND is_active=1
    """, (user_id,))

    tables = cursor.fetchall()

    if not tables:

        await message.answer(
            "❌ Hozir ishlayotgan stol yo‘q."
        )
        return

    buttons = []

    for table_id, number in tables:

        buttons.append([
            KeyboardButton(
                text=f"🛑 Stol {number}"
            )
        ])

    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    user_state[user_id] = {
        "action": "stop_table"
    }

    await message.answer(
        "⏹ Qaysi stolni to‘xtatamiz?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id]["action"] == "stop_table"
)
async def stop_selected_table(message: Message):

    user_id = message.from_user.id

    if not message.text.startswith("🛑 Stol "):

        await message.answer(
            "❌ Stolni tugmadan tanlang."
        )
        return

    number = int(
        message.text.replace("🛑 Stol ", "")
    )

    cursor.execute("""
        SELECT id,
               price_per_hour,
               start_time
        FROM tables
        WHERE user_id=workspace(?)
        AND table_number=?
        AND is_active=1
    """, (
        user_id,
        number
    ))

    result = cursor.fetchone()

    if not result:

        await message.answer(
            "❌ Ishlayotgan stol topilmadi."
        )
        return

    table_id, price, start_time = result

    start = datetime.fromisoformat(start_time)
    now = datetime.now()

    seconds = max(
        0,
        int((now - start).total_seconds())
    )

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    table_money = seconds / 3600 * price

    cursor.execute("""
        UPDATE tables
        SET is_active=0,
            start_time=NULL
        WHERE id=?
    """, (table_id,))

    db.commit()

    user_state[user_id] = {
        "action": "extras_question",
        "table_id": table_id,
        "table_number": number,
        "table_money": table_money,
        "start_time": start_time,
        "hours": hours,
        "minutes": minutes,
        "seconds": secs
    }

    await message.answer(
        f"⏹ VAQT TO‘XTATILDI!\n\n"
        f"🪑 Stol №{number}\n"
        f"⏱ {hours} soat "
        f"{minutes} daqiqa "
        f"{secs} soniya\n"
        f"💰 Stol: {table_money:.0f} so‘m\n\n"
        f"🥤 Qo‘shimcha bormi?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="✅ Ha"),
                    KeyboardButton(text="❌ Yo‘q")
                ],
                [
                    KeyboardButton(text="🔙 Orqaga")
                ]
            ],
            resize_keyboard=True
        )
    )


# =========================================================
# QO‘SHIMCHA YO‘Q
# =========================================================

@dp.message(
    lambda m:
    m.from_user.id in user_state
    and m.text == "❌ Yo‘q"
    and m.text != "❌ Tugatish"
)
async def no_extras(message: Message):

    user_id = message.from_user.id

    if user_state.get(user_id, {}).get("action") != "extras_question":
        return

    data = user_state[user_id]

    await finish_bill(
        message,
        data,
        {}
    )

    user_state.pop(user_id, None)


# =========================================================
# QO‘SHIMCHA HA
# =========================================================

@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "extras_question"
    and m.text == "✅ Ha"
)
async def yes_extras(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id
        FROM extras
        WHERE user_id=workspace(?)
    """, (user_id,))

    if not cursor.fetchone():

        await message.answer(
            "❌ Sizda qo‘shimcha mahsulot yo‘q.\n\n"
            "Avval 🥤 Qo‘shimcha qo‘shish orqali "
            "mahsulot yarating.",
            reply_markup=main_keyboard()
        )

        user_state.pop(user_id, None)

        return

    user_state[user_id]["action"] = "choose_extra"

    await message.answer(
        "🥤 Qo‘shimchani tanlang:",
        reply_markup=extras_keyboard(user_id)
    )


# =========================================================
# QO‘SHIMCHA KEYBOARD
# =========================================================

def extras_keyboard(user_id):

    cursor.execute("""
        SELECT id,
               name,
               price
        FROM extras
        WHERE user_id=workspace(?)
        ORDER BY id
    """, (user_id,))

    extras = cursor.fetchall()

    buttons = []

    for extra_id, name, price in extras:

        buttons.append([
            KeyboardButton(
                text=f"🥤 {name} — {price:.0f} so‘m"
            )
        ])

    buttons.append([
        KeyboardButton(text="❌ Tugatish")
    ])

    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# =========================================================
# QO‘SHIMCHA TANLASH
# =========================================================

@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "choose_extra"
)
async def choose_extra(message: Message):

    user_id = message.from_user.id

    if message.text == "❌ Tugatish":

        data = user_state[user_id]

        cursor.execute("""
            SELECT extra_id,
                   quantity
            FROM active_extras
            WHERE user_id=workspace(?)
            AND table_id=?
        """, (
            user_id,
            data["table_id"]
        ))

        rows = cursor.fetchall()

        extras = {
            extra_id: quantity
            for extra_id, quantity in rows
        }

        await finish_bill(
            message,
            data,
            extras
        )

        cursor.execute("""
            DELETE FROM active_extras
            WHERE user_id=workspace(?)
            AND table_id=?
        """, (
            user_id,
            data["table_id"]
        ))

        db.commit()

        user_state.pop(user_id, None)

        return

    if not message.text.startswith("🥤 "):

        await message.answer(
            "❌ Qo‘shimchani tugmadan tanlang."
        )
        return

    try:

        product = message.text.replace(
            "🥤 ",
            ""
        )

        name, price = product.rsplit(
            " — ",
            1
        )

    except ValueError:

        await message.answer(
            "❌ Xatolik."
        )
        return

    cursor.execute("""
        SELECT id
        FROM extras
        WHERE user_id=workspace(?)
        AND name=?
    """, (
        user_id,
        name
    ))

    result = cursor.fetchone()

    if not result:

        await message.answer(
            "❌ Mahsulot topilmadi."
        )
        return

    user_state[user_id]["selected_extra"] = result[0]
    user_state[user_id]["action"] = "extra_quantity"

    await message.answer(
        f"🥤 {name}\n\n"
        "Nechta?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="1"),
                    KeyboardButton(text="2"),
                    KeyboardButton(text="3")
                ],
                [
                    KeyboardButton(text="4"),
                    KeyboardButton(text="5"),
                    KeyboardButton(text="10")
                ],
                [
                    KeyboardButton(text="🔙 Orqaga")
                ]
            ],
            resize_keyboard=True
        )
    )


# =========================================================
# QO‘SHIMCHA MIQDORI
# =========================================================

@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "extra_quantity"
)
async def extra_quantity(message: Message):

    user_id = message.from_user.id

    try:

        quantity = int(message.text)

        if quantity <= 0:
            raise ValueError

    except ValueError:

        await message.answer(
            "❌ Miqdorni tugmalardan tanlang."
        )
        return

    data = user_state[user_id]

    table_id = data["table_id"]
    extra_id = data["selected_extra"]

    cursor.execute("""
        SELECT id
        FROM active_extras
        WHERE user_id=workspace(?)
        AND table_id=?
        AND extra_id=?
    """, (
        user_id,
        table_id,
        extra_id
    ))

    result = cursor.fetchone()

    if result:

        cursor.execute("""
            UPDATE active_extras
            SET quantity=quantity+?
            WHERE id=?
        """, (
            quantity,
            result[0]
        ))

    else:

        cursor.execute("""
            INSERT INTO active_extras
            (user_id, table_id, extra_id, quantity)
            VALUES (workspace(?), ?, ?, ?)
        """, (
            user_id,
            table_id,
            extra_id,
            quantity
        ))

    db.commit()

    user_state[user_id]["action"] = "choose_extra"

    user_state[user_id].pop(
        "selected_extra",
        None
    )

    await message.answer(
        "✅ Qo‘shimcha qo‘shildi!\n\n"
        "Yana qo‘shimcha tanlang yoki "
        "❌ Tugatish ni bosing.",
        reply_markup=extras_keyboard(user_id)
    )


# =========================================================
# YAKUNIY HISOB
# =========================================================

async def finish_bill(
    message,
    data,
    extras_data
):

    user_id = message.from_user.id

    total = data["table_money"]
    extras_money = 0

    text = (
        "🧾 YAKUNIY HISOB\n\n"
        f"🪑 Stol №{data['table_number']}\n"
        f"⏱ {data['hours']} soat "
        f"{data['minutes']} daqiqa "
        f"{data['seconds']} soniya\n"
        f"💰 Stol: "
        f"{data['table_money']:.0f} so‘m\n"
    )

    for extra_id, quantity in extras_data.items():

        cursor.execute("""
            SELECT name,
                   price
            FROM extras
            WHERE id=?
            AND user_id=?
        """, (
            extra_id,
            user_id
        ))

        result = cursor.fetchone()

        if not result:
            continue

        name, price = result

        money = price * quantity

        total += money
        extras_money += money

        text += (
            f"🥤 {name} × {quantity}: "
            f"{money:.0f} so‘m\n"
        )

    text += (
        "\n"
        "━━━━━━━━━━━━━━\n"
        f"💵 JAMI: {total:.0f} so‘m\n"
        "━━━━━━━━━━━━━━\n\n"
        "✅ Stol bo‘shatildi."
    )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# QO‘SHIMCHA QO‘SHISH
# =========================================================

@dp.message(F.text == "🥤 Qo‘shimcha qo‘shish")
async def create_extra(message: Message):

    user_state[message.from_user.id] = {
        "action": "extra_name"
    }

    await message.answer(
        "🥤 Qo‘shimcha nomini kiriting.\n\n"
        "Masalan: Suv\n\n"
        "🔙 Orqaga — bekor qilish"
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "extra_name"
)
async def extra_name(message: Message):

    user_id = message.from_user.id

    name = message.text.strip()

    if not name:

        await message.answer(
            "❌ Nom kiriting."
        )
        return

    user_state[user_id] = {
        "action": "extra_price",
        "name": name
    }

    await message.answer(
        f"🥤 {name}\n\n"
        "💰 Narxini kiriting:"
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "extra_price"
)
async def extra_price(message: Message):

    user_id = message.from_user.id

    try:

        price = float(message.text)

        if price <= 0:
            raise ValueError

    except ValueError:

        await message.answer(
            "❌ Narxni to‘g‘ri kiriting."
        )
        return

    name = user_state[user_id]["name"]

    cursor.execute("""
        INSERT INTO extras
        (user_id, name, price)
        VALUES (workspace(?), ?, ?)
    """, (
        user_id,
        name,
        price
    ))

    db.commit()

    user_state.pop(user_id, None)

    await message.answer(
        f"✅ Qo‘shimcha yaratildi!\n\n"
        f"🥤 {name}\n"
        f"💰 {price:.0f} so‘m",
        reply_markup=main_keyboard()
    )


# =========================================================
# QO‘SHIMCHALAR
# =========================================================

@dp.message(F.text == "📦 Qo‘shimchalar")
async def show_extras(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT name,
               price
        FROM extras
        WHERE user_id=workspace(?)
        ORDER BY id
    """, (user_id,))

    extras = cursor.fetchall()

    if not extras:

        await message.answer(
            "❌ Qo‘shimchalar mavjud emas.",
            reply_markup=main_keyboard()
        )
        return

    text = "📦 QO‘SHIMCHALAR\n\n"

    for name, price in extras:

        text += (
            f"🥤 {name} — "
            f"{price:.0f} so‘m\n"
        )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# STOL AYIRISH
# =========================================================

@dp.message(F.text == "➖ Stol ayirish")
async def remove_table(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id,
               table_number
        FROM tables
        WHERE user_id=workspace(?)
        ORDER BY table_number
    """, (user_id,))

    tables = cursor.fetchall()

    if not tables:

        await message.answer(
            "❌ Stol mavjud emas."
        )
        return

    buttons = []

    for table_id, number in tables:

        buttons.append([
            KeyboardButton(
                text=f"❌ Stol {number}"
            )
        ])

    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    user_state[user_id] = {
        "action": "delete_table"
    }

    await message.answer(
        "➖ Qaysi stolni o‘chirasiz?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "delete_table"
)
async def delete_table(message: Message):

    user_id = message.from_user.id

    if not message.text.startswith("❌ Stol "):

        await message.answer(
            "❌ Stolni tanlang."
        )
        return

    number = int(
        message.text.replace(
            "❌ Stol ",
            ""
        )
    )

    cursor.execute("""
        SELECT id,
               is_active
        FROM tables
        WHERE user_id=workspace(?)
        AND table_number=?
    """, (
        user_id,
        number
    ))

    result = cursor.fetchone()

    if not result:

        await message.answer(
            "❌ Stol topilmadi."
        )
        return

    table_id, active = result

    if active:

        await message.answer(
            "⚠️ Stol hozir ishlayapti.\n"
            "Avval vaqtni to‘xtating."
        )
        return

    cursor.execute(
        "DELETE FROM tables WHERE id=?",
        (table_id,)
    )

    db.commit()

    user_state.pop(user_id, None)

    await message.answer(
        f"✅ Stol №{number} o‘chirildi.",
        reply_markup=main_keyboard()
    )


# =========================================================
# KUNLIK HISOBOT
# =========================================================

@dp.message(F.text == "📅 Kunlik hisobot")
async def daily_report(message: Message):

    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    owner = workspace_id(user_id)

    cursor.execute("""
        SELECT COUNT(*),
               COALESCE(SUM(duration_seconds), 0),
               COALESCE(SUM(table_money), 0),
               COALESCE(SUM(extras_money), 0),
               COALESCE(SUM(total_money), 0)
        FROM sessions
        WHERE user_id=?
        AND substr(end_time, 1, 10)=?
    """, (owner, today))

    count, seconds, table_money, extras_money, total = cursor.fetchone()

    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60

    cursor.execute("""
        SELECT table_number,
               COUNT(*),
               COALESCE(SUM(duration_seconds), 0),
               COALESCE(SUM(total_money), 0)
        FROM sessions
        WHERE user_id=?
        AND substr(end_time, 1, 10)=?
        GROUP BY table_number
        ORDER BY table_number
    """, (owner, today))

    rows = cursor.fetchall()

    text = (
        "📅 KUNLIK HISOBOT\n\n"
        f"🪑 Ishlatilgan stol/sessiyalar: {count} ta\n"
        f"⏱ Jami vaqt: {hours} soat {minutes} daqiqa {secs} soniya\n"
        f"🪑 Stol xizmatlari: {table_money:.0f} so‘m\n"
        f"🥤 Qo‘shimchalar: {extras_money:.0f} so‘m\n"
        f"💵 JAMI DAROMAD: {total:.0f} so‘m\n"
    )

    if rows:
        text += "\n📋 STOLLAR BO‘YICHA:\n"
        for number, sessions_count, row_seconds, row_total in rows:
            rh = int(row_seconds) // 3600
            rm = (int(row_seconds) % 3600) // 60
            rs = int(row_seconds) % 60
            text += (
                f"\n🪑 Stol №{number}: {sessions_count} marta\n"
                f"⏱ {rh} soat {rm} daqiqa {rs} soniya\n"
                f"💰 {row_total:.0f} so‘m\n"
            )

    text += "\n━━━━━━━━━━━━━━\n"
    text += f"💰 UMUMIY: {total:.0f} so‘m"

    await message.answer(text, reply_markup=main_keyboard())


# Eski 📊 Hisobot tugmasi ham saqlanadi.
@dp.message(F.text == "📊 Hisobot")
async def report(message: Message):
    await daily_report(message)


# =========================================================
# ISHGA TUSHIRISH
# =========================================================

async def main():

    print("BOT ISHLAYAPTI...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
