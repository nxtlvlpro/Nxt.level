#!/usr/bin/env bash
# =====================================================================
# NXT8 — обновление кода + перезапуск.
# Безопасно вызывать в любой момент. Идемпотентно.
# Usage: sudo bash deploy/scripts/update.sh
# =====================================================================
set -euo pipefail

APP_USER="${APP_USER:-nxt8}"
APP_DIR="${APP_DIR:-/home/${APP_USER}/app}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo."
  exit 1
fi

echo "==> Backup hot-state ROI snapshot…"
bash "${APP_DIR}/deploy/scripts/backup-mongo.sh" || echo "  (backup warning, continuing)"

echo "==> git pull…"
sudo -u "${APP_USER}" git -C "${APP_DIR}" pull --ff-only

echo "==> backend: pip install (incremental)…"
sudo -u "${APP_USER}" bash -c "
  cd ${APP_DIR}/backend
  ./venv/bin/pip install -r requirements.txt --upgrade --quiet
"

echo "==> frontend: yarn install + build…"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"
sudo -u "${APP_USER}" bash -c "
  cd ${APP_DIR}/frontend
  yarn install --frozen-lockfile --silent
  yarn build
"

echo "==> supervisorctl restart backend…"
supervisorctl restart nxt8-backend
sleep 4
supervisorctl status nxt8-backend

echo "==> nginx reload (если нужно)…"
nginx -t && systemctl reload nginx

echo "==> Smoke test…"
DOMAIN_HINT=$(grep -h "^server_name" /etc/nginx/sites-enabled/* 2>/dev/null | head -1 | awk '{print $2}' | sed 's/;//')
if [[ -n "${DOMAIN_HINT}" && "${DOMAIN_HINT}" != "_" ]]; then
  bash "${APP_DIR}/deploy/scripts/healthcheck.sh" "${DOMAIN_HINT}"
else
  bash "${APP_DIR}/deploy/scripts/healthcheck.sh"
fi

echo
echo "==> ✅ Update complete."
