from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main import main_menu_kb
from bot.database.models import User

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message, user: User, command: CommandStart, session: AsyncSession):
    """Команда /start - показать главное меню"""
    # Check for referral
    referrer_id = command.args
    if referrer_id and referrer_id.isdigit():
        ref_id = int(referrer_id)
        # Cannot refer self and cannot update if already has referrer
        if ref_id != user.telegram_id and user.referrer_id is None:
            # Check if referrer exists
            from sqlalchemy import select
            referrer_result = await session.execute(select(User).where(User.telegram_id == ref_id))
            referrer = referrer_result.scalar_one_or_none()
            
            if referrer:
                user.referrer_id = referrer.id
                await session.commit()
                # Notify referrer (optional, maybe too spammy?)
                # await message.bot.send_message(ref_id, f"➕ Новый реферал: {message.from_user.first_name}")

    from bot.services.rate_service import get_ton_rub_rate
    rate = await get_ton_rub_rate()
    rate_text = f"📊 Курс TON: <b>{rate:.2f} ₽</b>" if rate else "📊 Курс TON: н/д"

    text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"{rate_text}\n\n"
        "Добро пожаловать в бот продажи VPN и DNS.\n\n"
        "🔐 <b>VPN</b> — безлимитный доступ через Outline\n"
        "🌐 <b>DNS</b> — приватный DNS с блокировкой рекламы\n\n"
        "Выберите действие:"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery, user: User):
    """Возврат в главное меню"""
    from bot.services.rate_service import get_ton_rub_rate
    rate = await get_ton_rub_rate()
    rate_text = f"📊 Курс TON: <b>{rate:.2f} ₽</b>" if rate else "📊 Курс TON: н/д"

    text = (
        f"🏠 <b>Главное меню</b>\n\n"
        f"{rate_text}\n"
        f"👤 Ваш ID: <code>{user.telegram_id}</code>\n"
        f"💰 Баланс: <b>{user.balance:.2f} TON</b>\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help"""
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
