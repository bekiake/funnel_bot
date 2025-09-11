import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_get_free_link_by_key, orm_check_free_link_usage, orm_use_free_link,
    orm_get_user
)
from kbds.inline import get_freelink_access_kb
from kbds.reply import phone_request_kb


def _format_duration_days(days: int) -> str:
    """Kunlarni o'qishga qulay formatga aylantirish"""
    if days >= 365000:
        return "Cheksiz"
    elif days >= 365:
        years = days // 365
        remaining_days = days % 365
        if remaining_days == 0:
            return f"{years} yil"
        else:
            return f"{years} yil {remaining_days} kun"
    elif days >= 30:
        months = days // 30
        remaining_days = days % 30
        if remaining_days == 0:
            return f"{months} oy"
        else:
            return f"{months} oy {remaining_days} kun"
    elif days >= 7:
        weeks = days // 7
        remaining_days = days % 7
        if remaining_days == 0:
            return f"{weeks} hafta"
        else:
            return f"{weeks} hafta {remaining_days} kun"
    else:
        return f"{days} kun"


class FreeLinkService:
    """Free link lar bilan ishlash uchun servis"""
    
    @staticmethod
    async def process_free_link(
        message: types.Message,
        session: AsyncSession,
        key: str,
        state: Optional[FSMContext] = None
    ) -> bool:
        """Free link orqali kirishni qayta ishlash"""
        try:
            # Free link mavjudligini tekshirish
            free_link = await orm_get_free_link_by_key(session, key)
            if not free_link:
                return False  # Bu free link emas, funnel tekshiramiz
            
            logging.info(f"User {message.from_user.id} accessing free link: {key}")
            
            # Free link faolmi va limitga yetmaganmi tekshirish
            if not free_link.is_active:
                await message.answer("❌ Bu link endi faol emas.")
                return True
                
            # Maksimal foydalanish limitini tekshirish (faqat -1 bo'lmasa)
            if free_link.max_uses != -1 and free_link.current_uses >= free_link.max_uses:
                await message.answer("❌ Bu linkdan maksimal foydalanish limitiga erishildi.")
                return True
            
            # Foydalanuvchi oldin bu linkdan foydalanganmi tekshirish
            already_used = await orm_check_free_link_usage(session, free_link.id, message.from_user.id)
            if already_used:
                await message.answer("❌ Siz bu linkdan oldin foydalangansiz.")
                return True
            
            # Telefon raqamni tekshirish
            user = await orm_get_user(session, message.from_user.id)
            if not user or not user.phone:
                # Telefon raqam yo'q - so'ramiz va free link keyni saqlaymiz
                if state:
                    await state.update_data(pending_free_link_key=key)
                    from handlers.user_private import UserStates
                    await state.set_state(UserStates.waiting_for_phone)
                
                await message.answer(
                    f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
                    f"Free linkdan foydalanish uchun avval telefon raqamingizni ulashing:",
                    reply_markup=phone_request_kb
                )
                return True
            
            # Telefon bor - free link access berish
            return await FreeLinkService._grant_free_link_access(message, session, free_link)
            
        except Exception as e:
            logging.error(f"Error processing free link: {e}")
            await message.answer("❌ Xatolik yuz berdi")
            return True
    
    @staticmethod
    async def _grant_free_link_access(
        message: types.Message,
        session: AsyncSession,
        free_link
    ) -> bool:
        """Free link orqali kanal access berish"""
        try:
            # Expires_at hisoblash
            expires_at = datetime.now() + timedelta(days=free_link.duration_days)
            
            # Free link ishlatilganligini yozish
            use = await orm_use_free_link(
                session=session,
                free_link_id=free_link.id,
                user_id=message.from_user.id,
                expires_at=expires_at
            )
            
            # Bot instance olish
            bot = message.bot
            
            # Bir martalik invite link yaratish
            try:
                # Foydalanuvchi uchun maxsus invite link yaratish
                # member_limit=1 - faqat bitta kishi qo'shilishi mumkin
                # expire_date - link tugash vaqti (1 soat)
                invite_link = await bot.create_chat_invite_link(
                    chat_id=free_link.channel_id,
                    member_limit=1,
                    expire_date=datetime.now() + timedelta(hours=1),
                    name=f"FreeLinkAccess_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                
                one_time_link = invite_link.invite_link
                
            except Exception as e:
                logging.error(f"Error creating invite link for channel {free_link.channel_id}: {e}")
                # Agar invite link yaratishda xatolik bo'lsa, standart linkni ishlatamiz
                one_time_link = free_link.channel_invite_link
            
            # Foydalanuvchiga xabar yuborish
            duration_text = _format_duration_days(free_link.duration_days)
            
            await message.answer(
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"🎁 <b>{free_link.name}</b> free linkidan muvaffaqiyatli foydalandingiz!\n\n"
                f"📢 <b>{duration_text}</b> davomida kanalga kirish imkoniyatingiz bor.\n"
                f"📅 <b>Muddat tugaydi:</b> {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"🔗 <b>Maxsus linkingiz:</b> (1 soat ichida faol)\n\n"
                f"Pastdagi tugma orqali kanalga qo'shiling:",
                reply_markup=get_freelink_access_kb(one_time_link)
            )
            
            logging.info(f"Free link access granted to user {message.from_user.id} for {free_link.duration_days} days with one-time link")
            return True
            
        except Exception as e:
            logging.error(f"Error granting free link access: {e}")
            await message.answer("❌ Xatolik yuz berdi")
            return True
