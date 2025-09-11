import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

from aiogram import types
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.orm_query import (
    orm_get_funnel_by_key,
    orm_start_funnel_statistic,
    orm_update_funnel_step,
    orm_complete_funnel,
    orm_get_active_subscription_plans,
    orm_get_user
)
from kbds.inline import get_funnel_next_step_kb, get_subscription_plans_kb
from kbds.reply import phone_request_kb


class FunnelService:
    """Сервис для работы с воронками"""
    
    @staticmethod
    async def start_funnel(
        message: types.Message,
        session: AsyncSession,
        funnel_key: str,
        state: Optional[FSMContext] = None
    ) -> bool:
        """Запуск воронки для пользователя"""
        try:
            # Avval foydalanuvchining telefon raqamini tekshiramiz
            user = await orm_get_user(session, message.from_user.id)
            if not user or not user.phone:
                # Telefon raqam yo'q - so'raymiz va funnel keyni saqlaymiz
                if state:
                    await state.update_data(pending_funnel_key=funnel_key)
                    from handlers.user_private import UserStates
                    await state.set_state(UserStates.waiting_for_phone)
                
                await message.answer(
                    f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
                    f"Botdan foydalanish uchun avval telefon raqamingizni ulashing:",
                    reply_markup=phone_request_kb
                )
                return True  # Telefon kiritilgandan keyin funnel davom etadi
            
            # Telefon bor - funnel ni boshlash
            return await FunnelService._start_funnel_process(message, session, funnel_key)
            
        except Exception as e:
            logging.error(f"Error starting funnel: {e}")
            await message.answer("❌ Xatolik yuz berdi")
            return False
    
    @staticmethod
    async def _start_funnel_process(
        message: types.Message,
        session: AsyncSession,
        funnel_key: str
    ) -> bool:
        """Воронка процессini boshlash (telefon raqam mavjud bo'lganda)"""
        try:
            # Получаем воронку из базы данных
            funnel = await orm_get_funnel_by_key(session, funnel_key)
            if not funnel:
                await message.answer("❌ Varonka topilmadi")
                return False
            
            # Получаем шаги воронки отдельным запросом
            from database.models import FunnelStep
            steps_query = select(FunnelStep).where(
                FunnelStep.funnel_id == funnel.id
            ).order_by(FunnelStep.step_number)
            steps_result = await session.execute(steps_query)
            steps = steps_result.scalars().all()
            
            if not steps:
                await message.answer("❌ Varonka bo'sh")
                return False
            
            # Создаем статистику для пользователя
            await orm_start_funnel_statistic(
                session, 
                message.from_user.id, 
                funnel.id
            )
            
            # Отправляем первый шаг
            await FunnelService._send_funnel_step(
                message, 
                session, 
                funnel,
                steps, 
                0
            )
            
            # Обновляем статистику для первого шага (step 0)
            await orm_update_funnel_step(
                session,
                message.from_user.id,
                funnel.id,
                0
            )
            
            logging.info(f"Started funnel '{funnel_key}' for user {message.from_user.id}")
            return True
            
        except Exception as e:
            logging.error(f"Error starting funnel process: {e}")
            await message.answer("❌ Xatolik yuz berdi")
            return False
    
    @staticmethod
    async def next_funnel_step(
        callback: types.CallbackQuery,
        session: AsyncSession,
        step_number: int
    ) -> bool:
        """Переход к следующему шагу воронки"""
        try:
            # Получаем текущую статистику пользователя
            from database.orm_query import select, FunnelStatistic, Funnel
            from sqlalchemy.orm import joinedload
            
            query = select(FunnelStatistic).where(
                FunnelStatistic.user_id == callback.from_user.id,
                FunnelStatistic.completed == False
            ).options(joinedload(FunnelStatistic.funnel))
            
            result = await session.execute(query)
            stat = result.unique().scalar_one_or_none()
            
            if not stat:
                await callback.answer("❌ Aktiv varonka topilmadi")
                return False
            
            funnel = stat.funnel
            
            # Получаем шаги воронки отдельным запросом
            from database.models import FunnelStep
            steps_query = select(FunnelStep).where(
                FunnelStep.funnel_id == funnel.id
            ).order_by(FunnelStep.step_number)
            steps_result = await session.execute(steps_query)
            steps = steps_result.scalars().all()
            
            # Проверяем, есть ли такой шаг
            logging.info(f"Step number: {step_number}, Total steps: {len(steps)}")
            if step_number >= len(steps):
                # Воронка завершена
                logging.info(f"Funnel completed for user {callback.from_user.id}")
                await orm_complete_funnel(session, callback.from_user.id, funnel.id)
                await FunnelService._send_completion_message(callback.message, session)
                await callback.answer("✅ Varonka tugallandi!")
                return True
            
            # Отмечаем предыдущий шаг как завершенный
            if step_number > 0:
                await orm_update_funnel_step(
                    session,
                    callback.from_user.id,
                    funnel.id,
                    step_number - 1,
                    mark_completed=True
                )
            
            # Убираем кнопку с предыдущего сообщения
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass  # Игнорируем ошибки редактирования
            
            # Отправляем следующий шаг
            await FunnelService._send_funnel_step(
                callback.message,
                session,
                funnel,
                steps,
                step_number
            )
            
            # Обновляем статистику для нового шага
            await orm_update_funnel_step(
                session,
                callback.from_user.id,
                funnel.id,
                step_number
            )
            
            await callback.answer()
            return True
            
        except Exception as e:
            logging.error(f"Error in next funnel step: {e}")
            await callback.answer("❌ Xatolik yuz berdi")
            return False
    
    @staticmethod
    async def _send_funnel_step(
        message: types.Message,
        session: AsyncSession,
        funnel,
        steps: list,
        step_index: int
    ):
        """Отправка конкретного шага воронки"""
        try:
            if step_index >= len(steps):
                return
            
            step = steps[step_index]
            total_steps = len(steps)
            
            # Определяем нужна ли кнопка "Далее"
            show_button = step_index < total_steps - 1
            button_text = step.button_text or "Keyingi ➡️"
            
            # Если это последний шаг, показываем кнопку "Tugallash"
            if step_index == total_steps - 1:
                show_button = True
                button_text = "✅ Tugallash"
            
            logging.info(f"Sending step {step_index + 1}/{total_steps}, show_button: {show_button}")
            
            # Создаем клавиатуру
            keyboard = None
            if show_button:
                keyboard = get_funnel_next_step_kb(
                    step_index, 
                    total_steps, 
                    button_text
                )
            
            # Отправляем контент в зависимости от типа
            if step.content_type == "text":
                await message.answer(
                    step.content_data or step.caption,
                    reply_markup=keyboard
                )
            
            elif step.content_type == "photo":
                await message.answer_photo(
                    step.content_data,
                    caption=step.caption,
                    reply_markup=keyboard
                )
            
            elif step.content_type == "video":
                await message.answer_video(
                    step.content_data,
                    caption=step.caption,
                    reply_markup=keyboard
                )
            
            elif step.content_type == "audio":
                await message.answer_audio(
                    step.content_data,
                    caption=step.caption,
                    reply_markup=keyboard
                )
            
            elif step.content_type == "document":
                await message.answer_document(
                    step.content_data,
                    caption=step.caption,
                    reply_markup=keyboard
                )
            
            # Фиксируем время начала просмотра
            start_time = datetime.now()
            
            # Обновляем статистику шага - ДОБАВЛЯЕМ ЭТО!
            # Нужно получить user_id из message или передать отдельно
            # Пока добавим логирование
            logging.info(f"Step {step_index + 1} sent to user, but step statistics not updated here")
            
        except Exception as e:
            logging.error(f"Error sending funnel step: {e}")
            await message.answer("❌ Xatolik yuz berdi")
    
    @staticmethod
    async def _send_completion_message(
        message: types.Message,
        session: AsyncSession
    ):
        """Отправка сообщения о завершении воронки"""
        try:
            # Получаем активные планы подписки
            plans = await orm_get_active_subscription_plans(session)
            
            if plans:
                keyboard = get_subscription_plans_kb(plans)
                await message.answer(
                    "🎉 <b>Tabriklaymiz!</b> Voronkani muvaffaqiyatli tugalladingiz!\n\n"
                    "📚 Ushbu darslikdan olgan bilimlaringizni sinab ko'ring!\n"
                    "🧪 Test topshirib, bilim darajangizni aniqlang.\n\n"
                    "💎 Premium obunaga o'tib, ko'proq test va amaliy mashqlar bilan tayyorlaning:",
                    reply_markup=keyboard
                )
            else:
                # Test tugmasi bilan
                from kbds.inline import get_back_to_menu_kb
                keyboard = get_back_to_menu_kb()
                await message.answer(
                    "🎉 <b>Tabriklaymiz!</b> Voronkani muvaffaqiyatli tugalladingiz!\n\n"
                    "📚 Ushbu darslikdan olgan bilimlaringizni sinab ko'ring!\n"
                    "🧪 Test topshirib, bilim darajangizni aniqlang.\n\n"
                    "📝 Test boshlash uchun: /test\n"
                    "📖 Boshqa darsliklar uchun: /start",
                    reply_markup=keyboard
                )
        
        except Exception as e:
            logging.error(f"Error sending completion message: {e}")


# Legacy support - сохраняем старую функцию для обратной совместимости
async def send_funnel_messages(message: types.Message, key: str, session: AsyncSession = None):
    """Legacy функция для запуска воронки"""
    if session:
        return await FunnelService.start_funnel(message, session, key)
    else:
        # Старый способ с JSON файлами
        FUNNELS_DIR = "funnels"
        file_path = os.path.join(FUNNELS_DIR, f"{key}.json")
        if not os.path.exists(file_path):
            await message.answer("❌ Bunday varonka topilmadi")
            logging.warning(f"Funnel not found: {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data.get("messages", [])
            if not messages:
                await message.answer("❌ Varonkada xabarlar topilmadi")
                logging.warning(f"No messages in funnel: {file_path}")
                return

            async def send_all():
                for text in messages:
                    await message.answer(text)
                    await asyncio.sleep(1.5)

            asyncio.create_task(send_all())
            logging.info(f"Started funnel for user {message.from_user.id} with key {key}")

        except Exception as e:
            await message.answer("❌ Xatolik yuz berdi")
            logging.error(f"Error sending funnel: {e}")
