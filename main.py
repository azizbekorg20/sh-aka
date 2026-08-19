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

TOKEN = "8866415165:AAEPrFMsv0KqjauBZiq3ZY-refC564JQC80"

# O'Z TELEGRAM IDINGIZNI YOZING
ADMIN_ID = 7822595706


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


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
    status TEXT DEFAULT 'pending'
)
""")

# Stollar endi UMUMIY (hech qanday user_id yo'q — hammaga bitta ro'yxat)
cursor.execute("""
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL UNIQUE,
    price_per_hour REAL NOT NULL,
    is_active INTEGER DEFAULT 0,
    start_time TEXT,
    started_by INTEGER
)
""")

# Qo'shimchalar ham UMUMIY
cursor.execute("""
CREATE TABLE IF NOT EXISTS extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL
)
""")

# Faol (hozirgi hisobdagi) qo'shimchalar — stolga bog'liq, userga emas
cursor.execute("""
CREATE TABLE IF NOT EXISTS active_extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL,
    extra_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL
)
""")

db.commit()


# =========================================================
# BOT
# =========================================================

bot = Bot(TOKEN)
dp = Dispatcher()

user_state = {}


# =========================================================
# ASOSIY MENYULAR
# =========================================================

def main_keyboard(user_id: int):
    """
    Admin — to'liq menyu (stol/qo'shimcha qo'shish-ayirish huquqi bilan).
    Oddiy foydalanuvchi — faqat ishlatish uchun menyu.
    """

    if is_admin(user_id):

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
                ]
            ],
            resize_keyboard=True
        )

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🪑 Stollar"),
                KeyboardButton(text="▶️ Vaqtni boshlash")
            ],
            [
                KeyboardButton(text="⏹ Vaqtni to‘xtatish"),
                KeyboardButton(text="📊 Hisobot")
            ],
            [
                KeyboardButton(text="📦 Qo‘shimchalar")
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
        reply_markup=main_keyboard(user_id)
    )


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

    # Admin har doim avtomatik tasdiqlangan hisoblanadi
    if is_admin(user_id):

        cursor.execute(
            "SELECT status FROM users WHERE user_id=?",
            (user_id,)
        )

        if not cursor.fetchone():

            cursor.execute("""
                INSERT INTO users
                (user_id, name, username, status)
                VALUES (?, ?, ?, 'approved')
            """, (
                user_id,
                message.from_user.full_name,
                message.from_user.username
            ))

            db.commit()

        else:

            cursor.execute(
                "UPDATE users SET status='approved' WHERE user_id=?",
                (user_id,)
            )
            db.commit()

        await message.answer(
            "👑 Xush kelibsiz, Admin!\n\n"
            "🏠 Asosiy menyu:",
            reply_markup=main_keyboard(user_id)
        )
        return

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
            reply_markup=main_keyboard(user_id)
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
        (user_id, name, username, status)
        VALUES (?, ?, ?, 'pending')
    """, (
        user_id,
        message.from_user.full_name,
        message.from_user.username
    ))

    db.commit()

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

    if not is_admin(callback.from_user.id):

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
        reply_markup=main_keyboard(user_id)
    )

    await callback.answer(
        "Foydalanuvchi tasdiqlandi ✅"
    )


# =========================================================
# ADMIN — YO‘Q
# =========================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_user(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):

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
# STOL QO‘SHISH (FAQAT ADMIN)
# =========================================================

@dp.message(F.text == "🪑 Stol qo‘shish")
async def add_table(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):

        await message.answer(
            "⛔ Bu funksiya faqat admin uchun."
        )
        return

    user_state[user_id] = {
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
        WHERE table_number=?
    """, (number,))

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
        (table_number, price_per_hour)
        VALUES (?, ?)
    """, (
        number,
        price
    ))

    db.commit()

    user_state.pop(user_id)

    await message.answer(
        f"✅ Stol qo‘shildi!\n\n"
        f"🪑 Stol №{number}\n"
        f"💰 1 soat: {price:.0f} so‘m",
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# STOLLAR (HAMMAGA UMUMIY RO‘YXAT)
# =========================================================

@dp.message(F.text == "🪑 Stollar")
async def show_tables(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT table_number,
               price_per_hour,
               is_active,
               start_time,
               started_by
        FROM tables
        ORDER BY table_number
    """)

    tables = cursor.fetchall()

    if not tables:

        await message.answer(
            "❌ Hozircha stol mavjud emas.",
            reply_markup=main_keyboard(user_id)
        )
        return

    text = "🪑 STOLLAR\n\n"

    for number, price, active, start_time, started_by in tables:

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

            cursor.execute(
                "SELECT name FROM users WHERE user_id=?",
                (started_by,)
            )
            starter = cursor.fetchone()
            starter_name = starter[0] if starter else "Noma'lum"

            text += (
                f"🟢 Stol №{number}\n"
                f"⏱ {hours} soat "
                f"{minutes} daqiqa "
                f"{secs} soniya\n"
                f"💰 {money:.0f} so‘m\n"
                f"👤 Boshlagan: {starter_name}\n\n"
            )

        else:

            text += (
                f"⚪ Stol №{number}\n"
                f"💰 1 soat: {price:.0f} so‘m\n"
                f"Holati: Bo‘sh\n\n"
            )

    await message.answer(
        text,
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# VAQT BOSHLASH (HAMMA TASDIQLANGAN FOYDALANUVCHI UCHUN)
# =========================================================

@dp.message(F.text == "▶️ Vaqtni boshlash")
async def start_timer(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, table_number
        FROM tables
        WHERE is_active=0
        ORDER BY table_number
    """)

    tables = cursor.fetchall()

    if not tables:

        await message.answer(
            "❌ Hozir bo‘sh stol yo‘q."
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
        WHERE table_number=?
    """, (number,))

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
            start_time=?,
            started_by=?
        WHERE id=?
    """, (
        now.isoformat(),
        user_id,
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
        reply_markup=main_keyboard(user_id)
    )

    # Boshqa hamma tasdiqlangan foydalanuvchilarga ham xabar berish (ixtiyoriy)
    cursor.execute(
        "SELECT user_id, name FROM users WHERE status='approved'"
    )
    starter_row = cursor.execute(
        "SELECT name FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    starter_name = starter_row[0] if starter_row else "Kimdir"

    for other_id, _name in cursor.execute(
        "SELECT user_id, name FROM users WHERE status='approved'"
    ).fetchall():

        if other_id == user_id:
            continue

        try:
            await bot.send_message(
                other_id,
                f"ℹ️ {starter_name} Stol №{number} vaqtini boshladi."
            )
        except Exception:
            pass


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
        WHERE is_active=1
    """)

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
        WHERE table_number=?
        AND is_active=1
    """, (number,))

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
            start_time=NULL,
            started_by=NULL
        WHERE id=?
    """, (table_id,))

    db.commit()

    user_state[user_id] = {
        "action": "extras_question",
        "table_id": table_id,
        "table_number": number,
        "table_money": table_money,
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

    cursor.execute("SELECT id FROM extras")

    if not cursor.fetchone():

        await message.answer(
            "❌ Hozircha qo‘shimcha mahsulot yo‘q."
            + (
                "\n\nAvval 🥤 Qo‘shimcha qo‘shish orqali "
                "mahsulot yarating."
                if is_admin(user_id)
                else ""
            ),
            reply_markup=main_keyboard(user_id)
        )

        user_state.pop(user_id, None)

        return

    user_state[user_id]["action"] = "choose_extra"

    await message.answer(
        "🥤 Qo‘shimchani tanlang:",
        reply_markup=extras_keyboard()
    )


# =========================================================
# QO‘SHIMCHA KEYBOARD (UMUMIY RO‘YXAT)
# =========================================================

def extras_keyboard():

    cursor.execute("""
        SELECT id,
               name,
               price
        FROM extras
        ORDER BY id
    """)

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
            WHERE table_id=?
        """, (data["table_id"],))

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
            WHERE table_id=?
        """, (data["table_id"],))

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
        WHERE name=?
    """, (name,))

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
        WHERE table_id=?
        AND extra_id=?
    """, (
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
            (table_id, extra_id, quantity)
            VALUES (?, ?, ?)
        """, (
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
        reply_markup=extras_keyboard()
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
        """, (extra_id,))

        result = cursor.fetchone()

        if not result:
            continue

        name, price = result

        money = price * quantity

        total += money

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
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# QO‘SHIMCHA QO‘SHISH (FAQAT ADMIN)
# =========================================================

@dp.message(F.text == "🥤 Qo‘shimcha qo‘shish")
async def create_extra(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):

        await message.answer(
            "⛔ Bu funksiya faqat admin uchun."
        )
        return

    user_state[user_id] = {
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
        (name, price)
        VALUES (?, ?)
    """, (
        name,
        price
    ))

    db.commit()

    user_state.pop(user_id, None)

    await message.answer(
        f"✅ Qo‘shimcha yaratildi!\n\n"
        f"🥤 {name}\n"
        f"💰 {price:.0f} so‘m",
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# QO‘SHIMCHALAR RO‘YXATI (HAMMAGA KO‘RINADI)
# =========================================================

@dp.message(F.text == "📦 Qo‘shimchalar")
async def show_extras(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, name, price
        FROM extras
        ORDER BY id
    """)

    extras = cursor.fetchall()

    if not extras:

        await message.answer(
            "❌ Qo‘shimchalar mavjud emas.",
            reply_markup=main_keyboard(user_id)
        )
        return

    buttons = []

    for extra_id, name, price in extras:
        buttons.append([
            KeyboardButton(
                text=f"🥤 {name} — {price:.0f} so‘m"
            )
        ])

    if is_admin(user_id):
        buttons.append([
            KeyboardButton(text="➖ Qo‘shimcha ayirish")
        ])

    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    await message.answer(
        "📦 QO‘SHIMCHALAR",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )
    )


# =========================================================
# QO‘SHIMCHA AYIRISH (FAQAT ADMIN)
# =========================================================

@dp.message(F.text == "➖ Qo‘shimcha ayirish")
async def remove_extra(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):

        await message.answer(
            "⛔ Bu funksiya faqat admin uchun."
        )
        return

    cursor.execute("""
        SELECT id, name, price
        FROM extras
        ORDER BY id
    """)

    extras = cursor.fetchall()

    if not extras:
        await message.answer(
            "❌ O‘chirish uchun qo‘shimcha yo‘q.",
            reply_markup=main_keyboard(user_id)
        )
        return

    buttons = []

    for extra_id, name, price in extras:
        buttons.append([
            KeyboardButton(
                text=f"❌ {name} — {price:.0f} so‘m"
            )
        ])

    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    user_state[user_id] = {
        "action": "delete_extra"
    }

    await message.answer(
        "➖ Qaysi qo‘shimchani o‘chirasiz?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )
    )


@dp.message(
    lambda m:
    m.from_user.id in user_state
    and user_state[m.from_user.id].get("action") == "delete_extra"
)
async def delete_extra(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return

    if not message.text.startswith("❌ "):
        await message.answer(
            "❌ Qo‘shimchani tugmadan tanlang."
        )
        return

    try:
        product = message.text.replace("❌ ", "", 1)
        name = product.rsplit(" — ", 1)[0]
    except ValueError:
        await message.answer("❌ Qo‘shimchani aniqlab bo‘lmadi.")
        return

    cursor.execute("""
        SELECT id
        FROM extras
        WHERE name=?
    """, (name,))

    result = cursor.fetchone()

    if not result:
        await message.answer("❌ Qo‘shimcha topilmadi.")
        return

    extra_id = result[0]

    # Shu qo‘shimcha faol hisoblarda bo‘lsa, ularni ham tozalaymiz.
    cursor.execute("""
        DELETE FROM active_extras
        WHERE extra_id=?
    """, (extra_id,))

    cursor.execute("""
        DELETE FROM extras
        WHERE id=?
    """, (extra_id,))

    db.commit()
    user_state.pop(user_id, None)

    await message.answer(
        f"✅ «{name}» qo‘shimchasi o‘chirildi.",
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# STOL AYIRISH (FAQAT ADMIN)
# =========================================================

@dp.message(F.text == "➖ Stol ayirish")
async def remove_table(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):

        await message.answer(
            "⛔ Bu funksiya faqat admin uchun."
        )
        return

    cursor.execute("""
        SELECT id,
               table_number
        FROM tables
        ORDER BY table_number
    """)

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

    if not is_admin(user_id):
        return

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
        WHERE table_number=?
    """, (number,))

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
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# HISOBOT (UMUMIY, HAMMAGA)
# =========================================================

@dp.message(F.text == "📊 Hisobot")
async def report(message: Message):

    user_id = message.from_user.id

    cursor.execute("SELECT COUNT(*) FROM tables")
    tables = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM extras")
    extras = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tables WHERE is_active=1")
    active = cursor.fetchone()[0]

    await message.answer(
        "📊 HISOBOT\n\n"
        f"🪑 Jami stollar: {tables}\n"
        f"🟢 Ishlayotgan stollar: {active}\n"
        f"🥤 Qo‘shimchalar: {extras}",
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# ISHGA TUSHIRISH
# =========================================================

async def main():

    print("BOT ISHLAYAPTI...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
