import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from database.engine import session_maker
from database.orm_query import (
    orm_get_expired_free_link_uses, 
    orm_mark_free_link_use_expired,
    orm_get_active_subscription_plans
)
from kbds.inline import get_subscription_plans_kb


class FreeLinkScheduler:
    """Free link muddatlarini tekshirish va foydalanuvchilarni chiqarish"""
    
    @staticmethod
    async def check_expired_free_links(bot: Bot):
        """Muddati tugagan free linklar uchun foydalanuvchilarni kanaldan chiqarish"""
        try:
            async with session_maker() as session:
                # Muddati tugagan ishlatishlarni olish
                expired_uses = await orm_get_expired_free_link_uses(session)
                
                for use in expired_uses:
                    try:
                        # Foydalanuvchini kanaldan chiqarish
                        await bot.kick_chat_member(
                            chat_id=use.free_link.channel_id,
                            user_id=use.user_id
                        )
                        
                        # Immediately unban to allow rejoining if they get another invite
                        await bot.unban_chat_member(
                            chat_id=use.free_link.channel_id,
                            user_id=use.user_id
                        )
                        
                        # Foydalanuvchiga xabar yuborish
                        subscription_plans = await orm_get_active_subscription_plans(session)
                        
                        await bot.send_message(
                            chat_id=use.user_id,
                            text=(
                                f"⏰ <b>Free access muddati tugadi</b>\n\n"
                                f"🎁 <b>{use.free_link.name}</b> uchun free access muddati tugadi.\n\n"
                                f"💎 Premium obuna orqali doimiy kirish huquqini oling:"
                            ),
                            reply_markup=get_subscription_plans_kb(subscription_plans) if subscription_plans else None
                        )
                        
                        # Expired deb belgilash
                        await orm_mark_free_link_use_expired(session, use.id)
                        
                        logging.info(f"Removed user {use.user_id} from channel {use.free_link.channel_id} - free link expired")
                        
                    except Exception as user_error:
                        logging.error(f"Error processing expired free link for user {use.user_id}: {user_error}")
                        # Mark as expired even if removal failed
                        await orm_mark_free_link_use_expired(session, use.id)
                        
        except Exception as e:
            logging.error(f"Error in check_expired_free_links: {e}")
    
    @staticmethod
    async def start_scheduler(bot: Bot):
        """Scheduler ni boshlash"""
        while True:
            try:
                await FreeLinkScheduler.check_expired_free_links(bot)
                # Har 1 soatda tekshirish
                await asyncio.sleep(3600)
            except Exception as e:
                logging.error(f"Error in scheduler: {e}")
                await asyncio.sleep(300)  # Xato bo'lsa 5 daqiqada qaytadan
