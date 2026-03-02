#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="185.216.87.218"
REMOTE_USER="root"
REMOTE_DIR="/opt/vpn-miniapp"
BRANCH="main"

ssh "${REMOTE_USER}@${REMOTE_HOST}" "
  set -e
  cd ${REMOTE_DIR}
  git fetch origin ${BRANCH}
  git checkout ${BRANCH}
  git reset --hard origin/${BRANCH}

  # Python app deps
  python3 -m venv .venv || true
  . .venv/bin/activate
  pip install -q --upgrade pip
  pip install -q -r requirements.txt fastapi uvicorn pyotp bcrypt slowapi jinja2 python-multipart sentry-sdk

  # Rebuild mini-app frontend
  cd dashboard-ui
  npm ci --silent
  npm run build --silent

  # Restart services
  systemctl restart vpn-miniapp
  systemctl restart vpn-api
"

echo "✅ Deployed ${BRANCH} to ${REMOTE_HOST}"
