"""Скрипт для добавления сервера в базу данных"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.database.models import Base, Server

async def add_server():
    # Create database
    os.makedirs("data", exist_ok=True)
    engine = create_async_engine("sqlite+aiosqlite:///data/bot.db", echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        server = Server(
            name="Server1",
            outline_api_url="https://185.216.87.218:21301/ViplnDtM4Ol2cnY0wiq3kg",
            adguard_api_url="http://185.216.87.218:80",
            adguard_user="admin",
            adguard_pass="agfa123agfa",
            users_count=0,
            max_users=60,
            is_active=True
        )
        session.add(server)
        await session.commit()
        print(f"✅ Сервер добавлен: {server.name} (ID: {server.id})")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(add_server())
