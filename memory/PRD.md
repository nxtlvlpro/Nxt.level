# NXT8 — Product Requirements Document

**Version:** v1.3.0-ultra (additive over v1.2.0-hermes-coo)
**Released:** 2026-05-17
**Status:** ✅ Hermes Ultra COO on LangGraph live (10 tools, 3 autonomy levels, critical-action gate). 17/17 backend tests green. См. `CHANGELOG.md`, `ROADMAP.md`, `PILOT_ZERO.md`.

---

## 1. Original problem statement (user verbatim)

> Создать AI-native операционную систему для компаний (NXT8), которая:
> - не требует от сотрудников промпт-инжиниринга
> - объединяет AI-инструменты в единый интеллектуальный слой
> - обладает корпоративной памятью
> - объясняет свои решения (confidence + verification)
> - измеряет ROI в реальном времени
> - использует DeepSeek как единое ядро

Provided ТЗ in 16 files (`xcod 0..14`) covering 10 modules + design HTML.

## 2. User-confirmed decisions

| # | Choice | Decision |
|---|--------|----------|
| 1 | LLM core | **1a** — DeepSeek API direct, key delivered later |
| 2 | Deployment | **2a** — single FastAPI + React + MongoDB; agents = internal modules |
| 3 | MVP scope | **3b** — Orchestrator + Memory + Reliability + Mentor + ROI + UI |
| 4 | UI design | **4a** — port HTML mockup 1:1 (dark + turquoise + LED matrix) |
| 5 | Voice | **5b** — stub for MVP, real impl in next phase |

## 3. Architecture (as built)

Single FastAPI process on :8001 with /api prefix routes; React on :3000.

```
/app/backend/
├── server.py                 FastAPI app, lifespan, /api router
├── core/
│   ├── deepseek.py           DeepSeek client w/ logprob→confidence + mock mode
│   └── db.py                 Motor MongoDB, ensure_indexes()
└── agents/
    ├── orchestrator.py       intent classify → dispatch → reliability → audit
    ├── memory.py             short-term (sessions) + long-term (TF-IDF semantic)
    ├── reliability.py        confidence + contradiction + hallucination
    ├── mentor.py             5 levels, weak patterns, recommendations
    └── roi.py                cost tracking + time-decay revenue attribution + hourly ROI

/app/frontend/src/
├── App.js                    6-view router (home/cmd/agents/map/alerts/mic)
├── components/
│   ├── TopTicker.jsx, Header.jsx, BottomNav.jsx
│   └── views/{Home,Chat,Agents,Map,Alerts,Mic}View.jsx
├── lib/api.js                axios → REACT_APP_BACKEND_URL/api
└── index.css                 LED-matrix bg, glass-card, glow, neo-btn
```

## 4. Implemented modules (12/14)

- ✅ **Core** — FastAPI, MongoDB, supervisor
- ✅ **Orchestrator** — `POST /api/chat` intent-routing pipeline + `POST /api/chat/stream` SSE
- ✅ **Memory** — short-term + long-term TF-IDF semantic search
- ✅ **Reliability** — confidence weighted + contradiction + hallucination check
- ✅ **Mentor** — 5 levels, weak patterns, recommendations
- ✅ **ROI** — cost tracking, revenue attribution, hourly snapshots
- ✅ **Voice** *(2026-05-16)* — Whisper STT + OpenAI TTS via Emergent key, `/voice/converse` one-shot loop, hold-to-talk MicView
- ✅ **LLM Provider chain** *(2026-05-16)* — OpenRouter primary (`deepseek/deepseek-chat-v3-0324` with logprobs) → DeepSeek direct fallback → mock
- ✅ **Cross-Department Coordinator** *(2026-05-16)* — `/api/cross-dept/{detect,coordinate,tasks}` heuristic dept-detection + LLM synthesis
- ✅ **Diagnostics** *(2026-05-16)* — `/api/diagnostics/{scan,contradictions,summary}` TF-IDF contradiction classifier on request audit log; hourly scheduler tick
- ✅ **Skill Creator** *(2026-05-16)* — `/api/skills/{scan,*,/{id}/toggle}` auto-discovers repeating prompt patterns ≥3 hits @ confidence ≥0.75; manual CRUD
- ✅ **Market Radar** *(2026-05-16)* — `/api/market/{signals,scan,digests}` ingest market signals + DeepSeek-powered intelligence digest
- ✅ **MemPalace Long-Term Memory** *(2026-05-17)* — native `mempalace==3.3.5` Python integration via `agents/mempalace_bridge.py`. ChromaDB-backed Wings→Rooms→Drawers store at `/app/data/mempalace/`. REST: `/api/mempalace/{health,store,search,wings}`. Auto-save of user/assistant chat pairs from `/api/chat/stream` into `chats/{session_id}`. Hermes COO gets 2 new tools: `mempalace_search`, `mempalace_store`.
- ✅ **UI** — 6 views, streaming chat with live token-by-token render + caret animation

## 5. Deferred to next phases

- ⏳ Production observability (Prometheus + Grafana from `install_finalize.sh`)
- ⏳ Multi-tenant company scoping
- ⏳ Slack / WhatsApp channel adapters
- ⏳ Voice Activity Detection (auto start/stop on silence) for truly "invisible" voice

## 6. API surface (verified)

```
GET   /api/health
POST  /api/seed                              (idempotent demo seed)
POST  /api/chat                              (main pipeline)
GET   /api/requests                          (audit log)
GET   /api/sessions/{session_id}

POST  /api/memory/store
POST  /api/memory/search
GET   /api/memory/list

POST  /api/reliability/assess

POST/GET  /api/mentor/employees
GET   /api/mentor/employees/{id}
POST  /api/mentor/performance
POST  /api/mentor/detect/{id}
GET   /api/mentor/patterns
GET   /api/mentor/recommend/{id}/{pattern}

GET   /api/roi/dashboard
GET   /api/roi/current
GET   /api/roi/trend?hours=
POST  /api/roi/deals
POST  /api/roi/interactions

GET   /api/alerts

POST  /api/chat/stream      (SSE: meta/delta/done frames)
POST  /api/voice/stt        (multipart audio → Whisper transcript)
POST  /api/voice/tts        (JSON {text,voice,speed} → audio/mpeg MP3)
POST  /api/voice/converse   (STT→orchestrator→TTS, audio_b64 mp3)

POST  /api/cross-dept/coordinate
GET   /api/cross-dept/detect?query=...
GET   /api/cross-dept/tasks

POST  /api/diagnostics/scan
GET   /api/diagnostics/contradictions
GET   /api/diagnostics/summary

POST  /api/skills/scan
GET   /api/skills?enabled=
POST  /api/skills
POST  /api/skills/{id}/toggle?enabled=

POST  /api/market/signals
GET   /api/market/signals?category=
POST  /api/market/scan?window_hours=
GET   /api/market/digests

GET   /api/mempalace/health
POST  /api/mempalace/store      ({content, wing, room, metadata?, source?})
POST  /api/mempalace/search     ({query, wing?, room?, top_k?})
GET   /api/mempalace/wings      (list Wings + Rooms + counts)
```

## 7. Current state / test results

- Backend: **38/38 pytest** pass (testing agent iter_3)
- Frontend: **21/21 ops dashboard E2E** pass (testing agent iter_4) — Ops Dashboard + 4 drill-down панелей работают через реальный backend
- 7 views: HOME, CMD (streaming chat), **OPS (cockpit + drill-down)**, AGENTS, MAP, ALERTS, MIC
- LLM: **LIVE** via OpenRouter primary (`deepseek/deepseek-chat-v3-0324`, logprobs ON) + DeepSeek direct fallback. typical latency 1.5–7s
- Voice: **LIVE** via Emergent Universal Key — whisper-1 STT + tts-1 MP3
- Hourly scheduler: ROI snapshot + session cleanup + diagnostics scan + skill discovery
- Seed: 6 corporate memories, 4 employees, 4 deals, 5 market signals, weak patterns для Junior Lee

## 8. Backlog / next tasks

**P2:**
- Observability layer: Prometheus + Grafana (port `install_finalize.sh`)
- Multi-tenant company scoping
- Slack / WhatsApp channel adapters

**P3 (polish, from testing agent code-review):**
- Toast/error UI на failure ops-сканов (diagnostics/skills/market)
- Submit-on-Enter в CrossDeptPanel textarea
- Refactor MarketPanel CAT_COLOR class-splitting (хрупкий парсинг)
- useEffect dependency `[sub]` в OpsView заменить на `[]` (мелкая семантика)

## 9. Personas

- **Operator / Manager** — uses HOME (tasks), OPS (cockpit), AGENTS (mentor), MAP (ROI), ALERTS
- **End user / employee** — uses CMD (chat) для knowledge, MIC для voice
- **Executive** — OPS dashboard (cross-dept synthesis, market digest) + MAP (ROI trend)
- **Admin / Eng** — uses /api/seed, /api/requests audit log, /api/health, OPS/Diagnostics панель
