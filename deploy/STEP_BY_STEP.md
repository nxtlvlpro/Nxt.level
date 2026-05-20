# NXT8 — Step-by-step Deployment Guide

Подробная пошаговая инструкция на случай, если `install.sh` не подходит (например, не Ubuntu, нестандартная архитектура, нужен ручной контроль).

> Для быстрого пути — смотрите `README.md` и `install.sh`.

---

## 0. Что должно быть готово

- VPS Ubuntu 22.04 LTS (или Debian 12), минимум 4 GB RAM, 30 GB SSD
- Root доступ по SSH
- Домен с настроенной A-записью на IP сервера (DNS пропагировал — проверить через `dig nxt8.pro +short`)
- Ключи: OpenRouter, OpenAI (для voice), опционально DeepSeek direct

---

## 1. Initial server hardening (10 мин)

```bash
# Подключаемся по SSH
ssh root@<server-ip>

# Обновление системы
apt update && apt upgrade -y

# Создаём пользователя (не работаем под root)
adduser nxt8
usermod -aG sudo nxt8

# Скопировать ssh ключ для nxt8 (или поставить пароль)
mkdir -p /home/nxt8/.ssh
cp ~/.ssh/authorized_keys /home/nxt8/.ssh/
chown -R nxt8:nxt8 /home/nxt8/.ssh
chmod 700 /home/nxt8/.ssh
chmod 600 /home/nxt8/.ssh/authorized_keys

# Опционально: запретить root-логин
sed -i 's/^#*PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Теперь логинимся как `nxt8` и работаем через `sudo`.

---

## 2. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

**Что НЕ открываем наружу:** 8001 (backend), 27017 (Mongo), 3000 (dev), 8642 (Hermes gateway). Они слушают только 127.0.0.1.

---

## 3. Системные пакеты

```bash
sudo apt install -y \
  curl wget gnupg ca-certificates \
  build-essential \
  python3.11 python3.11-venv python3-pip \
  nginx supervisor \
  git
```

---

## 4. Node.js 20 LTS + Yarn

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs

# Yarn через corepack
sudo corepack enable
sudo corepack prepare yarn@stable --activate

node -v && yarn -v
```

---

## 5. MongoDB 7

```bash
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

sudo apt update
sudo apt install -y mongodb-org

sudo systemctl enable --now mongod
sudo systemctl status mongod
```

**Для серверов с 2 GB RAM** — применить low-mem профиль:
```bash
sudo cp /home/nxt8/app/deploy/configs/mongod-low-mem.conf /etc/mongod.conf
sudo systemctl restart mongod
```

---

## 6. Получение кода и env

```bash
# Под пользователем nxt8
git clone https://github.com/mikkisisi1/nxt8.pro.git /home/nxt8/app
cd /home/nxt8/app

# Env файлы
cp deploy/configs/backend.env.example backend/.env
nano backend/.env
# Заполнить:
#   OPENROUTER_API_KEY (обязательно)
#   OPENAI_API_KEY     (обязательно для voice)
#   CORS_ORIGINS=https://nxt8.pro,https://www.nxt8.pro
#   (опционально) DEEPSEEK_API_KEY

cp deploy/configs/frontend.env.example frontend/.env
nano frontend/.env
# REACT_APP_BACKEND_URL=https://nxt8.pro
```

---

## 7. Python venv + зависимости

```bash
cd /home/nxt8/app/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
deactivate
```

⏱ Установка ~5–10 минут (178 пакетов). При первом старте ChromaDB подтянет 79 MB embedding-модели — нормально.

---

## 8. Frontend build

```bash
cd /home/nxt8/app/frontend

# Защита от OOM на маленьких VPS
export NODE_OPTIONS=--max-old-space-size=1536

yarn install --frozen-lockfile
yarn build
```

Результат — `frontend/build/` (статика, ~5 MB). React dev-server в проде **не запускаем** — статику отдаёт nginx.

---

## 9. Supervisor

```bash
sudo mkdir -p /var/log/nxt8
sudo chown nxt8:nxt8 /var/log/nxt8

sudo cp /home/nxt8/app/deploy/configs/supervisor-nxt8.conf /etc/supervisor/conf.d/nxt8.conf

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status nxt8-backend
# Должно быть: nxt8-backend  RUNNING
```

Логи:
```bash
sudo tail -f /var/log/nxt8/backend.err.log
```

---

## 10. Nginx + TLS

```bash
# Подставить ваш домен
DOMAIN=nxt8.pro

sudo cp /home/nxt8/app/deploy/configs/nginx-nxt8.conf /etc/nginx/sites-available/$DOMAIN

# Если домен не nxt8.pro — заменить:
sudo sed -i "s/nxt8.pro/$DOMAIN/g" /etc/nginx/sites-available/$DOMAIN

sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
sudo rm -f /etc/nginx/sites-enabled/default

# ВРЕМЕННО переключить на HTTP-only пока нет сертификата
sudo sed -i 's/listen 443 ssl http2;/listen 80;/' /etc/nginx/sites-enabled/$DOMAIN
sudo sed -i '/return 301 https/d' /etc/nginx/sites-enabled/$DOMAIN

sudo nginx -t
sudo systemctl reload nginx
```

Получаем сертификат:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN \
  --non-interactive --agree-tos -m ops@$DOMAIN
```

Восстанавливаем полный конфиг (HTTPS + redirect):
```bash
sudo cp /home/nxt8/app/deploy/configs/nginx-nxt8.conf /etc/nginx/sites-available/$DOMAIN
sudo sed -i "s/nxt8.pro/$DOMAIN/g" /etc/nginx/sites-available/$DOMAIN
sudo sed -i 's|# ssl_certificate |ssl_certificate |' /etc/nginx/sites-available/$DOMAIN
sudo sed -i 's|# ssl_certificate_key |ssl_certificate_key |' /etc/nginx/sites-available/$DOMAIN
sudo sed -i 's|# include /etc/letsencrypt|include /etc/letsencrypt|' /etc/nginx/sites-available/$DOMAIN
sudo sed -i 's|# ssl_dhparam|ssl_dhparam|' /etc/nginx/sites-available/$DOMAIN

sudo nginx -t && sudo systemctl reload nginx
```

---

## 11. Backup cron

```bash
sudo tee /etc/cron.d/nxt8-mongo-backup > /dev/null <<EOF
0 3 * * * root /bin/bash /home/nxt8/app/deploy/scripts/backup-mongo.sh >> /var/log/nxt8/backup.log 2>&1
EOF
sudo chmod 644 /etc/cron.d/nxt8-mongo-backup

# Проверка вручную
sudo bash /home/nxt8/app/deploy/scripts/backup-mongo.sh
ls -la /backup/
```

---

## 12. Smoke test

```bash
bash /home/nxt8/app/deploy/scripts/healthcheck.sh nxt8.pro
```

Откройте в браузере:
- `https://nxt8.pro` — UI
- `https://nxt8.pro/api/health` — JSON `{"status":"ok"}`
- `https://nxt8.pro/api/personas` — 8 персон в JSON

---

## 13. Прогрев ChromaDB (опционально, чтобы первый запрос не висел)

```bash
curl -X POST https://nxt8.pro/api/mempalace/store \
  -H "Content-Type: application/json" \
  -d '{"wing":"company","room":"intro","drawer":"deployed","content":"NXT8 deployed at nxt8.pro","metadata":{"source":"install"}}'
```

Первый вызов — ~30 секунд (качается модель `all-MiniLM-L6-v2`). Следующие — миллисекунды.

---

## 14. Готово

Дальнейшие операции:

- **Обновление кода:** `sudo bash /home/nxt8/app/deploy/scripts/update.sh`
- **Бэкап вручную:** `sudo bash /home/nxt8/app/deploy/scripts/backup-mongo.sh`
- **Логи:** `sudo tail -f /var/log/nxt8/backend.err.log`
- **Рестарт:** `sudo supervisorctl restart nxt8-backend`
- **Восстановление БД:** `sudo mongorestore --db nxt8 --drop /backup/nxt8-YYYY-MM-DD/nxt8/`

Любые вопросы — открыть issue в репозитории или см. `README.md` → `Troubleshooting`.
