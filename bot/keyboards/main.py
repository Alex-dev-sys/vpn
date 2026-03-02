import os
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

# Prices in RUB
VPN_PRICE_RUB = os.getenv("VPN_PRICE_RUB", "150")
DNS_PRICE_RUB = os.getenv("DNS_PRICE_RUB", "100")
PRO_PRICE_RUB = os.getenv("PRO_PRICE_RUB", "200")
MINI_APP_URL = os.getenv("MINI_APP_URL", "").strip()
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/your_support")


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = []

    # Mini App button only works with HTTPS URL
    if MINI_APP_URL.startswith("https://"):
        kb.append(
            [InlineKeyboardButton(text="🚀 Открыть Mini App", web_app=WebAppInfo(url=MINI_APP_URL))]
        )

    kb.extend(
        [
            [InlineKeyboardButton(text="🛍 Купить подписку", callback_data="buy_menu")],
            [InlineKeyboardButton(text="💎 Купить TON за RUB", callback_data="p2p_buy")],
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
            [InlineKeyboardButton(text="🤝 Партнёрка", callback_data="partnership")],
            [InlineKeyboardButton(text="🔑 Мои ключи", callback_data="my_keys")],
            [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def buy_menu_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=f"🔐 VPN — {VPN_PRICE_RUB}₽", callback_data="buy_vpn")],
        [InlineKeyboardButton(text=f"🌐 DNS — {DNS_PRICE_RUB}₽", callback_data="buy_dns")],
        [InlineKeyboardButton(text=f"⭐ PRO (VPN+DNS) — {PRO_PRICE_RUB}₽", callback_data="buy_pro")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_to_main_kb() -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def keys_menu_kb(has_vpn: bool = False, has_dns: bool = False) -> InlineKeyboardMarkup:
    kb = []

    if has_vpn:
        kb.append([InlineKeyboardButton(text="🔐 Мой VPN ключ", callback_data="show_vpn_key")])

    if has_dns:
        kb.append([InlineKeyboardButton(text="🌐 Мой DNS", callback_data="show_dns")])
        kb.append([InlineKeyboardButton(text="🔄 Обновить IP", callback_data="update_ip")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_payment_kb(product: str, wallet: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{product}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="buy_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🖥 Серверы", callback_data="admin_servers")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
