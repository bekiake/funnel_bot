from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Reklama haqida")],
        [KeyboardButton(text="💎 Premium obuna")],
        [KeyboardButton(text="ℹ️ Ma'lumot")],
        [KeyboardButton(text="❓ Yordam")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👥 Foydalanuvchilar")],
        [KeyboardButton(text="🔊 Broadcast")],
        [KeyboardButton(text="➕ Funnel yaratish"), KeyboardButton(text="📂 Funnel ro'yxati")],
        [KeyboardButton(text="🏷️ Tariflar"), KeyboardButton(text="📋 Obunalar")]
    ],
    resize_keyboard=True
)

# Клавиатура для создания воронки
funnel_creation_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Matn qo'shish")],
        [KeyboardButton(text="📷 Rasm qo'shish")],
        [KeyboardButton(text="🎥 Video qo'shish")],
        [KeyboardButton(text="🎵 Audio qo'shish")],
        [KeyboardButton(text="📎 Fayl qo'shish")],
        [KeyboardButton(text="✅ Tugallash"), KeyboardButton(text="❌ Bekor qilish")]
    ],
    resize_keyboard=True
)