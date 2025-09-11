from aiogram.filters import Filter
from aiogram import Bot, types
import logging


class ChatTypeFilter(Filter):
    def __init__(self, chat_types: list[str]) -> None:
        self.chat_types = chat_types

    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type in self.chat_types
    

class IsAdmin(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: types.Message, bot: Bot) -> bool:
        user_id = message.from_user.id
        is_admin = user_id in bot.my_admins_list
        logging.info(f"IsAdmin filter: user_id={user_id}, admin_list={bot.my_admins_list}, is_admin={is_admin}")
        return is_admin