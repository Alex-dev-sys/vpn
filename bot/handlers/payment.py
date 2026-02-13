"""
Обработчики покупки подписок (TON оплата через ссылки)

Используем TON deep links формата:
ton://transfer/<wallet>?amount=<nanotons>&text=<comment>

Это позволяет:
- Кликнуть ссылку → открывается кошелёк с заполненными данными
- Уникальный код в комментарии для трекинга
"""
import os
import logging
import secrets
import string
from datetime import datetime, timedelta
from urllib.parse import quote

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.database.models import User, Server, VPNKey, DNSAccess, Payment, PromoCode
from bot.keyboards.main import back_to_main_kb, main_menu_kb
from bot.services.outline_api import OutlineAPI
from bot.services.ton_api import verify_ton_payment

router = Router()
logger = logging.getLogger(__name__)

# Конфигурация
TON_WALLET = os.getenv("TON_WALLET", "UQCAKkJZSo2h5VAWyPO1vGtqFbRMp_x-rHlYfmTsUBFQUDl-")

# Цены в РУБЛЯХ (конвертируются в TON по текущему курсу)
VPN_PRICE_RUB = int(os.getenv("VPN_PRICE_RUB", "150"))
DNS_PRICE_RUB = int(os.getenv("DNS_PRICE_RUB", "100"))
PRO_PRICE_RUB = int(os.getenv("PRO_PRICE_RUB", "200"))

PRICES_RUB = {
    "vpn": VPN_PRICE_RUB,
    "dns": DNS_PRICE_RUB,
    "pro": PRO_PRICE_RUB
}

PRODUCT_NAMES = {
    "vpn": "🔐 VPN",
    "dns": "🌐 DNS", 
    "pro": "⭐ PRO (VPN+DNS)"
}


async def get_price_in_ton(product: str) -> tuple[float, float, int]:
    """
    Получает цену в TON по текущему курсу
    Returns: (price_ton, rate, price_rub)
    """
    from bot.services.rate_service import get_ton_rub_rate
    
    price_rub = PRICES_RUB[product]
    rate = await get_ton_rub_rate()
    
    if not rate or rate == 0:
        rate = 100  # Fallback rate if API fails
    
    price_ton = round(price_rub / rate, 2)
    return price_ton, rate, price_rub


def generate_payment_code() -> str:
    """Генерирует уникальный код платежа (8 символов)"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


def ton_to_nanoton(amount: float) -> int:
    """Конвертация TON в нанотоны (1 TON = 10^9 нанотонов)"""
    return int(amount * 1_000_000_000)


def create_ton_payment_link(wallet: str, amount_ton: float, comment: str) -> str:
    """
    Создаёт TON deep link для оплаты
    
    Форматы:
    - ton://transfer/<wallet>?amount=<nanotons>&text=<comment>
    - https://app.tonkeeper.com/transfer/<wallet>?amount=<nanotons>&text=<comment>
    """
    nanotons = ton_to_nanoton(amount_ton)
    encoded_comment = quote(comment)
    
    # Tonkeeper link (работает в браузере и приложении)
    return f"https://app.tonkeeper.com/transfer/{wallet}?amount={nanotons}&text={encoded_comment}"


def create_payment_keyboard(payment_code: str, product: str, amount: float, user_balance: float = 0.0) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой оплаты"""
    payment_link = create_ton_payment_link(TON_WALLET, amount, payment_code)
    
    kb = [
        [InlineKeyboardButton(text=f"💎 Оплатить {amount} TON", url=payment_link)],
        [InlineKeyboardButton(text="💎 Купить TON (P2P)", callback_data="p2p_buy")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_payment_{payment_code}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="buy_menu")]
    ]
    
    # Add balance payment button if sufficient funds
    if user_balance >= amount:
        kb.insert(0, [InlineKeyboardButton(text=f"💰 Оплатить с баланса ({amount} TON)", callback_data=f"pay_balance_{payment_code}")])
        
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def get_available_server(session: AsyncSession) -> Server | None:
    """Найти сервер с доступными слотами"""
    stmt = select(Server).where(
        Server.is_active == True,
        Server.users_count < Server.max_users
    ).order_by(Server.users_count)
    
    result = await session.execute(stmt)
    return result.scalar()


async def create_payment(session: AsyncSession, user: User, product: str, amount_ton: float, promo_code_id: int = None) -> Payment:
    """Создать запись платежа с уникальным кодом"""
    payment_code = generate_payment_code()
    
    # Проверяем уникальность кода
    while True:
        existing = await session.execute(
            select(Payment).where(Payment.payment_code == payment_code)
        )
        if not existing.scalar():
            break
        payment_code = generate_payment_code()
    
    payment = Payment(
        user_id=user.id,
        payment_code=payment_code,
        product_type=product,
        amount_ton=amount_ton,
        status="pending",
        expires_at=datetime.now() + timedelta(minutes=30),  # 30 минут на оплату
        promo_code_id=promo_code_id
    )
    session.add(payment)
    await session.commit()
    
    return payment


@router.callback_query(F.data == "buy_vpn")
async def cb_buy_vpn(callback: types.CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Покупка VPN"""
    await state.update_data(product="vpn")
    price_ton, rate, price_rub = await get_price_in_ton("vpn")
    
    # Check for active promo
    data = await state.get_data()
    promo_code = data.get("promo_code")
    discount = data.get("discount", 0)
    
    if discount > 0:
        price_rub = int(price_rub * (1 - discount / 100))
        price_ton = round(price_rub / rate, 2)
    
    payment = await create_payment(session, user, "vpn", price_ton, promo_code_id=data.get("promo_id"))
    
    text = (
        f"🔐 <b>Покупка VPN</b>\n\n"
        f"💰 Сумма: <b>{price_ton} TON</b> (~{price_rub}₽)\n"
    )
    if discount > 0:
        text += f"🏷 Скидка: {discount}% (по промокоду {promo_code})\n"
        
    text += (
        f"📊 Курс: {rate:.2f} ₽/TON\n"
        f"⏱ Срок: 30 дней\n\n"
        f"📝 Код платежа: <code>{payment.payment_code}</code>\n\n"
        f"👇 Нажмите кнопку ниже — откроется кошелёк с заполненными данными.\n"
        f"После оплаты нажмите «Я оплатил»."
    )
    
    kb = create_payment_keyboard(payment.payment_code, "vpn", price_ton, user.balance)
    
    # Add promo button if no discount yet
    if discount == 0:
        kb.inline_keyboard.insert(0, [InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")])
        
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "buy_dns")
async def cb_buy_dns(callback: types.CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Покупка DNS"""
    await state.update_data(product="dns")
    price_ton, rate, price_rub = await get_price_in_ton("dns")
    
    # Check for active promo
    data = await state.get_data()
    promo_code = data.get("promo_code")
    discount = data.get("discount", 0)
    
    if discount > 0:
        price_rub = int(price_rub * (1 - discount / 100))
        price_ton = round(price_rub / rate, 2)

    payment = await create_payment(session, user, "dns", price_ton, promo_code_id=data.get("promo_id"))
    
    text = (
        f"🌐 <b>Покупка DNS</b>\n\n"
        f"💰 Сумма: <b>{price_ton} TON</b> (~{price_rub}₽)\n"
    )
    if discount > 0:
        text += f"🏷 Скидка: {discount}% (по промокоду {promo_code})\n"

    text += (
        f"📊 Курс: {rate:.2f} ₽/TON\n"
        f"⏱ Срок: 30 дней\n\n"
        f"📝 Код платежа: <code>{payment.payment_code}</code>\n\n"
        f"👇 Нажмите кнопку ниже — откроется кошелёк с заполненными данными.\n"
        f"После оплаты нажмите «Я оплатил»."
    )
    
    kb = create_payment_keyboard(payment.payment_code, "dns", price_ton, user.balance)
    
    if discount == 0:
        kb.inline_keyboard.insert(0, [InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "buy_pro")
async def cb_buy_pro(callback: types.CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Покупка PRO (VPN+DNS)"""
    await state.update_data(product="pro")
    price_ton, rate, price_rub = await get_price_in_ton("pro")
    
    # Check for active promo
    data = await state.get_data()
    promo_code = data.get("promo_code")
    discount = data.get("discount", 0)
    
    if discount > 0:
        price_rub = int(price_rub * (1 - discount / 100))
        price_ton = round(price_rub / rate, 2)

    payment = await create_payment(session, user, "pro", price_ton, promo_code_id=data.get("promo_id"))
    
    text = (
        f"⭐ <b>Покупка PRO (VPN + DNS)</b>\n\n"
        f"💰 Сумма: <b>{price_ton} TON</b> (~{price_rub}₽)\n"
    )
    if discount > 0:
        text += f"🏷 Скидка: {discount}% (по промокоду {promo_code})\n"

    text += (
        f"📊 Курс: {rate:.2f} ₽/TON\n"
        f"⏱ Срок: 30 дней\n\n"
        f"📝 Код платежа: <code>{payment.payment_code}</code>\n\n"
        f"👇 Нажмите кнопку ниже — откроется кошелёк с заполненными данными.\n"
        f"После оплаты нажмите «Я оплатил»."
    )
    
    kb = create_payment_keyboard(payment.payment_code, "pro", price_ton, user.balance)
    
    if discount == 0:
        kb.inline_keyboard.insert(0, [InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


class PromoStates(StatesGroup):
    enter_code = State()

@router.callback_query(F.data == "enter_promo")
async def cb_enter_promo(callback: types.CallbackQuery, state: FSMContext):
    """Ввод промокода"""
    await state.set_state(PromoStates.enter_code)
    await callback.message.answer("🎟 Введите промокод:")
    await callback.answer()


@router.message(PromoStates.enter_code)
async def process_promo_code(message: types.Message, session: AsyncSession, state: FSMContext):
    """Обработка ввода промокода"""
    code = message.text.strip()
    
    # Find promo
    result = await session.execute(select(PromoCode).where(PromoCode.code == code))
    promo = result.scalar_one_or_none()
    
    if not promo:
        await message.answer("❌ Промокод не найден")
        return
        
    if promo.current_uses >= promo.max_uses:
        await message.answer("❌ Промокод больше не активен (лимит исчерпан)")
        return
        
    if promo.expires_at and promo.expires_at < datetime.now():
        await message.answer("❌ Срок действия промокода истёк")
        return

    # Apply promo
    await state.update_data(promo_code=code, discount=promo.discount_percent, promo_id=promo.id)
    await message.answer(f"✅ Промокод <b>{code}</b> применён! Скидка {promo.discount_percent}%")
    
    # Return to product selection or retry purchase
    data = await state.get_data()
    product = data.get("product")
    if product:
        # Trigger buy callback again to recalculate price
        # We can't easily trigger callback, but we can simulate logic or ask user to click again.
        # Better: Show "Continue" button
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Продолжить оформление", callback_data=f"buy_{product}")]
        ])
        await message.answer("Нажмите, чтобы продолжить с новой ценой:", reply_markup=kb)
    else:
         await message.answer("Выберите товар в меню.", reply_markup=back_to_main_kb())


@router.callback_query(F.data.startswith("pay_balance_"))
async def cb_pay_balance(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """Оплата с баланса"""
    payment_code = callback.data.replace("pay_balance_", "")
    
    # Get payment
    stmt = select(Payment).where(
        Payment.payment_code == payment_code,
        Payment.user_id == user.id
    )
    result = await session.execute(stmt)
    payment = result.scalar()
    
    if not payment:
        await callback.answer("❌ Платёж не найден", show_alert=True)
        return
        
    if payment.status == "completed":
        await callback.answer("✅ Платёж уже обработан", show_alert=True)
        return

    # Check balance again
    if user.balance < payment.amount_ton:
        await callback.answer("❌ Недостаточно средств на балансе", show_alert=True)
        return
        
    # Deduct balance
    user.balance -= payment.amount_ton
    
    # Activate
    await activate_subscription(session, user, payment, callback.message)
    await callback.answer("✅ Оплачено с баланса!")


@router.callback_query(F.data.startswith("check_payment_"))
async def cb_check_payment(callback: types.CallbackQuery, session: AsyncSession, user: User):
    """
    Проверка платежа по коду.
    
    TODO: Для продакшена — интеграция с TON API для автоматической проверки.
    Сейчас — ручное подтверждение админом или автоматическое для тестов.
    """
    payment_code = callback.data.replace("check_payment_", "")
    
    # Находим платёж
    stmt = select(Payment).where(
        Payment.payment_code == payment_code,
        Payment.user_id == user.id
    )
    result = await session.execute(stmt)
    payment = result.scalar()
    
    if not payment:
        await callback.answer("❌ Платёж не найден", show_alert=True)
        return
    
    if payment.status == "completed":
        await callback.answer("✅ Платёж уже обработан", show_alert=True)
        return
    
    if payment.expires_at < datetime.now():
        payment.status = "expired"
        await session.commit()
        await callback.answer("❌ Время платежа истекло. Создайте новый.", show_alert=True)
        return
    
    # --- ПРОВЕРКА ПЛАТЕЖА ЧЕРЕЗ TON API ---
    await callback.answer("🔍 Проверяю платёж...")
    
    payment_verified = await verify_ton_payment(
        wallet=TON_WALLET,
        amount_ton=payment.amount_ton,
        payment_code=payment.payment_code,
        since_minutes=30
    )
    
    if not payment_verified:
        await callback.message.edit_text(
            f"❌ <b>Платёж не найден</b>\n\n"
            f"Убедитесь что:\n"
            f"• Вы отправили <b>{payment.amount_ton} TON</b>\n"
            f"• В комментарии указан код: <code>{payment.payment_code}</code>\n"
            f"• Прошло не более 30 минут\n\n"
            f"Попробуйте ещё раз через минуту.",
            reply_markup=create_payment_keyboard(payment.payment_code, payment.product_type, payment.amount_ton, user.balance)
        )
        return
    
    # Платёж подтверждён — активируем подписку
    await activate_subscription(session, user, payment, callback.message)
    await callback.answer("✅ Оплата подтверждена!")


@router.callback_query(F.data.startswith("extend_vpn_"))
async def cb_extend_vpn(callback: types.CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Продление VPN"""
    try:
        key_id = int(callback.data.split("_")[-1])
        key = await session.get(VPNKey, key_id)
        
        if not key or key.user_id != user.id:
            await callback.answer("❌ Ключ не найден", show_alert=True)
            return

        # Use same price as new VPN
        price_ton, rate, price_rub = await get_price_in_ton("vpn")
        product_type = f"extend_vpn:{key.id}"
        
        payment = await create_payment(session, user, product_type, price_ton)
        
        text = (
            f"🔄 <b>Продление VPN</b>\n\n"
            f"💰 Сумма: <b>{price_ton} TON</b> (~{price_rub}₽)\n"
            f"📊 Курс: {rate:.2f} ₽/TON\n"
            f"⏱ +30 дней\n\n"
            f"👇 Оплатите продление:"
        )
        
        kb = create_payment_keyboard(payment.payment_code, "vpn", price_ton, user.balance)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in extend_vpn: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("extend_dns_"))
async def cb_extend_dns(callback: types.CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Продление DNS"""
    try:
        access_id = int(callback.data.split("_")[-1])
        access = await session.get(DNSAccess, access_id)
        
        if not access or access.user_id != user.id:
            await callback.answer("❌ Эту подписку нельзя продлить", show_alert=True)
            return

        price_ton, rate, price_rub = await get_price_in_ton("dns")
        product_type = f"extend_dns:{access.id}"
        
        payment = await create_payment(session, user, product_type, price_ton)
        
        text = (
            f"🔄 <b>Продление DNS</b>\n\n"
            f"💰 Сумма: <b>{price_ton} TON</b> (~{price_rub}₽)\n"
            f"📊 Курс: {rate:.2f} ₽/TON\n"
            f"⏱ +30 дней\n\n"
            f"👇 Оплатите продление:"
        )
        
        kb = create_payment_keyboard(payment.payment_code, "dns", price_ton, user.balance)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in extend_dns: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


async def activate_subscription(session: AsyncSession, user: User, payment: Payment, message: types.Message):
    """Активация подписки, продление и начисление бонусов"""
    server = await get_available_server(session)
    if not server:
        await message.answer("❌ Нет доступных серверов. Обратитесь в поддержку.")
        return

    dns_server_ip = os.getenv("DNS_SERVER_IP", "185.x.x.x")
    text = ""
    
    try:
        # --- RENEWAL LOGIC ---
        if payment.product_type.startswith("extend_"):
            p_type, item_id = payment.product_type.split(":")
            item_id = int(item_id)
            
            if p_type == "extend_vpn":
                key = await session.get(VPNKey, item_id)
                if key:
                    # If expired, add 30 days to NOW. If active, add 30 days to EXPIRY.
                    if key.expires_at < datetime.now():
                        key.expires_at = datetime.now() + timedelta(days=30)
                    else:
                        key.expires_at += timedelta(days=30)
                    
                    # Reactivate if terminated
                    if not key.is_active:
                        outline = OutlineAPI(server.outline_api_url)
                        new_key = await outline.create_key(name=f"user_{user.telegram_id}")
                        key.outline_key_id = new_key.id
                        key.access_url = new_key.access_url
                        key.is_active = True
                        server.users_count += 1
                    
                    key.notification_status = 0
                    text = (
                        f"✅ <b>VPN продлён!</b>\n\n"
                        f"📅 Новый срок: {key.expires_at.strftime('%d.%m.%Y')}\n"
                        f"🔑 Ключ: <code>{key.access_url}</code>"
                    )

            elif p_type == "extend_dns":
                access = await session.get(DNSAccess, item_id)
                if access:
                    if access.expires_at < datetime.now():
                        access.expires_at = datetime.now() + timedelta(days=30)
                    else:
                        access.expires_at += timedelta(days=30)
                    
                    if not access.is_active:
                        access.is_active = True
                        if access.current_ip:
                             from bot.services.adguard_api import AdGuardAPI
                             adguard = AdGuardAPI(server.adguard_api_url, server.adguard_user, server.adguard_pass)
                             await adguard.add_allowed_client(f"User {user.telegram_id}", [access.current_ip])
                    
                    access.notification_status = 0
                    text = (
                        f"✅ <b>DNS продлён!</b>\n\n"
                        f"📅 Новый срок: {access.expires_at.strftime('%d.%m.%Y')}"
                    )

        # --- NEW SUBSCRIPTION LOGIC ---
        else:
            expires_at = datetime.now() + timedelta(days=30)
            key_url = ""
            
            if payment.product_type in ("vpn", "pro"):
                outline = OutlineAPI(server.outline_api_url)
                key = await outline.create_key(name=f"user_{user.telegram_id}")
                key_url = key.access_url
                
                vpn_key = VPNKey(
                    user_id=user.id,
                    server_id=server.id,
                    outline_key_id=key.id,
                    access_url=key.access_url,
                    expires_at=expires_at,
                    is_active=True
                )
                session.add(vpn_key)
                server.users_count += 1
            
            if payment.product_type in ("dns", "pro"):
                dns_access = DNSAccess(
                    user_id=user.id,
                    server_id=server.id,
                    current_ip=None,
                    expires_at=expires_at,
                    is_active=True
                )
                session.add(dns_access)
            
            # Form response text
            if payment.product_type == "vpn":
                text = (
                    f"✅ <b>VPN активирован!</b>\n\n"
                    f"🔑 Ваш ключ:\n<code>{key_url}</code>\n\n"
                    f"📅 До: {expires_at.strftime('%d.%m.%Y')}\n\n"
                    f"📱 Скачайте Outline и вставьте ключ."
                )
            elif payment.product_type == "dns":
                text = (
                    f"✅ <b>DNS активирован!</b>\n\n"
                    f"🖥 DNS: <code>{dns_server_ip}</code>\n"
                    f"📅 До: {expires_at.strftime('%d.%m.%Y')}\n\n"
                    f"👉 Нажмите «🔄 Обновить IP» в разделе «Мои ключи»."
                )
            else:
                text = (
                    f"✅ <b>PRO активирован!</b>\n\n"
                    f"🔐 VPN ключ:\n<code>{key_url}</code>\n\n"
                    f"🖥 DNS: <code>{dns_server_ip}</code>\n"
                    f"📅 До: {expires_at.strftime('%d.%m.%Y')}\n\n"
                    f"Для DNS нажмите «🔄 Обновить IP»."
                )

        # Обновляем статус платежа
        payment.status = "completed"
        payment.completed_at = datetime.now()
        
        # --- REFERRAL BONUS ---
        if user.referrer_id:
            bonus = payment.amount_ton * 0.10  # 10%
            referrer_stmt = select(User).where(User.id == user.referrer_id)
            referrer_result = await session.execute(referrer_stmt)
            referrer = referrer_result.scalar_one_or_none()
            
            if referrer:
                referrer.balance += bonus
                try:
                    await message.bot.send_message(
                        referrer.telegram_id,
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"Ваш реферал совершил покупку. Вам начислено <b>{bonus:.2f} TON</b>."
                    )
                except Exception:
                    pass

        await session.commit()
        
        if text:
            await message.edit_text(text, reply_markup=back_to_main_kb())
        
    except Exception as e:
        logger.error(f"Failed to activate: {e}")
        await message.answer("❌ Ошибка активации. Напишите в поддержку.")
