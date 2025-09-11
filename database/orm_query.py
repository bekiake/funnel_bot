import math
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from database.models import User, Funnel, FunnelStep, FunnelStatistic, SubscriptionPlan, Subscription


# User operations
async def orm_add_user(
    session: AsyncSession,
    user_id: int,
    full_name: str | None = None,
    phone: str | None = None,
):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            User(user_id=user_id, full_name=full_name, phone=phone)
        )
        await session.commit()


async def orm_get_user(session: AsyncSession, user_id: int) -> User | None:
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Foydalanuvchini ID bo'yicha olish (subscriptions bilan)"""
    query = select(User).options(joinedload(User.subscriptions)).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()


async def orm_get_users_count(session: AsyncSession) -> int:
    query = select(func.count()).select_from(User)
    result = await session.execute(query)
    return result.scalar() or 0


async def orm_get_all_users(session: AsyncSession) -> list[User]:
    """Barcha foydalanuvchilarni olish"""
    query = select(User).order_by(User.created.desc())
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_user_funnel_stats(session: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Foydalanuvchi uchun funnel statistikasini olish"""
    # Jami boshlangan funnellar soni
    total_query = select(func.count(FunnelStatistic.id)).where(
        FunnelStatistic.user_id == user_id
    )
    total_result = await session.execute(total_query)
    total_started = total_result.scalar() or 0
    
    # Yakunlangan funnellar soni
    completed_query = select(func.count(FunnelStatistic.id)).where(
        FunnelStatistic.user_id == user_id,
        FunnelStatistic.completed == True
    )
    completed_result = await session.execute(completed_query)
    total_completed = completed_result.scalar() or 0
    
    return {
        'total_started': total_started,
        'total_completed': total_completed,
        'completion_rate': round(total_completed / total_started * 100, 1) if total_started > 0 else 0
    }


# Funnel operations
async def orm_create_funnel(
    session: AsyncSession,
    name: str,
    key: str,
    description: str | None = None
) -> Funnel:
    funnel = Funnel(name=name, key=key, description=description)
    session.add(funnel)
    await session.commit()
    await session.refresh(funnel)
    return funnel


async def orm_get_funnel_by_key(session: AsyncSession, key: str) -> Funnel | None:
    query = select(Funnel).where(Funnel.key == key, Funnel.is_active == True).options(
        joinedload(Funnel.steps)
    )
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()


async def orm_get_funnel_by_id(session: AsyncSession, funnel_id: int) -> Funnel | None:
    """Получить воронку по ID"""
    query = select(Funnel).where(Funnel.id == funnel_id).options(
        joinedload(Funnel.steps)
    )
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()


async def orm_get_funnel_statistics(session: AsyncSession, funnel_id: int) -> Dict[str, Any]:
    """Получить статистику воронки"""
    try:
        import logging
        logging.info(f"Getting stats for funnel_id: {funnel_id}")
        
        # Общее количество начавших воронку
        total_query = select(func.count(FunnelStatistic.id)).where(
            FunnelStatistic.funnel_id == funnel_id
        )
        total_result = await session.execute(total_query)
        total_started = total_result.scalar() or 0
        logging.info(f"Total started: {total_started}")
        
        # Количество завершивших
        completed_query = select(func.count(FunnelStatistic.id)).where(
            FunnelStatistic.funnel_id == funnel_id,
            FunnelStatistic.completed == True
        )
        completed_result = await session.execute(completed_query)
        completed = completed_result.scalar() or 0
        logging.info(f"Completed: {completed}")
        
        # В процессе
        in_progress = total_started - completed
        
        # Процент завершения
        completion_rate = (completed / total_started * 100) if total_started > 0 else 0
        
        stats = {
            'total_started': total_started,
            'completed': completed,
            'in_progress': in_progress,
            'completion_rate': completion_rate
        }
        logging.info(f"Final stats: {stats}")
        return stats
    except Exception as e:
        import logging
        logging.error(f"Error in orm_get_funnel_statistics: {e}")
        return {
            'total_started': 0,
            'completed': 0,
            'in_progress': 0,
            'completion_rate': 0
        }


async def orm_delete_funnel(session: AsyncSession, funnel_id: int) -> bool:
    """Удалить воронку и все связанные данные"""
    try:
        # Сначала удаляем статистику воронки
        delete_stats_query = delete(FunnelStatistic).where(FunnelStatistic.funnel_id == funnel_id)
        await session.execute(delete_stats_query)
        
        # Удаляем шаги воронки
        delete_steps_query = delete(FunnelStep).where(FunnelStep.funnel_id == funnel_id)
        await session.execute(delete_steps_query)
        
        # Удаляем саму воронку
        delete_funnel_query = delete(Funnel).where(Funnel.id == funnel_id)
        await session.execute(delete_funnel_query)
        
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        return False


async def orm_add_funnel_step(
    session: AsyncSession,
    funnel_id: int,
    step_number: int,
    content_type: str,
    content_data: str | None = None,
    caption: str | None = None,
    button_text: str | None = None
) -> FunnelStep:
    step = FunnelStep(
        funnel_id=funnel_id,
        step_number=step_number,
        content_type=content_type,
        content_data=content_data,
        caption=caption,
        button_text=button_text
    )
    session.add(step)
    await session.commit()
    await session.refresh(step)
    return step


# Funnel Statistics operations
async def orm_start_funnel_statistic(
    session: AsyncSession,
    user_id: int,
    funnel_id: int
) -> FunnelStatistic:
    # Проверяем, есть ли уже незавершенная статистика
    query = select(FunnelStatistic).where(
        FunnelStatistic.user_id == user_id,
        FunnelStatistic.funnel_id == funnel_id,
        FunnelStatistic.completed == False
    )
    result = await session.execute(query)
    existing_stat = result.scalar_one_or_none()
    
    if existing_stat:
        return existing_stat
    
    stat = FunnelStatistic(
        user_id=user_id,
        funnel_id=funnel_id,
        current_step=0,
        step_statistics={}
    )
    session.add(stat)
    await session.commit()
    await session.refresh(stat)
    return stat


async def orm_update_funnel_step(
    session: AsyncSession,
    user_id: int,
    funnel_id: int,
    step_number: int,
    view_time: float | None = None,
    mark_completed: bool = False
) -> bool:
    query = select(FunnelStatistic).where(
        FunnelStatistic.user_id == user_id,
        FunnelStatistic.funnel_id == funnel_id,
        FunnelStatistic.completed == False
    )
    result = await session.execute(query)
    stat = result.scalar_one_or_none()
    
    if not stat:
        import logging
        logging.error(f"No active funnel statistic found for user {user_id}, funnel {funnel_id}")
        return False
    
    # Обновляем текущий шаг (только если не завершаем предыдущий)
    if not mark_completed:
        stat.current_step = step_number
    
    # Обновляем статистику по шагам
    if not stat.step_statistics:
        stat.step_statistics = {}
    
    # КОПИРУЕМ существующую статистику для изменения
    current_stats = dict(stat.step_statistics) if stat.step_statistics else {}
    
    step_key = str(step_number)
    if step_key not in current_stats:
        current_stats[step_key] = {
            'start_time': datetime.now().isoformat(),
            'view_time': 0,
            'completed': False
        }
        import logging
        logging.info(f"Created new step {step_number} for user {user_id}")
    
    if view_time:
        current_stats[step_key]['view_time'] += view_time
    
    # Отмечаем шаг как завершенный
    if mark_completed:
        current_stats[step_key]['completed'] = True
        import logging
        logging.info(f"Marked step {step_number} as completed for user {user_id}")
    
    # ПОЛНОСТЬЮ ЗАМЕНЯЕМ JSON объект
    stat.step_statistics = current_stats
    
    # Принудительно помечаем объект как измененный
    from sqlalchemy.orm import Session
    session.add(stat)
    await session.commit()
    
    import logging
    logging.info(f"Updated step_statistics: {current_stats}")
    return True


async def orm_complete_funnel(
    session: AsyncSession,
    user_id: int,
    funnel_id: int
) -> bool:
    query = select(FunnelStatistic).where(
        FunnelStatistic.user_id == user_id,
        FunnelStatistic.funnel_id == funnel_id,
        FunnelStatistic.completed == False
    )
    result = await session.execute(query)
    stat = result.scalar_one_or_none()
    
    if not stat:
        return False
    
    stat.completed = True
    stat.completed_at = datetime.now()
    await session.commit()
    return True


# Subscription operations
async def orm_create_subscription_plan(
    session: AsyncSession,
    name: str,
    duration_days: int,
    price_usd: float,
    price_uzs: int,
    channel_id: int
) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        name=name,
        duration_days=duration_days,
        price_usd=price_usd,
        price_uzs=price_uzs,
        channel_id=channel_id
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def orm_get_active_subscription_plans(session: AsyncSession) -> list[SubscriptionPlan]:
    query = select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_create_subscription(
    session: AsyncSession,
    user_id: int,
    plan_id: int,
    expires_at: datetime,
    invite_link: str | None = None
) -> Subscription:
    subscription = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        expires_at=expires_at,
        invite_link=invite_link
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def orm_verify_payment(
    session: AsyncSession,
    subscription_id: int
) -> bool:
    query = select(Subscription).where(Subscription.id == subscription_id)
    result = await session.execute(query)
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        return False
    
    subscription.payment_verified = True
    await session.commit()
    return True


async def orm_get_user_active_subscriptions(
    session: AsyncSession,
    user_id: int
) -> list[Subscription]:
    query = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.is_active == True,
        Subscription.expires_at > datetime.now()
    ).options(joinedload(Subscription.plan))
    result = await session.execute(query)
    return result.unique().scalars().all()


async def orm_expire_subscription(
    session: AsyncSession,
    subscription_id: int
) -> bool:
    query = select(Subscription).where(Subscription.id == subscription_id)
    result = await session.execute(query)
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        return False
    
    subscription.is_active = False
    await session.commit()
    return True


# Broadcasting operations
async def send_message_to_all_users(
    bot,
    session: AsyncSession,
    text: str = None,
    photo: str = None,
    video: str = None,
    document: str = None,
    caption: str = None
):
    user_ids = await orm_get_all_users(session)
    import asyncio
    from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
    tasks = []
    for user_id in user_ids:
        async def send(uid):
            try:
                if photo:
                    await bot.send_photo(uid, photo, caption=caption)
                elif video:
                    await bot.send_video(uid, video, caption=caption)
                elif document:
                    await bot.send_document(uid, document, caption=caption)
                elif text:
                    await bot.send_message(uid, text)
            except (TelegramAPIError, TelegramNetworkError):
                pass  # bloklangan yoki xato bo'lsa, o'tkazib yuboriladi
        tasks.append(asyncio.create_task(send(user_id)))
    await asyncio.gather(*tasks)


