from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Reklama haqida")],
        [KeyboardButton(text="ℹ️ Ma'lumot")],
        [KeyboardButton(text="❓ Yordam")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="👥 Foydalanuvchilar")],
        [KeyboardButton(text="🔊 Broadcast")],
        [KeyboardButton(text="➕ Funnel yaratish")],
        [KeyboardButton(text="📂 Funnel ro'yxati")]
    ],
    resize_keyboard=True
)