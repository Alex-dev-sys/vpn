"""
Обработчики раздела 'Мои ключи'
"""
import os
import logging
from datetime import datetime

from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.database.models import User, Server, VPNKey, DNSAccess
from bot.keyboards.main import keys_menu_kb, back_to_main_kb
from bot.services.adguard_api import AdGuardAPI

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "show_vpn_key")
async def cb_show_vpn_key(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """Показать VPN ключ пользователя"""
    stmt = select(VPNKey).where(
        VPNKey.user_id == user.id,
        VPNKey.is_active == True,
        VPNKey.expires_at > datetime.now()
    ).order_by(VPNKey.expires_at.desc())
    
    result = await session.execute(stmt)
    vpn_key = result.scalar()
    
    if not vpn_key:
        await callback.answer("❌ У вас нет активного VPN", show_alert=True)
        return
    
    text = (
        f"🔐 <b>Ваш VPN ключ</b>\n\n"
        f"<code>{vpn_key.access_url}</code>\n\n"
        f"📅 Действует до: <b>{vpn_key.expires_at.strftime('%d.%m.%Y')}</b>\n\n"
        f"📱 Скопируйте ключ и вставьте в приложение Outline."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    await callback.answer()


@router.callback_query(F.data == "show_dns")
async def cb_show_dns(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """Показать информацию о DNS"""
    stmt = select(DNSAccess).where(
        DNSAccess.user_id == user.id,
        DNSAccess.is_active == True,
        DNSAccess.expires_at > datetime.now()
    ).order_by(DNSAccess.expires_at.desc())
    
    result = await session.execute(stmt)
    dns_access = result.scalar()
    
    if not dns_access:
        await callback.answer("❌ У вас нет активного DNS", show_alert=True)
        return
    
    dns_server_ip = os.getenv("DNS_SERVER_IP", "185.x.x.x")
    current_ip = dns_access.current_ip or "не привязан"
    
    text = (
        f"🌐 <b>Ваш DNS доступ</b>\n\n"
        f"🖥 DNS сервер: <code>{dns_server_ip}</code>\n"
        f"📍 Ваш IP: <code>{current_ip}</code>\n"
        f"📅 Действует до: <b>{dns_access.expires_at.strftime('%d.%m.%Y')}</b>\n\n"
        f"⚙️ Пропишите DNS-сервер в настройках вашего устройства.\n"
        f"Если IP изменился — нажмите «🔄 Обновить IP»."
    )
    await callback.message.edit_text(text, reply_markup=keys_menu_kb(has_vpn=False, has_dns=True))
    await callback.answer()


@router.callback_query(F.data == "update_ip")
async def cb_update_ip(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """
    Обновить IP пользователя для DNS доступа.
    
    ВАЖНО: Telegram не передаёт IP пользователя напрямую.
    Варианты получения IP:
    1. WebApp с запросом на наш сервер (рекомендуется)
    2. Пользователь вводит IP вручную
    3. Внешний сервис определения IP
    
    Здесь реализован вариант 2 для простоты — запрашиваем IP у пользователя.
    """
    stmt = select(DNSAccess).where(
        DNSAccess.user_id == user.id,
        DNSAccess.is_active == True,
        DNSAccess.expires_at > datetime.now()
    ).order_by(DNSAccess.expires_at.desc())
    
    result = await session.execute(stmt)
    dns_access = result.scalar()
    
    if not dns_access:
        await callback.answer("❌ У вас нет активного DNS", show_alert=True)
        return
    
    text = (
        "🔄 <b>Обновление IP</b>\n\n"
        "Отправьте ваш внешний IP-адрес.\n\n"
        "💡 Чтобы узнать свой IP, откройте в браузере:\n"
        "https://2ip.ru или https://whatismyip.com"
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    await callback.answer()


@router.message(F.text.regexp(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"))
async def handle_ip_input(message: types.Message, session: AsyncSession, user: User):
    """Обработка ввода IP адреса"""
    ip = message.text.strip()
    
    # Валидация IP
    parts = ip.split(".")
    if not all(0 <= int(p) <= 255 for p in parts):
        await message.answer("❌ Неверный формат IP-адреса. Попробуйте снова.")
        return
    
    # Находим активную подписку DNS
    stmt = select(DNSAccess).where(
        DNSAccess.user_id == user.id,
        DNSAccess.is_active == True,
        DNSAccess.expires_at > datetime.now()
    ).order_by(DNSAccess.expires_at.desc())
    
    result = await session.execute(stmt)
    dns_access = result.scalar()
    
    if not dns_access:
        await message.answer("❌ У вас нет активного DNS доступа.")
        return
    
    # Получаем сервер
    server_stmt = select(Server).where(Server.id == dns_access.server_id)
    server_result = await session.execute(server_stmt)
    server = server_result.scalar()
    
    if not server:
        await message.answer("❌ Сервер не найден. Обратитесь в поддержку.")
        return
    
    try:
        # Удаляем старый IP из AdGuard (если был)
        adguard = AdGuardAPI(server.adguard_api_url, server.adguard_user, server.adguard_pass)
        
        if dns_access.current_ip:
            await adguard.remove_allowed_client(dns_access.current_ip)
        
        # Добавляем новый IP
        success = await adguard.add_allowed_client(ip)
        
        if not success:
            await message.answer("❌ Ошибка обновления. Попробуйте позже.")
            return
        
        # Обновляем в БД
        dns_access.current_ip = ip
        await session.commit()
        
        dns_server_ip = os.getenv("DNS_SERVER_IP", "185.x.x.x")
        
        text = (
            f"✅ <b>IP обновлён!</b>\n\n"
            f"📍 Ваш IP: <code>{ip}</code>\n"
            f"🖥 DNS сервер: <code>{dns_server_ip}</code>\n\n"
            f"Теперь пропишите DNS-сервер в настройках вашего устройства."
        )
        await message.answer(text, reply_markup=back_to_main_kb())
        
    except Exception as e:
        logger.error(f"Failed to update IP: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже или обратитесь в поддержку.")
