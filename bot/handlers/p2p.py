"""
P2P Exchange handler - покупка TON за рубли
"""
import logging
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from bot.database.models import User, P2POrder, P2POrderStatus
from bot.keyboards.main import back_to_main_kb
from bot.services.rate_service import get_ton_rub_rate
from bot.services.settings_service import get_margin_percent, get_card_number, get_bank_name, get_sbp_phone
from bot.services.ton_wallet import validate_ton_address, get_wallet

logger = logging.getLogger(__name__)
router = Router()

# Config from env
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
MIN_TON = float(os.getenv("MIN_TON", "1"))
MAX_TON = float(os.getenv("MAX_TON", "100"))
HOT_WALLET_MNEMONICS = os.getenv("HOT_WALLET_MNEMONICS", "")
HOT_WALLET_ADDRESS = os.getenv("HOT_WALLET_ADDRESS", "").strip()
P2P_DAILY_LIMIT = int(os.getenv("P2P_DAILY_LIMIT", "50000"))  # RUB


def _wallet_env() -> tuple[str, str]:
    """Read wallet settings dynamically from env to avoid stale values."""
    mnemonics = os.getenv("HOT_WALLET_MNEMONICS", HOT_WALLET_MNEMONICS).strip()
    address = os.getenv("HOT_WALLET_ADDRESS", HOT_WALLET_ADDRESS).strip()
    return mnemonics, address


class P2PBuyStates(StatesGroup):
    """States for P2P buying"""
    amount = State()
    wallet = State()


# === P2P Keyboards ===
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def p2p_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="p2p_cancel")]]
    )


def p2p_payment_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"p2p_paid:{order_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"p2p_cancel:{order_id}")]
        ]
    )


def p2p_admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data=f"p2p_confirm:{order_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"p2p_reject:{order_id}")]
        ]
    )


def _wallet_matches_configured_address(wallet_address: str) -> bool:
    """Verify mnemonic-derived wallet address matches HOT_WALLET_ADDRESS."""
    # Optional strict check: set P2P_ENFORCE_WALLET_ADDRESS_MATCH=1 to enforce.
    if os.getenv("P2P_ENFORCE_WALLET_ADDRESS_MATCH", "0").strip() != "1":
        return True

    _, configured_address = _wallet_env()
    if not configured_address:
        return True

    derived = (wallet_address or "").strip()
    if derived == configured_address:
        return True

    try:
        from pytoniq import Address
        derived_raw = Address(derived).to_str(is_user_friendly=False)
        configured_raw = Address(configured_address).to_str(is_user_friendly=False)
        return derived_raw == configured_raw
    except Exception:
        return False


# === User Handlers ===

@router.callback_query(F.data == "p2p_buy")
async def cb_p2p_buy(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Start P2P purchase"""
    # Check for existing pending order
    result = await session.execute(
        select(P2POrder).where(
            P2POrder.user_id == user.id,
            P2POrder.status.in_([P2POrderStatus.PENDING.value, P2POrderStatus.WAITING_CONFIRMATION.value])
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        await callback.answer(f"У вас уже есть активный заказ #{existing.id}", show_alert=True)
        return
    
    # Get wallet balance for dynamic limit.
    # Do not fallback to static MAX_TON on errors, otherwise users see incorrect availability.
    hot_wallet_mnemonics, _ = _wallet_env()
    if not hot_wallet_mnemonics:
        await callback.answer("⚠️ Кошелек P2P не настроен. Обратитесь в поддержку.", show_alert=True)
        return

    try:
        wallet = await get_wallet(hot_wallet_mnemonics)
        if not _wallet_matches_configured_address(wallet.address or ""):
            logger.error(
                "HOT_WALLET_ADDRESS mismatch during balance fetch: derived=%s configured=%s",
                wallet.address,
                HOT_WALLET_ADDRESS,
            )
            await callback.answer("⚠️ Ошибка настройки кошелька P2P. Обратитесь в поддержку.", show_alert=True)
            return
        balance = await wallet.get_balance()
        max_available = max(0.0, balance - 0.1)  # Reserve 0.1 TON for gas
    except Exception as e:
        logger.error(f"Failed to get wallet balance: {e}")
        await callback.answer("⚠️ Не удалось получить баланс кошелька. Попробуйте позже.", show_alert=True)
        return

    if max_available < MIN_TON:
        await callback.answer(
            f"⚠️ Недостаточно TON на кошельке для P2P (доступно: {max_available:.2f} TON).",
            show_alert=True,
        )
        return

    await state.update_data(max_available=max_available)
    await state.set_state(P2PBuyStates.amount)
    
    await callback.message.edit_text(
        f"💎 <b>Купить TON за рубли</b>\n\n"
        f"Доступно для покупки: <b>{max_available:.2f} TON</b>\n"
        f"Введите количество TON для покупки:\n"
        f"(минимум {MIN_TON} TON)",
        reply_markup=p2p_cancel_kb()
    )
    await callback.answer()


@router.message(P2PBuyStates.amount)
async def process_p2p_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    """Process TON amount"""
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число. Например: 5 или 10.5")
        return
    
    if amount < MIN_TON:
        await message.answer(f"❌ Минимум: {MIN_TON} TON")
        return
    
    # Check against dynamic limit
    data = await state.get_data()
    max_available = data.get("max_available", 0.0)
    
    if amount > max_available:
        await message.answer(f"❌ Максимум доступно: {max_available:.2f} TON")
        return
    
    # Check daily limit
    from datetime import timedelta
    from sqlalchemy import func as sql_func
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    spent_today = (await session.execute(
        select(sql_func.sum(P2POrder.amount_rub)).where(
            P2POrder.user_id == user.id,
            P2POrder.created_at >= today,
            P2POrder.status.in_([P2POrderStatus.PENDING.value, P2POrderStatus.WAITING_CONFIRMATION.value, P2POrderStatus.COMPLETED.value])
        )
    )).scalar() or 0
    
    # Get rate
    rate = await get_ton_rub_rate()
    if not rate:
        await message.answer("❌ Не удалось получить курс. Попробуйте позже.")
        return
    
    # Hardcoded 10% margin
    margin = 10 
    final_rate = rate * (1 + margin / 100)
    new_order_rub = int(amount * final_rate)
    
    if spent_today + new_order_rub > P2P_DAILY_LIMIT:
        remaining = P2P_DAILY_LIMIT - spent_today
        await message.answer(
            f"❌ Превышен дневной лимит!\n\n"
            f"📊 Лимит: {P2P_DAILY_LIMIT:,} ₽/день\n"
            f"💸 Потрачено сегодня: {int(spent_today):,} ₽\n"
            f"💰 Осталось: {max(0, remaining):,} ₽"
        )
        return

    # Double check balance (just in case)
    try:
        hot_wallet_mnemonics, _ = _wallet_env()
        if hot_wallet_mnemonics:
            wallet = await get_wallet(hot_wallet_mnemonics)
            if not _wallet_matches_configured_address(wallet.address or ""):
                logger.error(
                    "HOT_WALLET_ADDRESS mismatch during amount check: derived=%s configured=%s",
                    wallet.address,
                    HOT_WALLET_ADDRESS,
                )
                await message.answer("⚠️ Ошибка настройки кошелька P2P. Обратитесь в поддержку.")
                return
            balance = await wallet.get_balance()
            if balance < amount + 0.05:
                await message.answer("⚠️ Баланс бота изменился. Попробуйте меньшую сумму.")
                # Update limit for retry
                await state.update_data(max_available=max(0.0, balance - 0.1))
                return
    except Exception as e:
        logger.warning(f"Balance check failed: {e}")
    
    await state.update_data(amount_ton=amount, amount_rub=new_order_rub, exchange_rate=final_rate)
    await state.set_state(P2PBuyStates.wallet)
    
    await message.answer(
        f"💎 <b>Расчёт</b>\n\n"
        f"Количество: <code>{amount}</code> TON\n"
        f"Курс: <code>{final_rate:.2f}</code> ₽/TON (+10%)\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>К оплате: {new_order_rub} ₽</b>\n\n"
        f"Введите адрес вашего TON-кошелька:",
        reply_markup=p2p_cancel_kb()
    )


@router.message(P2PBuyStates.wallet)
async def process_p2p_wallet(message: Message, session: AsyncSession, user: User, state: FSMContext, bot: Bot):
    """Process wallet address"""
    wallet_address = message.text.strip()
    
    is_valid, error = validate_ton_address(wallet_address)
    if not is_valid:
        await message.answer(f"❌ Неверный адрес:\n{error}")
        return
    
    data = await state.get_data()
    
    # Create order
    order = P2POrder(
        user_id=user.id,
        amount_ton=data["amount_ton"],
        amount_rub=data["amount_rub"],
        exchange_rate=data["exchange_rate"],
        wallet_address=wallet_address,
        status=P2POrderStatus.PENDING.value
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    
    # Get payment details
    card = await get_card_number(session)
    bank = await get_bank_name(session)
    sbp = await get_sbp_phone(session)
    
    payment_info = f"🏦 Банк: {bank}\n💳 Карта: <code>{card}</code>"
    if sbp:
        payment_info += f"\n📱 СБП: <code>{sbp}</code>"
    
    await state.clear()
    
    await message.answer(
        f"📋 <b>Заказ #{order.id}</b>\n\n"
        f"💎 Покупка: <code>{order.amount_ton}</code> TON\n"
        f"💵 Сумма: <code>{order.amount_rub}</code> ₽\n"
        f"👛 Кошелёк: <code>{wallet_address[:15]}...{wallet_address[-6:]}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"<b>Реквизиты:</b>\n{payment_info}\n\n"
        f"⚠️ Переведите <b>точно {order.amount_rub} ₽</b>\n\n"
        f"После оплаты нажмите «Я оплатил»",
        reply_markup=p2p_payment_kb(order.id)
    )


@router.callback_query(F.data.startswith("p2p_paid:"))
async def process_p2p_paid(callback: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    """User confirms payment"""
    order_id = int(callback.data.split(":")[1])
    
    result = await session.execute(select(P2POrder).where(P2POrder.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order or order.user_id != user.id:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order.status = P2POrderStatus.WAITING_CONFIRMATION.value
    await session.commit()
    
    await callback.message.edit_text(
        f"⏳ <b>Заказ #{order.id}</b>\n\n"
        f"Ожидайте подтверждения администратора.\n"
        f"TON будут отправлены автоматически."
    )
    
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>P2P Заказ #{order.id}</b>\n\n"
                f"👤 @{user.username or 'N/A'} (ID: {user.telegram_id})\n"
                f"💎 {order.amount_ton} TON\n"
                f"💵 {order.amount_rub} ₽\n"
                f"👛 <code>{order.wallet_address}</code>\n\n"
                f"⚠️ <b>ПРОВЕРЬТЕ ПОСТУПЛЕНИЕ СРЕДСТВ В БАНКОВСКОМ ПРИЛОЖЕНИИ!</b>\n"
                f"Не доверяйте скриншотам и уведомлениям.",
                reply_markup=p2p_admin_order_kb(order.id)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    
    await callback.answer()


@router.callback_query(F.data.startswith("p2p_cancel"))
async def process_p2p_cancel(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Cancel P2P order"""
    await state.clear()
    
    if ":" in callback.data:
        order_id = int(callback.data.split(":")[1])
        result = await session.execute(select(P2POrder).where(P2POrder.id == order_id))
        order = result.scalar_one_or_none()
        if order and order.user_id == user.id:
            order.status = P2POrderStatus.CANCELED.value
            order.cancel_reason = "Отменено пользователем"
            await session.commit()
    
    await callback.message.edit_text(
        "❌ Заказ отменён.\n\nВернуться в главное меню:",
        reply_markup=back_to_main_kb()
    )
    await callback.answer()


# === Admin Handlers ===

@router.callback_query(F.data.startswith("p2p_confirm:"))
async def admin_confirm_p2p(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Admin confirms P2P order"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    order_id = int(callback.data.split(":")[1])
    
    result = await session.execute(select(P2POrder).where(P2POrder.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order or order.status not in {P2POrderStatus.WAITING_CONFIRMATION.value, "processing"}:
        await callback.answer("❌ Заказ не найден или уже обработан", show_alert=True)
        return
    if order.status == "processing":
        await callback.answer("⏳ Заказ уже обрабатывается", show_alert=True)
        return

    lock_result = await session.execute(
        update(P2POrder)
        .where(P2POrder.id == order_id, P2POrder.status == P2POrderStatus.WAITING_CONFIRMATION.value)
        .values(status="processing")
    )
    await session.commit()
    if (lock_result.rowcount or 0) == 0:
        await callback.answer("⏳ Заказ уже обрабатывается", show_alert=True)
        return
    
    await callback.answer("⏳ Отправляю TON...")
    
    try:
        hot_wallet_mnemonics, _ = _wallet_env()
        if not hot_wallet_mnemonics:
            await callback.message.edit_text("❌ Кошелек P2P не настроен (нет HOT_WALLET_MNEMONICS).")
            return
        wallet = await get_wallet(hot_wallet_mnemonics)
        if not _wallet_matches_configured_address(wallet.address or ""):
            logger.error(
                "HOT_WALLET_ADDRESS mismatch during send: derived=%s configured=%s",
                wallet.address,
                HOT_WALLET_ADDRESS,
            )
            await callback.message.edit_text("❌ Ошибка настройки кошелька P2P. Проверьте HOT_WALLET_ADDRESS.")
            return
        tx_result = await wallet.send_ton(order.wallet_address, order.amount_ton)
        
        if tx_result.success:
            order.status = P2POrderStatus.COMPLETED.value
            order.tx_hash = tx_result.tx_hash
            order.completed_at = datetime.now()
            await session.commit()
            
            await callback.message.edit_text(
                f"✅ <b>Заказ #{order.id} выполнен!</b>\n\n"
                f"💎 {order.amount_ton} TON\n"
                f"🔗 <a href='https://tonviewer.com/transaction/{tx_result.tx_hash}'>TX</a>"
            )
            
            # Notify user
            user_result = await session.execute(select(User).where(User.id == order.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                await bot.send_message(
                    user.telegram_id,
                    f"✅ <b>Заказ #{order.id} выполнен!</b>\n\n"
                    f"💎 Отправлено: {order.amount_ton} TON\n"
                    f"🔗 <a href='https://tonviewer.com/transaction/{tx_result.tx_hash}'>Проверить</a>"
                )
        else:
            order.status = P2POrderStatus.WAITING_CONFIRMATION.value
            await session.commit()
            await callback.message.edit_text(f"❌ Ошибка: {tx_result.error}")
    except Exception as e:
        logger.error(f"P2P send failed: {e}")
        order.status = P2POrderStatus.WAITING_CONFIRMATION.value
        await session.commit()
        await callback.message.edit_text(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("p2p_reject:"))
async def admin_reject_p2p(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Admin rejects P2P order"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    order_id = int(callback.data.split(":")[1])
    
    result = await session.execute(select(P2POrder).where(P2POrder.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order.status = P2POrderStatus.CANCELED.value
    order.cancel_reason = "Отклонено администратором"
    await session.commit()
    
    await callback.message.edit_text(f"❌ Заказ #{order.id} отклонён")
    
    # Notify user
    user_result = await session.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        await bot.send_message(
            user.telegram_id,
            f"❌ <b>Заказ #{order.id} отклонён</b>\n\n"
            f"Обратитесь в поддержку если уже оплатили."
        )
    
    await callback.answer()
