# NXT8 — Product Requirements Document

**Current version:** v1.5.0-personas (additive over v1.4.0-mempalace + v1.4.1-router-fix)
**Last updated:** 2026-05-20 by Главный Системный Архитектор (E1)

## What was built (in chronological order)

1. **v0.1–v1.0 Pilot Zero** — 10 modules (orchestrator, memory, reliability, mentor, roi, voice, cross_dept, diagnostics, skill_creator, market_radar) + 7 UI views.
2. **v1.1 Hermes** — Hermes Agent proxy (gateway on :8642, offline in current env).
3. **v1.2 Hermes COO** — `hermes_coo.py` with 6 OpenAI-format tools.
4. **v1.3 Ultra** — `hermes_max_tools_and_coo.py` with 10 fenced-JSON tools + LangGraph supervisor.
5. **v1.4 MemPalace** — ChromaDB long-term memory layer + auto-save from chat/stream.
6. **v1.4.1 Router-fix** — fixed LangGraph router bug where tool results never returned to Hermes for final answer.
7. **v1.5 Personas Layer (this release)** — 8 marketing-aligned persona wrappers + tariff gate.

## Architecture (as built)

```
/app/backend/
├── server.py                    FastAPI app + ~50 endpoints
├── core/
│   ├── deepseek.py              OpenRouter primary → DeepSeek direct fallback → mock
│   └── db.py                    Motor MongoDB + ensure_indexes
├── nxt8_langgraph_ultra.py      LangGraph supervisor → hermes → tools → human_approval [+ router-fix]
└── agents/
    ├── orchestrator.py          intent classify → dispatch → reliability → audit
    ├── memory.py                short-term + TF-IDF long-term
    ├── reliability.py           confidence + contradictions + hallucination
    ├── mentor.py                5 levels, weak patterns, recommendations
    ├── roi.py                   cost tracking + revenue attribution + hourly
    ├── voice.py                 Whisper STT + OpenAI TTS via Emergent key
    ├── cross_dept.py            multi-dept coordinator
    ├── diagnostics.py           TF-IDF contradiction scan
    ├── skill_creator.py         auto-pattern → skill registration
    ├── market_radar.py          signals + DeepSeek digest
    ├── hermes_proxy.py          gateway HTTP proxy (currently offline)
    ├── hermes_coo.py            COO with 6 OpenAI-tools  ⚠ dup with hermes_max
    ├── hermes_max_tools_and_coo.py   COO with 10 fenced-JSON tools  ⚠ dup with hermes_coo
    ├── mempalace_bridge.py      ChromaDB long-term memory
    └── personas.py              [NEW v1.5] 8 marketing personas + tariff gate
```

## Current state (2026-05-20)

- **74/78 backend tests green.** 4 environmental failures (gateway offline, voice converse key shape, mock check) — not regressions.
- **Live LLM:** OpenRouter `deepseek/deepseek-chat-v3-0324`. Verified through orchestrator, hermes/ultra, all 8 personas.
- **Frontend:** 7 views including the new AGENTS = 8-persona grid with tariff gate.

## Personas → Tariff matrix

| Persona | Basic $9 | Simple $14 | Pro $19 | Enterprise $24 |
|---|---|---|---|---|
| Hermes | ✅ | ✅ | ✅ | ✅ |
| HR-Ментор | — | ✅ | ✅ | ✅ |
| Менеджер по клиентам | — | ✅ | ✅ | ✅ |
| Бухгалтер | — | — | ✅ | ✅ |
| Маркетолог | — | — | ✅ | ✅ |
| Compliance | — | — | ✅ | ✅ |
| Координатор проектов | — | — | — | ✅ |
| Аналитик | — | — | — | ✅ |

## Known architectural debt (from architect audit)

| Priority | Issue | Status |
|---|---|---|
| P0 | Two parallel Hermes COO files (6 vs 10 tools, OpenAI vs fenced-JSON) | Deferred — Phase 3 of unification plan |
| P0 | Cross-cutting (audit/cost/reliability) missing from 4/5 LLM channels | Deferred — Phase 1 of unification plan |
| P0 | LangGraph router-bug (tools never return to Hermes) | ✅ Fixed v1.4.1 |
| P1 | Hermes Gateway :8642 offline | Deferred — gateway is optional |
| P1 | 5/10 hermes_max tools are stubs with mock=True | Deferred |

## Next action items

- **VPS deployment** under `nxt8.pro` — playbook ready in chat (Contabo $7/mo, nginx + supervisor + certbot + Mongo backup).
- **Voice agent OpenAI key swap** — `agents/voice.py` currently uses EMERGENT_LLM_KEY which won't work outside Emergent env. Need OpenAI key + rewrite (~30 min).
- **Phase 1 cross-cutting hooks** — to make ROI dashboard truthful (currently undercounts ×10 because cost is recorded only in orchestrator).
- **Phase 3 Hermes unification** — merge `hermes_coo` + `hermes_max` into single `agents/hermes.py`.
- **Document upload module** — to give "Юрист" persona real document review capability (currently it's compliance-only).
