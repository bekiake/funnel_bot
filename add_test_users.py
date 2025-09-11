#!/usr/bin/env python3
"""
Test uchun 20 ta foydalanuvchi qo'shish skripti
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
import random

# Loyiha papkasini sys.path ga qo'shamiz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.engine import session_maker
from database.orm_query import orm_add_user
from database.models import User, FunnelStatistic, Funnel
from sqlalchemy import select


# Test foydalanuvchilar ma'lumotlari
TEST_USERS = [
    {"user_id": 1000001, "full_name": "Ahror Toshmatov", "phone": "+998901234567"},
    {"user_id": 1000002, "full_name": "Malika Karimova", "phone": "+998902345678"},
    {"user_id": 1000003, "full_name": "Sardor Rahmonov", "phone": "+998903456789"},
    {"user_id": 1000004, "full_name": "Nigora Usmonova", "phone": "+998904567890"},
    {"user_id": 1000005, "full_name": "Bobur Alimov", "phone": "+998905678901"},
    {"user_id": 1000006, "full_name": "Dildora Nazarova", "phone": "+998906789012"},
    {"user_id": 1000007, "full_name": "Jasur Qosimov", "phone": "+998907890123"},
    {"user_id": 1000008, "full_name": "Zarina Abdullayeva", "phone": "+998908901234"},
    {"user_id": 1000009, "full_name": "Farrux Ismoilov", "phone": "+998909012345"},
    {"user_id": 1000010, "full_name": "Umida Normuratova", "phone": "+998900123456"},
    {"user_id": 1000011, "full_name": "Otabek Tursunov", "phone": "+998911234567"},
    {"user_id": 1000012, "full_name": "Sevara Mirzayeva", "phone": "+998912345678"},
    {"user_id": 1000013, "full_name": "Bekzod Samadov", "phone": "+998913456789"},
    {"user_id": 1000014, "full_name": "Gulnoza Jurayeva", "phone": "+998914567890"},
    {"user_id": 1000015, "full_name": "Sherzod Yusupov", "phone": "+998915678901"},
    {"user_id": 1000016, "full_name": "Nodira Sultonova", "phone": "+998916789012"},
    {"user_id": 1000017, "full_name": "Aziz Mahmudov", "phone": "+998917890123"},
    {"user_id": 1000018, "full_name": "Kamola Hasanova", "phone": "+998918901234"},
    {"user_id": 1000019, "full_name": "Javlon Ergashev", "phone": "+998919012345"},
    {"user_id": 1000020, "full_name": "Yulduz Xolmatova", "phone": "+998920123456"},
]


async def add_test_users():
    """Test foydalanuvchilarini qo'shish"""
    print("🚀 Test foydalanuvchilarini qo'shish boshlandi...")
    
    async with session_maker() as session:
        added_count = 0
        
        for user_data in TEST_USERS:
            try:
                # Foydalanuvchi mavjudligini tekshirish
                query = select(User).where(User.user_id == user_data["user_id"])
                result = await session.execute(query)
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    print(f"⚠️  Foydalanuvchi {user_data['full_name']} ({user_data['user_id']}) allaqachon mavjud")
                    continue
                
                # Yangi foydalanuvchi qo'shish
                await orm_add_user(
                    session=session,
                    user_id=user_data["user_id"],
                    full_name=user_data["full_name"],
                    phone=user_data["phone"]
                )
                
                added_count += 1
                print(f"✅ Qo'shildi: {user_data['full_name']} ({user_data['user_id']})")
                
            except Exception as e:
                print(f"❌ Xato: {user_data['full_name']} qo'shishda xato - {e}")
    
    print(f"\n🎉 Jami {added_count} ta yangi foydalanuvchi qo'shildi!")


async def add_random_funnel_stats():
    """Test foydalanuvchilar uchun tasodifiy funnel statistikasi qo'shish"""
    print("\n📊 Tasodifiy funnel statistikasi qo'shish boshlandi...")
    
    async with session_maker() as session:
        # Mavjud funnellarni olish
        funnel_query = select(Funnel).where(Funnel.is_active == True)
        funnel_result = await session.execute(funnel_query)
        funnels = funnel_result.scalars().all()
        
        if not funnels:
            print("⚠️  Hech qanday aktiv funnel topilmadi")
            return
        
        stats_added = 0
        
        for user_data in TEST_USERS:
            # Har bir foydalanuvchi uchun 1-3 ta tasodifiy funnel statistikasi
            num_stats = random.randint(1, 3)
            
            for _ in range(num_stats):
                try:
                    funnel = random.choice(funnels)
                    
                    # Tasodifiy yakunlanganlik
                    is_completed = random.choice([True, False, False])  # 33% yakunlangan
                    current_step = random.randint(1, 5) if not is_completed else 0
                    
                    # Tasodifiy vaqt (oxirgi 30 kun ichida)
                    days_ago = random.randint(1, 30)
                    started_at = datetime.now() - timedelta(days=days_ago)
                    completed_at = started_at + timedelta(hours=random.randint(1, 48)) if is_completed else None
                    
                    # Statistika yaratish
                    stat = FunnelStatistic(
                        user_id=user_data["user_id"],
                        funnel_id=funnel.id,
                        current_step=current_step,
                        completed=is_completed,
                        started_at=started_at,
                        completed_at=completed_at,
                        step_statistics={}
                    )
                    
                    session.add(stat)
                    stats_added += 1
                    
                except Exception as e:
                    print(f"❌ Statistika qo'shishda xato: {e}")
        
        await session.commit()
        print(f"✅ {stats_added} ta funnel statistikasi qo'shildi!")


async def main():
    """Asosiy funksiya"""
    print("🔥 Test ma'lumotlarini qo'shish skripti\n")
    
    try:
        # Test foydalanuvchilarini qo'shish
        await add_test_users()
        
        # Funnel statistikalarini qo'shish
        await add_random_funnel_stats()
        
        print("\n✨ Barcha test ma'lumotlari muvaffaqiyatli qo'shildi!")
        print("💡 Endi admin panelda 'Foydalanuvchilar' bo'limini tekshiring")
        
    except Exception as e:
        print(f"❌ Umumiy xato: {e}")


if __name__ == "__main__":
    asyncio.run(main())
