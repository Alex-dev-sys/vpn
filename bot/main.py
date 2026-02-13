"""
Telegram Bot для продажи VPN (Outline) и DNS (AdGuard Home)

Запуск: python -m bot.main
"""
import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from bot.handlers import common, menu, payment, keys, admin, p2p
from bot.middlewares.db import DbSessionMiddleware, UserMiddleware
from bot.database.core import init_db
from bot.services.scheduler import setup_scheduler

# Загружаем переменные окружения
load_dotenv()

# Sentry error monitoring
import sentry_sdk
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)


async def main():
    # Настройка логирования
    # Настройка логирования с ротацией
    from logging.handlers import TimedRotatingFileHandler
    
    file_handler = TimedRotatingFileHandler(
        filename="bot.log", 
        when="midnight", 
        interval=1, 
        backupCount=7, 
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, stream_handler]
    )
    logger = logging.getLogger(__name__)

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return

    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Настройка Middleware
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserMiddleware())

    # Подключение роутеров
    dp.include_router(common.router)
    dp.include_router(menu.router)
    dp.include_router(payment.router)
    dp.include_router(keys.router)
    dp.include_router(admin.router)
    dp.include_router(p2p.router)

    # Инициализация БД
    await init_db()
    logger.info("Database initialized.")

    # Запуск планировщика
    setup_scheduler(bot)
    logger.info("Scheduler started.")

    # Запуск polling
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
