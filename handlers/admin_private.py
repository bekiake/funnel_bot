import logging
import os
import json
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
    get_subscriptions_list_kb, get_subscription_details_kb
)
from services.subscription import SubscriptionService
from database.orm_query import (
    orm_get_users_count,
    orm_get_all_users,
    send_message_to_all_users,
    orm_create_funnel,
    orm_add_funnel_step,
    orm_create_subscription_plan,
    orm_get_active_subscription_plans
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
    """Список пользователей с inline клавиатурой"""
    try:
        users = await orm_get_all_users(session)
        if users:
            text = f"👥 <b>Foydalanuvchilar ro'yxati</b>\n\n"
            text += f"📊 Jami: <b>{len(users)}</b> ta foydalanuvchi\n\n"
            text += "Profil ko'rish uchun ismga bosing:"
            
            await callback.message.edit_text(
                text, 
                reply_markup=get_users_list_kb(users, page=0)
            )
        else:
            await callback.message.edit_text(
                "🚫 Hech qanday foydalanuvchi topilmadi",
                reply_markup=get_back_to_admin_menu_kb()
            )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting users: {e}")
        await callback.answer("❌ Foydalanuvchilarni olishda xatolik")


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
        
        await callback.message.edit_text(text, reply_markup=get_admin_menu_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting subscriptions: {e}")
        await callback.answer("❌ Obunalar ro'yxatini olishda xatolik")


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
        users = await orm_get_all_users(session)
        
        if users:
            text = f"👥 <b>Foydalanuvchilar ro'yxati</b>\n\n"
            text += f"📊 Jami: <b>{len(users)}</b> ta foydalanuvchi\n\n"
            text += "Profil ko'rish uchun ismga bosing:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_users_list_kb(users, page=page)
            )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error in users pagination: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


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
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(FunnelStates.waiting_for_name)


@admin_router.message(FunnelStates.waiting_for_name)
async def funnel_create_name(message: Message, state: FSMContext):
    """Ввод названия воронки"""
    await state.update_data(name=message.text.strip())
    await message.answer(
        "🔑 Funnel kalitini kiriting (masalan: python_course):\n\n"
        "Bu kalit orqali foydalanuvchilar funnel ga kirishadi."
    )
    await state.set_state(FunnelStates.waiting_for_key)


@admin_router.message(FunnelStates.waiting_for_key)
async def funnel_create_key(message: Message, state: FSMContext):
    """Ввод ключа воронки"""
    key = message.text.strip().lower()
    await state.update_data(key=key)
    await message.answer(
        "📝 Funnel haqida qisqacha tavsif kiriting "
        "(yoki /skip deb yozing):"
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
    await callback.message.edit_text("📝 Matn xabarini yuboring:")
    await state.update_data(content_type="text")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_photo")
async def funnel_add_photo_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление фото в воронку"""
    await callback.message.edit_text("📷 Rasmni yuboring:")
    await state.update_data(content_type="photo")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_video")
async def funnel_add_video_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление видео в воронку"""
    await callback.message.edit_text("🎥 Videoni yuboring:")
    await state.update_data(content_type="video")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_audio")
async def funnel_add_audio_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление аудио в воронку"""
    await callback.message.edit_text("🎵 Audioni yuboring:")
    await state.update_data(content_type="audio")
    await state.set_state(FunnelStates.waiting_for_content)
    await callback.answer()


@admin_router.callback_query(F.data == "funnel_add_document")
async def funnel_add_document_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление документа в воронку"""
    await callback.message.edit_text("📎 Faylni yuboring:")
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
                "(Izoh yuboring yoki /skip deb yozing):"
            )
            await state.set_state(FunnelStates.waiting_for_caption)
        else:
            await message.answer(
                "🔘 Keyingi qadamga o'tish tugmasi matnini kiriting\n"
                "(masalan: 'Davom etish ➡️' yoki /skip):"
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
        "(masalan: 'Davom etish ➡️' yoki /skip):"
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


# Возврат в главное меню для всех остальных сообщений
@admin_router.message()
async def admin_unknown_message(message: Message):
    """Обработка неизвестных сообщений от админа"""
    logging.info(f"Admin {message.from_user.id} sent unknown message: {message.text}")
    await message.answer(
        "🤔 Noma'lum buyruq.\n\n"
        "Admin paneliga qaytish uchun /admin ni bosing:",
        reply_markup=get_admin_menu_kb()
    )