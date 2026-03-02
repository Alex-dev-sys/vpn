#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/vpn-bot.service"

mkdir -p "$SERVICE_DIR"
cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=VibeStudy VPN Telegram Bot (user)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/alex/.openclaw/workspace/vpn
ExecStart=/home/alex/.openclaw/workspace/vpn/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now vpn-bot
systemctl --user status --no-pager --lines=20 vpn-bot
