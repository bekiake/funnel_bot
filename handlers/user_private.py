from aiogram.filters import CommandStart

from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    orm_add_user,
)

from filters.chat_types import ChatTypeFilter
from aiogram import Router, F, types
from aiogram.types import Message
from kbds.reply import menu_kb
from services.funnel import send_funnel_messages
import logging


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession = None):
    if session:
        await orm_add_user(
            session=session,
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
    )
    
    if message.text and " " in message.text:
        key = message.text.split(" ", 1)[1]
        logging.info(f"User {message.from_user.id} started with key: {key}")
        await send_funnel_messages(message, key)
    else:
        await message.answer("Quyidagi menyudan tanlang:", reply_markup=menu_kb)
    
    
@user_private_router.message(F.text == "📢 Reklama haqida")
async def reklama_handler(message: Message):
    await message.answer("Reklama haqida ma'lumot...")


@user_private_router.message(F.text == "ℹ️ Ma'lumot")
async def info_handler(message: Message):
    await message.answer("Bot haqida umumiy ma'lumot...")
    
    
@user_private_router.message(F.text == "❓ Yordam")
async def help_handler(message: Message):
    await message.answer("Savollaringiz bo'lsa, shu yerga yozing va telefon raqamingizni qoldiring, tez orada siz bilan bog'lanamiz.")
