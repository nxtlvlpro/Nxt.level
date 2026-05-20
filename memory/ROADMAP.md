# NXT8 — Roadmap

**Текущая версия:** v1.0.0-pilot-zero (released 2026-05-16)

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
