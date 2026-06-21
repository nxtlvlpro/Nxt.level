# NXT8 — Roadmap

**Текущая версия:** v1.18.32-3d-agent-room-live-sync (2026-06-21)

## ✅ Done — 3D Agent Room Live Sync (2026-06-21)
- Added `/api/ops/live-agents` for authenticated tenant-aware live room state
- Connected polling into `/agents-room/` every 4 seconds
- Synced names, labels, counters, statuses and detail panel from real payload
- Fixed `TenantAwareCRUD` wrapper bug impacting session lookups via wrapped collections

## ✅ Done — 3D Agent Room Cinematic v2 (2026-06-13)
- Standalone room redesigned visually toward cinematic reference
- Browser-like top bar, digital walls, arc pod layout, floating labels, richer detail panel
- Selection flow and responsive behavior validated after redesign

## ✅ Done — 3D Agent Room Static Integration (2026-06-13)
- Standalone page `/agents-room/` integrated via `frontend/public/agents-room/index.html`
- Mobile and desktop navigation now include `🤖 Агенты` links opening room in a new tab
- 3D room supports click-to-inspect agent detail flow
- Responsive layout validated on desktop / tablet / mobile

## P0 — Active

- [ ] **Live Data Wiring for 3D Agent Room** — подключить `/api/ops/live-agents`,
      чтобы статусы и метрики в 3D-комнате отражали реальные данные системы.
- [ ] **Data Access Guard** — `core/access_guard.py` нужно интегрировать в
      tool-call middleware (manifests описывают read/write права, но они
      не enforce'ятся). Approval Gate уже решил часть (write actions),
      но read-доступ из чужого scope ещё открыт.

## P1 — Current Engineering Queue

- [ ] **Hermes real reasoning in preview** — убрать preview `mock=true` для внутреннего self-audit
- [ ] **Tool-layer overlap** — убрать `create_task` из `client_manager`, оставить создание задач `project_coord`
- [ ] **Mini-history in Analyst Findings UI** — показать `resolved by`, `escalated at`, `task_id`
- [ ] **Frontend hygiene** — убрать оставшиеся пустые `catch` в клиентском коде

## ✅ Done — WhatsApp Channel via Twilio (2026-06-05)
- `core/whatsapp_bot.py` + `/api/whatsapp/*` endpoints (connect/status/disconnect/webhook)
- HermesChat toolbar: pill «В WhatsApp» (зелёная) рядом с Telegram-кнопкой
- WhatsAppConnectCard в AgentsView
- Identity unification: тот же `nxt8.user_id` для web/Telegram/WhatsApp
- Approve/Reject через `A <id>` / `R <id>` (WhatsApp inline-кнопок нет → текстовые команды)
- Push approval-карточек в WhatsApp owner'а
- 13 регрессионных тестов passing
- Production-номер: `+13253263849`. **NB:** в Twilio Console нужно прописать inbound webhook URL до prod-деплоя

## ✅ Done — Share SSR + Hermes Telegram Button (2026-06-04)
- `/api/s/{share_id}` SSR HTML с `og:image`, `twitter:card`, redirect → SPA
- HermesChat toolbar: pill-кнопка «В Telegram» (active/connected состояния)
- Унификация identity: и веб-чат, и Telegram-бот используют `nxt8.user_id`
- 3 новых ssr-теста + 11 telegram-тестов — все зелёные

## ✅ Done — Telegram Channel (2026-06-04)
- `core/telegram_bot.py` — единый мост: webhook → handler → Hermes → reply
- Endpoints: `/api/telegram/{connect,status,disconnect,webhook/{secret},install-webhook}`
- `views/TelegramConnectCard.jsx` — UI с 1-click deep-link и polling статуса
- Inline-кнопки Approve/Reject из push-карточек напрямую в Telegram
- Free-text → Hermes (с typing-индикатором)
- Команды `/help`, `/approvals`, `/disconnect`
- 11 регрессионных тестов passing (mint/bind/unbind/free-text/buttons/push)
- Бот: `@nxt8ceo_bot`

## ✅ Done — Share My Journey / Viral Channel (2026-06-04)
- `core/share.py` — mint share_id, persist headline+steps, open/conversion counters
- PNG OG-card 1200×630 (PIL/Vera) → `/api/share/{id}/og.png` для превью в WhatsApp/Telegram/Twitter
- Endpoints: `POST /share/journey`, `GET /share/{id}`, `GET /share/{id}/og.png`,
  `POST /share/conversion`, `GET /share/stats`
- Frontend: ShareJourneyButton в DemoTour (после 5/5) — copy / native share / Telegram deep-link
- Viral attribution: `?ref=<share_id>` на загрузке → шторм localStorage → fired на checkout
- 7 регрессионных тестов: mint, headline truncate, counters, stats shape, PNG bytes, bad-id guard
- **95/95 tests passing**

## ✅ Done — Demo Tour (2026-06-04)
- `core/tour.py` + endpoints `/api/tour/{catalogue,events,funnel}`
- `DemoTour.jsx` плавающий чек-лист с 5 сценариями
- Auto-detection: «Спроси Hermes» (на отправку), «Открой команду агентов» (на view=agents),
  Inter-Agent диалоги и Approval Gate (IntersectionObserver на карточки)
- Анонимная аналитика по `client_id` в localStorage; voronka via `/tour/funnel`
- 4 регрессионных теста: catalogue, валидация, persist, funnel rate
- 88/88 backend tests passing

## ✅ Done — Plan & ROI Sync (2026-06-04)
- Canonical Stripe IDs (personal/team/operations/headquarters) теперь — единая истина
- Legacy basic/simple/pro/enterprise → aliases, backwards-compat
- Manifests tariff_tier синхронизированы с Stripe
- ROI phantom escalation cost: $186.67 в 64 записях вычищены
- ROI dashboard: фаза `pilot` вместо ложного -100% alert (266 false alerts удалено)
- 96 регрессионных тестов всё ещё passing (12 новых: plan_unification + roi_sanity)

## ✅ Done — Approval Gate (2026-06-04)
- core/approval_gate.py + REST endpoints
- Frontend pending-approvals card в AgentsView
- 5 регрессионных тестов
- Фиксы: empty messages → 400, past due_at, MAX_ITER=3

## P0 — Active

- [ ] **Tariff IDs sync** — `manifests.py` использует basic/simple/pro/enterprise,
      а `/api/payments/plans` отдаёт personal/team/operations/headquarters.
      Без этого tariff gating ломается.
- [ ] **ROI phantom cost** — `agents/roi.py` показывает фантомные $14.58/час →
      дашборд показывает −100% ROI.
- [ ] **Data Access Guard** — `core/access_guard.py` нужно интегрировать в
      tool-call middleware (manifests описывают read/write права, но они
      не enforce'ятся). Approval Gate уже решил часть (write actions),
      но read-доступ из чужого scope ещё открыт.

## P0 — Pilot Zero (now → +4 weeks)
Запуск на реальной компании. Никаких новых фич — только observability и операционная поддержка.

- [ ] Daily ROI snapshot review (operator)
- [ ] Weekly diagnostics scan review
- [ ] User feedback collection (issue tracker)
- [ ] MongoDB backup automation (cron)
- [ ] OpenRouter balance monitor (alert at $20 threshold)

## P1 — Post-Pilot (parallel tracks, после ROI confirmed)

### Track A: Executive Reporting
- [ ] Snapshot всех 4 OPS-модулей в один артефакт
- [ ] PDF export (через `weasyprint` или React → puppeteer)
- [ ] Markdown export (для копирования в Slack/Notion)
- [ ] Email scheduling (через Resend / SendGrid — выбрать позже)
- [ ] «Share executive report» кнопка в OPS dashboard

### Track B: Observability Layer
- [ ] Prometheus metrics endpoint (`/metrics`)
- [ ] Grafana dashboards (port `install_finalize.sh`)
- [ ] Tracing для LLM-вызовов (latency, tokens, provider)
- [ ] Alert rules: high escalation rate, low confidence, OpenRouter balance

## P2 — Scale (после подтверждения ROI на 1+ компании)

### Multi-tenancy
- [ ] `org_id` scoping во всех коллекциях MongoDB
- [ ] JWT/session auth (Emergent Google Auth или custom)
- [ ] Per-org API key для OpenRouter (или прокси с rate limits)
- [ ] Per-org seed flow + onboarding wizard

### Channel Adapters
- [ ] Slack bot (slash commands + DM)
- [ ] WhatsApp Business API (Twilio)
- [ ] Telegram bot
- [ ] Email-in / out (Resend)

## P3 — Polish (continuous, low priority)

- [ ] Toast/error UI на failure ops-сканов (diagnostics/skills/market)
- [ ] Submit-on-Enter в textarea CrossDeptPanel
- [ ] Refactor `CAT_COLOR` class-splitting в MarketPanel
- [ ] useEffect dependency `[sub]` → `[]` в OpsView
- [ ] Voice Activity Detection в MicView (auto stop по тишине)
- [ ] Streaming SSE для voice converse
- [ ] Confidence calibration через post-hoc reliability tuning
