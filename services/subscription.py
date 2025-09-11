import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import types, Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_get_active_subscription_plans,
    orm_create_subscription,
    orm_verify_payment,
    orm_get_user_active_subscriptions,
    orm_expire_subscription
)
from kbds.inline import (
    get_subscription_plans_kb,
    get_payment_kb,
    get_payment_verification_kb,
    get_back_to_menu_kb
)


class SubscriptionService:
    """Сервис для работы с подписками"""
    
    @staticmethod
    async def show_subscription_plans(
        message: types.Message,
        session: AsyncSession
    ):
        """Показать доступные планы подписки"""
        try:
            plans = await orm_get_active_subscription_plans(session)
            
            if not plans:
                await message.answer(
                    "🚫 Hozirda hech qanday tarif mavjud emas.",
                    reply_markup=get_back_to_menu_kb()
                )
                return
            
            text = "💎 <b>Premium obuna tariflari:</b>\n\n"
            
            for plan in plans:
                text += f"📋 <b>{plan.name}</b>\n"
                text += f"⏱ Muddati: {plan.duration_days} kun\n"
                text += f"💰 Narxi: ${plan.price_usd} / {plan.price_uzs:,} so'm\n\n"
            
            text += "Tarifni tanlang:"
            
            keyboard = get_subscription_plans_kb(plans)
            await message.answer(text, reply_markup=keyboard)
            
        except Exception as e:
            logging.error(f"Error showing subscription plans: {e}")
            await message.answer("❌ Xatolik yuz berdi")
    
    @staticmethod
    async def get_user_subscriptions(session: AsyncSession, user_id: int):
        """Получить все подписки пользователя"""
        try:
            return await orm_get_user_active_subscriptions(session, user_id)
        except Exception as e:
            logging.error(f"Error getting user subscriptions: {e}")
            return []
    
    @staticmethod
    async def select_plan(
        callback: types.CallbackQuery,
        session: AsyncSession,
        plan_id: int
    ):
        """Выбор плана подписки"""
        try:
            from database.orm_query import orm_get_subscription_plan_by_id
            
            # Получаем план
            plan = await orm_get_subscription_plan_by_id(session, plan_id)
            
            if not plan:
                await callback.answer("❌ Tarif topilmadi")
                return
            
            # Создаем подписку (пока не оплаченную)
            expires_at = datetime.now() + timedelta(days=plan.duration_days)
            subscription = await orm_create_subscription(
                session,
                callback.from_user.id,
                plan.id,
                expires_at
            )
            
            # Формируем сообщение о тарифе
            text = f"📋 <b>{plan.name}</b>\n\n"
            text += f"⏱ Muddati: {plan.duration_days} kun\n"
            text += f"💰 Narxi: ${plan.price_usd} / {plan.price_uzs:,} so'm\n\n"
            text += "💳 To'lov qilish uchun pastdagi tugmani bosing.\n"
            text += "To'lovdan so'ng admin tomonidan tasdiqlanadi."
            
            keyboard = get_payment_kb(
                subscription.id,
                plan.price_usd,
                plan.price_uzs
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
            
        except Exception as e:
            logging.error(f"Error selecting plan: {e}")
            await callback.answer("❌ Xatolik yuz berdi")
    
    @staticmethod
    async def process_payment(
        callback: types.CallbackQuery,
        session: AsyncSession,
        subscription_id: int
    ):
        """Обработка платежа"""
        try:
            from database.orm_query import select, Subscription, SubscriptionPlan
            from sqlalchemy.orm import joinedload
            
            # Получаем подписку
            query = select(Subscription).where(
                Subscription.id == subscription_id,
                Subscription.user_id == callback.from_user.id
            ).options(joinedload(Subscription.plan))
            
            result = await session.execute(query)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                await callback.answer("❌ Obuna topilmadi")
                return
            
            plan = subscription.plan
            
            # Сообщение для пользователя
            text = f"💳 <b>To'lov ma'lumotlari</b>\n\n"
            text += f"📋 Tarif: {plan.name}\n"
            text += f"💰 Summa: ${plan.price_usd} / {plan.price_uzs:,} so'm\n\n"
            text += f"💳 <b>To'lov qilish:</b>\n"
            text += f"1. Yuqoridagi summani quyidagi karta raqamiga o'tkazing\n"
            text += f"2. To'lov tasdig'ini admin @username ga yuboring\n"
            text += f"3. Admin tasdiqlashidan so'ng kanalga kirish uchun link yuboriladi\n\n"
            text += f"🏦 <b>Karta raqami:</b> <code>8600 1234 5678 9012</code>\n"
            text += f"👤 <b>Karta egasi:</b> EXAMPLE NAME\n\n"
            text += f"📝 <b>Obuna ID:</b> <code>{subscription.id}</code>\n"
            text += f"(Ushbu ID ni admin ga jo'nating)"
            
            keyboard = get_payment_verification_kb(subscription.id)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
            
            # Уведомляем админов о новом платеже
            await SubscriptionService._notify_admins_about_payment(
                callback.bot,
                subscription,
                plan
            )
            
        except Exception as e:
            logging.error(f"Error processing payment: {e}")
            await callback.answer("❌ Xatolik yuz berdi")
    
    @staticmethod
    async def verify_payment(
        session: AsyncSession,
        subscription_id: int,
        bot: Bot
    ) -> bool:
        """Подтверждение платежа администратором"""
        try:
            from database.orm_query import select, Subscription, SubscriptionPlan
            from sqlalchemy.orm import joinedload
            
            # Получаем подписку
            query = select(Subscription).where(
                Subscription.id == subscription_id
            ).options(joinedload(Subscription.plan))
            
            result = await session.execute(query)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return False
            
            # Подтверждаем платеж
            success = await orm_verify_payment(session, subscription_id)
            if not success:
                return False
            
            # Создаем ссылку для канала
            invite_link = await SubscriptionService._create_channel_invite_link(
                bot,
                subscription.plan.channel_id,
                subscription.expires_at
            )
            
            if invite_link:
                # Сохраняем ссылку
                subscription.invite_link = invite_link
                await session.commit()
                
                # Отправляем ссылку пользователю
                await SubscriptionService._send_invite_link(
                    bot,
                    subscription.user_id,
                    subscription.plan,
                    invite_link
                )
            
            return True
            
        except Exception as e:
            logging.error(f"Error verifying payment: {e}")
            return False
    
    @staticmethod
    async def _create_channel_invite_link(
        bot: Bot,
        channel_id: int,
        expires_at: datetime
    ) -> Optional[str]:
        """Создание временной ссылки для канала"""
        try:
            # Создаем ссылку с лимитом на одного пользователя
            invite_link = await bot.create_chat_invite_link(
                chat_id=channel_id,
                expire_date=expires_at,
                member_limit=1
            )
            return invite_link.invite_link
            
        except TelegramAPIError as e:
            logging.error(f"Error creating invite link: {e}")
            return None
    
    @staticmethod
    async def _send_invite_link(
        bot: Bot,
        user_id: int,
        plan,
        invite_link: str
    ):
        """Отправка ссылки пользователю"""
        try:
            text = f"✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
            text += f"📋 Tarif: {plan.name}\n"
            text += f"⏱ Muddati: {plan.duration_days} kun\n\n"
            text += f"🔗 <b>Kanalga kirish:</b>\n"
            text += f"{invite_link}\n\n"
            text += f"⚠️ <b>Diqqat:</b> Ushbu link faqat siz uchun yaratilgan va "
            text += f"muddati tugagandan so'ng avtomatik bekor qilinadi."
            
            await bot.send_message(user_id, text)
            
        except TelegramAPIError as e:
            logging.error(f"Error sending invite link to user {user_id}: {e}")
    
    @staticmethod
    async def _notify_admins_about_payment(
        bot: Bot,
        subscription,
        plan
    ):
        """Уведомление админов о новом платеже"""
        try:
            admin_ids = bot.my_admins_list if hasattr(bot, 'my_admins_list') else []
            
            text = f"💳 <b>Yangi to'lov!</b>\n\n"
            text += f"👤 Foydalanuvchi: {subscription.user_id}\n"
            text += f"📋 Tarif: {plan.name}\n"
            text += f"💰 Summa: ${plan.price_usd} / {plan.price_uzs:,} so'm\n"
            text += f"📝 Obuna ID: {subscription.id}\n\n"
            text += f"To'lovni tasdiqlash uchun: /verify_payment {subscription.id}"
            
            for admin_id in admin_ids:
                try:
                    await bot.send_message(admin_id, text)
                except TelegramAPIError:
                    continue
                    
        except Exception as e:
            logging.error(f"Error notifying admins: {e}")
    
    @staticmethod
    async def check_and_expire_subscriptions(
        session: AsyncSession,
        bot: Bot
    ):
        """Проверка и отключение просроченных подписок"""
        try:
            from database.orm_query import select, Subscription
            
            # Получаем просроченные подписки
            query = select(Subscription).where(
                Subscription.is_active == True,
                Subscription.expires_at <= datetime.now()
            )
            
            result = await session.execute(query)
            expired_subscriptions = result.scalars().all()
            
            for subscription in expired_subscriptions:
                try:
                    # Отключаем подписку
                    await orm_expire_subscription(session, subscription.id)
                    
                    # Уведомляем пользователя
                    await bot.send_message(
                        subscription.user_id,
                        f"⏰ Sizning premium obunangiz muddati tugadi.\n"
                        f"Davom etish uchun yangi obuna sotib oling."
                    )
                    
                    logging.info(f"Expired subscription {subscription.id} for user {subscription.user_id}")
                    
                except Exception as e:
                    logging.error(f"Error expiring subscription {subscription.id}: {e}")
                    continue
            
        except Exception as e:
            logging.error(f"Error checking expired subscriptions: {e}")
