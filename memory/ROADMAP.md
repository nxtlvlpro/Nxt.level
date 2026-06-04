# NXT8 — Roadmap

**Текущая версия:** v1.7.0-approval-gate (2026-06-04)

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
