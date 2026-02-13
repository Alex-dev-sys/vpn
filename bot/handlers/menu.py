from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from bot.database.models import User, VPNKey, DNSAccess
from bot.keyboards.main import main_menu_kb, buy_menu_kb, back_to_main_kb, keys_menu_kb

router = Router()


@router.callback_query(F.data == "profile")
async def cb_profile(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """Профиль пользователя"""
    # Считаем активные подписки
    vpn_stmt = select(func.count()).where(
        VPNKey.user_id == user.id, 
        VPNKey.is_active == True,
        VPNKey.expires_at > datetime.now()
    )
    dns_stmt = select(func.count()).where(
        DNSAccess.user_id == user.id, 
        DNSAccess.is_active == True,
        DNSAccess.expires_at > datetime.now()
    )
    
    vpn_count = (await session.execute(vpn_stmt)).scalar() or 0
    dns_count = (await session.execute(dns_stmt)).scalar() or 0
    
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"👤 Username: @{user.username or 'не указан'}\n"
        f"💰 Баланс: <b>{user.balance:.2f} TON</b>\n"
        f"📅 Регистрация: {user.registration_date.strftime('%d.%m.%Y')}\n\n"
        f"<b>Активные подписки:</b>\n"
        f"🔐 VPN: {vpn_count}\n"
        f"🌐 DNS: {dns_count}"
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    await callback.answer()


@router.callback_query(F.data == "partnership")
async def cb_partnership(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """Партнёрская программа"""
    # Count referrals
    stmt = select(func.count(User.id)).where(User.referrer_id == user.id)
    referrals_count = (await session.execute(stmt)).scalar() or 0
    
    bot_username = (await callback.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user.telegram_id}"
    
    text = (
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"Приглашайте друзей и получайте <b>10%</b> от их покупок на баланс!\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Приглашено: <b>{referrals_count}</b>\n"
        f"💰 Баланс: <b>{user.balance:.2f} TON</b>\n\n"
        f"Средства с баланса можно использовать для оплаты подписки."
    )
    
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    await callback.answer()


@router.callback_query(F.data == "buy_menu")
async def cb_buy_menu(callback: types.CallbackQuery):
    """Меню покупки подписок"""
    text = (
        "🛍 <b>Купить подписку</b>\n\n"
        "Выберите тариф (на 1 месяц):\n\n"
        "🔐 <b>VPN</b> — безлимитный трафик через Outline\n"
        "🌐 <b>DNS</b> — приватный DNS с блокировкой рекламы\n"
        "⭐ <b>PRO</b> — VPN + DNS со скидкой"
    )
    await callback.message.edit_text(text, reply_markup=buy_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "my_keys")
async def cb_my_keys(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """Раздел 'Мои ключи'"""
    now = datetime.now()
    
    # Проверяем наличие активных подписок
    vpn_stmt = select(VPNKey).where(
        VPNKey.user_id == user.id, 
        VPNKey.is_active == True,
        VPNKey.expires_at > now
    )
    dns_stmt = select(DNSAccess).where(
        DNSAccess.user_id == user.id, 
        DNSAccess.is_active == True,
        DNSAccess.expires_at > now
    )
    
    vpn_result = await session.execute(vpn_stmt)
    dns_result = await session.execute(dns_stmt)
    
    has_vpn = vpn_result.scalar() is not None
    has_dns = dns_result.scalar() is not None
    
    if not has_vpn and not has_dns:
        text = (
            "🔑 <b>Мои ключи</b>\n\n"
            "❌ У вас нет активных подписок.\n\n"
            "Нажмите «Купить подписку» для приобретения."
        )
    else:
        text = (
            "🔑 <b>Мои ключи</b>\n\n"
            "Выберите, что хотите посмотреть:"
        )
    
    await callback.message.edit_text(text, reply_markup=keys_menu_kb(has_vpn, has_dns))
    await callback.answer()
