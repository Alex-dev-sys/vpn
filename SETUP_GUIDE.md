# 📋 Полная инструкция по развёртыванию VPN + DNS бота

## 🖥️ Требования к серверу

- **ОС:** Ubuntu 22.04 LTS (рекомендуется)
- **RAM:** минимум 1 GB
- **CPU:** 1 ядро
- **IP:** статический публичный IP
- **Порты:** 53 (DNS), 80/3000 (AdGuard), 443 (Outline)в

---

## 1️⃣ Установка Docker

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com | sh

# Добавляем пользователя в группу docker
sudo usermod -aG docker $USER

# Перелогиниваемся
exit
# Заходим снова по SSH
```

---

## 2️⃣ Установка Outline VPN Server

```bash
# Скачиваем и запускаем установщик
sudo bash -c "$(wget -qO- https://raw.githubusercontent.com/Jigsaw-Code/outline-server/master/src/server_manager/install_scripts/install_server.sh)"
```

После установки вы получите:
```
✅ Outline Server установлен!

Management API URL: https://123.45.67.89:12345/AbCdEfGhIjKlMnOp
Certification SHA-256: XXXXXXXXXX...
```

**⚠️ СОХРАНИТЕ Management API URL — это ваш `OUTLINE_API_URL` для бота!**

### Проверка работы Outline

```bash
# Проверяем что контейнер запущен
docker ps | grep outline
```

---

## 3️⃣ Установка AdGuard Home

### Создаём директорию и docker-compose

```bash
mkdir -p ~/adguard && cd ~/adguard
```

Создайте файл `docker-compose.yml`:

```yaml
version: '3'
services:
  adguard:
    image: adguard/adguardhome:latest
    container_name: adguard
    restart: unless-stopped
    ports:
      - "53:53/tcp"    # DNS TCP
      - "53:53/udp"    # DNS UDP
      - "80:80/tcp"    # Web UI (можно 3000:3000 если 80 занят)
      - "3000:3000/tcp" # Первоначальная настройка / API
    volumes:
      - ./work:/opt/adguardhome/work
      - ./conf:/opt/adguardhome/conf
```

### Запуск AdGuard Home

```bash
docker compose up -d
```

### Первоначальная настройка

1. Откройте в браузере: `http://ВАШ_IP:3000`
2. Пройдите мастер настройки:
   - Web интерфейс: порт `80` (или `3000`)
   - DNS сервер: порт `53`
   - Логин: `admin`
   - Пароль: придумайте (запомните для бота!)

### Настройка Upstream DNS (Xbox DNS)

1. Зайдите: **Настройки → Настройки DNS**
2. В поле **Upstream DNS** введите:
   ```
   176.99.11.77
   80.78.247.254
   ```
3. Включите: **☑️ Parallel requests**
4. Нажмите **Сохранить**

### Настройка доступа (важно!)

1. Зайдите: **Настройки → Настройки доступа**
2. По умолчанию AdGuard принимает запросы от всех. 
3. Бот будет добавлять IP клиентов в "Разрешённые клиенты"
4. Если хотите блокировать всех кроме разрешённых — оставьте список пустым, бот сам добавит нужные IP

---

## 4️⃣ Настройка бота

### На Windows (локально для тестов)

```powershell
cd c:\Users\LXKLGNV\dns_vpn_bot

# Установка зависимостей
pip install -r requirements.txt
```

### Настройка .env

Отредактируйте файл `.env`:

```env
BOT_TOKEN=8540366107:AAHt7uUNsF5UdEVLhXAI0e-31rwyaxJadVA
ADMIN_IDS=ВАШ_TELEGRAM_ID

# Outline VPN Server (URL из шага 2)
OUTLINE_API_URL=https://123.45.67.89:12345/AbCdEfGhIjKlMnOp

# AdGuard Home
ADGUARD_URL=http://123.45.67.89:3000
ADGUARD_USER=admin
ADGUARD_PASS=ваш_пароль_от_adguard

# TON Payments
TON_WALLET=UQCAKkJZSo2h5VAWyPO1vGtqFbRMp_x-rHlYfmTsUBFQUDl-

# Цены (в TON)
VPN_PRICE=1.5
DNS_PRICE=0.8
PRO_PRICE=2.0

# IP вашего DNS сервера (показывается пользователям)
DNS_SERVER_IP=123.45.67.89
```

### Запуск бота

```bash
python -m bot.main
```

---

## 5️⃣ Первый запуск — добавление сервера

1. Напишите боту `/start`
2. Узнайте ваш Telegram ID из профиля
3. Добавьте его в `ADMIN_IDS` в `.env`
4. Перезапустите бота
5. Напишите `/admin` → должна появиться админ-панель
6. Добавьте сервер командой:

```
/add_server Server1|https://IP:PORT/SECRET|http://IP:3000|admin|password
```

Формат: `имя|outline_url|adguard_url|adguard_user|adguard_pass`

---

## 6️⃣ Деплой бота на сервер (опционально)

### Через systemd

Создайте файл `/etc/systemd/system/vpnbot.service`:

```ini
[Unit]
Description=VPN DNS Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/dns_vpn_bot
ExecStart=/usr/bin/python3 -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Активируем и запускаем
sudo systemctl daemon-reload
sudo systemctl enable vpnbot
sudo systemctl start vpnbot

# Проверяем логи
sudo journalctl -u vpnbot -f
```

---

## 🔧 Проверка работоспособности

### Проверка Outline API

```bash
curl -k https://IP:PORT/SECRET/access-keys
```

Должен вернуть JSON со списком ключей.

### Проверка AdGuard API

```bash
curl -u admin:password http://IP:3000/control/status
```

Должен вернуть JSON со статусом.

### Проверка бота

1. `/start` — главное меню
2. `Купить подписку` → выбрать VPN
3. Нажать "Оплатить" → должна открыться ссылка на Tonkeeper
4. Нажать "Я оплатил" → должен выдаться ключ

---

## 📱 Настройка DNS на устройствах

### Xbox

1. **Настройки → Сеть → Расширенные настройки**
2. **Настройки DNS → Вручную**
3. **Основной DNS:** `ВАШ_IP_СЕРВЕРА`
4. **Дополнительный DNS:** оставить пустым или `8.8.8.8`
5. Сохранить

### Windows

1. **Параметры → Сеть и Интернет → Ethernet/Wi-Fi**
2. **Изменить параметры адаптера**
3. ПКМ на адаптере → **Свойства**
4. **IPv4 → Свойства**
5. **Использовать следующие DNS:** `ВАШ_IP_СЕРВЕРА`

### Android

1. **Настройки → Сеть → Wi-Fi**
2. Долгое нажатие на сеть → **Изменить**
3. **Расширенные → DHCP → Статический**
4. **DNS 1:** `ВАШ_IP_СЕРВЕРА`

### iOS

1. **Настройки → Wi-Fi**
2. Нажать (i) рядом с сетью
3. **Настройка DNS → Вручную**
4. Удалить старые, добавить: `ВАШ_IP_СЕРВЕРА`

---

## ⚠️ Важные замечания

1. **Оплата** — сейчас подтверждение ручное. Для автоматической проверки нужна интеграция с TON API.

2. **Безопасность** — добавьте firewall:
   ```bash
   sudo ufw allow 22    # SSH
   sudo ufw allow 53    # DNS
   sudo ufw allow 80    # AdGuard Web
   sudo ufw allow 3000  # AdGuard API
   sudo ufw enable
   ```

3. **SSL для AdGuard** — рекомендуется настроить HTTPS через nginx/caddy для безопасного доступа к API.

---

## 📞 Поддержка

При проблемах проверьте:
1. Логи бота: `journalctl -u vpnbot -f`
2. Логи Docker: `docker logs adguard`
3. Доступность портов: `netstat -tlnp`
