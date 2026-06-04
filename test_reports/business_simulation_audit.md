# NXT8 — Отчёт по бизнес-симуляции (Quality Assurance Audit)

**Дата**: 2026-06-04  
**Источник**: `/app/scripts/simulate_business.sh` — 27 шагов реалистичного B2B SaaS-сценария  
**Результат**: 27/27 HTTP exit=0, **но при анализе содержимого найдены 12 серьёзных проблем**

---

## 🔴 P0 — КРИТИЧНЫЕ ДЕФЕКТЫ (блокеры production-качества)

### 1. Несогласованность tariff IDs между manifests и Stripe-каталогом
- **manifests.py**: `tariff_tier` = `basic`/`simple`/`pro`/`enterprise`
- **/api/payments/plans**: `personal`/`team`/`operations`/`headquarters`
- **Эффект**: `tariff_tier`-gating в манифестах никогда не сопоставится с реальной подпиской. Невозможно гейтить feature по тарифу. Пользователь купивший `Team` ($14) не получит ничего, что в manifests прописано как `simple`.

### 2. Контрактные несовместимости API ↔ frontend
- `POST /api/graph/v2/run` требует поле `task`, но шаблон вызова из чата шлёт `message` → **422 за 173ms**
- `POST /api/payments/checkout/session` требует `origin` (нет такого в payload фронта) → **422**
- `POST /api/cross-dept/coordinate` требует `query`, фронт может слать `text` → **422**
- **Эффект**: эти эндпоинты вызываются только из тестов / устаревших мест, реальный фронт молча падает.

### 3. ROI = −100% **в каждом часе** (system-level убыточность)
- `total_cost = $14.59/час`, `total_revenue = 0` → `roi = -1.0`
- Главный источник cost: **`human_escalation` = $14.58** (99.9% всех затрат)
- Тренд 24ч: 28 снэпшотов, **все ROI = −100%**
- **Эффект**: алёрт `warning: hourly ROI -100.00%` срабатывает **каждые 10 секунд**. Сигнальная система засыпана шумом, реальные тревоги не различить. Bookkeeper подтверждает: «стабильно отрицательный на всём горизонте».

### 4. escalation_rate = **48.6%** при целевом 20%
- 67 из 138 интентов помечены как `escalations`
- `knowledge`: 12 из 12 (100%)
- `roi`: 8 из 8 (100%)
- `mentor`: 2 из 2 (100%)
- `general`: 20 из 25 (80%)
- **Эффект**: pipeline-hooks триггерит эскалацию даже на high-confidence ответах (`knowledge` avg_confidence = 0.842). Порог сломан.

### 5. **Data Access Guard НЕ enforced на уровне кода**
Тест: Compliance (advisory, no write) попросили «создай задачу: уволить менеджера X».
- Compliance отказался — **но это решение LLM**, прочитавшего собственный manifest в system_prompt.
- В кодовой логике (server.py routes) **нет ни одной проверки `can_write()` / `requires_approval()`**.
- Если LLM однажды решит вернуть `{"action":"create_task",...}` (jailbreak, hallucination), запись пройдёт.
- В handoff это P0, но всё ещё **не сделано**.

### 6. Real Approval Gate не реализован
- `evolution_journal`: 21 proposed → 3 approved → **0 done**
- Approvals накапливаются, но никем не исполняются и не возвращаются в систему.
- Нет коллекции `db.pending_approvals`, нет UI для одобрения, нет executor'а.

---

## 🟡 P1 — СЕРЬЁЗНЫЕ ПРОБЛЕМЫ (важные на масштабе)

### 7. Hermes OS Cycle = 22 секунды
- Близко к **Cloudflare timeout 30s** — на больших цепочках упадёт.
- 10 нод × 2-3s/нода = 20-30s. Каждая нода вызывает DeepSeek.
- Нужен либо параллелизм нод, либо streaming-acknowledge.

### 8. mock-leakage обнаружен в данных
- `mock_rate = 5.8%` (8 из 138 ответов).
- Contradictions включают пары «нормальный ответ» vs «В рабочем режиме здесь будет ответ DeepSeek...» — то есть mock-ответы попали в production logs.
- divergence = 0.745.

### 9. 4-Layer Memory **не интегрирована с chat**
- В S1.x чат-сессии `sim-acme-ceo` обсуждался **SSO/Okta/SAML**.
- `POST /api/memory/search {"query":"SSO SAML Okta"}` → **count=0**.
- Сообщения чата НЕ попадают в Operational / Short-Term memory автоматически.
- Hermes OS Cycle пишет KG-edges, но они **только** от cycles, не от чата.
- **Эффект**: «4-layer memory» по факту — изолированный слой только для Hermes OS Cycle.

### 10. Шум алёртов (no deduplication)
- 3 одинаковых ROI-warning за 30 секунд (S5.4).
- `severity=warning` для системного состояния, не для события.
- Нужна агрегация: «алёрт активен / прекращён» вместо «событие создано».

### 11. Stripe webhook + payment_transactions
- Эндпоинт `/api/webhook/stripe` существует, но не проверено: записываются ли `payment_transactions` при оплате теста.
- Без webhook proper signature verification — потенциальная уязвимость.

### 12. Mock-mode провайдер LLM
- `health.deepseek.live = true, last_error = null` — норм.
- Но 5.8% mock_rate показывает: иногда DeepSeek/OpenRouter падает молча, и hooks возвращают mock-placeholder в production.
- Нужен hard-fail (HTTP 503) вместо silent mock.

---

## 🟢 ХОРОШО РАБОТАЕТ

- ✅ `/api/health` — все интеграции зеленые (Mongo + DeepSeek live + Voice)
- ✅ Chat /api/chat — 5-9s response (норм для LLM)
- ✅ Hermes OS Cycle — полные 10 нод, KG-edges пишутся, lessons накапливаются
- ✅ 15 манифестов корректно загружены
- ✅ Self-assessment даёт честные сигналы (mock_rate, escalation_rate)
- ✅ Bookkeeper отвечает структурно с таблицей
- ✅ Compliance корректно «знает себя» через manifest-injection
- ✅ Evolution roadmap **сам предложил**: "Pre-Approval Gate", "Deal Validator Agent", "Billing/Tariff Catalog API" — те же P0, что нашёл я. Система знает свои слабости 🎯

---

## РЕКОМЕНДУЕМЫЙ ПОРЯДОК УСТРАНЕНИЯ

| # | Приоритет | Задача | Эффект |
|---|-----------|--------|--------|
| 1 | 🔴 P0 | Унифицировать tariff IDs (manifests ↔ payments/plans) | Деблокирует gating |
| 2 | 🔴 P0 | Data Access Guard в коде (`core/access_guard.py` + middleware) | Безопасность |
| 3 | 🔴 P0 | Real Approval Gate (`db.pending_approvals` + UI + executor) | Архитектура |
| 4 | 🔴 P0 | Исправить ROI / human_escalation cost-modeling (фантомный $14.58/h) | Чистый сигнал |
| 5 | 🔴 P0 | Снизить escalation_rate (исправить пороги в `_pipeline_hooks.py`) | Качество AI |
| 6 | 🔴 P0 | Починить контракты Graph v2, Payments, Cross-dept (`task`/`origin`/`query`) | Совместимость |
| 7 | 🟡 P1 | Интегрировать chat → 4-Layer Memory | Память работает |
| 8 | 🟡 P1 | Алёрт-дедупликация (state-based, не event-based) | Сигнал/шум |
| 9 | 🟡 P1 | Mock leakage: hard-fail вместо silent placeholder | Чистые данные |
| 10 | 🟡 P1 | Параллелизация Hermes OS Cycle нод (Observe+Validate, Reason+Route) | Latency <15s |
