import asyncio
import os
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from dotenv import find_dotenv, load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv(find_dotenv())

from middlewares.db import DataBaseSession
from database.engine import create_db, session_maker
from handlers.user_private import user_private_router
from handlers.admin_private import admin_router
from handlers.admin_subscription import admin_subscription_router
from services.subscription import SubscriptionService
from services.scheduler import FreeLinkScheduler

from common.bot_cmds_list import private

ALLOWED_UPDATES = ['message', 'edited_message', 'callback_query']

bot = Bot(
    token=os.getenv('TOKEN'),
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        protect_content=True
    )
)

# Загружаем список администраторов из переменных окружения
admin_ids_str = os.getenv('ADMIN_IDS', '1210278389')
bot.my_admins_list = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
logging.info(f"Loaded admin IDs: {bot.my_admins_list}")

dp = Dispatcher()

# Подключаем роутеры - ВАЖНО: админские роутеры должны быть ПЕРВЫМИ!
dp.include_router(admin_router)
dp.include_router(admin_subscription_router)
dp.include_router(user_private_router)  # пользовательский роутер последний


async def check_subscriptions_task():
    """Периодическая задача для проверки истекших подписок"""
    while True:
        try:
            async with session_maker() as session:
                await SubscriptionService.check_and_expire_subscriptions(session, bot)
            await asyncio.sleep(3600)  # Проверяем каждый час
        except Exception as e:
            logging.error(f"Error in subscription check task: {e}")
            await asyncio.sleep(3600)


async def on_startup(bot):
    """Функция запуска бота"""
    logging.info("Bot starting...")
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    bot.username = bot_info.username
    logging.info(f"Bot username: @{bot.username}")
    
    # Создаем таблицы в базе данных
    # await drop_db()  # Раскомментировать для пересоздания БД
    await create_db()
    
    # Запускаем задачу проверки подписок
    asyncio.create_task(check_subscriptions_task())
    
    logging.info("Bot started successfully!")


async def on_shutdown(bot):
    """Функция остановки бота"""
    logging.info("Bot shutting down...")


async def main():
    """Основная функция запуска"""
    try:
        # Регистрируем события
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Подключаем middleware для работы с базой данных
        dp.update.middleware(DataBaseSession(session_pool=session_maker))

        # Удаляем вебхуки и начинаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Настраиваем команды бота
        await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands=private, scope=types.BotCommandScopeAllPrivateChats())
        
        # Schedulerni boshlash (background task)
        scheduler_task = asyncio.create_task(FreeLinkScheduler.start_scheduler(bot))
        
        logging.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
        
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
