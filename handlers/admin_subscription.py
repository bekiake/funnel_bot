import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from filters.chat_types import ChatTypeFilter, IsAdmin
from kbds.reply import admin_kb
from database.orm_query import (
    orm_create_subscription_plan,
    orm_get_active_subscription_plans
)


class SubscriptionPlanStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_duration = State() 
    waiting_for_price_usd = State()
    waiting_for_price_uzs = State()
    waiting_for_channel_id = State()


admin_subscription_router = Router()
admin_subscription_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_subscription_router.callback_query(F.data == "admin_plans_list")
async def admin_plans_list(callback: CallbackQuery, session: AsyncSession):
    """Список тарифных планов"""
    try:
        plans = await orm_get_active_subscription_plans(session)
        
        if not plans:
            text = "🚫 Hech qanday tarif mavjud emas."
        else:
            text = f"💰 <b>Tarif rejalar ({len(plans)}):</b>\n\n"
            
            for i, plan in enumerate(plans, 1):
                text += f"{i}. <b>{plan.name}</b>\n"
                text += f"   ⏱ Muddati: {plan.duration_days} kun\n"
                text += f"   💰 Narxi: ${plan.price_usd} / {plan.price_uzs:,} so'm\n"
                text += f"   📺 Kanal ID: {plan.channel_id}\n"
                text += f"   ✅ Aktiv: {'Ha' if plan.is_active else 'Yoq'}\n\n"
        
        await callback.message.edit_text(text)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing plans list: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@admin_subscription_router.callback_query(F.data == "admin_add_plan")
async def admin_add_plan_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания нового тарифного плана"""
    await callback.message.edit_text(
        "➕ <b>Yangi tarif yaratish</b>\n\n"
        "Tarif nomini kiriting:"
    )
    await state.set_state(SubscriptionPlanStates.waiting_for_name)
    await callback.answer()


@admin_subscription_router.message(SubscriptionPlanStates.waiting_for_name)
async def admin_plan_name(message: Message, state: FSMContext):
    """Ввод названия тарифа"""
    await state.update_data(name=message.text.strip())
    await message.answer(
        "⏱ Tarif muddatini kunlarda kiriting (masalan: 30):"
    )
    await state.set_state(SubscriptionPlanStates.waiting_for_duration)


@admin_subscription_router.message(SubscriptionPlanStates.waiting_for_duration)
async def admin_plan_duration(message: Message, state: FSMContext):
    """Ввод продолжительности тарифа"""
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            await message.answer("❌ Muddati ijobiy son bo'lishi kerak!")
            return
        
        await state.update_data(duration_days=duration)
        await message.answer(
            "💵 Narxni USD da kiriting (masalan: 10.99):"
        )
        await state.set_state(SubscriptionPlanStates.waiting_for_price_usd)
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Faqat raqam kiriting.")


@admin_subscription_router.message(SubscriptionPlanStates.waiting_for_price_usd)
async def admin_plan_price_usd(message: Message, state: FSMContext):
    """Ввод цены в USD"""
    try:
        price_usd = float(message.text.strip())
        if price_usd <= 0:
            await message.answer("❌ Narx ijobiy son bo'lishi kerak!")
            return
        
        await state.update_data(price_usd=price_usd)
        await message.answer(
            "🇺🇿 Narxni UZS da kiriting (masalan: 130000):"
        )
        await state.set_state(SubscriptionPlanStates.waiting_for_price_uzs)
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Raqam kiriting (masalan: 10.99).")


@admin_subscription_router.message(SubscriptionPlanStates.waiting_for_price_uzs)
async def admin_plan_price_uzs(message: Message, state: FSMContext):
    """Ввод цены в UZS"""
    try:
        price_uzs = int(message.text.strip())
        if price_uzs <= 0:
            await message.answer("❌ Narx ijobiy son bo'lishi kerak!")
            return
        
        await state.update_data(price_uzs=price_uzs)
        await message.answer(
            "📺 Kanal ID sini kiriting (masalan: -1001234567890):\n\n"
            "💡 Kanal ID ni olish uchun:\n"
            "1. Kanalga @userinfobot ni qo'shing\n"
            "2. Bot sizga kanal ID sini beradi"
        )
        await state.set_state(SubscriptionPlanStates.waiting_for_channel_id)
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Butun raqam kiriting.")


@admin_subscription_router.message(SubscriptionPlanStates.waiting_for_channel_id)
async def admin_plan_channel_id(message: Message, state: FSMContext, session: AsyncSession):
    """Сохранение тарифного плана"""
    try:
        channel_id = int(message.text.strip())
        
        data = await state.get_data()
        
        # Создаем тарифный план
        plan = await orm_create_subscription_plan(
            session,
            name=data["name"],
            duration_days=data["duration_days"],
            price_usd=data["price_usd"],
            price_uzs=data["price_uzs"],
            channel_id=channel_id
        )
        
        # Сообщение об успешном создании
        text = f"✅ <b>Tarif muvaffaqiyatli yaratildi!</b>\n\n"
        text += f"📋 Nomi: {plan.name}\n"
        text += f"⏱ Muddati: {plan.duration_days} kun\n"
        text += f"💰 Narxi: ${plan.price_usd} / {plan.price_uzs:,} so'm\n"
        text += f"📺 Kanal ID: {plan.channel_id}\n"
        text += f"🆔 Tarif ID: {plan.id}"
        
        await message.answer(text, reply_markup=admin_kb)
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri kanal ID formati! Raqam kiriting.")
    except Exception as e:
        logging.error(f"Error creating subscription plan: {e}")
        await message.answer("❌ Tarif yaratishda xatolik")
        await state.clear()


@admin_subscription_router.callback_query(F.data == "admin_stats")
async def admin_subscription_stats(callback: CallbackQuery, session: AsyncSession):
    """Статистика по подпискам"""
    try:
        from database.orm_query import select, Subscription, func
        
        # Общее количество подписок
        total_query = select(func.count()).select_from(Subscription)
        total_result = await session.execute(total_query)
        total_subs = total_result.scalar() or 0
        
        # Активные подписки
        active_query = select(func.count()).select_from(Subscription).where(
            Subscription.is_active == True
        )
        active_result = await session.execute(active_query)
        active_subs = active_result.scalar() or 0
        
        # Подтвержденные платежи
        verified_query = select(func.count()).select_from(Subscription).where(
            Subscription.payment_verified == True
        )
        verified_result = await session.execute(verified_query)
        verified_subs = verified_result.scalar() or 0
        
        text = f"📊 <b>Obuna statistikasi</b>\n\n"
        text += f"📋 Jami obunalar: {total_subs}\n"
        text += f"✅ Aktiv obunalar: {active_subs}\n"
        text += f"💳 To'langan obunalar: {verified_subs}\n"
        text += f"⏳ To'lanmagan: {total_subs - verified_subs}\n"
        
        if total_subs > 0:
            text += f"\n📈 Konversiya: {(verified_subs / total_subs * 100):.1f}%"
        
        await callback.message.edit_text(text)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error getting subscription stats: {e}")
        await callback.answer("❌ Xatolik yuz berdi")
