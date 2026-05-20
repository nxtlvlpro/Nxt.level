#!/usr/bin/env bash
# =====================================================================
# NXT8 — VPS installer (Ubuntu 22.04 LTS)
# Usage:  sudo bash deploy/install.sh <domain> <email_for_le>
# Example: sudo bash deploy/install.sh nxt8.pro ops@nxt8.pro
# =====================================================================
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
APP_USER="nxt8"
APP_DIR="/home/${APP_USER}/app"
LOG_DIR="/var/log/nxt8"
BACKUP_DIR="/backup"

if [[ -z "${DOMAIN}" || -z "${EMAIL}" ]]; then
  echo "Usage: sudo bash deploy/install.sh <domain> <email_for_letsencrypt>"
  echo "       sudo bash deploy/install.sh nxt8.pro ops@nxt8.pro"
  exit 1
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo (need root for apt/systemctl/nginx)."
  exit 1
fi

echo "==> Installing NXT8 on domain ${DOMAIN}"
echo "==> App dir: ${APP_DIR}"
echo

# Sanity: app dir must exist (operator already cloned the repo & put .env)
if [[ ! -f "${APP_DIR}/backend/server.py" ]]; then
  echo "ERROR: ${APP_DIR}/backend/server.py not found."
  echo "Clone repo first as user '${APP_USER}':"
  echo "  su - ${APP_USER} -c 'git clone https://github.com/mikkisisi1/nxt8.pro.git ${APP_DIR}'"
  exit 1
fi
if [[ ! -f "${APP_DIR}/backend/.env" ]]; then
  echo "ERROR: ${APP_DIR}/backend/.env not found."
  echo "Copy and edit:"
  echo "  cp ${APP_DIR}/deploy/configs/backend.env.example ${APP_DIR}/backend/.env"
  echo "  \$EDITOR ${APP_DIR}/backend/.env  # вписать реальные ключи"
  exit 1
fi
if [[ ! -f "${APP_DIR}/frontend/.env" ]]; then
  echo "ERROR: ${APP_DIR}/frontend/.env not found."
  echo "Copy and edit:"
  echo "  cp ${APP_DIR}/deploy/configs/frontend.env.example ${APP_DIR}/frontend/.env"
  exit 1
fi

# =================== 1. APT & system packages ===================
echo "==> [1/9] System packages…"
export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y \
  curl wget gnupg ca-certificates \
  build-essential \
  python3.11 python3.11-venv python3-pip \
  nginx supervisor \
  git ufw

# Node.js 20 LTS via NodeSource
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null | cut -c2-3)" -lt 18 ]]; then
  echo "==> Installing Node.js 20 LTS"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi
# yarn via corepack
corepack enable
corepack prepare yarn@stable --activate

# =================== 2. MongoDB 7 ===================
echo "==> [2/9] MongoDB 7…"
if ! command -v mongod >/dev/null 2>&1; then
  curl -fsSL https://pgp.mongodb.com/server-7.0.asc \
    | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
    > /etc/apt/sources.list.d/mongodb-org-7.0.list
  apt update
  apt install -y mongodb-org
fi
systemctl enable mongod
systemctl start mongod

# Опционально: low-mem профиль для 2 GB VPS (только если RAM < 3 GB)
RAM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
if [[ "${RAM_MB}" -lt 3000 ]]; then
  echo "==> Low RAM detected (${RAM_MB} MB). Applying mongod low-mem profile."
  cp "${APP_DIR}/deploy/configs/mongod-low-mem.conf" /etc/mongod.conf
  systemctl restart mongod
fi

# =================== 3. Firewall ===================
echo "==> [3/9] Firewall (UFW)…"
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable

# =================== 4. App-user setup ===================
echo "==> [4/9] App user & dirs…"
id -u "${APP_USER}" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "${APP_USER}"
mkdir -p "${LOG_DIR}" "${BACKUP_DIR}"
chown -R "${APP_USER}":"${APP_USER}" "${LOG_DIR}" "${APP_DIR}"
chmod 755 "${BACKUP_DIR}"

# =================== 5. Python venv & deps ===================
echo "==> [5/9] Python venv + pip install (это 5-10 минут)…"
sudo -u "${APP_USER}" bash -c "
  cd ${APP_DIR}/backend
  if [[ ! -d venv ]]; then
    python3.11 -m venv venv
  fi
  ./venv/bin/pip install --upgrade pip wheel
  ./venv/bin/pip install -r requirements.txt
"

# =================== 6. Frontend build ===================
echo "==> [6/9] Frontend (yarn install + build)…"
# На маленьких серверах ограничим память Node
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"
sudo -u "${APP_USER}" bash -c "
  cd ${APP_DIR}/frontend
  yarn install --frozen-lockfile
  yarn build
"

# =================== 7. Supervisor ===================
echo "==> [7/9] Supervisor program…"
cp "${APP_DIR}/deploy/configs/supervisor-nxt8.conf" /etc/supervisor/conf.d/nxt8.conf
supervisorctl reread
supervisorctl update
sleep 3
supervisorctl status nxt8-backend || true

# =================== 8. Nginx + TLS ===================
echo "==> [8/9] Nginx site + Let's Encrypt…"

# Подставим домен в шаблон конфига
sed "s/nxt8\.pro/${DOMAIN}/g" "${APP_DIR}/deploy/configs/nginx-nxt8.conf" \
  > "/etc/nginx/sites-available/${DOMAIN}"

ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default

# nginx test → начнём с HTTP-only (без ssl) на время certbot
sed -i 's/listen 443 ssl http2;/listen 80;/' "/etc/nginx/sites-enabled/${DOMAIN}"
sed -i 's/listen \[::\]:443 ssl http2;/listen [::]:80;/' "/etc/nginx/sites-enabled/${DOMAIN}"
# Удалим временно блок HTTP→HTTPS чтобы избежать loop
sed -i '/return 301 https/d' "/etc/nginx/sites-enabled/${DOMAIN}"

nginx -t
systemctl reload nginx

# Сертификат
if ! command -v certbot >/dev/null 2>&1; then
  apt install -y certbot python3-certbot-nginx
fi
certbot --nginx \
  --non-interactive --agree-tos \
  --email "${EMAIL}" \
  -d "${DOMAIN}" -d "www.${DOMAIN}" || {
    echo "⚠ certbot failed. Если DNS ещё не прокинулся — подождите 30 минут и запустите:"
    echo "  sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
}

# Восстановим финальный конфиг (HTTPS + redirect)
cp "${APP_DIR}/deploy/configs/nginx-nxt8.conf" "/etc/nginx/sites-available/${DOMAIN}"
sed -i "s/nxt8\.pro/${DOMAIN}/g" "/etc/nginx/sites-available/${DOMAIN}"
# В нашем шаблоне TLS-блок закомментирован — раскомментируем
sed -i 's|# ssl_certificate |ssl_certificate |' "/etc/nginx/sites-available/${DOMAIN}"
sed -i 's|# ssl_certificate_key |ssl_certificate_key |' "/etc/nginx/sites-available/${DOMAIN}"
sed -i 's|# include /etc/letsencrypt|include /etc/letsencrypt|' "/etc/nginx/sites-available/${DOMAIN}"
sed -i 's|# ssl_dhparam|ssl_dhparam|' "/etc/nginx/sites-available/${DOMAIN}"

nginx -t && systemctl reload nginx

# =================== 9. Backup cron + healthcheck ===================
echo "==> [9/9] Backup cron + smoke-test…"
cat > /etc/cron.d/nxt8-mongo-backup <<EOF
# NXT8 daily Mongo backup → ${BACKUP_DIR}/nxt8-YYYY-MM-DD (14 days retention)
0 3 * * * root /bin/bash ${APP_DIR}/deploy/scripts/backup-mongo.sh >> /var/log/nxt8/backup.log 2>&1
EOF
chmod 644 /etc/cron.d/nxt8-mongo-backup

# Smoke test
sleep 5
bash "${APP_DIR}/deploy/scripts/healthcheck.sh" "${DOMAIN}" || {
  echo "⚠ Smoke-test упал. Смотрите логи:"
  echo "   sudo tail -n 100 /var/log/nxt8/backend.err.log"
  echo "   sudo supervisorctl status"
  exit 2
}

echo
echo "==> ✅ NXT8 deployed at https://${DOMAIN}"
echo
echo "   UI:      https://${DOMAIN}"
echo "   Health:  https://${DOMAIN}/api/health"
echo "   Logs:    sudo tail -f /var/log/nxt8/backend.err.log"
echo "   Status:  sudo supervisorctl status"
echo "   Update:  sudo bash ${APP_DIR}/deploy/scripts/update.sh"
echo "   Backup:  /backup (daily, 14 days retention)"
