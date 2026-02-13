import os
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base

# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

DATABASE_URL = "sqlite+aiosqlite:///data/bot.db"

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db():
    """Создание таблиц в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получение сессии БД (генератор)"""
    async with async_session_factory() as session:
        yield session
