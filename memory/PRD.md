# NXT8 — Product Requirements Document

**Current version:** v1.6.0-unified (additive over v1.5.0-personas)
**Last updated:** 2026-05-20 by Главный Системный Архитектор (E1)

## What was built (in chronological order)

1. **v0.1–v1.0 Pilot Zero** — 10 modules (orchestrator, memory, reliability, mentor, roi, voice, cross_dept, diagnostics, skill_creator, market_radar) + 7 UI views.
2. **v1.1 Hermes** — Hermes Agent proxy (gateway on :8642, offline in current env).
3. **v1.2 Hermes COO** — `hermes_coo.py` with 6 OpenAI-format tools.
4. **v1.3 Ultra** — `hermes_max_tools_and_coo.py` with 10 fenced-JSON tools + LangGraph supervisor.
5. **v1.4 MemPalace** — ChromaDB long-term memory layer + auto-save from chat/stream.
6. **v1.4.1 Router-fix** — fixed LangGraph router bug where tool results never returned to Hermes for final answer.
7. **v1.5 Personas Layer** — 8 marketing-aligned persona wrappers + tariff gate.
8. **v1.6 Unification (this release):**
   - **Phase 1: Universal Audit Hooks** — `agents/_pipeline_hooks.py` injected into 5 LLM channels (chat-stream, hermes/chat, hermes/ultra, personas/*, voice/converse). ROI dashboard now sees real cost across ALL channels (was undercounting ~10×).
   - **Phase 3: Hermes Unification** — `agents/hermes.py` is now the single source of truth (15 unified tools, fenced-JSON only). `hermes_coo.py` + `hermes_max_tools_and_coo.py` reduced to thin shims (re-exports). Tasks + Followups now stored in unified `db.tasks` with `kind` field.
   - **Voice/converse `should_escalate` fix** — was missing in response payload; broke `test_voice_converse_full_loop`.
   - **Document Parsing (Compliance persona)** — new `agents/documents.py`, `POST /api/documents/upload`, `GET /api/documents`, `GET /api/documents/{id}`. PDF/DOCX/TXT extraction → MemPalace ingestion (wing=documents) → DeepSeek risk pass → persisted verdict (severity / findings / recommended_actions). Compliance persona system_prompt updated to use mempalace_search wing=documents.

## Architecture (as built)

```
/app/backend/
├── server.py                    FastAPI app + ~55 endpoints
├── core/
│   ├── deepseek.py              OpenRouter primary → DeepSeek direct fallback → mock
│   └── db.py                    Motor MongoDB + ensure_indexes (now incl. tasks(kind), documents)
├── nxt8_langgraph_ultra.py      LangGraph supervisor → hermes → tools → human_approval [+ router-fix]
└── agents/
    ├── orchestrator.py          intent classify → dispatch → reliability → audit
    ├── memory.py                short-term + TF-IDF long-term
    ├── reliability.py           confidence + contradictions + hallucination
    ├── mentor.py                5 levels, weak patterns, recommendations
    ├── roi.py                   cost tracking + revenue attribution + hourly
    ├── voice.py                 Whisper STT + OpenAI TTS (dual provider: OpenAI SDK / Emergent key)
    ├── cross_dept.py            multi-dept coordinator
    ├── diagnostics.py           TF-IDF contradiction scan
    ├── skill_creator.py         auto-pattern → skill registration
    ├── market_radar.py          signals + DeepSeek digest
    ├── hermes_proxy.py          gateway HTTP proxy (currently offline)
    ├── hermes.py                [NEW v1.6] UNIFIED Hermes COO: 15 tools + chat()
    ├── hermes_coo.py            [v1.6 shim] re-export from hermes
    ├── hermes_max_tools_and_coo.py   [v1.6 shim] re-export from hermes
    ├── mempalace_bridge.py      ChromaDB long-term memory
    ├── personas.py              8 marketing personas + tariff gate
    ├── documents.py             [NEW v1.6] PDF/DOCX/TXT ingestion + risk review
    └── _pipeline_hooks.py       [NEW v1.6] Universal LLM audit/cost hook
```

## Personas → Tariff matrix

| Persona | Basic $9 | Simple $14 | Pro $19 | Enterprise $24 |
|---|---|---|---|---|
| Hermes | ✅ | ✅ | ✅ | ✅ |
| HR-Ментор | — | ✅ | ✅ | ✅ |
| Менеджер по клиентам | — | ✅ | ✅ | ✅ |
| Бухгалтер | — | — | ✅ | ✅ |
| Маркетолог | — | — | ✅ | ✅ |
| Compliance (с разбором документов) | — | — | ✅ | ✅ |
| Координатор проектов | — | — | — | ✅ |
| Аналитик | — | — | — | ✅ |

## API surface (key endpoints)

- `POST /api/chat`, `POST /api/chat/stream` (SSE)
- `POST /api/hermes/chat`, `POST /api/hermes/ultra`
- `POST /api/personas/{persona_id}/chat` + `GET /api/personas`
- `POST /api/voice/converse` (STT → Hermes → TTS), `/api/voice/stt`, `/api/voice/tts`
- `POST /api/documents/upload`, `GET /api/documents`, `GET /api/documents/{id}` *(new in v1.6)*
- `POST /api/seed`, `GET /api/health`, `GET /api/roi/*`, `GET /api/mentor/*`, `GET /api/mempalace/*`

## Known architectural debt

| Priority | Issue | Status |
|---|---|---|
| P0 | Two parallel Hermes COO files | ✅ Fixed v1.6 (single `agents/hermes.py`) |
| P0 | Cross-cutting (audit/cost/reliability) missing from 4/5 LLM channels | ✅ Fixed v1.6 (`_pipeline_hooks.py`) |
| P0 | LangGraph router-bug | ✅ Fixed v1.4.1 |
| P0 | `should_escalate` missing in `/voice/converse` | ✅ Fixed v1.6 |
| P1 | Hermes Gateway :8642 offline | Deferred — gateway is optional |
| P1 | 5/15 hermes tools are stubs with mock=True | Deferred |
| P1 | No frontend UI for documents upload | Deferred |
| P2 | Slack/WhatsApp/CRM/Email channel adapters | Deferred |
| P2 | Multi-tenant org_id scoping in all collections | Deferred |

## Next action items (P1+)

- Frontend: AGENTS view — add upload button for Compliance persona pointing at `/api/documents/upload` + table of past reviews.
- Real implementations for 5 stub tools (`generate_communication_summary`, `suggest_next_best_action`, `find_opportunities_in_contact`, `suggest_reply_template`, `evaluate_action_roi`).
- Channel adapters (Slack/WhatsApp/CRM/Email).
- Multi-tenant `org_id` scoping in all collections.
- VPS deployment validation under `nxt8.pro` (kit already exists in `/app/deploy/`).
