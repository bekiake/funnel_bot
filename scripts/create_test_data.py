"""
Скрипт для создания тестовых данных в базе данных
"""
import asyncio
import sys
import os

# Добавляем корневую папку в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.engine import session_maker
from database.orm_query import (
    orm_create_funnel,
    orm_add_funnel_step,
    orm_create_subscription_plan
)


async def create_test_funnel():
    """Создание тестовой воронки"""
    async with session_maker() as session:
        try:
            # Создаем воронку
            funnel = await orm_create_funnel(
                session,
                name="Python dasturlash kursi",
                key="python_course",
                description="Python dasturlash asoslari haqida to'liq kurs"
            )
            
            print(f"✅ Funnel yaratildi: {funnel.name} (ID: {funnel.id})")
            
            # Добавляем шаги
            steps_data = [
                {
                    "step_number": 1,
                    "content_type": "text",
                    "content_data": "🐍 Python dasturlash kursiga xush kelibsiz!\n\nBu kursda siz o'rganasiz:\n• Python asoslari\n• Ma'lumotlar strukturalari\n• Obyektga yo'naltirilgan dasturlash\n• Web dasturlash",
                    "button_text": "Keyingi dars ➡️"
                },
                {
                    "step_number": 2, 
                    "content_type": "text",
                    "content_data": "📝 1-dars: Python o'rnatish va sozlash\n\nAvval Python dasturlash muhitini o'rnatishni o'rganamiz:\n1. Python.org saytidan yuklab oling\n2. IDE tanlang (VS Code, PyCharm)\n3. Birinchi 'Hello World' dasturi",
                    "button_text": "Keyingi dars ➡️"
                },
                {
                    "step_number": 3,
                    "content_type": "text", 
                    "content_data": "🔢 2-dars: O'zgaruvchilar va ma'lumot turlari\n\nPythonda asosiy ma'lumot turlari:\n• int - butun sonlar\n• float - haqiqiy sonlar\n• str - matnlar\n• bool - mantiqiy qiymatlar\n• list - ro'yxatlar\n• dict - lug'atlar",
                    "button_text": "Keyingi dars ➡️"
                },
                {
                    "step_number": 4,
                    "content_type": "text",
                    "content_data": "🎉 Tabriklaymiz!\n\nSiz Python kursining asosiy qismini tugatdingiz.\n\nToliq kurs uchun bizning premium kanalimizga obuna bo'ling va yanada chuqur bilimlar oling!"
                }
            ]
            
            for step_data in steps_data:
                step = await orm_add_funnel_step(session, funnel.id, **step_data)
                print(f"  ✅ Qadam {step.step_number} qo'shildi")
            
            print(f"\n🔗 Funnel linki: https://t.me/your_bot?start={funnel.key}")
            
        except Exception as e:
            print(f"❌ Xatolik: {e}")


async def create_test_subscription_plans():
    """Создание тестовых тарифных планов"""
    async with session_maker() as session:
        try:
            plans_data = [
                {
                    "name": "1 kunlik obuna",
                    "duration_days": 1,
                    "price_usd": 1.99,
                    "price_uzs": 25000,
                    "channel_id": -1001234567890  # Заменить на реальный ID канала
                },
                {
                    "name": "1 haftalik obuna", 
                    "duration_days": 7,
                    "price_usd": 9.99,
                    "price_uzs": 130000,
                    "channel_id": -1001234567890
                },
                {
                    "name": "1 oylik obuna",
                    "duration_days": 30,
                    "price_usd": 29.99,
                    "price_uzs": 390000,
                    "channel_id": -1001234567890
                }
            ]
            
            for plan_data in plans_data:
                plan = await orm_create_subscription_plan(session, **plan_data)
                print(f"✅ Tarif yaratildi: {plan.name} (ID: {plan.id})")
            
        except Exception as e:
            print(f"❌ Xatolik: {e}")


async def main():
    """Основная функция"""
    print("🚀 Test ma'lumotlarni yaratish...")
    
    await create_test_funnel()
    print()
    await create_test_subscription_plans()
    
    print("\n✅ Barcha test ma'lumotlar yaratildi!")


if __name__ == "__main__":
    asyncio.run(main())
