import math
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import User


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



async def orm_get_users_count(session: AsyncSession) -> int:
    from sqlalchemy import func
    query = select(func.count()).select_from(User)
    result = await session.execute(query)
    return result.scalar() or 0

async def orm_get_all_users(session: AsyncSession) -> list:
    query = select(User.user_id)
    result = await session.execute(query)
    return [row[0] for row in result.fetchall()]

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


