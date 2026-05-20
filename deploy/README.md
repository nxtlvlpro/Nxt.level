# NXT8 — VPS Deployment

Развёртывание NXT8 на собственный VPS (Ubuntu 22.04 LTS) под доменом `nxt8.pro`.
Архитектура: FastAPI + MongoDB + React (static build) + Nginx + Supervisor.

## Содержание

- [Quick path (одной командой)](#quick-path)
- [Step-by-step](#step-by-step)
- [Файлы в этой папке](#файлы-в-папке)
- [Recurring ops (backup / update / TLS renew)](#recurring-ops)
- [Troubleshooting](#troubleshooting)

---

## Quick path

**Что нужно подготовить ДО:**

1. VPS Ubuntu 22.04 LTS, root доступ. **Минимум 4 GB RAM** (Contabo VPS S за $7/мес — идеально).
2. Домен `nxt8.pro` с A-записью на IP сервера (DNS пропагация 5–60 мин).
3. Ключи:
   - **OpenRouter** (`sk-or-v1-...`) — обязателен. https://openrouter.ai/keys
   - **OpenAI** (`sk-...`) — обязателен для voice (Whisper + TTS). https://platform.openai.com/api-keys
   - (опц.) DeepSeek direct (`sk-...`) — fallback. https://platform.deepseek.com/

**Запуск:**

```bash
ssh root@<server-ip>
# Однократная подготовка пользователя
adduser nxt8 && usermod -aG sudo nxt8
su - nxt8

# Клонирование репозитория
git clone https://github.com/mikkisisi1/nxt8.pro.git /home/nxt8/app
cd /home/nxt8/app

# Заполнить env (см. deploy/configs/backend.env.example)
cp deploy/configs/backend.env.example backend/.env
nano backend/.env   # вписать реальные ключи

cp deploy/configs/frontend.env.example frontend/.env
nano frontend/.env  # вписать REACT_APP_BACKEND_URL=https://nxt8.pro

# Запуск автоматического инсталлятора
sudo bash deploy/install.sh nxt8.pro nxt8@yourcompany.com
```

Скрипт сам:
- Установит системные пакеты, Mongo 7, Python 3.11, Node 20, Nginx, certbot
- Поставит зависимости (pip + yarn)
- Соберёт frontend (production build)
- Применит конфиги supervisor + nginx
- Получит TLS-сертификат Let's Encrypt
- Включит daily backup MongoDB
- Прогонит smoke-test

Если всё OK — `https://nxt8.pro` открывает UI, `https://nxt8.pro/api/health` возвращает `status=ok`.

---

## Step-by-step

Если предпочитаете идти по шагам или нужно адаптировать к необычной конфигурации — см. [STEP_BY_STEP.md](STEP_BY_STEP.md).

---

## Файлы в папке

```
deploy/
├── README.md                    ← этот файл
├── STEP_BY_STEP.md              ← подробный мануал
├── install.sh                   ← главный инсталлятор (запускать через sudo)
├── configs/
│   ├── backend.env.example      ← шаблон backend/.env с комментариями
│   ├── frontend.env.example     ← шаблон frontend/.env
│   ├── nginx-nxt8.conf          ← nginx site-config (HTTPS + SSE + /api proxy)
│   ├── supervisor-nxt8.conf     ← supervisor program для backend
│   └── mongod-low-mem.conf      ← Mongo cacheSizeGB=0.5 для 2-GB серверов
└── scripts/
    ├── healthcheck.sh           ← smoke-test (curl /api/health + /api/seed)
    ├── backup-mongo.sh          ← daily mongodump → /backup с ротацией 14 дней
    └── update.sh                ← git pull → pip install → yarn build → restart
```

---

## Recurring ops

### Обновление кода (после git push)

```bash
sudo bash /home/nxt8/app/deploy/scripts/update.sh
```

Делает: `git pull` → `pip install -r requirements.txt` → `yarn install` → `yarn build` → `supervisorctl restart backend`.

### Backup MongoDB (автомат)

`deploy/install.sh` сам ставит cron на 03:00 каждый день. Файлы — в `/backup/nxt8-YYYY-MM-DD/`, ротация 14 дней.

Ручной backup в любой момент:
```bash
sudo bash /home/nxt8/app/deploy/scripts/backup-mongo.sh
```

### Восстановление из бэкапа

```bash
sudo mongorestore --db nxt8 --drop /backup/nxt8-2026-05-20/nxt8/
```

### TLS renewal

`certbot` ставит cron `/etc/cron.d/certbot` автоматически. Проверить:
```bash
sudo certbot renew --dry-run
```

### Проверка статуса

```bash
sudo supervisorctl status         # должны быть RUNNING: backend
sudo systemctl status mongod      # active
sudo systemctl status nginx       # active
bash deploy/scripts/healthcheck.sh
```

---

## Troubleshooting

| Симптом | Что проверить |
|---|---|
| `/api/health` → 502 | `tail /var/log/nxt8/backend.err.log`. Обычно — невалидный ключ OPENROUTER или MongoDB не стартанул. |
| Backend OOM (kill -9) | `dmesg | grep -i "out of memory"`. Лечится `configs/mongod-low-mem.conf` (cacheSizeGB=0.5). |
| Voice 502 | Проверить `OPENAI_API_KEY` в backend/.env. EMERGENT_LLM_KEY вне Emergent не работает. |
| SSE обрывается через 60s | Должно быть `proxy_read_timeout 300s` и `proxy_buffering off` — проверить `/etc/nginx/sites-enabled/nxt8.pro`. |
| `yarn install` падает OOM | `NODE_OPTIONS=--max-old-space-size=1024 yarn install`, или билд локально + scp build/ на сервер. |
| ChromaDB 30 сек на первый запрос | Норма (качается 79 MB embed model). Сделать прогрев: `curl -X POST .../api/mempalace/store -d '{...}'`. |
| Hermes Gateway :8642 — нужен? | **Нет**, в коде он опциональный. Оставьте `HERMES_API_KEY=` пустым, fallback на DeepSeek работает. |

Подробнее — в `STEP_BY_STEP.md`.

---

## Стоимость в месяц (типовая)

| Статья | Сумма |
|---|---|
| Contabo VPS S 4 vCPU / 8 GB / 200 GB NVMe | $6.99 |
| Домен `.pro` | ~$2/мес |
| OpenRouter (deepseek-v3-0324, ~$0.27/$1.10 за M токенов) | $10–40 |
| OpenAI (voice: $0.006/мин Whisper + $15/M chars TTS) | $5–15 |
| **Итого** | **$25–65** |

Окупается с 2–3 клиентов на тарифе Basic ($9/мес).
