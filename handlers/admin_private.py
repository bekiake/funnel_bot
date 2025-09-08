from aiogram.filters import CommandObject
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import json
from kbds.reply import admin_kb
import logging

class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_content = State()

class FunnelStates(StatesGroup):
    waiting_for_key = State()
    waiting_for_messages = State()

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

# /admin - test xabar
@admin_router.message(Command("admin"))
async def admin_test(message: Message):
	await message.answer("Admin panelga xush kelibsiz!", reply_markup=admin_kb)

# /stats - statistikani ko'rish
@admin_router.message(F.text == "📊 Statistika")
async def admin_stats(message: Message, session: AsyncSession = None):
	if session:
		from database.orm_query import orm_get_users_count
		count = await orm_get_users_count(session)
		await message.answer(f"Bot foydalanuvchilari soni: <b>{count}</b>")
	else:
		await message.answer("DB session topilmadi")

# /users - userlar ro'yxati
@admin_router.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message, session: AsyncSession = None):
	if session:
		from database.orm_query import orm_get_all_users
		users = await orm_get_all_users(session)
		if users:
			text = "\n".join([str(u) for u in users])
			await message.answer(f"Foydalanuvchilar:\n{text}")
		else:
			await message.answer("Hech qanday user topilmadi")
	else:
		await message.answer("DB session topilmadi")

@admin_router.message(F.text == "🔊 Broadcast")
async def broadcast_start(message: Message, state: FSMContext):
    await message.answer("Yuboriladigan xabar yoki media yuboring:")
    await state.set_state(BroadcastStates.waiting_for_content)


@admin_router.message(BroadcastStates.waiting_for_content)
async def broadcast_send(message: Message, session: AsyncSession = None, state: FSMContext = None):
    if session:
        from database.orm_query import send_message_to_all_users
        from aiogram import Bot
        bot: Bot = message.bot
        await message.answer("Xabar yuborilmoqda...")
        # Matn, rasm, video, document
        if message.photo:
            file_id = message.photo[-1].file_id
            await send_message_to_all_users(bot, session, None, photo=file_id, caption=message.caption or "")
        elif message.video:
            file_id = message.video.file_id
            await send_message_to_all_users(bot, session, None, video=file_id, caption=message.caption or "")
        elif message.document:
            file_id = message.document.file_id
            await send_message_to_all_users(bot, session, None, document=file_id, caption=message.caption or "")
        elif message.text:
            await send_message_to_all_users(bot, session, message.text)
        else:
            await message.answer("Yuboriladigan matn yoki media topilmadi!")
            await state.clear()
            return
        await message.answer("Barcha userlarga xabar yuborildi!")
    else:
        await message.answer("DB session topilmadi")
    await state.clear()


@admin_router.message(F.text == "➕ Funnel yaratish")
async def funnel_create_start(message: Message, state: FSMContext):
    await message.answer("Funnel kalitini kiriting (masalan: trading):")
    await state.set_state(FunnelStates.waiting_for_key)

@admin_router.message(FunnelStates.waiting_for_key)
async def funnel_create_key(message: Message, state: FSMContext):
    await state.update_data(key=message.text.strip())
    await message.answer("Funnel uchun xabarlarni kiriting (har bir xabar yangi qatorda, tugatgach /done deb yozing):")
    await state.set_state(FunnelStates.waiting_for_messages)

@admin_router.message(FunnelStates.waiting_for_messages)
async def funnel_create_messages(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("key")
    if message.text.strip() == "/done":
        messages = data.get("messages", [])
        funnel_path = os.path.join("funnels", f"{key}.json")
        with open(funnel_path, "w", encoding="utf-8") as f:
            json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)
        await message.answer(f"✅ {key} funnel yaratildi!")
        await state.clear()
    else:
        messages = data.get("messages", [])
        messages.append(message.text)
        await state.update_data(messages=messages)

@admin_router.message(F.text == "📂 Funnel ro'yxati")
async def funnels_list(message: Message):
    funnel_dir = "funnels"
    files = [f for f in os.listdir(funnel_dir) if f.endswith(".json")]
    if not files:
        await message.answer("Hech qanday funnel topilmadi.")
    else:
        text = "\n".join(files)
        await message.answer(f"Funnel fayllar:\n{text}")