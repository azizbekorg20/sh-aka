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
ADMIN_ID =8437797764


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

db.commit()


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
        WHERE user_id=? AND table_number=?
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
        VALUES (?, ?, ?)
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
        WHERE user_id=?
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
        WHERE user_id=?
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
        WHERE user_id=?
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
        WHERE user_id=?
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
        WHERE user_id=?
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
        WHERE user_id=?
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
        WHERE user_id=?
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
            WHERE user_id=?
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
            WHERE user_id=?
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
        WHERE user_id=?
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
        WHERE user_id=?
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
            VALUES (?, ?, ?, ?)
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
        VALUES (?, ?, ?)
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
        SELECT id, name, price
        FROM extras
        WHERE user_id=?
        ORDER BY id
    """, (user_id,))

    extras = cursor.fetchall()

    if not extras:

        await message.answer(
            "❌ Qo‘shimchalar mavjud emas.",
            reply_markup=main_keyboard()
        )
        return

    buttons = []

    for extra_id, name, price in extras:
        buttons.append([
            KeyboardButton(
                text=f"🥤 {name} — {price:.0f} so‘m"
            )
        ])

    buttons.append([
        KeyboardButton(text="➖ Qo‘shimcha ayirish")
    ])
    buttons.append([
        KeyboardButton(text="🔙 Orqaga")
    ])

    await message.answer(
        "📦 QO‘SHIMCHALAR\n\n"
        "Kerakli qo‘shimchani tanlang yoki ayirishni bosing:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )
    )


# =========================================================
# QO‘SHIMCHA AYIRISH
# =========================================================

@dp.message(F.text == "➖ Qo‘shimcha ayirish")
async def remove_extra(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, name, price
        FROM extras
        WHERE user_id=?
        ORDER BY id
    """, (user_id,))

    extras = cursor.fetchall()

    if not extras:
        await message.answer(
            "❌ O‘chirish uchun qo‘shimcha yo‘q.",
            reply_markup=main_keyboard()
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
        WHERE user_id=?
        AND name=?
    """, (user_id, name))

    result = cursor.fetchone()

    if not result:
        await message.answer("❌ Qo‘shimcha topilmadi.")
        return

    extra_id = result[0]

    # Shu qo‘shimcha faol hisoblarda bo‘lsa, ularni ham tozalaymiz.
    cursor.execute("""
        DELETE FROM active_extras
        WHERE user_id=?
        AND extra_id=?
    """, (user_id, extra_id))

    cursor.execute("""
        DELETE FROM extras
        WHERE id=?
        AND user_id=?
    """, (extra_id, user_id))

    db.commit()
    user_state.pop(user_id, None)

    await message.answer(
        f"✅ «{name}» qo‘shimchasi o‘chirildi.",
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
        WHERE user_id=?
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
        WHERE user_id=?
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
# HISOBOT
# =========================================================

@dp.message(F.text == "📊 Hisobot")
async def report(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT COUNT(*)
        FROM tables
        WHERE user_id=?
    """, (user_id,))

    tables = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM extras
        WHERE user_id=?
    """, (user_id,))

    extras = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tables
        WHERE user_id=?
        AND is_active=1
    """, (user_id,))

    active = cursor.fetchone()[0]

    await message.answer(
        "📊 HISOBOT\n\n"
        f"🪑 Jami stollar: {tables}\n"
        f"🟢 Ishlayotgan stollar: {active}\n"
        f"🥤 Qo‘shimchalar: {extras}",
        reply_markup=main_keyboard()
    )


# =========================================================
# ISHGA TUSHIRISH
# =========================================================

async def main():

    print("BOT ISHLAYAPTI...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())