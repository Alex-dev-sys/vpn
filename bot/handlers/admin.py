"""
Админ обработчики
"""
import os
import logging
from datetime import datetime

from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.database.models import User, Server, VPNKey, DNSAccess
from bot.keyboards.main import admin_kb, back_to_main_kb

router = Router()
logger = logging.getLogger(__name__)

# Список админов из env
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь админом"""
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Админ панель"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("🔧 <b>Админ-панель</b>", reply_markup=admin_kb())


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery, session: AsyncSession):
    """Статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    now = datetime.now()
    
    # Считаем статистику
    users_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    
    active_vpn = (await session.execute(
        select(func.count(VPNKey.id)).where(VPNKey.is_active == True, VPNKey.expires_at > now)
    )).scalar() or 0
    
    active_dns = (await session.execute(
        select(func.count(DNSAccess.id)).where(DNSAccess.is_active == True, DNSAccess.expires_at > now)
    )).scalar() or 0
    
    servers_count = (await session.execute(select(func.count(Server.id)))).scalar() or 0
    
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"🔐 Активных VPN: {active_vpn}\n"
        f"🌐 Активных DNS: {active_dns}\n"
        f"🖥 Серверов: {servers_count}"
    )
    
    await callback.message.edit_text(text, reply_markup=admin_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_servers")
async def cb_admin_servers(callback: types.CallbackQuery, session: AsyncSession):
    """Список серверов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    stmt = select(Server)
    result = await session.execute(stmt)
    servers = result.scalars().all()
    
    if not servers:
        text = "🖥 <b>Серверы</b>\n\n❌ Нет серверов.\n\nДобавьте сервер командой:\n/add_server"
    else:
        lines = ["🖥 <b>Серверы</b>\n"]
        for s in servers:
            status = "✅" if s.is_active else "❌"
            lines.append(f"{status} <b>{s.name}</b>: {s.users_count}/{s.max_users}")
        text = "\n".join(lines)
    
    await callback.message.edit_text(text, reply_markup=admin_kb())
    await callback.answer()


@router.message(Command("add_server"))
async def cmd_add_server(message: types.Message, session: AsyncSession):
    """
    Добавить сервер. Формат:
    /add_server name|outline_url|adguard_url|adguard_user|adguard_pass
    """
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.replace("/add_server", "").strip()
    
    if not args or "|" not in args:
        await message.answer(
            "📝 Формат:\n"
            "<code>/add_server name|outline_api_url|adguard_api_url|adguard_user|adguard_pass</code>\n\n"
            "Пример:\n"
            "<code>/add_server Server1|https://1.2.3.4:12345/SECRET|http://1.2.3.4:3000|admin|password</code>"
        )
        return
    
    parts = args.split("|")
    if len(parts) != 5:
        await message.answer("❌ Неверный формат. Нужно 5 параметров через |")
        return
    
    name, outline_url, adguard_url, adguard_user, adguard_pass = parts
    
    server = Server(
        name=name.strip(),
        outline_api_url=outline_url.strip(),
        adguard_api_url=adguard_url.strip(),
        adguard_user=adguard_user.strip(),
        adguard_pass=adguard_pass.strip(),
        users_count=0,
        is_active=True
    )
    session.add(server)
    await session.commit()
    
    await message.answer(f"✅ Сервер <b>{name}</b> добавлен!")


from bot.database.models import PromoCode

@router.message(Command("add_promo"))
async def cmd_add_promo(message: types.Message, session: AsyncSession):
    """
    Добавить промокод.
    Команда: /add_promo CODE PERCENT [USES]
    Пример: /add_promo SALE20 20 100
    """
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("📝 Формат: <code>/add_promo CODE PERCENT [USES]</code>")
        return

    code = args[1].upper()
    try:
        percent = int(args[2])
        uses = int(args[3]) if len(args) > 3 else 999999
    except ValueError:
        await message.answer("❌ Процент и кол-во использований должны быть числами")
        return

    if not (1 <= percent <= 100):
        await message.answer("❌ Процент должен быть от 1 до 100")
        return

    # Check existence
    existing = await session.execute(select(PromoCode).where(PromoCode.code == code))
    if existing.scalar():
        await message.answer(f"❌ Промокод {code} уже существует")
        return

    promo = PromoCode(
        code=code,
        discount_percent=percent,
        max_uses=uses,
        expires_at=None  # Can be added later
    )
    session.add(promo)
    await session.commit()
    
    await message.answer(f"✅ Промокод <b>{code}</b> ({percent}%) создан! (Лимит: {uses})")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, session: AsyncSession):
    """
    Рассылка всем пользователям.
    Команда: /broadcast TEXT
    """
    if not is_admin(message.from_user.id):
        return

    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("📝 Введите текст рассылки после команды")
        return

    await message.answer("⏳ Начинаю рассылку...")

    # Get all users
    result = await session.execute(select(User.telegram_id))
    user_ids = result.scalars().all()
    
    success = 0
    blocked = 0
    
    for user_id in user_ids:
        try:
            await message.bot.send_message(user_id, text)
            success += 1
        except Exception as e:
            # Bot was blocked by user
            blocked += 1
            
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {success}\n"
        f"🚫 Заблокировано: {blocked}"
    )


from bot.services.backup_service import BackupService
from aiogram.types import FSInputFile

@router.message(Command("backup"))
async def cmd_backup(message: types.Message):
    """
    Создать и отправить бэкап базы данных
    """
    if not is_admin(message.from_user.id):
        return

    await message.answer("⏳ Создаю бэкап...")
    
    try:
        backup_path = BackupService.create_backup()
        file = FSInputFile(backup_path)
        
        await message.answer_document(
            file,
            caption=f"📦 <b>Ручной бэкап</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
    except Exception as e:
        logger.error(f"Manual backup failed: {e}")
        await message.answer(f"❌ Ошибка создания бэкапа: {e}")
