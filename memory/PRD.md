# NXT8 — Product Requirements Document

**Current version:** v1.13.0-graph-v2 (additive over v1.12.0-onboarding)
**Last updated:** 2026-06-04 by Главный Системный Архитектор (E1)

## 🔒 LOCKED COMPONENTS

The following parts of the codebase are **explicitly frozen by the product owner**. Future agents MUST ask the user before changing any value listed here:

- **Header layout** — see `/app/frontend/src/config/header.locked.js` (logo height = `h-4`, left bleed = `-ml-6`, header `py-0`, shell top padding `pt-0`, home view padding `pt-0 pb-4`). The cropped PNG at `/app/frontend/public/nxt8-logo.png` is also part of the contract — it must remain tight-cropped (no transparent padding).

## What was built (in chronological order)

1. **v0.1–v1.0 Pilot Zero** — 10 modules (orchestrator, memory, reliability, mentor, roi, voice, cross_dept, diagnostics, skill_creator, market_radar) + 7 UI views.
2. **v1.1 Hermes** — Hermes Agent proxy (gateway on :8642, offline in current env).
3. **v1.2 Hermes COO** — `hermes_coo.py` with 6 OpenAI-format tools.
4. **v1.3 Ultra** — `hermes_max_tools_and_coo.py` with 10 fenced-JSON tools + LangGraph supervisor.
5. **v1.4 MemPalace** — ChromaDB long-term memory layer + auto-save from chat/stream.
6. **v1.4.1 Router-fix** — fixed LangGraph router bug where tool results never returned to Hermes for final answer.
7. **v1.5 Personas Layer** — 8 marketing-aligned persona wrappers + tariff gate.
8. **v1.6 Unification:**
   - **Phase 1: Universal Audit Hooks** — `agents/_pipeline_hooks.py` injected into 5 LLM channels (chat-stream, hermes/chat, hermes/ultra, personas/*, voice/converse). ROI dashboard now sees real cost across ALL channels (was undercounting ~10×).
   - **Phase 3: Hermes Unification** — `agents/hermes.py` is now the single source of truth (15 unified tools, fenced-JSON only). `hermes_coo.py` + `hermes_max_tools_and_coo.py` reduced to thin shims (re-exports). Tasks + Followups now stored in unified `db.tasks` with `kind` field.
   - **Voice/converse `should_escalate` fix** — was missing in response payload; broke `test_voice_converse_full_loop`.
   - **Document Parsing (Compliance persona)** — new `agents/documents.py`, `POST /api/documents/upload`, `GET /api/documents`, `GET /api/documents/{id}`. PDF/DOCX/TXT extraction → MemPalace ingestion (wing=documents) → DeepSeek risk pass → persisted verdict (severity / findings / recommended_actions). Compliance persona system_prompt updated to use mempalace_search wing=documents.
9. **v1.7 P1 Wave:**
   - **DocumentsPanel UI** — `frontend/src/components/views/ops/DocumentsPanel.jsx`: drag-and-drop upload zone, severity stats grid (CRITICAL/HIGH/MEDIUM/LOW), document cards with expandable findings + recommended actions, real-time list refresh. Added as 6th widget in OpsView (`widget-documents`).
   - **5 Real-LLM Hermes tools** — replaced legacy stubs (`mock=True`) with DeepSeek-backed implementations:
     - `generate_communication_summary` → summary + sentiment + key_topics + open_questions + suggested_next_action
     - `suggest_next_best_action` → action + owner + urgency + horizon_hours + rationale + expected_impact
     - `find_opportunities_in_contact` → opportunities[] (upsell/cross-sell/renewal/retention) with value range + memory snippet retrieval from MemPalace
     - `suggest_reply_template` → contextual draft (subject + body + CTA) tailored to last_message + intent + tone + language (with canned fallback for tone-only invocations)
     - `evaluate_action_roi` → estimated_roi + value range + cost estimate + horizon + rationale + risks + company_roi_context from latest `db.roi_history` snapshot
10. **v1.8 Landing-as-HomeView:**
    - **HomeView переработан** в маркетинговый лендинг по ТЗ — заменён старый дашборд (TasksCard + PipelineCard + quickchat) на: Hero-блок → ticker → горизонтальный свайп AI-агентов (7 карточек) → встроенный Hermes-чат с переключателем текст/голос → ticker → Тарифы (4 карты $9/$14/$19/$24) → ticker → Как работает (3 шага) → Пилот CTA. Существующий app shell (TopTicker / Header / SideNav / BottomNav) сохранён без изменений.
    - **Hermes inline chat** — `POST /api/hermes/chat` для текста, `POST /api/voice/converse` (Whisper STT → Hermes → TTS) для голоса.
    - **CTA routing** — все «Подключить» / «Начать» / «Запустить пилот» открывают `https://nxt8.pro/checkout?plan={id}` в новой вкладке (placeholder; Stripe integration отложена).
    - **Цвет/стиль** — без изменений (turquoise glass-cards + LED-matrix).
11. **v1.9 i18n / EN default + RU switcher (this release, 2026-05-26):**
    - **Lightweight in-house i18n** — `frontend/src/i18n/translations.js` (flat dotted keys for EN/RU) + `LanguageContext.jsx` (React Context + `useT()` hook + `localStorage` persistence under `nxt8.lang`).
    - **Default language = English**; previous Russian-only UI moved to opt-in via the burger.
    - **Real language switcher** in Burger → `Languages` panel: two pill-cards (EN / RU) with native + translated name, active check-mark, persists across reloads.
    - **Voice respects language** — `MicView` and the inline HomeView voice mode now pass the current `lang` to `POST /api/voice/converse` so Whisper STT transcribes accurately in EN or RU and TTS replies in the matching language.
    - **Hermes inline chat respects language** — the HomeView Hermes chat prepends a system instruction (`Reply in English / Отвечай по-русски`) so DeepSeek answers in the chosen language regardless of the user's input language.
    - **Translated surfaces (in this pass):** Header / Seed error / BurgerMenu (all sections incl. pricing tiers) / HomeView (carousel intro + 7 agent cards + Hermes chat + tariffs + how-it-works + pilot CTA) / MicView (status + captions + errors) / ChatPanel (welcome + thinking + connection errors) / AlertsView (events count + empty state + locale-aware time) / MapView (titles + empty/loading states) / AgentsView personas modal (welcome + plan-gate + typing + ask placeholder + footer) / OpsView widget fallback copy (cross-dept / skills / market / hermes / documents).
    - **Untranslated by design:** technical cockpit labels (`ops.cockpit`, `cross-dept · coordinator`, `roi.map · hourly`, etc.) and global ticker symbols remain as-is.

12. **v1.10 JOKER sandbox sub-agent (2026-06-04):**
    - **Goal** — protect the operational core from joke/meme/trolling/fantasy traffic. Per ТЗ: zero-trust, separate audit ledger, never touches MemPalace / tasks / requests / roi.
    - **`agents/classifier.py`** — two-stage intent router. Stage 1: regex pre-filter (free, covers ~80 % of noise — "анекдот", "загадка", "кто сильнее", "joke", "meme", emoji-only, hard greetings) and BUSINESS keywords that always win (sales, project, KPI, contract, marketing, finance, HR, analytics, …). Stage 2 (only when ambiguous): a single DeepSeek call with `max_tokens=6` returning `BUSINESS` or `NON_BUSINESS`.
    - **`agents/joker.py`** — isolated sandbox: short system prompt (RU + EN), `max_tokens=150`, history limited to last 4 turns, temperature 0.8, NO imports from `agents.memory`, `agents.mempalace_bridge`, `agents.documents`, no task creation, no MemPalace writes.
    - **Rate-limit** — 20 turns / 30 min per `session_id`; on overflow → `max_tokens=40` + history=1 (downgraded flag persisted to audit).
    - **Routing point** — `agents/hermes.py:hermes_chat()`. On every turn the LAST user message is classified before the system prompt is built. If `route == "joker"`, JOKER replies and the payload is returned in the SAME shape Hermes uses (`content`, `tool_calls=[]`, `provider="joker_sandbox"`, plus `routed_to / routing_reason / routing_stage / downgraded`) so all downstream consumers (`/api/hermes/chat`, `/api/voice/converse`, `/api/voice/converse/stream`, `/api/chat`, `/api/personas`) work without code changes.
    - **Isolation enforcement** — in `server.py:/api/hermes/chat`, if `routed_to == "joker"` the universal `finalize_llm_turn` pipeline hook is **skipped**, so JOKER traffic never lands in `db.requests` or `db.costs`. JOKER keeps its own ledger.
    - **New collection** `db.joker_audit` (indexes on `session_id+ts` and `ts`). Schema: `{id, session_id, user_id, lang, message[:500], reply[:500], tokens_total, downgraded, channel:"joker", ts}`.
    - **New endpoint** `GET /api/joker/stats?window_minutes=60` — returns `{turns, tokens, downgraded, window_minutes}` aggregated from `joker_audit` only.
    - **Auto-return to business** — classifier runs on EVERY turn. A user who joked, then asks "статус по сделкам" lands back in Hermes immediately, no UI toggle.
    - **UX** — completely transparent. No badge in HomeView bubbles per user request. `routed_to` field is present in API response for future Ops/Diagnostics widget.
    - **Verified** end-to-end with 5 curl scenarios: regex-joker, regex-fantasy, LLM-tiebreaker-joker, hard-business, /api/joker/stats — all pass.

13. **v1.10.1 Voice UX polish (2026-06-04):**
    - **Waveform integration finished** — the existing `frontend/src/components/Waveform.jsx` is now actually fed audio in BOTH directions inside HomeView voice mode: live MediaStream during recording, currently-playing `<audio>` element during TTS playback (was previously dead — `activeAudio` state was declared but never set).
    - **Breathing mic button** — the idle large mic CTA on HomeView was hard to notice (faint `border-brand-turquoise/40` only). Replaced with a smooth 3.2 s "breathing" turquoise glow (`.voice-mic-breathe` keyframes on border + box-shadow + inner shadow) plus a slower outer halo ring (`.voice-mic-halo`) for layered depth. Animation gates OFF when the button is in red/turquoise/purple event states so the visual language stays clear.

14. **v1.11 Channel Adapters — Wingman-inspired ingress layer (2026-06-04):**
    - **Motivation** — user asked to evaluate migrating to wingman-ai as a skeleton. Deep analysis (TS+Bun+SQLite local dev-tool vs Python+FastAPI+MongoDB SaaS) showed migration would require ~300h rewrite for a functionally weaker product. Decision: **stay on current stack, cherry-pick best ideas**. First port: Wingman's channel/bindings ingress.
    - **`backend/channels/`** — new package introducing a uniform ingress contract:
      - `base.py` — `InboundEvent`, `OutboundReply`, abstract `ChannelAdapter`, `ChannelBinding` dataclasses. Adapter contract: `parse(payload, headers) → InboundEvent` + `format(reply, event) → dict`.
      - `webhook.py` — `WebhookAdapter` (generic JSON ingress, optional HMAC-SHA256 signature verification with constant-time `hmac.compare_digest`).
      - `registry.py` — most-specific-first bindings router. Merges built-in defaults from `data/channels.json` with runtime DB overrides from `db.channel_bindings`. Resolution: longest matching `intent_filter` regex wins; empty filter is the wildcard.
      - `invoke_agent_for_binding()` dispatches to `agents.hermes.hermes_chat` / `agents.joker.respond` / `agents.personas.run_persona` with consistent `OutboundReply` shape — keeps channels package free of upstream agent imports cycles.
    - **Persona dispatch unlocks the tariff gate** — channel webhooks are server-to-server, so they call `run_persona(..., plan_id="enterprise")` to bypass user-tier restrictions while still respecting persona system prompts and tools.
    - **Endpoints** in `server.py`:
      - `GET  /api/channels` — list merged bindings (file + DB)
      - `POST /api/channels/bindings` — upsert runtime binding (stored in Mongo)
      - `DELETE /api/channels/bindings?channel_id=&intent_filter=` — remove runtime binding
      - `POST /api/channels/webhook/{channel_id}` — main ingress: parses JSON `{text, user_id, lang, attachments}`, resolves binding, verifies HMAC if `signing_secret` set, invokes agent, logs to `db.channel_events`, returns formatted reply.
      - `GET  /api/channels/{channel_id}/events?limit=20` — recent activity feed for Ops dashboard.
    - **New collections** in `db.py:ensure_indexes`:
      - `db.channel_bindings` — unique index on `(channel_id, intent_filter)`.
      - `db.channel_events` — indexes on `(channel_id, ts)` and `(ts)`. Schema: `{id, channel_id, channel_kind, external_user_id, session_id, binding_agent, binding_filter, text_in[:500], text_out[:500], tokens_total, latency_ms, routed_to, ts}`.
    - **Seed file** `backend/data/channels.json` — 3 demo bindings on the `demo-webhook` channel: catch-all → Hermes, regex `\\b(joke|анекдот|meme|загадк|riddle)\\b` → JOKER, regex `\\b(сотрудник|команд|hr|onboard|hire|увольн)\\b` → `persona:hr_mentor`. Shows how a single channel can fan out by intent.
    - **Stable session** — `make_session_id(channel_id, external_user_id)` is deterministic, so a returning external user keeps conversational context across calls without out-of-band negotiation.
    - **Verified end-to-end** with 10 curl scenarios: list, wildcard→hermes, intent→joker, intent→persona:hr_mentor (1210-char data-driven response), upsert via API, valid HMAC, invalid HMAC→401, unknown channel→404, recent events feed, delete binding.
    - **What this unlocks** — Slack / WhatsApp / Email / CRM adapters become a 1-class port each (`channels/slack.py`, etc.) without touching `server.py` or any agent code. JOKER and Personas automatically gain external reach.

15. **v1.11.1 Voice quality upgrade — `gpt-4o-mini-tts` + tts-1-hd auto-fallback (2026-06-04):**
    - **Goal** — make the TTS voice noticeably "alive" without forcing the user to bring their own OpenAI key.
    - **`agents/voice.py` rewritten** — default model bumped from `tts-1` → `gpt-4o-mini-tts`. New `instructions` parameter (style/tone control) auto-picked per detected STT language:
      - `DEFAULT_INSTRUCTIONS_EN` — "calm, confident COO briefing a colleague; warm, measured, natural pauses, faint smile, no theatrics".
      - `DEFAULT_INSTRUCTIONS_RU` — same persona in Russian.
    - **Two-path provider** (unchanged design but updated TTS surface):
      - **Native OpenAI SDK** (when `OPENAI_API_KEY` is set): direct `client.audio.speech.create(model="gpt-4o-mini-tts", instructions=..., voice="onyx", ...)`. Full feature parity.
      - **Emergent proxy via litellm** (when only `EMERGENT_LLM_KEY` is set): bypasses the emergentintegrations `OpenAITextToSpeech` helper (which whitelists only tts-1/tts-1-hd and drops the `instructions` arg) and goes straight through `litellm.aspeech(model="openai/gpt-4o-mini-tts", api_base=<emergent proxy>, ...)`.
    - **Graceful auto-fallback** — if the provider rejects `gpt-4o-mini-tts` (HTTP 400 "Invalid model name"), `synthesize()` transparently retries with `tts-1-hd` and the caller never sees a 502.
    - **`/api/voice/converse` and `/api/voice/converse/stream`** — now pass the detected STT `language` as `lang` into `synthesize()` so the style instructions are auto-localised (RU prompt for RU speech, EN prompt for EN speech).
    - **Current production reality on Emergent platform:** confirmed via support ticket that the Emergent LLM proxy currently exposes only `tts-1` and `tts-1-hd`. The user's voice today therefore runs on **`tts-1-hd` automatically** (warmer + clearer than the previous `tts-1`) via the fallback. To unlock the full `gpt-4o-mini-tts` + style-instructions experience, add `OPENAI_API_KEY` to `backend/.env` — the native SDK path activates immediately, no other code changes needed.
    - **Verified** with 3 curl scenarios: EN + RU + explicit tts-1-hd — all return HTTP 200 with valid MP3 payloads (22–70 KB depending on text length).

16. **v1.11.2 Voice fully live — `gpt-4o-mini-tts` activated (2026-06-04):**
    - User provided their own `OPENAI_API_KEY`, written to `backend/.env`. On restart, `voice.py` log line confirmed `voice: native OpenAI SDK (key=OPENAI_API_KEY)` — the Emergent proxy fallback is no longer in use.
    - The voice on the landing now runs on **OpenAI `gpt-4o-mini-tts` + onyx + auto style-instructions** (RU/EN switched by Whisper-detected language). Verified with 2 curl scenarios: 161 KB MP3 for ~155 EN chars, 171 KB for ~135 RU chars (HD-rate output with natural intonation pauses baked in).
    - STT (Whisper-1) and rest of LLM stack (DeepSeek-V3 via OpenRouter) untouched. Only TTS billing now routes to the user's OpenAI account.

17. **v1.12 Onboarding survey + Hermes brief (2026-06-04):**
    - **Goal** — every "Connect / Подключить" tariff CTA now opens a 7-question intake before the user pays. Survey answers are sent to DeepSeek and Hermes responds with a personalised 4-block reply ("what we saw / who'll work with you / what changes in 30 days / next step"). A 3-digit access code (`888`) unlocks free pilot access without payment.
    - **Backend `agents/onboarding.py`** (new, 350+ LOC) — fully self-contained:
      - `INDUSTRY_TEMPLATES`, `PROFESSIONS`, `TOOL_INTEGRATIONS`, `URGENCY_CTAS`, `INSIGHTS` static tables (RU+EN).
      - `get_insight(qid, answer, lang)` — hybrid 4c per user choice: static matrix first, DeepSeek fallback for unmapped combos (max 80 tokens, source flagged as `static`/`llm`/`fallback`).
      - `build_brief(profile)` — deterministic mapping pain → profession (Sales rep / Operations director / Marketer / Bookkeeper / Legal counsel / Analyst / Coordinator), tools → integration plan, urgency → CTA copy.
      - `generate_hermes_reply(profile, brief, lang)` — DeepSeek with strict JSON schema (`intro / block1_understood / block2_team[] / block3_in_30_days[] / block4_cta`), schema-validated, with locale-matched fallback when LLM output cannot be parsed.
      - `verify_access_code` / `consume_access_code` with `db.access_codes` collection seeded at startup with `888` (`Pilot 2026`, max_uses=10 000).
      - `funnel_stats(days)` aggregating `client_profiles` for an Ops dashboard widget.
    - **New endpoints** (`server.py`):
      - `POST /api/onboarding/insight` — per-answer "💡 ДЛЯ ВАС" line.
      - `POST /api/onboarding/verify-code` — read-only 3-digit code check.
      - `POST /api/onboarding/profiles` — persist survey + consume code if present, returns `{profile_id, test_access}`.
      - `GET  /api/onboarding/profiles/{id}` — read for admin / Ops.
      - `POST /api/onboarding/brief/{id}` — build brief + generate Hermes 4-block reply, persisted back into the profile.
      - `GET  /api/onboarding/funnel?days=30` — counters for Ops.
    - **New collections** in `db.py`:
      - `client_profiles` — indexes on `(created_at)`, `(urgency, created_at)`, `phone`, `telegram`.
      - `access_codes` — unique index on `code`.
    - **Frontend `components/OnboardingFlow.jsx`** (new, 480+ LOC) — full-screen modal on mobile, centered card on desktop, state-machine `intro → q1..q7 → processing → reply`:
      - Single-select questions (industry, team_size, goal, urgency) with radio-like OptionPills.
      - Multi-select with `q.max` cap (pain primary+secondary, tools_current) — internal array stored under `<q.id>_arr` to avoid colliding with the flat `pain_primary` / `pain_secondary` keys that mirror it for the backend payload.
      - Yes/No "extras" pills (has_sales_team, has_marketer).
      - Contact form (name, phone, telegram) + 3-digit access-code input with live validation (green / red border + `CODE ACCEPTED · Pilot 2026` mark).
      - Processing screen with 4-step animated checklist (700 ms each) covering DeepSeek brief time.
      - Hermes reply screen renders all 4 blocks plus team-card grid (2-up on desktop, 1-up on mobile) and a CTA that switches to "Start free test" when `test_access === true`.
      - `localStorage` (`nxt8.onboarding.v1`) persists step/qIndex/answers — page reload mid-flow restores progress.
    - **HomeView wiring** — added module-level `goToCheckout()` redirect: instead of opening checkout directly it dispatches `CustomEvent('nxt8:open-onboarding', { detail: { planId } })`. The default export listens for this event and renders `<OnboardingFlow>`. Every existing tariff "Connect" button on the page (3D carousel cards, tariff cards section, pilot CTA) now flows through the survey without touching their individual props.
    - **i18n** — 70+ new keys under `onb.*` namespace, full EN + RU coverage of question titles, options, intro, processing checklist, reply block labels, error states.
    - **Verified** end-to-end:
      - Backend: 13/13 pytest checks (insights static + LLM RU fallback, code 888/123/ab, profile save with/without code, missing-field 400, brief generation in ~7-12 s, 404 on unknown profile).
      - Frontend: full happy-path through Q1-Q7 + screenshot confirms processing → reply with personalised DeepSeek output ("Alex, I hear you loud and clear — losing leads in ecommerce is like watching money walk out the door."), 2 team cards, 3×30d items, free-test CTA when code 888 supplied.
    - **What this unlocks commercially** — every paid tier now ships with an automatic qualification step that doubles as a delight moment. Hot leads (urgency=hot + code=888) bypass payment for the pilot, warm leads land in checkout with context already captured, cold leads still see a personalised brief which improves retention for the email digest.

18. **v1.13 Hermes Constitutional Graph v2 (2026-06-04):**
    - **Source of truth** — user-supplied `HERMES LANGGRAPH EXECUTION CONSTITUTION v1.0` (Hermes-first, deterministic flow, state-only comms, traceability).
    - **`agents/hermes_graph_v2.py`** (new, 500+ LOC) — faithful implementation of every constitutional article, lives in parallel with the legacy `nxt8_langgraph_ultra.py` so production traffic stays on the v1 graph until v2 is battle-tested.
    - **Constitutional state schema (§3)** implemented as a `TypedDict`-style nested dict: `task / intent / context / hermes / memory / agents / artifacts / tools / routing / status`. Every node writes ONLY state deltas. `status.history` accumulates a per-hop audit trail (§2.5).
    - **Six constitutional nodes** (§5) — `hermes_check`, `planner`, `executor`, `reviewer`, `fixer`, `hermes_validation`, plus a small `finalization` packer.
    - **Single LLM, multiple roles** — per user policy "всё через DeepSeek", every role runs DeepSeek-V3 with a role-specific system prompt. ~2× cheaper than four separate models, fully deterministic JSON outputs.
    - **Hermes Policy Gate (§4)** — first node, returns `{status: allowed|restricted|denied, allowed_agents, blocked_actions, constraints, required_checks, approval_required}`. DENY short-circuits the graph immediately (verified end-to-end with a malicious-task curl: graph stopped at 3 hops, no plan generated, no execution attempted).
    - **Deterministic routing (§2/§6)** — `routing.next` set explicitly by every node with `reason` text. The runtime is a tiny built-in loop honouring `routing.next` directly — LangGraph is not required at runtime (it remains available behind an `LANGGRAPH_OK` flag for future tracing UIs).
    - **Plan → Execute → Review → Fix loop** — Reviewer FAIL routes to Fixer (`routing.next=fixer`), Fixer increments `status.retry_count` and routes back to Executor. §9 retry cap = 3 → STOP and surface `error.code=retry_exhausted`.
    - **Hermes Validation (§5.5)** — final authority node after all plan steps are reviewed PASS. Approve → finalization. Reject → planner (replan) with its own retry counter.
    - **Hard hop-cap** `MAX_HOPS=25` protects against any pathological loop; `MAX_PLAN_STEPS=3` keeps a single synchronous run under Cloudflare's 100 s edge timeout (42 s observed for a 3-step plan).
    - **Endpoint** `POST /api/graph/v2/run` — body `{task, intent?, task_type?, context?}` → returns the FULL final `GraphState` so callers can inspect every layer of the audit trail and the packed `final_output`.
    - **Verified end-to-end** through three curl scenarios:
      1. **ALLOWED business task** — full flow runs (hermes_check → planner → 4×(executor→reviewer) → hermes_validation → finalization). Hermes approves, final output is coherent business prose.
      2. **DENIED malicious task** — graph short-circuits at hermes_check in 3 hops with `error.code=denied` and a clear reason. No plan, no execution, no leak.
      3. **Cloudflare 100s timing test** — 3-step plan completes in 42 s through the preview URL.
    - **What this unlocks** — every future Hermes feature can opt into the constitutional graph for stronger guarantees (audit log, policy gate, fix loop) WITHOUT touching the legacy supervisor flow. When the v2 graph proves itself, the legacy `nxt8_langgraph_ultra.py` can be retired and v2 becomes the canonical Hermes runtime.

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
| P1 | 5/15 hermes tools are stubs with mock=True | ✅ Fixed v1.7 (real LLM-backed) |
| P1 | No frontend UI for documents upload | ✅ Fixed v1.7 (DocumentsPanel) |
| P2 | Slack/WhatsApp/CRM/Email channel adapters | Deferred |
| P2 | Multi-tenant org_id scoping in all collections | Deferred |
| P2 | `agents/hermes.py` exceeds 700-line guideline (785 lines) | Refactor candidate — split comms tools out |
| P2 | Delete legacy shims `hermes_coo.py` + `hermes_max_tools_and_coo.py` once all references migrated | Refactor candidate |

## Next action items (P2+)

- **Channel adapters** (Slack / WhatsApp / CRM / Email) — feed real comm data into `generate_communication_summary`.
- **Multi-tenant `org_id` scoping** in all collections (tasks, requests, documents, roi_history, alerts).
- **Refactor** `agents/hermes.py` (785 lines) — split tool implementations into `agents/hermes_tools_comms.py` + DRY the LLM-JSON-parse helper into `_llm_json_tool()` wrapper.
- **Delete legacy shims** `hermes_coo.py` + `hermes_max_tools_and_coo.py` after migrating remaining imports.
- **VPS deployment validation** under `nxt8.pro` (kit already exists in `/app/deploy/`).
- **DocumentsPanel UX polish** — show severity-stats grid with zeros on first empty load; add explicit fetch-error banner instead of silent empty list.
- Hermes Gateway (`:8642`) optional native execution path.
