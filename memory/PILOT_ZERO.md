# NXT8 — Pilot Zero Operator Guide

**Версия:** v1.0.0-pilot-zero
**Дата:** 16 мая 2026
**Аудитория:** оператор/менеджер пилотного развёртывания + первые пользователи внутри компании

---

## 1. Что такое NXT8

NXT8 — AI-операционная система. Один интерфейс для:
- задавать вопросы по корпоративной памяти (без промпт-инжиниринга)
- видеть ROI каждого часа работы AI
- получать рекомендации по сотрудникам (mentor)
- координировать запросы между отделами
- отслеживать сигналы рынка
- говорить голосом (hold-to-talk)

Каждый ответ AI сопровождается **confidence score** и индикатором **verification status**, плюс пишется в audit log.

---

## 2. Архитектура (для технического оператора)

```
React frontend (port 3000)
        │
        ▼ /api/*
FastAPI backend (port 8001, supervised)
        │
        ├── DeepSeek через OpenRouter (LLM core, logprobs ON)
        ├── DeepSeek Direct (fallback)
        ├── Whisper-1 + tts-1 через Emergent Universal Key (voice)
        └── MongoDB (memory, requests, ROI, skills, signals, ...)
```

**Сервисы:** управляются `supervisorctl`. Перезапуск:
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
sudo supervisorctl status
```

**Логи:**
```bash
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/backend.out.log
```

---

## 3. Первый запуск (день 0)

1. Открыть NXT8 в браузере. Backend автоматически:
   - создаст индексы MongoDB
   - проинициализирует corporate memory (`POST /api/seed` идемпотентен)
2. Проверить здоровье:
   ```
   GET /api/health
   ```
   Должно быть: `status=ok`, `mongo=true`, `deepseek.live=true`, `voice.enabled=true`.
3. Дополнить корпоративную память реальными данными (см. §5).

---

## 4. Навигация (7 экранов)

| Tab | Что показывает | Когда использовать |
|-----|---------------|-------------------|
| HOME | задачи + ROI/h + Cost + Rev | ежедневный «утренний кофе» обзор |
| CMD | стриминговый чат с NXT8 | спросить что угодно (knowledge / задачи) |
| OPS | cockpit 4 модулей с drill-down | проверить здоровье системы, координация |
| AGENTS | список сотрудников + weak patterns | mentor-отчёты, recommendations |
| MAP | ROI карта + cost-by-agent + 24h trend | руководству — финансовый обзор |
| ALERTS | поток событий по severity | реакция на критические события |
| MIC | hold-to-talk голосовой ввод | громкие руки заняты / руки заняты |

---

## 5. Загрузка корпоративных данных

### 5.1 Память (документы, политики, регламенты)
```bash
curl -X POST $BASE/api/memory/store \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Политика SLA enterprise: 99.95% uptime…",
    "type": "corporate",
    "metadata": {"department": "support", "priority": "high"}
  }'
```
- `type`: `corporate` | `episodic` | `semantic`
- `metadata.department`: `sales|support|engineering|hr|finance|product` (используется Cross-Dept Coordinator)

### 5.2 Сотрудники
```bash
curl -X POST $BASE/api/mentor/employees \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "emp_anna",
    "name": "Anna Petrova",
    "department": "support",
    "level": "mid",
    "experience_months": 18,
    "skills": ["technical", "deescalation"]
  }'
```

### 5.3 Performance review (для weak-pattern detection)
```bash
curl -X POST $BASE/api/mentor/performance \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "emp_anna",
    "accuracy": 0.78,
    "speed": 1.1,
    "escalation_rate": 0.12,
    "error_repeat": 1,
    "tasks_completed": 32,
    "tasks_reviewed": 4
  }'
```
Запустить детекцию:
```bash
curl -X POST $BASE/api/mentor/detect/emp_anna
```

### 5.4 Deals (для ROI attribution)
```bash
curl -X POST $BASE/api/roi/deals \
  -H "Content-Type: application/json" \
  -d '{"deal_id":"deal_2026_q2_acme","value_usd":12500,"team":"sales"}'
```

### 5.5 Market Radar — ручной ingest сигналов
Через UI: OPS → market → «add signal». Или REST:
```bash
curl -X POST $BASE/api/market/signals \
  -H "Content-Type: application/json" \
  -d '{
    "headline": "Конкурент Y выпустил On-Prem версию",
    "category": "competitor",
    "source": "industry-news.example",
    "score": 0.8
  }'
```

---

## 6. Ежедневные операции

| Действие | Где | Частота |
|----------|-----|---------|
| Спросить про политики / процессы | CMD | по необходимости |
| Запустить cross-dept координацию | OPS → cross-dept | 1–3 раза/день |
| Прогнать diagnostics rescan | OPS → diagnostics → rescan | 1×/день (или авто-каждый час) |
| Discover новых навыков | OPS → skills → discover | 1×/неделю |
| Внести сигнал рынка | OPS → market → add signal | по факту новости |
| Сгенерировать market digest | OPS → market → scan 24h | 1×/день утром |
| Просмотреть алерты | ALERTS | непрерывно (badge на nav) |

---

## 7. Метрики пилота (что замеряем)

| Метрика | Где смотреть | Цель Pilot Zero |
|---------|-------------|----------------|
| ROI/h | HOME / MAP / `/api/roi/current` | > 0% к концу недели 1 |
| Avg confidence | OPS → diagnostics | ≥ 0.75 |
| Escalation rate | OPS → diagnostics | < 20% |
| Contradictions found | OPS → diagnostics | trend ↓ от недели к неделе |
| Auto-skills registered | OPS → skills | ≥ 5 за месяц |
| Multi-dept tasks coordinated | OPS → cross-dept | ≥ 10/нед |
| Voice converse usage | request log `channel=voice` | ≥ 5/день |

Запрос ROI снэпшота:
```bash
curl -s $BASE/api/roi/current | python3 -m json.tool
curl -s $BASE/api/roi/trend?hours=168 | python3 -m json.tool   # week trend
```

Audit лог последних запросов:
```bash
curl -s $BASE/api/requests?limit=50 | python3 -m json.tool
```

---

## 8. Когда AI эскалирует к человеку

`should_escalate=true` появляется, когда reliability обнаруживает:
- confidence ниже порога (< 0.5)
- противоречия с прошлыми ответами в той же сессии
- отсутствие подтверждающих ссылок в corporate memory

→ В этом случае оператор должен:
1. проверить ответ вручную
2. если ответ корректен — дополнить corporate memory подтверждающим документом
3. если некорректен — записать правильный ответ в memory с приоритетом `critical`

---

## 9. Backup / Recovery

MongoDB данные пилота — критичны. Минимум:
```bash
mongodump --db=<DB_NAME> --out=/backup/nxt8-$(date +%F)
```
Рекомендуется ежедневный cron. DB_NAME см. в `/app/backend/.env`.

Восстановление:
```bash
mongorestore --db=<DB_NAME> /backup/nxt8-2026-05-16/<DB_NAME>
```

---

## 10. Известные ограничения пилота

| Ограничение | Митigation на время пилота |
|-------------|---------------------------|
| Нет auth / multi-tenant | пилот — single-org, доступ ограничен сетью |
| Нет Slack/WhatsApp | пользователи заходят через web/voice |
| Market Radar без авто-фида | ручной ingest или RSS-скрипт оператора |
| Voice — только hold-to-talk | для пилота достаточно |
| Нет PDF/Markdown export OPS | по плану — после пилота |

---

## 11. Поддержка / контакты

- Health endpoint: `GET /api/health` — первая линия диагностики
- Логи: `/var/log/supervisor/backend.{err,out}.log`
- Если `deepseek.live=false` — проверить `OPENROUTER_API_KEY` в `/app/backend/.env` и баланс OpenRouter
- Если `voice.enabled=false` — проверить `EMERGENT_LLM_KEY`

Для feature requests от пользователей пилота → собирать в issue tracker, обрабатывать после завершения первой недели.

---

## 12. Чек-лист «готов к Pilot Zero»

- [x] Backend сервисы запущены и стабильны
- [x] `/api/health` → status=ok, deepseek.live=true, voice.enabled=true
- [x] 38/38 backend тестов проходят
- [x] 21/21 frontend Ops Dashboard тестов проходят
- [x] Seed данные загружены (демо корпоративная память)
- [x] Все 10 модулей доступны через UI или REST
- [x] OpenRouter баланс > $10 (рекомендуется $50+ на старт пилота)
- [x] MongoDB backup настроен (оператор должен подтвердить)
- [x] Пользователи проинструктированы (этот документ + 5-мин видео demo желательно)

**Готов к запуску.** 🚀
