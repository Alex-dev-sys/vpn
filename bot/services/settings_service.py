"""
Settings service for managing bot configuration in database
"""
import os
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Settings, SETTING_CARD_NUMBER, SETTING_BANK_NAME, SETTING_MARGIN_PERCENT, SETTING_SBP_PHONE

# Defaults from env
DEFAULT_MARGIN = float(os.getenv("DEFAULT_MARGIN", "5"))
DEFAULT_CARD_NUMBER = os.getenv("DEFAULT_CARD_NUMBER", "")
DEFAULT_BANK_NAME = os.getenv("DEFAULT_BANK_NAME", "Сбербанк")


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    """Get setting value from database"""
    result = await session.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def set_setting(session: AsyncSession, key: str, value: str):
    """Set setting value in database"""
    result = await session.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = value
    else:
        setting = Settings(key=key, value=value)
        session.add(setting)
    
    await session.commit()


async def get_card_number(session: AsyncSession) -> str:
    """Get payment card number"""
    return await get_setting(session, SETTING_CARD_NUMBER, DEFAULT_CARD_NUMBER)


async def get_bank_name(session: AsyncSession) -> str:
    """Get bank name"""
    return await get_setting(session, SETTING_BANK_NAME, DEFAULT_BANK_NAME)


async def get_margin_percent(session: AsyncSession) -> float:
    """Get margin percentage"""
    value = await get_setting(session, SETTING_MARGIN_PERCENT, str(DEFAULT_MARGIN))
    try:
        return float(value)
    except ValueError:
        return DEFAULT_MARGIN


async def get_sbp_phone(session: AsyncSession) -> Optional[str]:
    """Get SBP phone number"""
    value = await get_setting(session, SETTING_SBP_PHONE, "")
    return value if value else None


async def init_default_settings(session: AsyncSession):
    """Initialize default settings if not exist"""
    result = await session.execute(select(Settings))
    if not result.scalars().first():
        await set_setting(session, SETTING_CARD_NUMBER, DEFAULT_CARD_NUMBER)
        await set_setting(session, SETTING_BANK_NAME, DEFAULT_BANK_NAME)
        await set_setting(session, SETTING_MARGIN_PERCENT, str(DEFAULT_MARGIN))
