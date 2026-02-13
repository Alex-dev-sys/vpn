"""
Фоновые задачи — Терминатор подписок

Запускается каждый час и деактивирует истёкшие подписки:
- VPN: удаляет ключ из Outline
- DNS: удаляет IP из AdGuard Home allowed_clients
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bot.database.core import async_session_factory
from bot.database.models import User, Server, VPNKey, DNSAccess
from bot.services.outline_api import OutlineAPI
from bot.services.adguard_api import AdGuardAPI

logger = logging.getLogger(__name__)

# Глобальная ссылка на бота для отправки уведомлений
_bot = None


def set_bot_instance(bot):
    """Установить инстанс бота для уведомлений"""
    global _bot
    _bot = bot


async def notify_user(telegram_id: int, text: str, reply_markup=None):
    """Отправить уведомление пользователю"""
    global _bot
    if _bot:
        try:
            await _bot.send_message(telegram_id, text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to notify user {telegram_id}: {e}")


async def terminate_expired_vpn():
    """Деактивировать истёкшие VPN ключи"""
    logger.info("Checking for expired VPN keys...")
    
    async with async_session_factory() as session:
        # Находим истёкшие активные ключи
        stmt = select(VPNKey).where(
            VPNKey.is_active == True,
            VPNKey.expires_at < datetime.now()
        )
        result = await session.execute(stmt)
        expired_keys = result.scalars().all()
        
        for vpn_key in expired_keys:
            try:
                # Получаем сервер
                server_stmt = select(Server).where(Server.id == vpn_key.server_id)
                server_result = await session.execute(server_stmt)
                server = server_result.scalar()
                
                if server:
                    # Удаляем ключ из Outline
                    outline = OutlineAPI(server.outline_api_url)
                    await outline.delete_key(vpn_key.outline_key_id)
                    
                    # Уменьшаем счётчик пользователей
                    if server.users_count > 0:
                        server.users_count -= 1
                
                # Деактивируем в БД
                vpn_key.is_active = False
                
                # Получаем пользователя для уведомления
                user_stmt = select(User).where(User.id == vpn_key.user_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar()
                
                if user:
                    await notify_user(
                        user.telegram_id,
                        "⚠️ Ваша VPN подписка истекла.\n\n"
                        "Для продления нажмите «🛍 Купить подписку»."
                    )
                    logger.info(f"VPN key expired for user {user.telegram_id}")
                    
            except Exception as e:
                logger.error(f"Error terminating VPN key {vpn_key.id}: {e}")
        
        await session.commit()


async def terminate_expired_dns():
    """Деактивировать истёкший DNS доступ"""
    logger.info("Checking for expired DNS access...")
    
    async with async_session_factory() as session:
        stmt = select(DNSAccess).where(
            DNSAccess.is_active == True,
            DNSAccess.expires_at < datetime.now()
        )
        result = await session.execute(stmt)
        expired_access = result.scalars().all()
        
        for dns_access in expired_access:
            try:
                # Получаем сервер
                server_stmt = select(Server).where(Server.id == dns_access.server_id)
                server_result = await session.execute(server_stmt)
                server = server_result.scalar()
                
                if server and dns_access.current_ip:
                    # Удаляем IP из AdGuard
                    adguard = AdGuardAPI(
                        server.adguard_api_url,
                        server.adguard_user,
                        server.adguard_pass
                    )
                    await adguard.remove_allowed_client(dns_access.current_ip)
                
                # Деактивируем в БД
                dns_access.is_active = False
                
                # Получаем пользователя для уведомления
                user_stmt = select(User).where(User.id == dns_access.user_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar()
                
                if user:
                    await notify_user(
                        user.telegram_id,
                        "⚠️ Ваша DNS подписка истекла.\n\n"
                        "Для продления нажмите «🛍 Купить подписку»."
                    )
                    logger.info(f"DNS access expired for user {user.telegram_id}")
                    
            except Exception as e:
                logger.error(f"Error terminating DNS access {dns_access.id}: {e}")
        
        await session.commit()


async def send_expiry_reminders():
    """Send reminders 3 days and 1 day before subscription expires"""
    logger.info("Checking for expiring subscriptions...")
    
    from datetime import timedelta
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    now = datetime.now()
    three_days = now + timedelta(days=3)
    one_day = now + timedelta(days=1)
    
    async with async_session_factory() as session:
        # --- VPN Reminders ---
        # 3 Days
        stmt = select(VPNKey).where(
            VPNKey.is_active == True,
            VPNKey.expires_at > now,
            VPNKey.expires_at <= three_days,
            VPNKey.notification_status == 0
        )
        result = await session.execute(stmt)
        keys_3d = result.scalars().all()
        
        for key in keys_3d:
            try:
                user = await session.get(User, key.user_id)
                if user:
                    days = (key.expires_at - now).days
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data=f"extend_vpn_{key.id}")]
                    ])
                    await notify_user(
                        user.telegram_id,
                        f"⏰ <b>VPN: Осталось {days} дн.</b>\n\n"
                        f"Ваша подписка истекает {key.expires_at.strftime('%d.%m.%Y')}.\n"
                        f"Продлите сейчас, чтобы не потерять доступ.",
                        reply_markup=kb
                    )
                    key.notification_status = 1
                    logger.info(f"Sent VPN 3-day reminder to {user.telegram_id}")
            except Exception as e:
                logger.error(f"VPN 3-day reminder error: {e}")

        # 1 Day
        stmt = select(VPNKey).where(
            VPNKey.is_active == True,
            VPNKey.expires_at > now,
            VPNKey.expires_at <= one_day,
            VPNKey.notification_status < 2
        )
        result = await session.execute(stmt)
        keys_1d = result.scalars().all()
        
        for key in keys_1d:
            try:
                user = await session.get(User, key.user_id)
                if user:
                    hours = int((key.expires_at - now).total_seconds() / 3600)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Продлить срочно", callback_data=f"extend_vpn_{key.id}")]
                    ])
                    await notify_user(
                        user.telegram_id,
                        f"🚨 <b>VPN: Осталось меньше суток ({hours} ч)!</b>\n\n"
                        f"Ваша подписка истекает {key.expires_at.strftime('%d.%m.%Y %H:%M')}.\n"
                        f"Продлите, иначе ключ будет отключен.",
                        reply_markup=kb
                    )
                    key.notification_status = 2
                    logger.info(f"Sent VPN 1-day reminder to {user.telegram_id}")
            except Exception as e:
                logger.error(f"VPN 1-day reminder error: {e}")

        # --- DNS Reminders ---
        # 3 Days
        stmt = select(DNSAccess).where(
            DNSAccess.is_active == True,
            DNSAccess.expires_at > now,
            DNSAccess.expires_at <= three_days,
            DNSAccess.notification_status == 0
        )
        result = await session.execute(stmt)
        access_3d = result.scalars().all()

        for access in access_3d:
            try:
                user = await session.get(User, access.user_id)
                if user:
                    days = (access.expires_at - now).days
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data=f"extend_dns_{access.id}")]
                    ])
                    await notify_user(
                        user.telegram_id,
                        f"⏰ <b>DNS: Осталось {days} дн.</b>\n\n"
                        f"Ваша подписка истекает {access.expires_at.strftime('%d.%m.%Y')}.\n"
                        f"Продлите сейчас, чтобы не потерять доступ.",
                        reply_markup=kb
                    )
                    access.notification_status = 1
                    logger.info(f"Sent DNS 3-day reminder to {user.telegram_id}")
            except Exception as e:
                logger.error(f"DNS 3-day reminder error: {e}")

        # 1 Day
        stmt = select(DNSAccess).where(
            DNSAccess.is_active == True,
            DNSAccess.expires_at > now,
            DNSAccess.expires_at <= one_day,
            DNSAccess.notification_status < 2
        )
        result = await session.execute(stmt)
        access_1d = result.scalars().all()
        
        for access in access_1d:
            try:
                user = await session.get(User, access.user_id)
                if user:
                    hours = int((access.expires_at - now).total_seconds() / 3600)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Продлить срочно", callback_data=f"extend_dns_{access.id}")]
                    ])
                    await notify_user(
                        user.telegram_id,
                        f"🚨 <b>DNS: Осталось меньше суток ({hours} ч)!</b>\n\n"
                        f"Ваша подписка истекает {access.expires_at.strftime('%d.%m.%Y %H:%M')}.\n"
                        f"Продлите, иначе доступ будет отключен.",
                        reply_markup=kb
                    )
                    access.notification_status = 2
                    logger.info(f"Sent DNS 1-day reminder to {user.telegram_id}")
            except Exception as e:
                logger.error(f"DNS 1-day reminder error: {e}")
        
        await session.commit()


async def check_expired_subscriptions():
    """Основная задача проверки истёкших подписок"""
    await terminate_expired_vpn()
    await terminate_expired_dns()
    await send_expiry_reminders()


def setup_scheduler(bot=None):
    """Настройка и запуск планировщика"""
    if bot:
        set_bot_instance(bot)
    
    scheduler = AsyncIOScheduler()
    

    # Проверка каждый час
    scheduler.add_job(
        check_expired_subscriptions, 
        "interval", 
        minutes=60,
        id="terminator",
        name="Subscription Terminator"
    )
    
    # Бэкап базы данных (раз в сутки в 03:00)
    from bot.services.backup_service import BackupService
    
    async def run_backup_job():
        # Need to pass bot instance
        if _bot:
            await BackupService.send_backup_to_admins(_bot)
            
    scheduler.add_job(
        run_backup_job,
        "cron",
        hour=3,
        minute=0,
        id="backup_daily",
        name="Daily Database Backup"
    )
    
    scheduler.start()
    logger.info("Scheduler started - checking subscriptions every 60 minutes")
    
    return scheduler
