from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Payment, User
from bot.handlers.payment import create_payment_keyboard
from bot.keyboards.main import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message, user: User, command: CommandStart, session: AsyncSession):
    """Команда /start - показать главное меню и обработать deep links."""
    # Deep link from mini app for P2P flow
    if command.args == "p2p":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💎 Купить TON за RUB", callback_data="p2p_buy")]]
        )
        await message.answer(
            "💎 <b>P2P обмен TON</b>\n\n"
            "Нажмите кнопку ниже, чтобы начать покупку TON за рубли.",
            reply_markup=kb,
        )
        return

    # Deep link from mini app for payment verification flow
    if command.args and command.args.startswith("pay_"):
        payment_code = command.args.replace("pay_", "", 1).strip().upper()
        result = await session.execute(
            select(Payment).where(Payment.payment_code == payment_code, Payment.user_id == user.id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            await message.answer("❌ Платеж не найден. Создайте новый через витрину.", reply_markup=main_menu_kb())
            return

        text = (
            "💳 <b>Проверка оплаты</b>\n\n"
            f"Код: <code>{payment.payment_code}</code>\n"
            f"Сумма: <b>{payment.amount_ton} TON</b>\n\n"
            "После оплаты нажмите кнопку «Я оплатил»."
        )
        await message.answer(
            text,
            reply_markup=create_payment_keyboard(
                payment.payment_code, payment.product_type, payment.amount_ton, user.balance
            ),
        )
        return

    # Referral logic
    referrer_id = command.args
    if referrer_id and referrer_id.isdigit():
        ref_id = int(referrer_id)
        if ref_id != user.telegram_id and user.referrer_id is None:
            referrer_result = await session.execute(select(User).where(User.telegram_id == ref_id))
            referrer = referrer_result.scalar_one_or_none()
            if referrer:
                user.referrer_id = referrer.id
                await session.commit()

    from bot.services.rate_service import get_ton_rub_rate

    rate = await get_ton_rub_rate()
    rate_text = f"📊 Курс TON: <b>{rate:.2f} ₽</b>" if rate else "📊 Курс TON: н/д"

    text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "1️⃣ <b>Откройте приложение</b>\n\n"
        "2️⃣ Нажмите <b>«Установка и настройка»</b> и следуйте инструкции,\n"
        "чтобы подключить устройство\n\n"
        "3️⃣ <b>Готово!</b> Пользуйтесь VPN и DNS без ограничений\n\n"
        "Возникли вопросы или сложности? "
        "<a href='https://t.me/your_support'>Напишите в службу поддержки</a>, "
        "мы обязательно вам поможем 👨🏻‍💻\n\n"
        f"{rate_text}"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery, user: User):
    """Возврат в главное меню."""
    from bot.services.rate_service import get_ton_rub_rate

    rate = await get_ton_rub_rate()
    rate_text = f"📊 Курс TON: <b>{rate:.2f} ₽</b>" if rate else "📊 Курс TON: н/д"

    text = (
        "🏠 <b>Главное меню</b>\n\n"
        f"{rate_text}\n"
        f"👤 Ваш ID: <code>{user.telegram_id}</code>\n"
        f"💰 Баланс: <b>{user.balance:.2f} TON</b>\n\n"
        "Выберите действие:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=main_menu_kb())
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help."""
    text = (
        "💡 <b>Помощь</b>\n\n"
        "<b>VPN (Outline):</b>\n"
        "После покупки вы получите ключ для подключения. "
        "Установите приложение Outline на устройство и вставьте ключ.\n\n"
        "<b>DNS (AdGuard):</b>\n"
        "После покупки нажмите «Обновить IP» — мы авторизуем ваш IP-адрес. "
        "Затем пропишите наш DNS-сервер в настройках устройства.\n\n"
        "🆘 По вопросам: /support"
    )
    await message.answer(text, reply_markup=main_menu_kb())
