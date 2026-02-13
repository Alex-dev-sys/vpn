from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from bot.database.core import async_session_factory
from bot.database.models import User
from sqlalchemy import select


class DbSessionMiddleware(BaseMiddleware):
    """Middleware для создания сессии БД на каждый update"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """Middleware для получения/создания пользователя в БД"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        session = data.get("session")
        if not session:
            return await handler(event, data)
        
        tg_user: TgUser = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        # Ищем пользователя в БД
        stmt = select(User).where(User.telegram_id == tg_user.id)
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()

        # Создаем, если не существует
        if not db_user:
            db_user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
            )
            session.add(db_user)
            await session.commit()
            await session.refresh(db_user)
        
        data["user"] = db_user
        return await handler(event, data)
