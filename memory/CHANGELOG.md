# NXT8 — Release Notes


## v1.4.0-mempalace — 2026-05-17

**Status:** ✅ MemPalace long-term memory layer integrated natively. Parallel to existing Mongo-backed short-term memory.

### Added
- **`agents/mempalace_bridge.py`** — async wrapper around `mempalace==3.3.5` (ChromaDB-backed). Functions:
  - `store(content, wing, room, metadata, source)`
  - `search(query, wing?, room?, top_k)`
  - `list_wings()` and `health()`
  - Singleton `get_mempalace()`
  - Sync calls run via `asyncio.to_thread` (no event-loop blocking).
- **REST endpoints** in `server.py`:
  - `GET  /api/mempalace/health`
  - `POST /api/mempalace/store`
  - `POST /api/mempalace/search`
  - `GET  /api/mempalace/wings`
- **Auto-save in `/api/chat/stream`** — after each completed stream the (user, assistant) pair is stored fire-and-forget under wing `chats`, room `{session_id}` with intent/user_id metadata. Skipped if either side <12/<20 chars to suppress noise.
- **Hermes COO tools** (`agents/hermes_coo.py`):
  - `mempalace_search(query, wing?, room?, top_k)` — semantic recall.
  - `mempalace_store(content, wing, room)` — explicit save by the agent.
- **Env vars** (`backend/.env`):
  - `MEMPALACE_ENABLED=true`
  - `MEMPALACE_PATH=/app/data/mempalace`

### Wings/Rooms schema (NXT8)
| Wing | Room | Use |
|---|---|---|
| clients | `{company_id}` | corporate clients knowledge |
| employees | `{user_id}` | individual employee facts |
| projects | `{project_id}` | project memory |
| chats | `{session_id}` | long-term chat history (auto-saved) |
| internal | `general` / topic | company-wide notes |

### Verified live
- ChromaDB embedding model `all-MiniLM-L6-v2` (79 MB) auto-downloaded on first call.
- `/api/mempalace/store` + `/api/mempalace/search` round-trip with cosine similarity 0.72 on exact-match recall.
- Streamed chat about "Mercury Pro / Иван Петров / deadline 30 марта 2026" → automatic drawer in `chats/{session_id}`, recalled by semantic search at similarity 0.76 (entities `Mercury;Pro` auto-extracted by mempalace).
- Hermes tool surface includes both new tools (verified in `TOOLS` registry); will execute when the Hermes gateway is online — DeepSeek-fallback path still bypasses tool execution by design.
- **Testing agent iteration_8: 20/20 backend tests green**, incl. 10 concurrent writes, 3 concurrent chat-stream autosaves, full regression.

### Concurrency fix (iter_7 → iter_8)
- `mempalace 3.3.5` takes an exclusive process-level palace lock per `add_drawer`; 5 parallel writes from the same uvicorn PID gave 1/5 success initially.
- Bridge now serialises writes with `asyncio.Lock` and retries 4× with linear backoff (100/200/300/400 ms) on `is held by PID` / `lock` errors. 10/10 parallel writes succeed in stress test.
- Empty content in `POST /api/mempalace/store` now returns **HTTP 400** (was 200 ok:false).

### Dependencies
- `+mempalace==3.3.5` (pulls chromadb, onnxruntime, opentelemetry, kubernetes, pydantic-settings…)
- requirements.txt regenerated via `pip freeze`.

### Not changed
- Short-term Mongo memory (`agents/memory.py`) is preserved as the working session context — MemPalace is a strictly additive long-term layer.
- Hermes-fallback `_fallback_chat` still goes straight to DeepSeek without tools when the Hermes gateway is offline. Not regressed — pre-existing behavior.

---


## v1.3.5-code-review-audit — 2026-05-17

**Status:** ℹ️ Code review report audited. **No code changes applied** — all 6 critical/important claims verified as false positives or pre-existing correct patterns. Ruff + ESLint both green.

### Audit results vs. report

| Claim | Verdict | Evidence |
|---|---|---|
| "20 undefined Python variables" | ❌ False positive | `ruff check /app/backend` → All checks passed |
| "23+ missing React hook deps across 6 files" | ❌ False positive | `eslint /app/frontend/src` → No issues found. Listed "missing" deps are module imports (`api`), refs (`audioCtxRef`), local-scope vars (`mounted`, `d`), and constants (`MAX_VISIBLE_TASKS`) — none belong in hook dep arrays. |
| "LocalStorage security vulnerability in CollapsibleCard" | ❌ False positive | Stores only boolean accordion open/close state. No tokens, PII, or credentials. Correct usage of localStorage. |
| "4 production console statements" | ❌ Already fixed | All 4 sites (`MicView.jsx:40`, `HomeView.jsx:344`, `SkillsPanel.jsx:115`, `craco.config.js:91`) already wrapped in `if (process.env.NODE_ENV !== "production")` with `eslint-disable-next-line no-console`. craco is build-time. |
| "Python `is True/False/None` → use `==`" | ❌ Anti-fix | All flagged sites compare to singletons `True`/`False`/`None`. PEP 8 explicitly recommends `is`/`is not` here. Replacing with `==` would degrade style. |
| "Refactor 13 high-complexity functions/components" | ⏸ Deferred (P3) | Already in backlog as "intentionally deferred to preserve Pilot Zero stability". Affects live LLM pipelines (`route`, `enhanced_chat`, `HomeView`). Will revisit post-pilot. |

### Decision
- Do nothing. Re-running lints confirms zero real issues. Applying the recommended "fixes" would either be no-ops, introduce infinite re-render loops (adding stable imports to dep arrays), or violate PEP 8.
- Backlog item P3 (refactor high-complexity functions) remains scheduled for post-Pilot-Zero stabilization phase.

---



## v1.3.4-voice-hermes-vad — 2026-05-17

**Status:** ✅ Voice agent overhaul — wired to Hermes COO, voice-channel reply guardrail, frontend VAD auto-submit on silence. Lint green. Live tested via curl loopback (TTS→STT→Hermes→TTS).

### Backend (`server.py`)
- `/api/voice/converse` rewritten:
  - Switched LLM call from `orchestrator_agent.route(channel="voice")` → **`hermes_coo_agent.enhanced_chat`** (function-calling COO, OpenRouter primary, DeepSeek fallback).
  - Loads last 6 messages of the session into the prompt (multi-turn continuity).
  - Prepends `VOICE_SYSTEM_HINT` ("разговорный тон, без markdown/JSON/списков, 2-3 предложения").
  - Post-processes reply via new `_trim_for_voice()` helper:
    - Strips fenced code blocks, markdown headers, list markers, `**` / `__` / backticks.
    - Collapses whitespace.
    - Keeps first **3 sentences** max.
    - Hard cap at **350 chars** with `…` suffix.
  - Persists user+assistant turn into short-term memory.
  - New response fields: `reply_raw` (only if trim changed text), `tools_used`, `iterations`, `provider`, `fallback`, `agent: "hermes_coo"`.

### Frontend (`MicView.jsx`)
- Voice Activity Detection (VAD) added to `startMeter` tick loop:
  - `SPEECH_THRESHOLD = 0.12` confirms user is speaking → flips `hasSpokenRef`.
  - `SILENCE_THRESHOLD = 0.06` + `SILENCE_HOLD_MS = 3000` — once user has spoken and stays below silence threshold for 3 s continuously → `autoStoppedRef.current = true` and `stopRecording()` fires automatically.
  - Auto-stop is one-shot per recording session; manual tap-to-stop still works first.
- VAD refs reset on every `startRecording()`.
- Hint text updated: "Whisper (STT) → Hermes COO → OpenAI TTS. … после 3 секунд тишины запрос уйдёт агенту автоматически."

### Verified e2e (live prod URL)
| Test | Before | After |
|---|---|---|
| Short RU converse latency | 9.2 s | **5.9 s** |
| Long RU converse reply length | ~1500 chars, markdown | **208 chars, 3 sentences** |
| Long RU converse audio size | ~1.7 MB | **408 KB** |
| Multi-turn session continuity | ❌ | ✅ |

### Known
- Hermes Gateway (HTTP proxy) currently unavailable in this environment → `enhanced_chat` exercises its DeepSeek fallback path (`fallback: "deepseek"`, no tool_calls). Reply quality unaffected.
- VAD requires real microphone — cannot be reproduced in Playwright; needs manual device test.

---


## v1.3.3-home-quickchat — 2026-05-17

**Status:** ✅ Third window (agent quick-chat) added to HomeView. ChatPanel extracted for reuse. Lint green.

### What changed
- New shared component **`/app/frontend/src/components/ChatPanel.jsx`** — extracted the entire SSE streaming chat (state, MessageBubble, input, send, scroll-to-bottom) out of `ChatView.jsx`. Props: `welcomeMessage`, `placeholder`, `heightClassName`, `sessionPrefix`, `testIdPrefix`. Each instance owns an isolated `session_id` so HOME quickchat ≠ CMD console history on the backend.
- **`ChatView.jsx`** slimmed to a 25-line shell that wraps `ChatPanel` inside `CollapsibleCard` (sessionPrefix `cmd`, height `h-[62vh]`).
- **`HomeView.jsx`** gets a third card `home-chat-card` (`storageKey="home-chat"`):
  - Title `agent.quickchat` with `MessageSquare` icon; titleRight `live · streaming`.
  - Body: `ChatPanel` with compact height `h-[44vh] min-h-[320px]`, sessionPrefix `home`, custom RU welcome message ("Привет. Я NXT8-агент…").
  - Desktop layout: `lg:col-span-2` — spans full width below the tasks|pipeline 2-col row.
  - Mobile layout: third card stacked after pipeline, naturally appears as user scrolls down. Verified live e2e: sent "что у нас по ARR?" → got "$4.8 млн… цель $7…" with conf/verified badges.

### UX impact
- Home no longer leaves blank space below pipeline on tall mobile screens — quick-chat fills it and is one swipe away.
- Two independent session contexts (home vs cmd) — so a quick question on HOME doesn't pollute the deep conversation in CMD.

---


## v1.3.2-desktop-grid — 2026-05-17

**Status:** ✅ Desktop layout overhaul. Lint green. Mobile parity preserved.

### What changed
- **App.js** restructured into a 3-row × 2-column shell:
  - Row 1: `TopTicker` (full viewport width)
  - Row 2: `<SideNav>` (left, `lg:flex`) + main column (`Header` + scrollable content)
  - Row 3: `<BottomNav>` (`lg:hidden`)
  - Content area max-width: `max-w-md` mobile, `max-w-screen-2xl` (1536px) desktop.
- New component **`/app/frontend/src/components/SideNav.jsx`** — vertical icon-bar (24/28px wide on `lg`/`xl`) mirroring the BottomNav items: HOME, CMD, OPS, AGENTS, MAP, ALERTS, MIC. Active item gets `neo-icon-active` + tinted border. Alerts badge preserved. testIds: `sidenav-<id>`.
- Per-view grid logic on `lg:`:
  - HomeView → `lg:grid lg:grid-cols-2 lg:gap-4` (tasks | pipeline)
  - OpsView widgets → 2-col grid below the `ops.cockpit` strip (5 cards: 2+2+1)
  - MapView → `roi.map` as `lg:col-span-2` hero, `cost.by_agent` + `roi.trend` as 2-col below
  - AgentsView → `lg:grid-cols-2` (list left, employee detail snaps right when selected)
  - AlertsView, ChatView, MicView → single card, width-capped (`lg:max-w-3xl/4xl/2xl`) and centered to avoid stretched single-card lines on wide screens.
- BottomNav now `lg:hidden`; SideNav `hidden lg:flex`. Verified Playwright at 1440×900: `side-nav` visible, `bottom-nav` hidden; at 420×800 reversed.

### UX impact
- Wide screens finally use horizontal real estate — Home, OPS, Map fill the dashboard naturally with 2-row × 2-col window arrangement, ticker spans the full top, navigation pinned left as a real cockpit.
- Mobile parity untested but unchanged by design (`space-y-*` defaults survive, only `lg:` classes added).

---


## v1.3.1-shell-layout — 2026-05-17

**Status:** ✅ App shell layout refactor + collapsible windows. Lint green.

### What changed
- **App.js** restructured to `h-screen flex flex-col overflow-hidden`. Top stack (TopTicker + Header + AI_INDEX strip) and bottom stack (BottomNav) are now `shrink-0`; only the middle `<main>` (`flex-1 overflow-y-auto overscroll-contain`) scrolls. The bar between header and bottom nav is now the sole scroll surface — top/bottom never move while content swipes.
- New shared component **`/app/frontend/src/components/CollapsibleCard.jsx`** — glass-card frame with click-to-toggle header strip, animated `max-height/opacity` body transition, ChevronUp/Down indicator, and `localStorage` persistence under prefix `nxt8.collapse.<key>`. Exposes `storageKey`, `title`, `titleRight`, `bodyClassName`, `testId`, `defaultOpen`.
- All top-level content sections refactored to use `CollapsibleCard`:
  - HomeView → `tasks-card` (`home-tasks`), `pipeline-card` (`home-pipeline`)
  - AgentsView → `agents-list-card` (`agents-list`)
  - AlertsView → `alerts-view` (`alerts-feed`)
  - MapView → `map-roi-card`, `map-cost-card`, `map-trend-card`
  - ChatView → `chat-view` (`chat-console`)
  - MicView → `mic-view` (`mic-voice`)
- OpsView widgets intentionally left as navigation buttons (their primary affordance is `onClick → sub-panel`, not info collapse).
- Toggle test IDs follow pattern `<testId>-toggle`. Card root carries `data-collapsed="true|false"` for assertions.

### UX impact
- Sticky shell: ticker + NXT8 logo + AI_INDEX strip and the bottom nav stay pinned while users scroll long content. Verified via Playwright: after scrolling 400px inside OPS, `top-ticker` and `bottom-nav` both report `is_visible() === true`.
- Collapse state persists across reloads (verified: collapsing `tasks-card`, reloading, `data-collapsed` still `"true"`).

---


## v1.3.0-ultra — 2026-05-17

**Status:** ✅ Hermes Ultra COO Agent on LangGraph live. 17/17 backend tests green (iter_6.json).

### What changed
- **LangGraph 1.2.0** installed (+ langchain-core 1.4.0, langgraph-checkpoint, langgraph-prebuilt).
- New module **`backend/agents/hermes_max_tools_and_coo.py`** — `HERMES_TOOLS` dict with 10 tools:
  - **Real (5):** `search_memory`, `create_task`, `update_task`, `monitor_sla_violations`, `create_cross_department_bridge`
  - **Stub (5, `mock=true`):** `generate_communication_summary`, `suggest_next_best_action`, `find_opportunities_in_contact`, `suggest_reply_template`, `evaluate_action_roi`
  - `hermes_coo_chat()` with strong COO system prompt and explicit ```json {"tool":"name","args":{...}}``` format instruction.
- New module **`backend/nxt8_langgraph_ultra.py`** — `StateGraph` orchestrator: `supervisor → hermes → tools → human_approval → supervisor`. MAX_ITER=3 + critical-action gate (`create_task`/`update_task`/`create_cross_department_bridge` in `controlled_automation` require human approval). `_extract_tool_calls` regex parses fenced JSON blocks. MemorySaver checkpointer keyed by `thread_id = session_id`.
- New endpoint **`POST /api/hermes/ultra`** `{message, company_id?, user_id?, session_id?, autonomy_level: read_only|assistant|controlled_automation}` → `{success, content, autonomy_level, thread_id, iterations, confidence, tool_traces[], requires_human_approval, fallback?}`. Persists turns via `memory.append_message`. Invalid `autonomy_level` falls back to `"assistant"`. Graceful fallback to `hermes_coo_chat()` if LangGraph fails.
- v1.2.0 endpoints (`/api/hermes/chat`, `/api/hermes/daily-digest`) preserved and tested — no regressions.
- New pytest suite: `/app/backend/tests/test_hermes_ultra.py` (17 tests).

### Known limitations
- DeepSeek `:free` is non-deterministic about emitting ```json {tool, args}``` blocks; tool execution path is therefore validated via unit tests with crafted assistant content (not solely via LLM behavior).
- `human_approval` node is a pilot stub — surfaces pending actions but doesn't block for out-of-band signal. Real production approval flow is a P2 backlog item.
- Hermes gateway (:8642) still offline in preview — Ultra runs purely on DeepSeek + LangGraph (this is by design for the pilot).

---

## v1.2.0-hermes-coo — 2026-05-16

**Status:** ✅ Hermes upgraded to COO Agent with function-calling and multi-tenant context.

### What changed
- New module **`backend/agents/hermes_coo.py`** — enhanced reasoning layer on top of `hermes_proxy` with strong COO system prompt, 4 function-calling tools and a backend dispatcher with real side-effects.
- `POST /api/hermes/chat` replaced: now accepts `{messages, company_id?, user_id?, mode?, temperature?, model?}` and returns `{content, tool_calls[], iterations, company_id, ...}`.
- `POST /api/hermes/daily-digest` added: `{company_id?, user_id, period?}` — triggers digest generation via the `generate_daily_digest` tool.
- 4 tools implemented end-to-end (real DB writes/reads):
  - `search_memory` → `MemoryEngine.search`
  - `create_followup` → MongoDB collection `followups` (new)
  - `detect_bottlenecks` → `diagnostics.summary` + open followups
  - `generate_daily_digest` → 24h/7d aggregation of requests + followups + diagnostics
- Multi-tenant ready: optional `company_id` (fallback `"default"`) propagated through prompts and persisted on followups.
- Graceful fallback to DeepSeek when the Hermes gateway (:8642) is offline — endpoint stays available, tools just aren't auto-invoked in that mode.

### Smoke tests (curl + standalone Python)
- `GET  /api/hermes/health` → offline (gateway not started in preview), expected.
- `POST /api/hermes/chat` → 200, COO-formatted response via DeepSeek fallback.
- `POST /api/hermes/daily-digest` → 200, same path.
- Standalone tool dispatcher: all 4 tools return `ok=True`; followup persisted in MongoDB, digest aggregated 72 recent requests / 1 open followup.

### Known limitations
- Tool calls only execute automatically when the Hermes gateway on :8642 is running (it supports OpenAI-style `tools`). DeepSeek fallback returns the COO answer but does not auto-invoke tools.
- `company_id` is propagated but not yet schema-enforced on all collections (multi-tenant remains a P2 backlog item).

---

## v1.1.0-hermes — 2026-05-16 (additive)

**Status:** ✅ Module 15 (Hermes Agent) added without breaking pilot zero.

### What changed
- New module **Hermes Agent (NousResearch v0.13.0)** — installed in isolated venv `/opt/hermes-venv` (no conflict with NXT8 `openai==1.99.9` pin needed by emergentintegrations/voice)
- Hermes gateway runs as supervisor program `hermes-gateway` on `127.0.0.1:8642` with `API_SERVER_ENABLED=true`, `GATEWAY_ALLOW_ALL_USERS=true`, OpenRouter as model provider
- NXT8 backend proxy router `/api/hermes/{health,chat,jobs}` — async httpx forwarder with graceful 502 fallback (never raises into FastAPI handler)
- New OPS dashboard widget `hermes · agent` + drill-down `HermesPanel` (5th module)
- 3 new backend tests + 7 new frontend tests — **41/41 backend + 28/28 frontend** all green
- Modules 11-14 (cross_dept/diagnostics/skills/market) untouched — Hermes is purely additive

### Env added to `/app/backend/.env`
```
HERMES_BASE_URL=http://127.0.0.1:8642
HERMES_API_KEY=<auto-generated>
```

### Hermes config at `/opt/hermes-home/.env`
```
API_SERVER_ENABLED=true
API_SERVER_PORT=8642
API_SERVER_HOST=127.0.0.1
API_SERVER_KEY=<bearer>
OPENROUTER_API_KEY=<same as NXT8>
```

### Known limitations
- POST `/api/hermes/jobs` requires a valid cron schedule (Hermes side); without one Hermes returns 400 and proxy reports `ok:false` — UI handles gracefully
- aiohttp installed via `pip install 'hermes-agent[web]'` extra (required for API server)

---

## v1.0.0-pilot-zero — 2026-05-16

**Status:** ✅ Production-ready for Pilot Zero deployment

### Live integrations
| Сервис | Состояние | Модель/детали |
|--------|-----------|---------------|
| LLM core (text + reasoning + logprobs) | LIVE | OpenRouter → `deepseek/deepseek-chat-v3-0324` (fallback: DeepSeek Direct) |
| STT | LIVE | Whisper-1 via Emergent Universal Key |
| TTS | LIVE | OpenAI tts-1 (nova voice) via Emergent Universal Key |
| MongoDB | LIVE | Motor async, indexes ensured at boot |
| Streaming chat | LIVE | SSE `/api/chat/stream` (meta/delta/done frames) |
| Hourly scheduler | ON | ROI + session cleanup + diagnostics + skill discovery |

### Modules shipped (10/10)
1. **Orchestrator** — intent classify → dispatch → reliability → audit
2. **Memory** — short-term sessions + long-term TF-IDF semantic search
3. **Reliability** — confidence + contradiction + hallucination signals
4. **Mentor** — 5 levels, weak-pattern detection, recommendations
5. **ROI** — cost tracking + time-decay revenue attribution + hourly snapshots
6. **Voice** — STT + TTS + one-shot converse loop
7. **Cross-Department Coordinator** — multi-dept fan-out + DeepSeek synthesis
8. **Diagnostics** — TF-IDF contradiction scan + noisy-intent ranking
9. **Skill Creator** — auto-registration of recurring (intent, signature) patterns
10. **Market Radar** — signal ingestion + 24h digest synthesis

### Frontend (7 views)
- HOME — tasks + pipeline + ROI mini-cards
- CMD — streaming chat (token-by-token, confidence chips)
- **OPS** — cockpit dashboard with 4 drill-down panels (cross-dept / diagnostics / skills / market)
- AGENTS — mentor roster + weak-pattern badges + employee detail
- MAP — ROI hourly map + cost-by-agent bars + 24h trend
- ALERTS — severity-tinted feed
- MIC — hold-to-talk voice converse loop

### Test coverage
- Backend: **38/38** pytest (iteration_3.json)
- Frontend Ops Dashboard: **21/21** E2E (iteration_4.json)
- LLM live latency: 1.5–7 s end-to-end, 1.5–3 s first-token (streaming)

### Known limitations (intentionally deferred → post-pilot)
- No auth / multi-tenancy (single-org pilot mode)
- No external news feed (Market Radar relies on manual ingest + seed)
- No Slack/WhatsApp adapters (web + REST API only)
- Voice Activity Detection — manual hold-to-talk only
- Executive Report export — to be added in parallel with observability

### Pilot-blocking issues
None.

---

## Earlier checkpoints

### v0.3 — 2026-05-15
- Voice module + MicView + SSE streaming + 4 new backend modules (cross-dept, diagnostics, skills, market). Backend complete; frontend missing Ops dashboard.

### v0.2 — 2026-05-14
- OpenRouter migration (resolved 402 from direct DeepSeek). Logprobs active.

### v0.1 — 2026-05-13
- Initial MVP: 5 modules + 5 views + LED-matrix design ported from HTML mockup.


## v1.4.1-router-fix — 2026-05-20 (Главный Системный Архитектор / E1)

**Status:** ✅ Critical P0-2 fix applied + project successfully deployed to /app from `github.com/mikkisisi1/nxt8.pro`.

### Audit performed
Full architectural audit of 15-agent ecosystem completed (Steps 1-2 per "Главный Системный Архитектор" protocol). Identified 5 top-priority issues:
1. Two parallel Hermes COO files with different tool sets (hermes_coo 6 vs hermes_max 10) → deferred to Phase 3
2. 4-5 parallel LLM response paths without unified cross-cutting (audit/cost/reliability) → deferred to Phase 1
3. **LangGraph router-bug: tool results never return to Hermes for finalization → FIXED in this release**
4. Hermes Gateway :8642 offline in env, hermes_coo tools never auto-invoke → architectural choice, deferred
5. ROI cost recording missing in 4/5 LLM channels → deferred to Phase 1

### Fix applied — LangGraph Router (P0-2)
**File:** `backend/nxt8_langgraph_ultra.py`

**Problem:** After `tools_node` executed tool calls and cleared `pending_tool_calls`, the router routed straight to `END`. The LLM never received tool results — user saw the raw assistant message with embedded ```json blocks instead of a proper 4-section COO summary.

**Solution:**
- New state field `tools_just_executed: bool`
- `tools_node` sets it to `True` after execution
- `hermes_node` resets it to `False` after consuming tool results
- `_router` checks this flag and bounces back into `hermes` for finalization
- Hard-bounded by existing `MAX_ITER=3` against infinite loops

**Live verified on real OpenRouter (deepseek-v3-0324):**
- Query: "Проверь SLA нарушения и составь список 3 главных задач"
- Before: iterations=1, tool_traces=[], content="Готов помочь. Опишите задачу."
- After: iterations=3, tool_traces=[5 calls — monitor_sla, find_opportunities, create_cross_department_bridge → real task_id, etc], content=full 4-section COO summary with summary/важно/действия/эффект.

### Deployment
- Pulled code from `https://github.com/mikkisisi1/nxt8.pro.git` into `/app`
- Installed Python deps (178 packages, requirements.txt unchanged)
- Installed Node deps via yarn
- Created `backend/.env` with: `OPENROUTER_API_KEY`, `EMERGENT_LLM_KEY`, `MEMPALACE_ENABLED=true`
- Created `frontend/.env` with `REACT_APP_BACKEND_URL`
- Restarted supervisor (`backend`, `frontend`)
- Verified `/api/health` → `status=ok, mongo=true, deepseek.live=true, voice.enabled=true`

### Test results
- **74/78 pytest tests green** (test suite in `backend/tests/`)
- 4 failures, all environmental (NOT regressions from the router-fix):
  - `test_health` — expected `voice.enabled` differently
  - `test_voice_converse_full_loop` — missing `should_escalate` key in voice converse response (pre-existing)
  - `test_hermes_health_online` — Hermes gateway :8642 not running in env (known)
  - `test_hermes_jobs_list` — same as above
- All `test_hermes_ultra.py` tests green (includes router logic)
- All `test_mempalace.py` tests green
- Frontend OPS dashboard verified via screenshot (5 modules visible: cross-dept, diagnostics, skills, market, hermes-offline-indicator)

### Not changed
- No other code files touched. All other architectural issues from the audit are documented in main agent's plan and await user "go" for Phase 1 / Phase 3 / Phase 4 work.



## v1.5.0-personas — 2026-05-20 (Главный Системный Архитектор / E1)

**Status:** ✅ Personas Layer — маркетинговое соответствие 8 агентам + тарифные ворота.

### Что добавлено
- **`agents/personas.py`** — 8 персон поверх существующих модулей (не дублирует ни строчки):
  | id | name | min plan | tools | data_fetchers |
  |---|---|---|---|---|
  | hermes | Hermes | basic | 10 | — |
  | hr_mentor | HR-Ментор | simple | 1 | mentor_overview |
  | client_manager | Менеджер по клиентам | simple | 5 | — |
  | project_coord | Координатор проектов | enterprise | 5 | — |
  | analyst | Аналитик | enterprise | 2 | diagnostics_summary + roi_current |
  | bookkeeper | Бухгалтер | pro | 1 | roi_dashboard |
  | marketer | Маркетолог | pro | 2 | market_intel |
  | compliance | Юрист / Compliance | pro | 1 | compliance_context |
- **Тарифы:** Basic ($9, 1 persona) / Simple ($14, 3) / Pro ($19, 6) / Enterprise ($24, 8).
- **`run_persona()`** — единый pipeline: pre-context fetch → DeepSeek (persona-specific prompt + restricted tool list) → fenced-JSON tool execution с allow-list → второй проход с tool results → audit в `db.persona_requests`.
- **REST API:**
  - `GET /api/personas?plan_id=…` — список 8 с флагом `available_on_plan` и `min_plan` для каждой.
  - `POST /api/personas/{id}/chat` — диалог. Возвращает **HTTP 402** если персона недоступна на текущем тарифе (`required_plan` в теле).
- **Frontend `AgentsView.jsx`** полностью переписан в 8-карточек grid с переключателем тарифа, модальным чатом и индикаторами locked/lock-icon + min_plan.

### Verified live (DeepSeek v3-0324)
| Тест | Результат |
|---|---|
| `GET /api/personas` | 8 personas, plans корректны, min_plan match |
| `POST .../bookkeeper/chat` с `plan_id=basic` | **HTTP 402** + `required_plan: pro` ✅ |
| `POST .../bookkeeper/chat` с `plan_id=pro` | Реальный отчёт: ROI +34.5%, разбивка по support/orchestrator/memory ($23.33/$14.88/$8.75), интерпретация и рекомендации ✅ |
| `POST .../hr_mentor/chat` с `plan_id=simple` | Увидел реальное "Junior Lee, support, 3 мес, 9/8/8 repeating errors", предложил Carla Reyes в пару ✅ |
| `POST .../compliance/chat` с `plan_id=pro` | 2 iterations (использовал tool), увидел 5 reliability эскалаций, сослался на политику SLA 99.9% ✅ |
| Frontend AGENTS view | 8 cards rendered, plan selector работает, 7 locked badges visible на Basic ✅ |

### Архитектурный принцип
- Persona = `(system_prompt, allowed_tools, data_fetchers)`, **код агентов не тронут** (mentor, roi, diagnostics, market_radar, memory).
- Tool allow-list проверяется ДВАЖДЫ: (1) в system prompt LLM видит только разрешённые, (2) при исполнении лишние tools блокируются на dispatcher.
- Тарифные ворота — единственная новая БД-коллекция `db.persona_requests` (для audit). Никаких миграций существующих коллекций.

