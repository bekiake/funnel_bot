import logging
import os
import json
import re
from datetime import datetime

from aiogram.filters import CommandObject, Command, CommandStart
from aiogram import F, Router, types
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from filters.chat_types import ChatTypeFilter, IsAdmin
from kbds.inline import (
    get_admin_menu_kb, get_funnel_creation_kb, get_admin_subscription_kb, 
    get_back_to_admin_menu_kb, get_broadcast_kb, get_users_list_kb, 
    get_user_profile_kb, get_funnels_list_kb, get_funnel_details_kb,
    get_subscriptions_list_kb, get_subscription_details_kb, get_cancel_add_plan_kb,
    get_funnel_cancel_kb, get_funnel_content_kb,
    get_free_links_menu_kb, get_free_links_list_kb, get_free_link_info_kb,
    get_free_link_cancel_kb, get_max_users_selection_kb, get_duration_selection_kb,
    get_delete_confirmation_kb
)
from services.subscription import SubscriptionService


def parse_duration_to_days(duration_text: str) -> int:
    """Duration textni kunlarga aylantirish"""
    duration_text = duration_text.lower().strip()
    
    # Cheksiz
    if duration_text in ['cheksiz', 'cheksizlikka', 'unlimited', 'forever']:
        return 365000  # ~1000 yil
    
    # Faqat raqam
    if duration_text.isdigit():
        return int(duration_text)
    
    # Regex bilan parse qilish
    patterns = {
        r'(\d+)\s*(kun|day)s?': 1,
        r'(\d+)\s*(hafta|week)s?': 7,
        r'(\d+)\s*(oy|month)s?': 30,
        r'(\d+)\s*(yil|year)s?': 365
    }
    
    for pattern, multiplier in patterns.items():
        match = re.search(pattern, duration_text)
        if match:
            number = int(match.group(1))
            return number * multiplier
    
    # Hech narsa topilmasa xatolik
    raise ValueError(f"Noto'g'ri duration format: {duration_text}")


def format_duration_days(days: int) -> str:
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


from database.orm_query import (
    orm_get_users_count,
    orm_get_all_users,
    orm_get_user_funnel_stats,
    send_message_to_all_users,
    orm_create_funnel,
    orm_add_funnel_step,
    orm_create_subscription_plan,
    orm_get_active_subscription_plans,
    orm_create_free_link, orm_get_all_free_links, orm_get_free_link_by_key,
    orm_delete_free_link, orm_permanent_delete_free_link, orm_deactivate_free_link, orm_activate_free_link
)


class BroadcastStates(StatesGroup):
    waiting_for_content = State()


class FunnelStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_key = State()
    waiting_for_description = State()
    adding_steps = State()
    waiting_for_content = State()
    waiting_for_caption = State()
    waiting_for_button_text = State()


class SubscriptionPlanStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_duration = State()
    waiting_for_price_usd = State()
    waiting_for_price_uzs = State()
    waiting_for_channel_id = State()


class FreeLinkStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_key = State()
    waiting_for_max_uses = State()
    waiting_for_duration_days = State()


admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_router.message(Command("admin"))
async def admin_start(message: Message):
    """Админская панель"""
    await message.answer(
        "👨‍💻 <b>Admin panelga xush kelibsiz!</b>\n\n"
        "Quyidagi funksiyalardan foydalanishingiz mumkin:",
        reply_markup=get_admin_menu_kb()
    )


@admin_router.message(CommandStart())
async def admin_start_cmd(message: Message, session: AsyncSession):
    """Admin /start handler"""
    try:
        # Добавляем админа в базу данных
        from database.orm_query import orm_add_user
        await orm_add_user(
            session=session,
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
        )
        
        logging.info(f"Admin {message.from_user.id} used /start command")
        
        # Показываем админское меню
        await message.answer(
            f"👨‍💻 <b>Assalomu alaykum, admin {message.from_user.first_name}!</b>\n\n"
            f"Admin panelga xush kelibsiz:",
            reply_markup=get_admin_menu_kb()
        )
        
    except Exception as e:
        logging.error(f"Error in admin start command: {e}")
        await message.answer("❌ Xatolik yuz berdi")


# Отладочный хендлер для проверки админских прав
@admin_router.message(F.text == "test_admin")
async def test_admin_handler(message: Message):
    """Тестовый хендлер для проверки админских прав"""
    await message.answer(f"✅ Siz admin ekansiz! ID: {message.from_user.id}")


# ===================== CALLBACK ХЕНДЛЕРЫ ДЛЯ АДМИНСКОГО МЕНЮ =====================

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery, session: AsyncSession):
    """Статистика бота"""
    try:
        users_count = await orm_get_users_count(session)
        
        text = f"📊 <b>Bot statistikasi</b>\n\n"
        text += f"👥 Jami foydalanuvchilar: <b>{users_count}</b>\n"
        text += f"📅 So'ngi yangilanish: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        await callback.message.edit_text(text, reply_markup=get_back_to_admin_menu_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        await callback.answer("❌ Statistikani olishda xatolik")


@admin_router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: CallbackQuery, session: AsyncSession):
    """Foydalanuvchilar ro'yxati (pagination bilan)"""
    try:
        users = await orm_get_all_users(session)
        await show_users_page(callback.message, session, users, page=0, edit=True)
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting users: {e}")
        await callback.answer("❌ Foydalanuvchilarni olishda xatolik")


async def show_users_page(message, session: AsyncSession, users: list = None, page: int = 0, edit: bool = False):
    """Foydalanuvchilarni sahifa bo'lib ko'rsatish"""
    try:
        if users is None:
            users = await orm_get_all_users(session)
        
        if not users:
            text = "🚫 Hech qanday foydalanuvchi topilmadi"
            keyboard = get_back_to_admin_menu_kb()
            
            if edit:
                await message.edit_text(text, reply_markup=keyboard)
            else:
                await message.answer(text, reply_markup=keyboard)
            return
        
        # Pagination settings
        USERS_PER_PAGE = 10
        total_users = len(users)
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        
        # Current page bounds
        start_idx = page * USERS_PER_PAGE
        end_idx = min(start_idx + USERS_PER_PAGE, total_users)
        current_users = users[start_idx:end_idx]
        
        # Build text
        text = f"👥 <b>Foydalanuvchilar ro'yxati</b>\n\n"
        text += f"📊 Jami: <b>{total_users}</b> ta foydalanuvchi\n"
        text += f"📄 Sahifa: <b>{page + 1}</b> / <b>{total_pages}</b>\n\n"
        
        for i, user in enumerate(current_users, start=start_idx + 1):
            text += f"<b>{i}.</b> "
            text += f"👤 {user.full_name or 'Nomsiz'}\n"
            text += f"🆔 ID: <code>{user.user_id}</code>\n"
            
            if user.phone:
                text += f"📞 {user.phone}\n"
            
            # User statistics
            stats = await orm_get_user_funnel_stats(session, user.user_id)
            if stats and stats.get('total_started', 0) > 0:
                text += f"📊 Voronkalar: {stats.get('total_completed', 0)}/{stats.get('total_started', 0)} ({stats.get('completion_rate', 0)}%)\n"
            
            text += f"📅 Ro'yxat: {user.created.strftime('%d.%m.%Y')}\n"
            text += f"⏰ Oxirgi: {user.updated.strftime('%d.%m.%Y')}\n\n"
        
        # Create pagination keyboard
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        
        # Page numbers navigation (like website pagination)
        if total_pages > 1:
            # Show first page if not on first page and there are more than 3 pages
            if page > 0 and total_pages > 3:
                builder.add(InlineKeyboardButton(text="1", callback_data="users_page:0"))
                if page > 2:
                    builder.add(InlineKeyboardButton(text="...", callback_data="noop"))
            
            # Show current page and adjacent pages
            start_page = max(0, page - 1)
            end_page = min(total_pages, page + 2)
            
            for p in range(start_page, end_page):
                if p == page:
                    # Current page (highlighted)
                    builder.add(InlineKeyboardButton(text=f"• {p + 1} •", callback_data="noop"))
                else:
                    builder.add(InlineKeyboardButton(text=str(p + 1), callback_data=f"users_page:{p}"))
            
            # Show last page if not on last page and there are more than 3 pages
            if page < total_pages - 1 and total_pages > 3:
                if page < total_pages - 3:
                    builder.add(InlineKeyboardButton(text="...", callback_data="noop"))
                builder.add(InlineKeyboardButton(text=str(total_pages), callback_data=f"users_page:{total_pages-1}"))
        
        # Add a row separator
        if total_pages > 1:
            builder.row()
        
        # Navigation buttons
        if page > 0:
            builder.add(InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"users_page:{page-1}"
            ))
        
        if page < total_pages - 1:
            builder.add(InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"users_page:{page+1}"
            ))
        
        # Back button
        builder.row()
        builder.add(InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="back_to_admin_menu"
        ))
        
        if edit:
            await message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text, reply_markup=builder.as_markup())
            
    except Exception as e:
        logging.error(f"Error showing users page: {e}")
        if edit:
            await message.edit_text("❌ Xatolik yuz berdi", reply_markup=get_back_to_admin_menu_kb())
        else:
            await message.answer("❌ Xatolik yuz berdi", reply_markup=get_back_to_admin_menu_kb())


@admin_router.callback_query(F.data == "admin_broadcast")
async def broadcast_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начало рассылки"""
    await callback.message.edit_text(
        "📢 <b>Ommaviy xabar yuborish</b>\n\n"
        "Yuboriladigan xabar yoki media faylni yuboring:",
        reply_markup=get_broadcast_kb()
    )
    await state.set_state(BroadcastStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "admin_create_funnel")
async def funnel_create_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начало создания воронки"""
    await callback.message.edit_text(
        "🎯 <b>Yangi funnel yaratish</b>\n\n"
        "Funnel nomini kiriting:",
        reply_markup=get_funnel_creation_kb()
    )
    await state.set_state(FunnelStates.waiting_for_name)
    await callback.answer()


@admin_router.callback_query(F.data == "admin_funnel_list")
async def funnels_list_callback(callback: CallbackQuery, session: AsyncSession):
    """Funnel ro'yxati"""
    try:
        from database.orm_query import select, Funnel
        
        query = select(Funnel).where(Funnel.is_active == True)
        result = await session.execute(query)
        funnels = result.scalars().all()
        
        text = f"🎯 <b>Funnel ro'yxati</b>\n\n"
        text += f"📊 Jami: <b>{len(funnels)}</b> ta funnel\n\n"
        text += "Tafsilotlar ko'rish uchun funnel nomiga bosing:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_funnels_list_kb(funnels)
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting funnels: {e}")
        await callback.answer("❌ Funnellar ro'yxatini olishda xatolik")


@admin_router.callback_query(F.data.startswith("funnel_details:"))
async def funnel_details_handler(callback: CallbackQuery, session: AsyncSession):
    """Funnel tafsilotlari"""
    try:
        funnel_id = int(callback.data.split(":")[1])
        from database.orm_query import select, Funnel
        
        query = select(Funnel).where(Funnel.id == funnel_id)
        result = await session.execute(query)
        funnel = result.scalar_one_or_none()
        
        if funnel:
            description = funnel.description or "Yo'q"
            bot_username = getattr(callback.bot, 'username', 'your_bot')
            text = f"🎯 <b>{funnel.name}</b>\n\n"
            text += f"🔑 Kalit: <code>{funnel.key}</code>\n"
            text += f"📝 Tavsif: {description}\n"
            text += f"📅 Yaratilgan: {funnel.created.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"🔗 Link: <code>https://t.me/{bot_username}?start={funnel.key}</code>\n"
            
            # Qadamlar soni
            from database.orm_query import func
            from database.models import FunnelStep
            steps_query = select(func.count()).select_from(FunnelStep).where(FunnelStep.funnel_id == funnel.id)
            steps_result = await session.execute(steps_query)
            steps_count = steps_result.scalar() or 0
            text += f"📋 Qadamlar: {steps_count} ta\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_funnel_details_kb(funnel_id)
            )
        else:
            await callback.message.edit_text(
                "❌ Funnel topilmadi",
                reply_markup=get_back_to_admin_menu_kb()
            )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting funnel details: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("funnel_stats:"))
async def funnel_stats_handler(callback: CallbackQuery, session: AsyncSession):
    """Показать статистику воронки"""
    try:
        funnel_id = int(callback.data.split(":")[1])
        
        # Получаем воронку
        from database.orm_query import orm_get_funnel_by_id, orm_get_funnel_statistics
        funnel = await orm_get_funnel_by_id(session, funnel_id)
        if not funnel:
            await callback.answer("❌ Funnel topilmadi")
            return
        
        # Получаем статистику воронки
        stats = await orm_get_funnel_statistics(session, funnel_id)
        
        text = f"📊 <b>{funnel.name} - Statistika</b>\n\n"
        text += f"🔗 Kalit: <code>{funnel.key}</code>\n"
        text += f"👥 Jami boshlagan: {stats.get('total_started', 0)} ta\n"
        text += f"✅ Tugallaganlar: {stats.get('completed', 0)} ta\n"
        text += f"⏳ Jarayonda: {stats.get('in_progress', 0)} ta\n"
        text += f"📈 Tugallanish foizi: {stats.get('completion_rate', 0):.1f}%\n\n"
        text += f"📅 Yaratilgan: {funnel.created.strftime('%d.%m.%Y %H:%M')}\n"
        
        if funnel.updated:
            text += f"🔄 Yangilangan: {funnel.updated.strftime('%d.%m.%Y %H:%M')}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_funnel_details_kb(funnel_id)
        )
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error getting funnel stats: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("funnel_edit:"))
async def funnel_edit_handler(callback: CallbackQuery, session: AsyncSession):
    """Tahrirlash voronka"""
    try:
        funnel_id = int(callback.data.split(":")[1])
        
        # Получаем воронку
        from database.orm_query import orm_get_funnel_by_id
        funnel = await orm_get_funnel_by_id(session, funnel_id)
        if not funnel:
            await callback.answer("❌ Funnel topilmadi")
            return
        
        text = (
            f"✏️ <b>Voronka tahrirlash</b>\n\n"
            f"📋 Nom: {funnel.name}\n"
            f"🔑 Kalit: {funnel.key}\n\n"
            f"⚠️ Voronka tahrirlash funksiyasi ishlab chiqilmoqda.\n"
            f"Hozircha faqat ko'rish va o'chirish mumkin."
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_funnel_details_kb(funnel_id)
        )
        await callback.answer("ℹ️ Tahrirlash tez orada qo'shiladi")
        
    except Exception as e:
        logging.error(f"Error editing funnel: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("funnel_delete:"))
async def funnel_delete_handler(callback: CallbackQuery, session: AsyncSession):
    """O'chirish voronka"""
    try:
        funnel_id = int(callback.data.split(":")[1])
        
        # Получаем воронку
        from database.orm_query import orm_get_funnel_by_id
        funnel = await orm_get_funnel_by_id(session, funnel_id)
        if not funnel:
            await callback.answer("❌ Funnel topilmadi")
            return
        
        # Создаем клавиатуру подтверждения
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Ha, o'chirish",
            callback_data=f"confirm_funnel_delete:{funnel_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=f"funnel_details:{funnel_id}"
        ))
        builder.adjust(1)
        
        text = (
            f"⚠️ <b>Voronkani o'chirish</b>\n\n"
            f"📋 Nom: {funnel.name}\n"
            f"🔑 Kalit: {funnel.key}\n\n"
            f"❗️ Diqqat! Bu amal qaytarib bo'lmaydi.\n"
            f"Voronka va unga bog'liq barcha ma'lumotlar o'chib ketadi.\n\n"
            f"Rostdan ham o'chirmoqchimisiz?"
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error deleting funnel: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("confirm_funnel_delete:"))
async def confirm_funnel_delete_handler(callback: CallbackQuery, session: AsyncSession):
    """Tasdiqlash voronka o'chirish"""
    try:
        funnel_id = int(callback.data.split(":")[1])
        
        # O'chirish funksiyasini chaqirish
        from database.orm_query import orm_delete_funnel
        success = await orm_delete_funnel(session, funnel_id)
        
        if success:
            await callback.message.edit_text(
                "✅ <b>Voronka muvaffaqiyatli o'chirildi!</b>\n\n"
                "Asosiy menyuga qaytish uchun pastdagi tugmani bosing.",
                reply_markup=get_back_to_admin_menu_kb()
            )
            await callback.answer("✅ O'chirildi!")
        else:
            await callback.answer("❌ O'chirishda xatolik")
        
    except Exception as e:
        logging.error(f"Error confirming funnel delete: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data == "admin_tariffs")
async def subscription_plans_menu_callback(callback: CallbackQuery):
    """Меню управления тарифами"""
    await callback.message.edit_text(
        "💰 <b>Obuna tariflari boshqaruvi</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=get_admin_subscription_kb()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_subscriptions")
async def subscriptions_list_callback(callback: CallbackQuery, session: AsyncSession):
    """Список активных подписок"""
    try:
        from database.orm_query import select, Subscription, User, SubscriptionPlan
        from sqlalchemy.orm import joinedload
        
        query = select(Subscription).where(
            Subscription.is_active == True
        ).options(
            joinedload(Subscription.user),
            joinedload(Subscription.plan)
        )
        
        result = await session.execute(query)
        subscriptions = result.unique().scalars().all()
        
        if not subscriptions:
            text = "🚫 Hech qanday aktiv obuna topilmadi."
        else:
            text = f"📋 <b>Aktiv obunalar ({len(subscriptions)}):</b>\n\n"
            
            for sub in subscriptions:
                text += f"👤 User: {sub.user_id}\n"
                text += f"📋 Tarif: {sub.plan.name}\n"
                text += f"💰 Narx: ${sub.plan.price_usd}\n"
                text += f"⏱ Tugash: {sub.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"✅ To'langan: {'Ha' if sub.payment_verified else 'Yoq'}\n\n"
        
        await callback.message.edit_text(text, reply_markup=get_back_to_admin_menu_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting subscriptions: {e}")
        await callback.answer("❌ Obunalar ro'yxatini olishda xatolik")


@admin_router.callback_query(F.data == "admin_plans_list")
async def admin_plans_list_callback(callback: CallbackQuery, session: AsyncSession):
    """Тарифлар рўйхати"""
    try:
        plans = await orm_get_active_subscription_plans(session)
        
        if not plans:
            text = "🚫 Hech qanday tarif topilmadi.\n\nYangi tarif yaratish uchun pastdagi tugmani bosing."
        else:
            text = f"📋 <b>Tariflar ro'yxati ({len(plans)}):</b>\n\n"
            
            for plan in plans:
                text += f"💎 <b>{plan.name}</b>\n"
                text += f"💰 Narx: ${plan.price_usd}\n"
                text += f"⏱ Muddati: {plan.duration_days} kun\n"
                text += f"📝 Tavsif: {plan.description}\n"
                text += f"✅ Holati: {'Faol' if plan.is_active else 'Nofaol'}\n\n"
        
        await callback.message.edit_text(text, reply_markup=get_subscriptions_list_kb(plans))
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting plans list: {e}")
        await callback.answer("❌ Tariflar ro'yxatini olishda xatolik")


@admin_router.callback_query(F.data == "admin_add_plan")
async def admin_add_plan_callback(callback: CallbackQuery, state: FSMContext):
    """Янги тариф қўшиш"""
    await state.set_state(SubscriptionPlanStates.waiting_for_name)
    
    await callback.message.edit_text(
        "💰 <b>Yangi tarif yaratish</b>\n\n"
        "Tarif nomini kiriting:",
        reply_markup=get_cancel_add_plan_kb()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_subscription_stats")
async def admin_subscription_stats_callback(callback: CallbackQuery, session: AsyncSession):
    """Обуналар статистикаси"""
    try:
        from database.orm_query import select, Subscription, SubscriptionPlan, func
        
        # Жами обуналар сони
        total_subs = await session.scalar(select(func.count(Subscription.id)))
        
        # Фаол обуналар сони  
        active_subs = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        )
        
        # Тўланган обуналар сони
        paid_subs = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.payment_verified == True)
        )
        
        text = f"📊 <b>Obunalar statistikasi</b>\n\n"
        text += f"📋 Jami obunalar: <b>{total_subs or 0}</b>\n"
        text += f"✅ Faol obunalar: <b>{active_subs or 0}</b>\n"
        text += f"💳 To'langan obunalar: <b>{paid_subs or 0}</b>\n"
        text += f"📅 So'ngi yangilanish: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        await callback.message.edit_text(text, reply_markup=get_back_to_admin_menu_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting subscription stats: {e}")
        await callback.answer("❌ Statistikani olishda xatolik")


# ===================== NAVIGATION CALLBACK ХЕНДЛЕРЫ =====================

@admin_router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_handler(callback: CallbackQuery):
    """Обработка возврата в админское меню"""
    await callback.message.edit_text(
        "👨‍💻 <b>Admin panelga xush kelibsiz!</b>\n\n"
        "Quyidagi funksiyalardan foydalanishingiz mumkin:",
        reply_markup=get_admin_menu_kb()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "back_to_subscriptions")
async def back_to_subscriptions_handler(callback: CallbackQuery, session: AsyncSession):
    """Обработка возврата в меню подписок"""
    try:
        subscriptions = await SubscriptionService.get_all_subscriptions(session)
        text = "💎 <b>Obunalar boshqaruvi</b>\n\n"
        
        if subscriptions:
            text += f"📊 Jami obunalar: {len(subscriptions)}\n\n"
            for sub in subscriptions[:10]:  # Показываем только первые 10
                status = "✅ Faol" if sub.is_active else "❌ Nofaol"
                text += f"👤 {sub.user.full_name}\n"
                text += f"📋 Tarif: {sub.plan.name}\n"
                text += f"💰 Narx: ${sub.plan.price_usd}\n"
                text += f"⏱ Tugash: {sub.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"✅ To'langan: {'Ha' if sub.payment_verified else 'Yoq'}\n\n"
        else:
            text += "Hech qanday obuna topilmadi."
        
        await callback.message.edit_text(text, reply_markup=get_admin_subscription_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting subscriptions: {e}")
        await callback.answer("❌ Obunalar ro'yxatini olishda xatolik")


@admin_router.callback_query(F.data == "cancel_subscription_creation")
async def cancel_subscription_creation_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены создания плана подписки"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Obuna plani yaratish bekor qilindi.</b>\n\n"
        "Admin paneliga qaytish uchun pastdagi tugmani bosing:",
        reply_markup=get_back_to_admin_menu_kb()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "cancel_funnel_creation")
async def cancel_funnel_creation_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены создания воронки"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Voronka yaratish bekor qilindi.</b>\n\n"
        "Admin paneliga qaytish uchun pastdagi tugmani bosing:",
        reply_markup=get_back_to_admin_menu_kb()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены broadcast"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Broadcast bekor qilindi.</b>\n\n"
        "Admin paneliga qaytish uchun pastdagi tugmani bosing:",
        reply_markup=get_back_to_admin_menu_kb()
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("users_page:"))
async def users_pagination_handler(callback: CallbackQuery, session: AsyncSession):
    """Pagination для списка пользователей"""
    try:
        page = int(callback.data.split(":")[1])
        await show_users_page(callback.message, session, page=page, edit=True)
        await callback.answer()
    except Exception as e:
        logging.error(f"Error in users pagination: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)


@admin_router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    """Dummy handler for non-clickable buttons"""
    await callback.answer()


@admin_router.callback_query(F.data.startswith("user_profile:"))
async def user_profile_handler(callback: CallbackQuery, session: AsyncSession):
    """Показ профиля пользователя"""
    try:
        user_id = int(callback.data.split(":")[1])
        
        # Получаем информацию о пользователе
        from database.orm_query import orm_get_user_by_id
        user = await orm_get_user_by_id(session, user_id)
        
        if user:
            text = f"👤 <b>Foydalanuvchi profili</b>\n\n"
            text += f"🆔 ID: <code>{user.id}</code>\n"
            text += f"👤 Ism: <b>{user.full_name}</b>\n"
            text += f"📅 Ro'yxatdan o'tgan: {user.created.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"⏰ So'ngi faollik: {user.updated.strftime('%d.%m.%Y %H:%M')}\n"
            
            # Qo'shimcha ma'lumotlar
            if hasattr(user, 'subscriptions'):
                active_subs = [s for s in user.subscriptions if s.is_active]
                text += f"💎 Faol obunalar: {len(active_subs)} ta\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_user_profile_kb(user_id)
            )
        else:
            await callback.message.edit_text(
                "❌ Foydalanuvchi topilmadi",
                reply_markup=get_back_to_admin_menu_kb()
            )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting user profile: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


# ===================== СТАРЫЕ ТЕКСТОВЫЕ ХЕНДЛЕРЫ (для обратной совместимости) =====================


@admin_router.message(F.text == "📊 Statistika")
async def admin_stats(message: Message, session: AsyncSession):
    """Статистика бота"""
    try:
        users_count = await orm_get_users_count(session)
        
        # Можно добавить больше статистики
        text = f"📊 <b>Bot statistikasi</b>\n\n"
        text += f"👥 Jami foydalanuvchilar: <b>{users_count}</b>\n"
        text += f"📅 So'ngi yangilanish: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        await message.answer(text)
    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        await message.answer(
            "❌ <b>Statistikani olishda xatolik</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )


@admin_router.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message, session: AsyncSession):
    """Список пользователей"""
    try:
        users = await orm_get_all_users(session)
        if users:
            # Разбиваем на части, если много пользователей
            if len(users) > 50:
                text = f"👥 <b>Jami foydalanuvchilar: {len(users)}</b>\n\n"
                text += "Birinchi 50 tasi:\n"
                text += "\n".join([f"• {u}" for u in users[:50]])
                text += f"\n\n... va yana {len(users) - 50} ta"
            else:
                text = f"👥 <b>Barcha foydalanuvchilar ({len(users)}):</b>\n\n"
                text += "\n".join([f"• {u}" for u in users])
            
            await message.answer(text)
        else:
            await message.answer("🚫 Hech qanday foydalanuvchi topilmadi")
    except Exception as e:
        logging.error(f"Error getting users: {e}")
        await message.answer(
            "❌ <b>Foydalanuvchilarni olishda xatolik</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )


@admin_router.message(F.text == "🔊 Broadcast")
async def broadcast_start(message: Message, state: FSMContext):
    """Начало рассылки"""
    await message.answer(
        "📢 <b>Ommaviy xabar yuborish</b>\n\n"
        "Yuboriladigan xabar yoki media faylni yuboring:",
        reply_markup=get_broadcast_kb()
    )
    await state.set_state(BroadcastStates.waiting_for_content)


@admin_router.message(BroadcastStates.waiting_for_content)
async def broadcast_send(message: Message, session: AsyncSession, state: FSMContext):
    """Отправка рассылки"""
    try:
        bot = message.bot
        await message.answer("📤 Xabar yuborilmoqda...")
        
        # Определяем тип контента и отправляем
        if message.photo:
            file_id = message.photo[-1].file_id
            await send_message_to_all_users(
                bot, session, None, 
                photo=file_id, 
                caption=message.caption or ""
            )
        elif message.video:
            file_id = message.video.file_id
            await send_message_to_all_users(
                bot, session, None, 
                video=file_id, 
                caption=message.caption or ""
            )
        elif message.document:
            file_id = message.document.file_id
            await send_message_to_all_users(
                bot, session, None, 
                document=file_id, 
                caption=message.caption or ""
            )
        elif message.text:
            await send_message_to_all_users(bot, session, message.text)
        else:
            await message.answer(
                "❌ <b>Noto'g'ri format!</b> Matn yoki media yuboring.",
                reply_markup=get_back_to_admin_menu_kb()
            )
            await state.clear()
            return
        
        await message.answer(
            "✅ <b>Barcha foydalanuvchilarga xabar yuborildi!</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )
    except Exception as e:
        logging.error(f"Error in broadcast: {e}")
        await message.answer(
            "❌ <b>Xabar yuborishda xatolik</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )
    
    await state.clear()


@admin_router.message(F.text == "➕ Funnel yaratish")
async def funnel_create_start(message: Message, state: FSMContext):
    """Начало создания воронки"""
    await message.answer(
        "🎯 <b>Yangi funnel yaratish</b>\n\n"
        "Funnel nomini kiriting:",
        reply_markup=get_funnel_cancel_kb()
    )
    await state.set_state(FunnelStates.waiting_for_name)


@admin_router.message(FunnelStates.waiting_for_name)
async def funnel_create_name(message: Message, state: FSMContext):
    """Ввод названия воронки"""
    await state.update_data(name=message.text.strip())
    await message.answer(
        "🔑 Funnel kalitini kiriting (masalan: python_course):\n\n"
        "Bu kalit orqali foydalanuvchilar funnel ga kirishadi.",
        reply_markup=get_funnel_cancel_kb()
    )
    await state.set_state(FunnelStates.waiting_for_key)


@admin_router.message(FunnelStates.waiting_for_key)
async def funnel_create_key(message: Message, state: FSMContext):
    """Ввод ключа воронки"""
    key = message.text.strip().lower()
    await state.update_data(key=key)
    await message.answer(
        "📝 Funnel haqida qisqacha tavsif kiriting "
        "(yoki /skip deb yozing):",
        reply_markup=get_funnel_cancel_kb()
    )
    await state.set_state(FunnelStates.waiting_for_description)


@admin_router.message(FunnelStates.waiting_for_description)
async def funnel_create_description(message: Message, state: FSMContext, session: AsyncSession):
    """Ввод описания и создание воронки"""
    try:
        data = await state.get_data()
        description = None if message.text.strip() == "/skip" else message.text.strip()
        
        # Создаем воронку в базе данных
        funnel = await orm_create_funnel(
            session,
            name=data["name"],
            key=data["key"],
            description=description
        )
        
        await state.update_data(funnel_id=funnel.id, step_number=1)
        
        await message.answer(
            f"✅ <b>Funnel '{data['name']}' yaratildi!</b>\n\n"
            f"🔗 Link: <code>https://t.me/test_ad_project_bot?start={data['key']}</code>\n\n"
            f"Endi funnel uchun qadamlarni qo'shing:",
            reply_markup=get_funnel_creation_kb()
        )
        await state.set_state(FunnelStates.adding_steps)
        
    except Exception as e:
        logging.error(f"Error creating funnel: {e}")
        await message.answer(
            "❌ <b>Funnel yaratishda xatolik</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )
        await state.clear()


@admin_router.message(FunnelStates.adding_steps)
async def funnel_adding_steps(message: Message, state: FSMContext):
    """Обработка добавления шагов"""
    if message.text == "📝 Matn qo'shish":
        await message.answer("📝 Matn xabarini yuboring:")
        await state.update_data(content_type="text")
        await state.set_state(FunnelStates.waiting_for_content)
    
    elif message.text == "📷 Rasm qo'shish":
        await message.answer("📷 Rasmni yuboring:")
        await state.update_data(content_type="photo")
        await state.set_state(FunnelStates.waiting_for_content)
    
    elif message.text == "🎥 Video qo'shish":
        await message.answer("🎥 Videoni yuboring:")
        await state.update_data(content_type="video")
        await state.set_state(FunnelStates.waiting_for_content)
    
    elif message.text == "🎵 Audio qo'shish":
        await message.answer("🎵 Audioni yuboring:")
        await state.update_data(content_type="audio")
        await state.set_state(FunnelStates.waiting_for_content)
    
    elif message.text == "📎 Fayl qo'shish":
        await message.answer("📎 Faylni yuboring:")
        await state.update_data(content_type="document")
        await state.set_state(FunnelStates.waiting_for_content)
    
    elif message.text == "✅ Tugallash":
        await message.answer(
            "✅ Funnel muvaffaqiyatli yaratildi!",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()
    
    elif message.text == "❌ Bekor qilish":
        await message.answer(
            "❌ Funnel yaratish bekor qilindi.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()


# ===================== CALLBACK ХЕНДЛЕРЫ ДЛЯ СОЗДАНИЯ ВОРОНКИ =====================

@admin_router.callback_query(F.data == "funnel_add_text")
async def funnel_add_text_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление текста в воронку"""
    await callback.message.edit_text(
        "📝 Matn xabarini yuboring:",
        reply_markup=get_funnel_content_kb()
    )
    await state.update_data(content_type="text")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_photo")
async def funnel_add_photo_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление фото в воронку"""
    await callback.message.edit_text(
        "📷 Rasmni yuboring:",
        reply_markup=get_funnel_content_kb()
    )
    await state.update_data(content_type="photo")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_video")
async def funnel_add_video_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление видео в воронку"""
    await callback.message.edit_text(
        "🎥 Videoni yuboring:",
        reply_markup=get_funnel_content_kb()
    )
    await state.update_data(content_type="video")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_audio")
async def funnel_add_audio_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление аудио в воронку"""
    await callback.message.edit_text(
        "🎵 Audioni yuboring:",
        reply_markup=get_funnel_content_kb()
    )
    await state.update_data(content_type="audio")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_document")
async def funnel_add_document_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление документа в воронку"""
    await callback.message.edit_text(
        "📎 Faylni yuboring:",
        reply_markup=get_funnel_content_kb()
    )
    await state.update_data(content_type="document")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_finish")
async def funnel_finish_callback(callback: CallbackQuery, state: FSMContext):
    """Завершение создания воронки"""
    await callback.message.edit_text(
        "✅ Funnel muvaffaqiyatli yaratildi!",
        reply_markup=get_admin_menu_kb()
    )
    await state.clear()
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_cancel")
async def funnel_cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена создания воронки"""
    await callback.message.edit_text(
        "❌ Funnel yaratish bekor qilindi.",
        reply_markup=get_admin_menu_kb()
    )
    await state.clear()
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_back_to_steps")
async def funnel_back_to_steps_callback(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа контента"""
    await callback.message.edit_text(
        "Qanday turdagi kontent qo'shasiz?",
        reply_markup=get_funnel_creation_kb()
    )
    await state.set_state(FunnelStates.adding_steps)
    await callback.answer()


@admin_router.message(FunnelStates.waiting_for_content)
async def funnel_content_handler(message: Message, state: FSMContext):
    """Обработка контента для шага"""
    try:
        data = await state.get_data()
        content_type = data["content_type"]
        
        # Проверяем соответствие типа контента
        if content_type == "text" and message.text:
            await state.update_data(content_data=message.text)
        elif content_type == "photo" and message.photo:
            await state.update_data(content_data=message.photo[-1].file_id)
        elif content_type == "video" and message.video:
            await state.update_data(content_data=message.video.file_id)
        elif content_type == "audio" and message.audio:
            await state.update_data(content_data=message.audio.file_id)
        elif content_type == "document" and message.document:
            await state.update_data(content_data=message.document.file_id)
        else:
            await message.answer(f"❌ Noto'g'ri format! {content_type} yuboring.")
            return
        
        # Сохраняем caption если есть
        if message.caption:
            await state.update_data(caption=message.caption)
        
        # Спрашиваем про подпись (если не text)
        if content_type != "text" and not message.caption:
            await message.answer(
                "📝 Ushbu media uchun izoh qo'shasizmi?\n"
                "(Izoh yuboring yoki /skip deb yozing):",
                reply_markup=get_funnel_content_kb()
            )
            await state.set_state(FunnelStates.waiting_for_caption)
        else:
            await message.answer(
                "🔘 Keyingi qadamga o'tish tugmasi matnini kiriting\n"
                "(masalan: 'Davom etish ➡️' yoki /skip):",
                reply_markup=get_funnel_content_kb()
            )
            await state.set_state(FunnelStates.waiting_for_button_text)
    
    except Exception as e:
        logging.error(f"Error handling funnel content: {e}")
        await message.answer(
            "❌ <b>Xatolik yuz berdi</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )


@admin_router.message(FunnelStates.waiting_for_caption)
async def funnel_caption_handler(message: Message, state: FSMContext):
    """Обработка подписи к медиа"""
    if message.text.strip() != "/skip":
        await state.update_data(caption=message.text)
    
    await message.answer(
        "🔘 Keyingi qadamga o'tish tugmasi matnini kiriting\n"
        "(masalan: 'Davom etish ➡️' yoki /skip):",
        reply_markup=get_funnel_content_kb()
    )
    await state.set_state(FunnelStates.waiting_for_button_text)


@admin_router.message(FunnelStates.waiting_for_button_text)
async def funnel_button_handler(message: Message, state: FSMContext, session: AsyncSession):
    """Сохранение шага воронки"""
    try:
        data = await state.get_data()
        
        button_text = None if message.text.strip() == "/skip" else message.text.strip()
        
        # Сохраняем шаг в базу данных
        await orm_add_funnel_step(
            session,
            funnel_id=data["funnel_id"],
            step_number=data["step_number"],
            content_type=data["content_type"],
            content_data=data.get("content_data"),
            caption=data.get("caption"),
            button_text=button_text
        )
        
        step_num = data["step_number"]
        await state.update_data(step_number=step_num + 1)
        
        await message.answer(
            f"✅ {step_num}-qadam qo'shildi!\n\n"
            f"Yana qadam qo'shasizmi?",
            reply_markup=get_funnel_creation_kb()
        )
        await state.set_state(FunnelStates.adding_steps)
        
    except Exception as e:
        logging.error(f"Error saving funnel step: {e}")
        await message.answer(
            "❌ <b>Qadamni saqlashda xatolik</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )


@admin_router.message(F.text == "📂 Funnel ro'yxati")
async def funnels_list(message: Message, session: AsyncSession):
    """Список воронок"""
    try:
        from database.orm_query import select, Funnel
        
        query = select(Funnel).where(Funnel.is_active == True)
        result = await session.execute(query)
        funnels = result.scalars().all()
        
        if not funnels:
            await message.answer("🚫 Hech qanday funnel topilmadi.")
        else:
            text = "📂 <b>Aktiv funnellar:</b>\n\n"
            for funnel in funnels:
                text += f"🎯 <b>{funnel.name}</b>\n"
                text += f"🔑 Kalit: <code>{funnel.key}</code>\n"
                text += f"🔗 Link: <code>https://t.me/your_bot?start={funnel.key}</code>\n"
                text += f"📅 Yaratilgan: {funnel.created.strftime('%d.%m.%Y')}\n\n"
            
            await message.answer(text)
    except Exception as e:
        logging.error(f"Error getting funnels list: {e}")
        await message.answer("❌ Funnellar ro'yxatini olishda xatolik")


@admin_router.message(F.text == "🏷️ Tariflar")
async def subscription_plans_menu(message: Message):
    """Меню управления тарифами"""
    await message.answer(
        "💰 <b>Obuna tariflari boshqaruvi</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=get_admin_subscription_kb()
    )


@admin_router.message(F.text == "📋 Obunalar")
async def subscriptions_list(message: Message, session: AsyncSession):
    """Список активных подписок"""
    try:
        from database.orm_query import select, Subscription, User, SubscriptionPlan
        from sqlalchemy.orm import joinedload
        
        query = select(Subscription).where(
            Subscription.is_active == True
        ).options(
            joinedload(Subscription.user),
            joinedload(Subscription.plan)
        )
        
        result = await session.execute(query)
        subscriptions = result.unique().scalars().all()
        
        if not subscriptions:
            await message.answer("🚫 Hech qanday aktiv obuna topilmadi.")
        else:
            text = f"📋 <b>Aktiv obunalar ({len(subscriptions)}):</b>\n\n"
            
            for sub in subscriptions:
                text += f"👤 User: {sub.user_id}\n"
                text += f"📋 Tarif: {sub.plan.name}\n"
                text += f"💰 Narx: ${sub.plan.price_usd}\n"
                text += f"⏱ Tugash: {sub.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"✅ To'langan: {'Ha' if sub.payment_verified else 'Yoq'}\n\n"
            
            await message.answer(text)
    except Exception as e:
        logging.error(f"Error getting subscriptions: {e}")
        await message.answer("❌ Obunalar ro'yxatini olishda xatolik")


# Команда для подтверждения платежа
@admin_router.message(Command("verify_payment"))
async def verify_payment_command(message: Message, command: CommandObject, session: AsyncSession):
    """Подтверждение платежа администратором"""
    try:
        if not command.args:
            await message.answer("❌ Obuna ID ni kiriting: /verify_payment 123")
            return
        
        subscription_id = int(command.args)
        success = await SubscriptionService.verify_payment(
            session, 
            subscription_id, 
            message.bot
        )
        
        if success:
            await message.answer(
                f"✅ <b>{subscription_id} obuna uchun to'lov tasdiqlandi!</b>",
                reply_markup=get_back_to_admin_menu_kb()
            )
        else:
            await message.answer(
                f"❌ <b>{subscription_id} obuna topilmadi yoki xatolik</b>",
                reply_markup=get_back_to_admin_menu_kb()
            )
    
    except ValueError:
        await message.answer(
            "❌ <b>Noto'g'ri obuna ID formati</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )
    except Exception as e:
        logging.error(f"Error verifying payment: {e}")
        await message.answer(
            "❌ <b>To'lovni tasdiqlashda xatolik</b>",
            reply_markup=get_back_to_admin_menu_kb()
        )


# ===================== FREE LINK HANDLERS =====================

@admin_router.callback_query(F.data == "admin_free_links")
async def admin_free_links_menu(callback: CallbackQuery):
    """Free linklar menyusi"""
    try:
        await callback.message.edit_text(
            "🎁 <b>Free linklar boshqaruvi</b>\n\n"
            "Free linklar orqali foydalanuvchilarga vaqtinchalik kanalga kirish imkonini bering.",
            reply_markup=get_free_links_menu_kb()
        )
    except Exception as e:
        logging.error(f"Error in admin_free_links_menu: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data == "create_free_link")
async def create_free_link_start(callback: CallbackQuery, state: FSMContext):
    """Free link yaratishni boshlash"""
    try:
        await callback.message.edit_text(
            "📝 <b>Yangi free link yaratish</b>\n\n"
            "Free link nomini kiriting:",
            reply_markup=get_free_link_cancel_kb()
        )
        await state.set_state(FreeLinkStates.waiting_for_name)
    except Exception as e:
        logging.error(f"Error in create_free_link_start: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.message(FreeLinkStates.waiting_for_name)
async def free_link_name(message: Message, state: FSMContext):
    """Free link nomini qabul qilish"""
    try:
        await state.update_data(name=message.text)
        
        await message.answer(
            "🔑 <b>Free link kalitini kiriting</b>\n\n"
            "Bu kalit link manzilida ishlatiladi: t.me/botusername?start=KALIT\n"
            "Misol: freelink123",
            reply_markup=get_free_link_cancel_kb()
        )
        await state.set_state(FreeLinkStates.waiting_for_key)
    except Exception as e:
        logging.error(f"Error in free_link_name: {e}")
        await message.answer("❌ Xatolik yuz berdi")


@admin_router.message(FreeLinkStates.waiting_for_key)
async def free_link_key(message: Message, state: FSMContext, session: AsyncSession):
    """Free link kalitini qabul qilish"""
    try:
        key = message.text.strip()
        
        # Kalit unique ekanligini tekshirish
        existing = await orm_get_free_link_by_key(session, key)
        if existing:
            await message.answer(
                "❌ <b>Bu kalit allaqachon mavjud!</b>\n\n"
                "Boshqa kalit kiriting:",
                reply_markup=get_free_link_cancel_kb()
            )
            return
        
        await state.update_data(key=key)
        
        await message.answer(
            "👥 <b>Maksimal foydalanuvchilar sonini tanlang</b>\n\n"
            "Nechta foydalanuvchi ushbu linkdan foydalana oladi?",
            reply_markup=get_max_users_selection_kb()
        )
        await state.set_state(FreeLinkStates.waiting_for_max_uses)
    except Exception as e:
        logging.error(f"Error in free_link_key: {e}")
        await message.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("max_users_"))
async def free_link_max_users_callback(callback: CallbackQuery, state: FSMContext):
    """Maksimal foydalanuvchilar sonini callback orqali qabul qilish"""
    try:
        max_users_data = callback.data.split("_")[-1]
        
        if max_users_data == "unlimited":
            max_uses = -1
            max_uses_text = "Cheksiz"
        else:
            max_uses = int(max_users_data)
            max_uses_text = str(max_uses)
        
        await state.update_data(max_uses=max_uses)
        
        await callback.message.edit_text(
            f"✅ <b>Maksimal foydalanuvchilar:</b> {max_uses_text}\n\n"
            "⏰ <b>Muddatni tanlang</b>\n\n"
            "Foydalanuvchi necha muddat kanalda bo'ladi?",
            reply_markup=get_duration_selection_kb()
        )
        await state.set_state(FreeLinkStates.waiting_for_duration_days)
        await callback.answer()
    except Exception as e:
        logging.error(f"Error in free_link_max_users_callback: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("duration_"))
async def free_link_duration_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Muddat callback orqali qabul qilish va free link yaratish"""
    try:
        duration_data = callback.data.split("_")
        
        if duration_data[-1] == "unlimited":
            duration_days = 365000  # ~1000 yil
            duration_text = "Cheksiz"
        elif duration_data[-1] == "day":
            duration_days = int(duration_data[1])
            duration_text = f"{duration_days} kun"
        elif duration_data[-1] == "days":
            duration_days = int(duration_data[1])
            if duration_days == 3:
                duration_text = "3 kun"
            elif duration_days == 7:
                duration_text = "7 kun"
            elif duration_days == 14:
                duration_text = "2 hafta"
            elif duration_days == 30:
                duration_text = "1 oy"
            elif duration_days == 90:
                duration_text = "3 oy"
            elif duration_days == 180:
                duration_text = "6 oy"
            elif duration_days == 365:
                duration_text = "1 yil"
            else:
                duration_text = f"{duration_days} kun"
        
        # State datani olish
        data = await state.get_data()
        
        # max_uses ni olish (agar yo'q bo'lsa, default 1)
        max_uses = data.get('max_uses', 1)
        
        # Default kanal ID va invite linkni olish
        default_channel_id = os.getenv('DEFAULT_CHANNEL_ID')
        if not default_channel_id:
            await callback.message.edit_text(
                "❌ <b>Default kanal ID topilmadi!</b>\n\n"
                "Iltimos .env faylida DEFAULT_CHANNEL_ID ni sozlang.",
                reply_markup=get_free_links_menu_kb()
            )
            await state.clear()
            return
        
        # Bot orqali kanal uchun invite link yaratish
        try:
            # Permanent invite link yaratish (expire_date berilmasa)
            invite_response = await callback.bot.create_chat_invite_link(
                chat_id=default_channel_id,
                name=f"FreeLinkChannel_{data['key']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            channel_invite_link = invite_response.invite_link
            
        except Exception as e:
            logging.error(f"Error creating invite link for channel {default_channel_id}: {e}")
            await callback.message.edit_text(
                "❌ <b>Kanal uchun invite link yaratishda xatolik!</b>\n\n"
                "Bot kanalni admin qilganligini tekshiring va qaytadan urinib ko'ring.",
                reply_markup=get_free_links_menu_kb()
            )
            await state.clear()
            return
        
        # Free link yaratish
        free_link = await orm_create_free_link(
            session=session,
            key=data['key'],
            name=data['name'],
            channel_id=default_channel_id,
            channel_invite_link=channel_invite_link,
            duration_days=duration_days,
            max_uses=max_uses,
            created_by=callback.from_user.id
        )
        
        bot_username = (await callback.bot.get_me()).username
        link_url = f"https://t.me/{bot_username}?start={data['key']}"
        
        max_uses_text = "Cheksiz" if max_uses == -1 else str(max_uses)
        
        await callback.message.edit_text(
            f"✅ <b>Free link muvaffaqiyatli yaratildi!</b>\n\n"
            f"📝 <b>Nom:</b> {data['name']}\n"
            f"🔑 <b>Kalit:</b> {data['key']}\n"
            f"👥 <b>Maksimal foydalanuvchilar:</b> {max_uses_text}\n"
            f"📅 <b>Muddat:</b> {duration_text}\n"
            f"📢 <b>Kanal:</b> <code>{default_channel_id}</code>\n"
            f"🔗 <b>Kanal invite:</b> <code>{channel_invite_link}</code>\n\n"
            f"🌐 <b>Free link:</b>\n<code>{link_url}</code>",
            reply_markup=get_free_links_menu_kb()
        )
        
        await state.clear()
        await callback.answer("✅ Free link yaratildi!")
        
    except Exception as e:
        logging.error(f"Error in free_link_duration_callback: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data == "free_links_list")
async def free_links_list(callback: CallbackQuery, session: AsyncSession):
    """Free linklar ro'yxati"""
    try:
        free_links = await orm_get_all_free_links(session)
        
        if not free_links:
            await callback.message.edit_text(
                "📋 <b>Free linklar ro'yxati</b>\n\n"
                "❌ Hozircha free linklar mavjud emas.",
                reply_markup=get_free_links_menu_kb()
            )
            return
        
        await callback.message.edit_text(
            "📋 <b>Free linklar ro'yxati</b>\n\n"
            "Free link tanlang:",
            reply_markup=get_free_links_list_kb(free_links)
        )
    except Exception as e:
        logging.error(f"Error in free_links_list: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("free_link_info_"))
async def free_link_info(callback: CallbackQuery, session: AsyncSession):
    """Free link ma'lumotlari"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        status = "🟢 Faol" if free_link.is_active else "🔴 Nofaol"
        bot_username = (await callback.bot.get_me()).username
        link_url = f"https://t.me/{bot_username}?start={free_link.key}"
        
        max_uses_display = "Cheksiz" if free_link.max_uses == -1 else str(free_link.max_uses)
        
        text = (
            f"🎁 <b>Free link ma'lumotlari</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> {free_link.key}\n"
            f"📢 <b>Kanal:</b> {free_link.channel_id}\n"
            f"📅 <b>Muddat:</b> {free_link.duration_days} kun\n"
            f"📊 <b>Ishlatilgan:</b> {free_link.current_uses}/{max_uses_display}\n"
            f"📈 <b>Holat:</b> {status}\n"
            f"⏰ <b>Yaratilgan:</b> {free_link.created.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Link:</b>\n<code>{link_url}</code>"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_free_link_info_kb(free_link_id, free_link.is_active)
        )
    except Exception as e:
        logging.error(f"Error in free_link_info: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("toggle_free_link_"))
async def toggle_free_link_status(callback: CallbackQuery, session: AsyncSession):
    """Free link holatini o'zgartirish (faol/nofaol)"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        # Holatni o'zgartirish
        free_link.is_active = not free_link.is_active
        await session.commit()
        
        status_text = "yoqildi" if free_link.is_active else "o'chirildi"
        await callback.answer(f"✅ Free link {status_text}")
        
        # Ma'lumotlarni yangilash
        status = "🟢 Faol" if free_link.is_active else "🔴 Nofaol"
        bot_username = (await callback.bot.get_me()).username
        link_url = f"https://t.me/{bot_username}?start={free_link.key}"
        
        max_uses_display = "Cheksiz" if free_link.max_uses == -1 else str(free_link.max_uses)
        
        text = (
            f"🎁 <b>Free link ma'lumotlari</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> {free_link.key}\n"
            f"📢 <b>Kanal:</b> {free_link.channel_id}\n"
            f"📅 <b>Muddat:</b> {free_link.duration_days} kun\n"
            f"📊 <b>Ishlatilgan:</b> {free_link.current_uses}/{max_uses_display}\n"
            f"📈 <b>Holat:</b> {status}\n"
            f"⏰ <b>Yaratilgan:</b> {free_link.created.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Link:</b>\n<code>{link_url}</code>"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_free_link_info_kb(free_link_id, free_link.is_active)
        )
        
    except Exception as e:
        logging.error(f"Error in toggle_free_link_status: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("deactivate_free_link_"))
async def deactivate_free_link_request(callback: CallbackQuery, session: AsyncSession):
    """Free link deaktivatsiya qilish so'rovi"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        await callback.message.edit_text(
            f"🚫 <b>Free link deaktivatsiya qilish</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> {free_link.key}\n\n"
            f"⚠️ Bu freelink deaktivatsiya qilinadi. Yangi foydalanuvchilar linkdan foydalana olmaydi, "
            f"lekin mavjud foydalanuvchilar hali ham faol.\n\n"
            f"Ma'lumotlar bazada saqlanib qoladi va keyin qayta faollashtirish mumkin.\n\n"
            f"Davom etasizmi?",
            reply_markup=get_delete_confirmation_kb(free_link_id, "deactivate")
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error in deactivate_free_link_request: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("permanent_delete_free_link_"))
async def permanent_delete_free_link_request(callback: CallbackQuery, session: AsyncSession):
    """Free link butunlay o'chirish so'rovi"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        await callback.message.edit_text(
            f"🗑️ <b>Free link butunlay o'chirish</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> {free_link.key}\n\n"
            f"⚠️ <b>OGOHLANTIRISH!</b>\n"
            f"Bu freelink va unga bog'liq barcha ma'lumotlar butunlay o'chiriladi:\n"
            f"• Freelink ma'lumotlari\n"
            f"• Foydalanuvchilar statistikasi\n"
            f"• Foydalanish tarixi\n\n"
            f"❗ Bu amalni bekor qilib bo'lmaydi!\n\n"
            f"Davom etasizmi?",
            reply_markup=get_delete_confirmation_kb(free_link_id, "permanent")
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error in permanent_delete_free_link_request: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("confirm_deactivate_"))
async def confirm_deactivate_free_link(callback: CallbackQuery, session: AsyncSession):
    """Free link deaktivatsiya qilishni tasdiqlash"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish va deaktivatsiya qilish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        # Deaktivatsiya qilish
        await orm_deactivate_free_link(session, free_link_id)
        
        await callback.message.edit_text(
            f"✅ <b>Free link deaktivatsiya qilindi</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> {free_link.key}\n\n"
            f"🚫 Free link deaktivatsiya qilindi. Yangi foydalanuvchilar linkdan foydalana olmaydi.\n"
            f"Ma'lumotlar saqlanib qoldi va keyin qayta faollashtirish mumkin.",
            reply_markup=get_free_links_menu_kb()
        )
        await callback.answer("✅ Free link deaktivatsiya qilindi")
        
    except Exception as e:
        logging.error(f"Error in confirm_deactivate_free_link: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("confirm_permanent_delete_"))
async def confirm_permanent_delete_free_link(callback: CallbackQuery, session: AsyncSession):
    """Free link butunlay o'chirishni tasdiqlash"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link o'chirish
        await orm_permanent_delete_free_link(session, free_link_id)
        
        await callback.message.edit_text(
            f"✅ <b>Free link butunlay o'chirildi</b>\n\n"
            f"🗑️ Free link va unga bog'liq barcha ma'lumotlar butunlay o'chirildi.\n"
            f"Bu amal bekor qilinmaydi.",
            reply_markup=get_free_links_menu_kb()
        )
        await callback.answer("✅ Free link butunlay o'chirildi")
        
    except Exception as e:
        logging.error(f"Error in confirm_permanent_delete_free_link: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


# Eski delete_free_link funksiyasini yangilaymiz (eski callback uchun)
@admin_router.callback_query(F.data.startswith("toggle_status_"))
async def toggle_free_link_status(callback: CallbackQuery, session: AsyncSession):
    """Free link statusini o'zgartirish"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        # Statusni o'zgartirish
        if free_link.is_active:
            await orm_deactivate_free_link(session, free_link_id)
            new_status = "deaktivatsiya qilindi"
            status_emoji = "🔴"
        else:
            await orm_activate_free_link(session, free_link_id)
            new_status = "faollashtirildi"
            status_emoji = "🟢"
        
        # Yangilangan ma'lumotlarni ko'rsatish
        status_text = f"{status_emoji} {'Faol' if not free_link.is_active else 'Faol emas'}"
        max_uses_text = "Cheksiz" if free_link.max_uses == -1 else str(free_link.max_uses)
        
        await callback.message.edit_text(
            f"📋 <b>Free Link Ma'lumotlari</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> <code>{free_link.key}</code>\n"
            f"📊 <b>Status:</b> {status_text}\n"
            f"👥 <b>Maksimal foydalanuvchilar:</b> {max_uses_text}\n"
            f"📈 <b>Hozirgi foydalanuvchilar:</b> {free_link.current_uses}\n"
            f"📅 <b>Yaratilgan sana:</b> {free_link.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Freelink URL:</b>\n"
            f"<code>https://t.me/{(await callback.bot.get_me()).username}?start={free_link.key}</code>",
            reply_markup=get_free_link_info_kb(free_link.id, not free_link.is_active)
        )
        await callback.answer(f"✅ Free link {new_status}")
        
    except Exception as e:
        logging.error(f"Error in toggle_free_link_status: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_free_link(callback: CallbackQuery, session: AsyncSession):
    """Free link o'chirishni bekor qilish"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        # Free link ma'lumotlarini olish
        from database.orm_query import select, FreeLink
        query = select(FreeLink).where(FreeLink.id == free_link_id)
        result = await session.execute(query)
        free_link = result.scalar_one_or_none()
        
        if not free_link:
            await callback.answer("❌ Free link topilmadi")
            return
        
        # Freelink ma'lumotlarini ko'rsatish
        status_text = "🟢 Faol" if free_link.is_active else "🔴 Faol emas"
        max_uses_text = "Cheksiz" if free_link.max_uses == -1 else str(free_link.max_uses)
        
        await callback.message.edit_text(
            f"📋 <b>Free Link Ma'lumotlari</b>\n\n"
            f"📝 <b>Nom:</b> {free_link.name}\n"
            f"🔑 <b>Kalit:</b> <code>{free_link.key}</code>\n"
            f"📊 <b>Status:</b> {status_text}\n"
            f"👥 <b>Maksimal foydalanuvchilar:</b> {max_uses_text}\n"
            f"📈 <b>Hozirgi foydalanuvchilar:</b> {free_link.current_uses}\n"
            f"📅 <b>Yaratilgan sana:</b> {free_link.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Freelink URL:</b>\n"
            f"<code>https://t.me/{(await callback.bot.get_me()).username}?start={free_link.key}</code>",
            reply_markup=get_free_link_info_kb(free_link.id, free_link.is_active)
        )
        await callback.answer("❌ O'chirish bekor qilindi")
        
    except Exception as e:
        logging.error(f"Error in cancel_delete_free_link: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_router.callback_query(F.data.startswith("delete_free_link_"))
async def delete_free_link(callback: CallbackQuery, session: AsyncSession):
    """Free link o'chirish"""
    try:
        free_link_id = int(callback.data.split("_")[-1])
        
        await orm_delete_free_link(session, free_link_id)
        
        await callback.answer("✅ Free link o'chirildi")
        
        # Ro'yxatga qaytish
        free_links = await orm_get_all_free_links(session)
        
        if not free_links:
            await callback.message.edit_text(
                "📋 <b>Free linklar ro'yxati</b>\n\n"
                "❌ Hozircha free linklar mavjud emas.",
                reply_markup=get_free_links_menu_kb()
            )
            return
        
        await callback.message.edit_text(
            "📋 <b>Free linklar ro'yxati</b>\n\n"
            "Free link tanlang:",
            reply_markup=get_free_links_list_kb(free_links)
        )
    except Exception as e:
        logging.error(f"Error in delete_free_link: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


# Free link state uchun cancel handler
@admin_router.message(
    F.text.in_(["❌ Bekor qilish", "/cancel"]), 
    FreeLinkStates()
)
async def cancel_free_link_creation(message: Message, state: FSMContext):
    """Free link yaratishni bekor qilish"""
    await state.clear()
    await message.answer(
        "❌ <b>Free link yaratish bekor qilindi</b>",
        reply_markup=get_free_links_menu_kb()
    )


# Возврат в главное меню для всех остальных сообщений (ENG OXIRIDA BO'LISHI KERAK!)
@admin_router.message()
async def admin_unknown_message(message: Message):
    """Обработка неизвестных сообщений от админа"""
    logging.info(f"Admin {message.from_user.id} sent unknown message: {message.text}")
    await message.answer(
        "🤔 Noma'lum buyruq.\n\n"
        "Admin paneliga qaytish uchun /admin ni bosing:",
        reply_markup=get_admin_menu_kb()
    )