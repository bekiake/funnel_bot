import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base


#from .env file:
# DATABASE_URL=sqlite+aiosqlite:///my_base.db
# DATABASE_URL=postgresql+asyncpg://login:password@localhost:5432/db_name

# Получаем URL базы данных из переменной окружения
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Используем SQLite по умолчанию, если переменная не задана
    DATABASE_URL = 'sqlite+aiosqlite:///my_base.db'
    print("⚠️ DATABASE_URL не найден в .env, используется SQLite по умолчанию")

# Определяем тип базы данных
is_postgresql = "postgresql" in DATABASE_URL.lower()
is_sqlite = "sqlite" in DATABASE_URL.lower()

if is_postgresql:
    print("🐘 Используется PostgreSQL")
    # PostgreSQL специфичные настройки
    engine = create_async_engine(
        DATABASE_URL, 
        echo=True,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )
elif is_sqlite:
    print("📁 Используется SQLite")
    # SQLite специфичные настройки
    engine = create_async_engine(
        DATABASE_URL, 
        echo=True,
        connect_args={"check_same_thread": False}
    )
else:
    print("❓ Неизвестный тип базы данных, используем стандартные настройки")
    engine = create_async_engine(DATABASE_URL, echo=True)

# engine = create_async_engine(os.getenv('DB_URL'), echo=True)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)



async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
