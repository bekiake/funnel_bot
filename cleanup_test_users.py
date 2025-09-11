#!/usr/bin/env python3
"""
Test foydalanuvchilarini tozalash skripti
"""
import asyncio
import sys
import os

# Loyiha papkasini sys.path ga qo'shamiz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.engine import session_maker
from database.models import User, FunnelStatistic
from sqlalchemy import select, delete


async def cleanup_test_users():
    """Test foydalanuvchilarini o'chirish"""
    print("🧹 Test foydalanuvchilarini tozalash boshlandi...")
    
    async with session_maker() as session:
        # Test user ID range: 1000001 - 1000020
        test_user_ids = list(range(1000001, 1000021))
        
        # Funnel statistikalarini o'chirish
        stats_delete = delete(FunnelStatistic).where(
            FunnelStatistic.user_id.in_(test_user_ids)
        )
        stats_result = await session.execute(stats_delete)
        deleted_stats = stats_result.rowcount
        
        # Foydalanuvchilarni o'chirish
        users_delete = delete(User).where(
            User.user_id.in_(test_user_ids)
        )
        users_result = await session.execute(users_delete)
        deleted_users = users_result.rowcount
        
        await session.commit()
        
        print(f"✅ {deleted_stats} ta funnel statistikasi o'chirildi")
        print(f"✅ {deleted_users} ta test foydalanuvchi o'chirildi")
        print("🎉 Tozalash tugadi!")


if __name__ == "__main__":
    asyncio.run(cleanup_test_users())
