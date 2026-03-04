# DNS VPN Bot

Премиальный Telegram-проект для продажи:
- VPN-подписки (Outline)
- DNS-подписки (AdGuard Home)
- P2P покупки TON за RUB
- Web Dashboard + Mini App интерфейс

---

## Что внутри

### Telegram Bot (`aiogram`)
- покупка VPN / DNS / PRO
- TON-платежи с кодом платежа
- проверка оплаты и выдача доступа
- P2P сценарий: RUB -> TON
- реферальная система
- админ-команды и рассылки

### Dashboard (`FastAPI`)
- статистика, пользователи, заказы
- подтверждение/отмена P2P
- API для Mini App:
  - `GET /api/mini/bootstrap`
  - `POST /api/mini/create-payment`
  - `GET /api/mini/faq`

### Mini App (`Next.js`)
- витрина с реальными ценами и статусами
- запуск оплаты TON и deep-link в бота
- запуск P2P сценария
- профиль, рефералка, FAQ, поддержка
- deep-link установка ключа на устройство

---

## Стек

- Python 3.11+
- aiogram 3
- SQLAlchemy + SQLite
- FastAPI + Jinja2
- Next.js 16 + React 19
- APScheduler
- Docker / Docker Compose

---

## Структура проекта

```text
bot/             # Telegram bot (handlers/services/database)
dashboard/       # FastAPI dashboard + mini API
dashboard-ui/    # Next.js mini app frontend
alembic/         # DB migrations
data/            # SQLite DB
scripts/         # service scripts
```

---

## Быстрый старт (локально)

### 1. Клонирование и зависимости

```bash
git clone https://github.com/Alex-dev-sys/vpn.git
cd vpn
pip install -r requirements.txt
```

### 2. Настройка `.env`

Минимально важно:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_IDS=123456789
DASHBOARD_PASSWORD=CHANGE_ME_STRONG
DATABASE_URL=sqlite+aiosqlite:///data/bot.db

TON_WALLET=YOUR_TON_WALLET
HOT_WALLET_MNEMONICS=...

VPN_PRICE_RUB=199
DNS_PRICE_RUB=149
PRO_PRICE_RUB=299

DNS_SERVER_IP=YOUR_SERVER_IP

BOT_USERNAME=your_bot_username
SUPPORT_USERNAME=your_support_username

MINI_APP_URL=https://your-domain.com
CORS_ORIGINS=https://your-domain.com
MINI_APP_STRICT_AUTH=1
SESSION_TTL_SECONDS=43200
COOKIE_SECURE=1
COOKIE_SAMESITE=lax
```

### 3. Запуск бота

```bash
python -m bot.main
```

### 4. Запуск dashboard API

```bash
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```

### 5. Запуск mini app

```bash
cd dashboard-ui
npm install
npm run dev
```

---

## Telegram Mini App настройка

1. Привяжите домен в `@BotFather` (`/setdomain`).
2. В `.env` укажите:
   - `MINI_APP_URL=https://your-domain.com`
3. В главном меню бота появится кнопка `🚀 Открыть Mini App`.

Важно: Mini App должен быть доступен по **HTTPS**.

---

## Docker

```bash
docker compose up -d --build
```

Сервисы:
- `bot`
- `dashboard` (порт `8080`)

---

## Полезные команды

### Проверка фронта
```bash
cd dashboard-ui
npm run lint
npm run build
```

### Проверка Python-файлов
```bash
python -m py_compile dashboard/app.py bot/handlers/common.py
python -m pytest
```

### Healthcheck
```bash
curl http://127.0.0.1:8080/health/live
curl http://127.0.0.1:8080/health/ready
```

---

## Безопасность

- Никогда не коммитьте реальный `.env`
- Используйте сильный пароль dashboard
- Включите HTTPS для dashboard и mini app
- Ограничьте доступ к админке по IP (если возможно)
- Регулярно делайте бэкапы `data/bot.db`

---

## Roadmap (ближайшее)

- Telegram initData верификация в mini API
- CSRF/сессионное усиление dashboard
- Автотесты на критичные сценарии оплаты
- Улучшение аналитики продаж и retention

---

## License

Private project / internal use.
