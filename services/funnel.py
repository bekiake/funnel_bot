import os
import json
import logging
import asyncio

FUNNELS_DIR = "funnels"

async def send_funnel_messages(message, key: str):
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
