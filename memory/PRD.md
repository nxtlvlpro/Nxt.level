# NXT8 — Product Requirements Document

**Current version:** v1.18.6-p0-tenant-isolation-layer
**Last updated:** 2026-06-09 by E1

## What's new — v1.18.6 (2026-06-09)

**P0 tenant isolation infrastructure completed.** Добавлен единый
tenant-aware слой для MongoDB и проведён проход по критичным модулям.

- `core/db.py`
  - добавлен `TenantAwareCRUD`
  - добавлены request-context helpers (`set_request_company_context`, etc.)
  - `get_db()` теперь возвращает tenant-aware proxy
- `server.py`
  - добавлен middleware `inject_company_context`
  - критичные Mongo paths переведены на tenant-aware access
- `core/auth.py`
  - auth gate теперь выставляет `request.state.company_id` и `request.state.force_admin`
- Пропатчены критичные модули с Mongo access:
  - `agents/roi.py`
  - `agents/memory.py`
  - `agents/diagnostics.py`
  - `agents/documents.py`
  - `core/approval_gate.py`
  - `agents/hermes_evolution.py`
  - `agents/mentor.py`
  - `agents/market_radar.py`
  - `agents/skill_creator.py`
  - `agents/pulse.py`
  - `agents/digest.py`
  - `agents/personas.py`
  - `agents/onboarding.py`
- Обновлены multi-tenancy tests: `backend/tests/test_multi_tenancy.py`
- Независимая backend-валидация: **33/33 PASS**
- `pytest -q backend/tests/test_multi_tenancy.py`: **17/17 PASS**
- Ручные smoke logs подтвердили изоляцию:
  - tenant A/B tasks separated
  - documents separated
  - ROI snapshots separated
  - admin sees all

## What's new — v1.18.5 (2026-06-09)

**Phase 2 almost complete:** переведена последняя subordinate persona —
`project_coord`. Теперь через skills-based `nxt8_graph` работают все 7
подчинённых Hermes.

- Добавлен skill-файл `backend/skills/project_coord.md`
- `SKILL_ROUTED_PERSONAS` теперь включает 7 persona:
  - `hr_mentor`, `analyst`, `client_manager`, `bookkeeper`, `marketer`, `compliance`, `project_coord`
- Подтверждён tool-loop для `project_coord`:
  - `create_cross_department_bridge`
- Plan-gate сохранён: `project_coord` доступен только на `headquarters`
- Hermes сознательно НЕ переводился и остаётся отдельным migration-track.

## What's new — v1.18.4 (2026-06-09)

**Phase 2 expanded further:** в skill-based путь через `nxt8_graph` переведены
ещё три persona: `bookkeeper`, `marketer`, `compliance`.

- Добавлены skill-файлы:
  - `backend/skills/bookkeeper.md`
  - `backend/skills/marketer.md`
  - `backend/skills/compliance.md`
- `SKILL_ROUTED_PERSONAS` теперь включает 6 persona:
  - `hr_mentor`, `analyst`, `client_manager`, `bookkeeper`, `marketer`, `compliance`
- Подтверждено поведение:
  - `bookkeeper` корректно отвечает на основе контекста без обязательного tool-loop
  - `marketer` вызывает `suggest_next_best_action`
  - `compliance` сначала вызывает `mempalace_search`, а при пустом поиске запрашивает документ у пользователя
- Исправлен compliance-prompt: убран провоцирующий `ask_colleague`, чтобы
  при пустом поиске не было лишних invalid tool-calls.
- Plan-gate для всех трёх persona сохранён на уровне `operations+`.
- Нетронутыми остались legacy persona: как минимум `project_coord`, а также
  оставшиеся не мигрированные роли.

## What's new — v1.18.3 (2026-06-09)

**Phase 2 expanded:** в skill-based путь через `nxt8_graph` переведены ещё две
persona: `analyst` и `client_manager`.

- Добавлены новые skill-файлы:
  - `backend/skills/analyst.md`
  - `backend/skills/client_manager.md`
- В `backend/agents/personas.py` selective routing расширен до:
  - `hr_mentor`
  - `analyst`
  - `client_manager`
- Для skill-based persona сохранён старый persona-route contract и plan-gate.
- Добавлена общая сборка контекста для routed persona:
  - fetchers из legacy-конфигурации
  - company context block
  - audit в `persona_requests`
- Подтверждены реальные tool loops:
  - `analyst` → `evaluate_action_roi`
  - `client_manager` → `create_task`
- Остальные persona всё ещё работают через legacy path и не затронуты.

## What's new — v1.18.2 (2026-06-09)

**Phase 2 (safe scope B) completed for `hr_mentor`.** Только persona
`hr_mentor` переведена на новый `nxt8_graph` внутри compatibility shim
`backend/agents/personas.py`, без затрагивания остальных persona.

- `/api/personas/hr_mentor/chat` теперь использует `core/nxt8_graph.py`
  вместо legacy-пайплайна.
- Сохранён старый контракт ответа: `success`, `persona_id`,
  `persona_name`, `session_id`, `content`, `tool_traces`, `iterations`,
  `confidence`, `provider`, `mock`, `plan_id`, `tokens_total`.
- Plan-gate сохранён: `hr_mentor` остаётся доступным только на нужных
  тарифах (`team+`).
- Tool loop подтверждён и в persona-route: `award_skill_points` реально
  вызывается, `persona_requests.provider='nxt8_graph'`.
- Исправлен дефект с `pattern='unknown'`: теперь `pattern` явно
  передаётся в tool-call, а fallback-инференс в `agents/ai_mentor.py`
  нормализует `role_task_format` по `reason`, если LLM пропустил поле.
- Чистота данных подтверждена в `db.user_profiles`:
  `skill_points=10`, `patterns_used=['role_task_format']`,
  `last_pattern='role_task_format'`.
- Остальные persona по-прежнему идут через legacy-путь и не затронуты.

## What's new — v1.18.1 (2026-06-09)

**Scheduler multi-instance safety via Mongo lease-lock.** Закрыт риск
дублирования фоновых задач при горизонтальном масштабировании backend-а.
Вместо ошибочного пути через `MongoDBJobStore` добавлен отдельный
distributed lease-lock слой: `backend/core/scheduler_lock.py`.

- Новый owner-id формируется как `hostname:pid:uuid8`.
- `try_acquire(job_id, owner_id, lease_seconds)` использует атомарный
  `find_one_and_update(..., upsert=True)` + защиту от `DuplicateKeyError`.
- `release(job_id, owner_id)` удаляет lock строго по owner, чтобы не
  сбить чужой lease после takeover.
- В `core/scheduler.py` под эксклюзивный lock переведены только 3
  глобальные job: `pulse_tick` (30 мин), `daily_digest` (2 часа),
  `session_cleanup` (30 мин).
- `_refresh_tenants_cache` намеренно НЕ обёрнут в global lock, потому что
  это process-local cache и каждый инстанс должен обновлять его сам.
- В `core/db.py` добавлен индекс `scheduler_locks.locked_until`.
- Покрытие: `backend/tests/test_scheduler_lock.py` (6 тестов) + проверка
  регистрации `session_cleanup` job в `test_memory_m3_session_limits.py`.
- Ручной smoke с двумя конкурентными owner дал ожидаемый результат:
  `{'results': ['ok', None], 'calls': 1}`.

## What's new — v1.18 (2026-06-05)

**Memory Sprint · Fix M3 — Session size cap + TTL.** Закрыта последняя
дыра memory-sprint'а: `db.sessions.messages[]` ограничен 200 элементами
(защита от 16 MB BSON-лимита). Анонимные сессии получают BSON-Date
`expires_at = now + 90d`, на которое навешен MongoDB TTL-индекс; сессии
известных пользователей `expires_at` не получают (история хранится
вечно). При промоушене анонимной сессии в авторизованную `expires_at`
автоматически снимается через `$unset`. APScheduler ежедневно в 03:00
(`Europe/Moscow`) запускает `cleanup_expired_sessions` (24h sweeper для
анонимов), результаты пишутся в `db.scheduler_jobs`. Env-флаги:
`SESSION_CLEANUP_ENABLED`, `SESSION_CLEANUP_HOUR`. Покрытие — 7 тестов
в `/app/backend/tests/test_memory_m3_session_limits.py`.

## What's new — v1.17 (2026-06-04)

**Telegram-канал в 1 клик.** Клиенты привязывают свой Telegram к NXT8
deep-link'ом через бота `@nxt8ceo_bot` и управляют Hermes из мессенджера:
двусторонний чат, inline-кнопки Approve/Reject на pending-approvals,
push-уведомления о новых одобрениях. Подробности → `CHANGELOG.md` v1.10.0-telegram-channel.

## 🔒 LOCKED COMPONENTS

The following parts of the codebase are **explicitly frozen by the product owner**. Future agents MUST ask the user before changing any value listed here:

- **Header layout** — see `/app/frontend/src/config/header.locked.js` (logo height = `h-4`, left bleed = `-ml-6`, header `py-0`, shell top padding `pt-0`, home view padding `pt-0 pb-4`). The cropped PNG at `/app/frontend/public/nxt8-logo.png` is also part of the contract — it must remain tight-cropped (no transparent padding).

## What was built (in chronological order)

### v1.16 — Hermes as CEO + Real Agent-to-Agent Communication (2026-02-06)

**Why:** До этой версии Hermes был «COO-диспетчером», а подчинённые
агенты знали о нём только декларативно — реальных каналов
коммуникации между ними не было. Pipeline выглядел как 7 изолированных
chat-окон.

**Что сделано:**

1. **Hermes теперь CEO (не COO).** Изменены `manifests.py`,
   `agent_charter.py`, `hermes_directive.py`, `persona_prompts.py`,
   `personas.py`. Личность CEO: воля, профит-инстинкт, поиск слабых
   мест, прямой характер. В каждом разговоре обязан искать минимум
   одну точку роста прибыли или слабость компании и фиксировать
   через `propose_improvement`.

2. **`agents/inter_agent.py`** — новый модуль, 3 настоящих
   инструмента межагентной коммуникации:
   - `delegate_to_agent(agent_id, task, context?)` — Hermes как CEO
     синхронно вызывает любого из 7 подчинённых через `run_persona`,
     получает их ответ, использует в финальном вердикте.
   - `escalate_to_hermes(reason, evidence?, urgency?, from_agent,
     question?)` — путь снизу вверх: любой подчинённый эскалирует
     ситуацию CEO, запись падает в `db.escalations`, Hermes
     синхронно выдаёт verdict, который возвращается эскалирующему.
   - `ask_colleague(from_agent, agent_id, question, context?)` —
     peer-to-peer Q&A между подчинёнными без участия Hermes
     (например, Bookkeeper спрашивает Marketer о ценовом контексте
     перед ROI-расчётом).

3. **Реестр HERMES_TOOLS расширен до 27** (было 24): три новых
   инструмента зарегистрированы в `agents/hermes.py`, и documented
   в системном промпте Hermes-а. Все 7 подчинённых получили
   `escalate_to_hermes` + `ask_colleague` в `allowed_tools` через
   автоматическую инжекцию в конце `PERSONAS`-словаря.

4. **Логирование диалогов.** Каждый межагентный вызов пишется в
   `db.agent_dialogues` (kind, from_agent, to_agent, topic, request,
   response, company_id, user_id, created_at). Эскалации
   дополнительно живут в `db.escalations` с собственным жизненным
   циклом (open → answered).

5. **Новые API:**
   - `GET /api/agents/dialogues?limit=&agent_id=`
   - `GET /api/agents/escalations?limit=&status=`

6. **UI:** В `AgentsView.jsx` добавлен раздел «Связь команды (CEO ↔
   агенты)» — список реальных межагентных событий с цветными бейджами
   (DELEGATE / ESCALATE / ASK) и модалкой деталей (тема, запрос,
   ответ, urgency, confidence). Полл каждые 15 сек.

7. **Регрессионный тест** `backend/tests/test_inter_agent.py` — 5
   проверок: tools registered, subordinates имеют новые caps, Hermes
   = CEO, delegate отвергает не-Hermes, ask_colleague отвергает
   self/hermes-as-target.

**Подтверждено живой проверкой:** Bookkeeper эскалировал
ROI-проблему → Hermes принял эскалацию → САМ делегировал Analyst и
Project Coord → собрал их ответы в финальный CEO-вердикт со
ссылками на работу подчинённых. Многоуровневая делегация работает
сквозь несколько LLM-вызовов.



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

19. **v1.13.1 DeepSeek direct API as primary LLM provider (2026-06-04):**
    - User supplied a paid DeepSeek API key (`sk-16a498275dc148f4b0566477a4a3149b`) and asked to switch the LLM stack from OpenRouter's free tier to direct DeepSeek.
    - **`backend/.env`** now carries `DEEPSEEK_API_KEY` alongside the existing `OPENROUTER_API_KEY`.
    - **`core/deepseek.py:_DeepSeekClient.__init__`** — provider order reversed: direct DeepSeek (`api.deepseek.com/v1`, model `deepseek-chat`) is now FIRST in the chain; OpenRouter (`openrouter.ai/api/v1`, `deepseek/deepseek-chat-v3-0324`) remains the automatic fallback if the direct API ever errors or hits a quota.
    - **`/api/health`** confirms the active provider after restart: `{deepseek.model: "deepseek-chat", mock_mode: false, active_provider: "deepseek_direct"}`.
    - **Latency win** — observed Hermes chat round-trip dropped from 8-15 s (OpenRouter `:free` rate-limited) to ~2.5 s on the direct API. Quality of the V3 model is identical.

20. **v1.13.2 Complexity-aware model routing (deepseek-chat ↔ deepseek-reasoner) (2026-06-04):**
    - **Goal** — cut LLM spend without losing quality on hard tasks. `deepseek-reasoner` (R1) is ~2× more expensive than `deepseek-chat` (V3), so it must be used surgically.
    - **`core/complexity_router.py`** (new) — stateless heuristic that inspects ONLY the user-role content of the outgoing messages (system prompts ignored, otherwise Hermes' big system block would inflate every score). Pattern matches against:
      - **Reasoner triggers** (RU+EN): `анализ/посчитай/докажи/оптимизируй/спланируй`, `analyze/compute/optimize/plan`, `trade-off/compare`, `strategy/архитектур/forecast`, math/percent tokens, debug/stack-trace, algorithm/complexity.
      - **Cheap triggers**: greetings, thanks, rephrase/translate/summarize, jokes.
      - Body length ≥ 1500 chars combined with ≥1 reasoning hit also escalates.
      - Two or more reasoner hits OR (one hit + long body) → `deepseek-reasoner`. Otherwise → `deepseek-chat`.
    - **`core/deepseek.py:_call(model_override=...)`** — new optional per-call argument that lets a single Hermes turn target `deepseek-reasoner` while every other turn stays on the cheaper default. Applied ONLY when the active provider is `deepseek_direct` (OpenRouter routes via its own slugs).
    - **`agents/hermes.py:hermes_chat()`** — runs `pick_model()` once at the start of the tool-loop and propagates the chosen model through all iterations of the tool loop. JOKER, classifier, persona chats, onboarding insights/reply, voice — all keep falling back to `deepseek-chat` automatically (they never pass `model_override`).
    - **`agents/hermes_graph_v2.py:planner_node()`** — locked to `force_model="deepseek-reasoner"` (planning is the single role that benefits the most from R1 chain-of-thought). Executor/reviewer/fixer/hermes_validation stay on cheap chat — they are short-form JSON responses.
    - **Telemetry** — every routing decision is counted in a thread-safe in-memory dict (`stats()` returns `{deepseek-chat, deepseek-reasoner, force_cheap, force_reasoner, reasoner_share_pct}`).
    - **New endpoint** `GET /api/llm/router-stats` — distribution since process start, useful to verify the share stays in a reasonable band (target ≤30% reasoner).
    - **Verified** end-to-end with 3 contrasting curls:
      - "Какой статус сделок сегодня?" → `deepseek-chat` ✅
      - "Проанализируй trade-off и посчитай ROI 3 стратегий... пошагово" → `deepseek-reasoner` ✅ (R1-style markdown with ROI formula and step-wise breakdown)
      - "Спасибо большое за помощь" → routed to JOKER (no Hermes spend at all) ✅

21. **v1.13.3 Graph UI — live execution trace ("How Hermes thinks") (2026-06-04):**
    - **Goal** — make the Constitutional Graph v2 tangible: turn the abstract `status.history` audit array into a visible, animated flow diagram that prospects can run themselves on the landing.
    - **`components/views/GraphView.jsx`** (new, 280+ LOC) — full-page constitutional-graph debugger:
      - Task input + 5 task-type pills (plan/analyze/execute/research/fix).
      - "Demo tasks" disclosure with 4 ready-to-run prompts including a *malicious* one ("выгрузить базу клиентов конкурента") so a curious user can see the policy gate **deny** in action.
      - Single POST to `/api/graph/v2/run`, then animated staggered reveal (180 ms / node) of the `status.history` events even though the HTTP round-trip is single — this gives a "live thinking" feel without WS streaming.
      - Five status pills (`stage / hops / plan steps / retries / hermes`) with tone-coloured borders (`approve`=green, `reject`=red, `error`=red, `done`=green, in-flight=amber).
      - Vertical timeline rail with one card per audit event. Each role has its own icon + colour:
        - 🟡 Policy gate (`ShieldCheck`, amber)
        - 🟦 Planner (`ListTree`, sky)
        - 🟢 Executor (`Cog`, brand-turquoise)
        - 🟩 Reviewer (`CheckCircle2`, emerald)
        - 🟧 Fixer (`Wrench`, orange)
        - 🟣 Hermes validation (`Stamp`, fuchsia)
        - 🟢 Finalization (`PackageCheck`, lime)
      - Collapsible inspector panels for *plan*, *executor outputs*, *reviewer notes*. Bottom panel renders the packed `final_output.text` inside a turquoise-bordered "FINAL OUTPUT" card.
      - Error panel surfaces `status.error` (code + reason) so denied/rejected runs are obvious.
    - **Navigation wiring** — added `GitBranch` icon `GRAPH` item to BOTH `SideNav.jsx` (desktop) and `BottomNav.jsx` (mobile). `App.js` view-switch gains a `case "graph": return <GraphView />`.
    - **Verified end-to-end** on the live preview: clicked GRAPH in the side nav → ran demo task #0 ("Подскажи 3 действия чтобы увеличить конверсию...") → graph traversed 8 hops, status went `done`, Hermes verdict `approve`, plan-steps 1, retries 0 — all rendered correctly with staggered animation. Final output box landed with rich markdown answer.
    - **What this unlocks commercially** — competitor AI products usually show only the *answer*. NXT8 now shows *how the answer was reasoned*, *who reviewed it*, and *that Hermes approved it before it left the system*. This is a strong differentiator for enterprise/CTO buyers and a literal demo crowd-pleaser.

22. **v1.14.0 Agent Constitution v1.0 — Manifests + Self-introspection (2026-02-06):**
    - **Motivation** — пользователь: "важно чтобы вся система слаженно работала, агенты четко понимали свою задачу. ключевые решения агентов должны обязательно проходить проверку перед внедрением".
    - **`agents/manifests.py`** (new, 450+ LOC) — единый источник истины для **15 паспортов** (8 персон + 7 системных нод графа + JOKER). Каждый паспорт содержит:
      - `specialty` — узкая специализация одной строкой
      - `expertise` — список конкретных методологий (Bloom's taxonomy для HR, LTV/CAC для Bookkeeper, GDPR/AI Act/152-ФЗ для Compliance, RACI/OKR/CPM для Project Coord, и т.д.)
      - `functions` / `must_not` — должностная и boundaries
      - `data_access` — read/write матрица по коллекциям MongoDB (`*` = wildcard для Hermes)
      - `reports_to` — иерархия подчинения (терминируется на `human_operator`)
      - `can_delegate_to` — кому можно делегировать (только Hermes имеет non-empty список — все остальные делегируют через него)
      - `escalates_when` — условия эскалации (ROI < -0.2 для Bookkeeper, severity=CRITICAL для Compliance, etc.)
      - `decision_authority` — `advisory` / `execute_with_approval` / `execute_autonomous`
    - **Approval Gate principle** — high-impact actions (`create_task`, `update_task`, `create_cross_department_bridge`, `mempalace_store`, `delegate_to`) автоматически требуют approval от Hermes для всех агентов кроме самого Hermes (`AUTHORITY_AUTONOMOUS`). Логика в `manifests.requires_approval()`.
    - **Self-introspection injection** — `render_manifest_for_prompt(agent_id)` рендерит компактный prompt-блок "## КТО ТЫ ЕСТЬ" со всеми разделами манифеста и инжектится в system_prompt каждой персоны (`personas.py:run_persona`) и каждой роли Constitutional Graph (`hermes_graph_v2.py:_llm_role_call(role_id=...)`). Агент **буквально читает свой паспорт** перед каждым ответом.
    - **Новые endpoints** в `server.py`:
      - `GET /api/agents/manifests` — все 15 манифестов + список high/low-impact actions + 3 уровня authority.
      - `GET /api/agents/{agent_id}/manifest` — один манифест + render_manifest_for_prompt() для отладки.
    - **`backend/tests/test_manifests.py`** (new) — 42 теста: required fields, валидный data_access, отсутствие циклов в reports_to, "только Hermes делегирует", "только Hermes автономен", requires_approval logic, can_read/can_write helpers, prompt-block содержит "КТО ТЫ ЕСТЬ" + "Approval Gate". **42/42 PASS**.
    - **Verified end-to-end** живыми LLM-запросами через `/api/personas/{id}/chat`:
      - Bookkeeper ("кому ты подчиняешься?") → корректно: "Подчиняюсь Hermes (COO-агент). Фреймворки: LTV/CAC/Payback, Cost decomposition, Hourly ROI… Нет права писать в roi_history".
      - HR-Mentor → корректно: "Bloom's taxonomy, 70-20-10, Lominger… не могу создавать задачи — только предлагаю".
      - Compliance → корректно: read-only, write только в `audit_log`, перечисляет GDPR/152-ФЗ/CCPA/AI Act/SOC 2.
      - Constitutional Graph v2 run после изменений: 8 hops, Hermes verdict=approve, final output coherent. Регрессии нет.
    - **What this unlocks** — каждый агент теперь "корпоративный сотрудник" с настоящей должностной, узкой экспертизой и понятным местом в иерархии. Это устраняет "галлюцинации компетенций" (когда LLM пытается ответить вне своей зоны) и **создаёт основу для следующего этапа** — реального Approval Gate (Этап 4: chain of command + delegation tool) и enforcement матрицы доступа в коде (Этап 3: access_guard).

23. **v1.14.1 Deep Experts + Region Awareness (2026-02-06):**
    - **Motivation** — пользователь: "агент юрист должен понимать законы региона где работает компания. агент рекламщик должен глубоко разбираться в самых лучших маркетинговых стратегиях и глубоко изучать мировые тенденции. поэтому нужно прокачать каждого на максимум возможностей".
    - **`agents/persona_prompts.py`** (new, 300+ LOC) — **world-class brief** для каждой из 8 персон, написанный как "найм senior-консультанта":
      - **Hermes** — McKinsey/BCG-уровневый COO: RACI/DACI decision tree, эскалация при confidence<0.7 или $5k+ сделках, 5-блочный формат ответа.
      - **HR-Mentor** — Bloom's taxonomy + 70-20-10 + Lominger 67 competencies + 5-уровневая NXT8 шкала, region-aware (ТК РФ vs EU WTD vs US at-will).
      - **Client Manager** — LTV/CAC/Payback + NPS/CSAT/CES + BANT/SPIN/MEDDIC + AIDA/Empathy-Bridge-Solution copywriting + SLA bands + region-aware каналы и holiday windows.
      - **Project Coord** — PMP/SAFe-уровень: RACI + OKR + CPM + dependency mapping + Agile ceremonies + risk register с probability×impact.
      - **Analyst** — FAANG data analyst: confidence intervals, correlation≠causation, attribution models (first/last/linear/time-decay/U-shaped), cohort retention, anomaly >3σ.
      - **Bookkeeper** — CFA-ориентация: Unit Economics (CAC/LTV/Payback >12), cost decomposition NXT8-specific (deepseek V3 vs R1, compute, escalation, storage), hourly ROI, anomaly detection.
      - **Marketer** — CMO уровень с Gary Vee × April Dunford × Andrew Chen mindset: JTBD + AIDA/PASTOR/PAS + 4P/7P/4C + PESO + Porter's 5 Forces + PESTEL + North Star Metric + ГЛОБАЛЬНЫЕ ТРЕНДЫ 2026 (AI-content automation, privacy-first ad-tech, short-form video, community-led growth, multi-modal search, creator economy, email renaissance).
      - **Compliance** — DLA Piper/Baker McKenzie senior associate: глубокое знание GDPR (Art. 6/7/17/33/35/44-49), 152-ФЗ (ст. 18 ч.5 локализация, ст. 22 РКН), AI Act (4 risk tiers), CCPA/CPRA, PIPL, LGPD, DPDP Act + методология анализа документа (тип → governing law → 7 категорий риска → severity matrix).
    - **`core/company_context.py`** (new) — единый source of truth о том, ГДЕ и В ЧЁМ работает компания. Хранится в `db.company_settings` (singleton по `company_id`). Поля: `region` (ISO-2), `country`, `industry`, `team_size`, `currency`, `primary_language`, `primary_channels`, `data_residency`. Auto-derives currency + channels из region.
    - **9 регионов** в `REGIONAL_REGULATIONS` map: RU (152-ФЗ, ТК РФ, ФЗ-38, ФЗ-54), EU (GDPR, AI Act, ePrivacy, DSA, DMA, NIS2), US (CCPA, HIPAA, SOX, FTC §5, GLBA, COPPA), UK, CN (PIPL), BR (LGPD), IN (DPDP), AE, SG + GLOBAL fallback.
    - **9 регионов** в `REGIONAL_MARKET_CONTEXT`: каждый со своей валютой и каналами (RU → Telegram/VK/Yandex/WhatsApp, БЕЗ Meta; CN → WeChat/Douyin/Weibo/Xiaohongshu/Baidu, БЕЗ Google/Meta; и т.д.).
    - **`render_company_block(settings)`** — компактный prompt-блок, который инжектится в **КАЖДЫЙ** persona system prompt перед ответом. Содержит регион, валюту, регуляции, каналы. Указание: "если ответ зависит от закона/тренда/валюты — ОБЯЗАТЕЛЬНО используй данные выше".
    - **Новые endpoints**:
      - `GET /api/company-settings?company_id=default` — текущий контекст + регуляции + prompt block.
      - `PUT /api/company-settings` — апдейт (auto-derives currency/каналы от region).
    - **`backend/tests/test_company_context.py`** (new) — 18 тестов: дефолтные поля, region→regs (RU→152-ФЗ, EU→GDPR, CN→PIPL, BR→LGPD, IN→DPDP), region→currency, render_company_block содержит правильные законы и не содержит чужие. **18/18 PASS**.
    - **Verified end-to-end** живыми LLM-проверками с переключением региона:
      - region=RU + Compliance "какие 3 закона?" → процитировал **152-ФЗ** с конкретными статьями (п.1 ст.9, ст.18 ч.5, ст.22), штрафы в **₽ (75k/300k)**, упомянул Роскомнадзор, ФЗ-38.
      - region=EU + Compliance тот же вопрос → переключился на **GDPR Art. 6/7/28/33/37**, ePrivacy, DPO Германии (BfDI), штрафы **20M EUR / 4% global turnover**.
      - region=EU + Marketer "3 канала на квартал" → **LinkedIn (€2-3k/мес) + Email**.
      - region=RU + Marketer тот же → **Telegram (50-100k ₽) + Yandex.Direct** (никакого Meta).
    - **Total tests passing**: 60/60 (42 manifests + 18 company_context).
    - **What this unlocks** — каждый агент стал **узким специалистом мирового класса с региональной адаптацией**. Compliance в Мюнхене и Compliance в Москве — буквально два разных юриста. Маркетолог адаптируется под локальный mix каналов. Это устраняет "general LLM advice" в пользу контекстно-релевантных решений и закрывает требование пользователя "каждый агент максимально прокачен по своей специальности".

24. **v1.14.2 NXT8 Charter — Anti-Hallucination + Proactive Business Value (2026-02-06):**
    - **Motivation** — пользователь: "первоочередная задача системы и каждого агента — использовать каждую возможность когда агент может улучшить работу компании, принести прибыль, помочь в структуре и данных. строгий запрет на выдумывает. лучше сказать не знаю или взять паузу на поиск ответа в интернете".
    - **`agents/agent_charter.py`** (new) — `CHARTER` константа с тремя обязательными принципами:
      1. **Проактивный поиск бизнес-ценности** — каждый ответ ищет revenue/economy/process/risk-reduction. Если запрос — простой факт, агент добавляет блок "💡 Возможность для бизнеса" с 1-3 идеями.
      2. **Строгий запрет на вымысел** — НИКОГДА не выдумывать факты/числа/даты/цитаты/законы/URL. При неуверенности агент должен (a) честно сказать "Не знаю", (b) вызвать `web_search`, или (c) попросить контекст у пользователя.
      3. **Источник для каждого факта** — пометки `(memory)`, `(doc: …)`, `(web: <url>)`, `(общие знания)`, `(контекст компании)`.
    - **`with_charter(prompt)`** helper и автоматический инжект CHARTER **ПЕРЕД** всеми остальными блоками во всех агентов: 8 персон (`personas.py:run_persona`), 7 системных нод Constitutional Graph (`hermes_graph_v2.py:_llm_role_call`), главный Hermes (`hermes.py:_system_prompt`).
    - **web_search + fetch_url для ВСЕХ персон** — раньше эти инструменты были только у Hermes. Теперь все 8 персон могут гуглить (DuckDuckGo via `ddgs`) и читать страницы (`trafilatura`). Добавлены в `allowed_tools` каждой персоны и в манифесты (через `LOW_IMPACT_ACTIONS` — не требует approval gate, безопасное действие).
    - **`backend/tests/test_charter.py`** (new) — 13 тестов: CHARTER содержит все 3 принципа + ключевые слова, `with_charter` корректно префиксит/возвращает CHARTER на пустом вводе, **все 8 персон имеют web_search/fetch_url в манифесте** (Hermes wildcard). **13/13 PASS**.
    - **Verified end-to-end** двумя жёсткими сценариями на живом DeepSeek:
      - **"Не знаю"-триггер**: Marketer спрошен "ровно какая цена Salesforce Pro?" → НЕ выдумал цифру. Ответ: "Я не знаю точную цену… могу выполнить web_search… или обратиться к Bookkeeper". Завершил блоком "💡 Возможность для бизнеса" (сравнить с AmoCRM/Bitrix24/HubSpot, "разница 30-50% в пользу российских").
      - **Реальный web_search**: Marketer спрошен про "тренды AI-маркетинга 2026" → реально вызвал `web_search` (5 hits, реальные URL thegutenberg.com, novasapienlabs.com), потом `fetch_url` для чтения статьи. Никаких выдуманных ссылок.
    - **Total tests**: 73/73 passing (42 manifests + 18 company_context + 13 charter).
    - **Что это даёт бизнесу** — устранена самая опасная категория ошибок LLM (галлюциногенные цены, законы, URLs). Каждый ответ либо подкреплён источником, либо честно помечен "не знаю + где искать". Каждый ответ обязательно ищет business value. Это превращает NXT8 из "умного болтуна" в **trustworthy AI workforce**, которому можно делегировать ответы клиентам и руководству.

25. **v1.15.0 Hermes Evolution Engine — Self-Development (2026-02-06):**
    - **Motivation** — пользователь предоставил Hermes Core Operating Directive (12 секций: единая точка управления, корп.память, контроль исполнения, самоулучшение, развитие конституции, развитие агентов, орг.аналитика, граф знаний, цикл улучшений, саморазвитие, evolution roadmap, главная метрика).
    - **`agents/hermes_directive.py`** (new) — DIRECTIVE константа из 12 секций, инжектится в `_system_prompt(hermes)` прямо после CHARTER. Hermes теперь буквально читает свою сверх-цель перед каждым ответом.
    - **`agents/hermes_evolution.py`** (new, 280+ LOC) — самообучающаяся механика:
      - `propose_improvement(area, description, expected_benefit?, business_impact?, priority?)` → `db.hermes_evolution_log`. Area: `capability/agent/integration/architecture/product/process/policy`. Priority: P0..P3.
      - `list_evolution_roadmap(area?, status?, limit?)` — читает журнал, группирует по area.
      - `approve_proposal(id, status)` — proposed → approved/rejected/done.
      - `propose_policy(title, scope, proposed_rule, justification?, severity?)` → `db.policy_proposals` (детекция отсутствующих правил, §5 Директивы).
      - `list_policy_proposals(status?, limit?)`.
      - `detect_automation_candidates(window?, min_count?)` — сканирует `db.requests`, находит повторяющиеся intent'ы. Возвращает recommendation: `ready_to_automate` / `improve_prompt_first` / `fix_provider_first` (на основе avg_confidence ≥0.75 и escalation_rate <0.20).
      - `hermes_self_assessment(window?)` — Hermes видит СВОИ метрики: avg_confidence, escalation_rate, mock_rate, top-5 intents, счётчики evolution journal по статусам, honest signals (⚠ если avg<0.7 или escalation>20% или mock>5%).
      - `_safe_int()` — устойчивый парсер: «"200"», 200, «"7d"» → fallback к default. Hermes часто передаёт временные строки.
    - **Все 7 tools зарегистрированы в `HERMES_TOOLS`** через тонкие `_t_*` wrappers. Tools doc дополнен (Hermes явно видит, что они существуют).
    - **Новые endpoints**:
      - `GET /api/hermes/evolution/roadmap?area=&status=&limit=` — журнал.
      - `GET /api/hermes/evolution/policies?status=&limit=` — предложенные правила.
      - `POST /api/hermes/evolution/approve` — approve/reject/done.
      - `GET /api/hermes/self-assessment?window=` — live KPI Hermes + сигналы.
    - **`backend/tests/test_hermes_evolution.py`** (new) — 9 тестов: DIRECTIVE содержит все 12 секций, 7 tools зарегистрированы, propose_improvement валидирует area+description, persist+approve flow, propose_policy валидирует rule, detect_automation_candidates shape, hermes_self_assessment shape. **9/9 PASS** (с MONGO_URL из .env).
    - **Verified end-to-end** живой LLM-проверкой:
      - `/api/hermes/self-assessment` → реальный отчёт: 125 scanned, escalation_rate=49% (⚠ выше 20%), mock_rate=6% (⚠ нестабилен) → Hermes видит свои проблемы.
      - Запрос "вызови self-assessment + propose 2 improvements + list roadmap" → Hermes реально вызвал 4 tools подряд:
        - `hermes_self_assessment` → ok
        - `propose_improvement(area=process)` → "Автоматизировать еженедельный дайджест" P1 (экономия 2ч/нед)
        - `propose_improvement(area=integration)` → "Google Calendar / Outlook integration" P2 (снижение пропущенных дедлайнов на 20%)
        - `list_evolution_roadmap` → roadmap прочитан
      - Финальный ответ Hermes — структурированное резюме с пометкой "✅ Записал в Evolution Roadmap: …" как требует §Правило вызова Директивы.
    - **`GET /api/hermes/evolution/roadmap`** показывает 4 записи в 3 категориях (integration/process/capability) — живой роадмап.
    - **Total tests**: 82/82 (42 manifests + 18 company_context + 13 charter + 9 evolution).
    - **What this unlocks** — Hermes теперь **самообучающийся CEO**: каждый ответ может содержать запись в Evolution Journal. Со временем (после N пользовательских сессий) у компании будет реальный backlog улучшений NXT8 с приоритетами, бизнес-импактом и категориями. Это **первая в индустрии реализация саморазвивающегося AI-COO**, который письменно ведёт журнал собственного развития, открытый для человеческого approval.

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


---

## v1.16.0 — Hermes Operating Architecture (Phase 1, 2026-02-06)

User-supplied spec: "NXT8 Hermes LangGraph Operating Architecture" — a 10-node continuous StateGraph that turns Hermes from a one-shot task executor into the company's always-on operating system. Cycle: **Observe → Understand → Validate → Reason → Route → Execute → Monitor → Learn → Improve → Evolve**.

### What ships in Phase 1
- **`backend/agents/hermes_os_graph.py`** — new 10-node graph, parallel to (NOT replacing) `hermes_graph_v2.py`.
  - All 10 nodes implemented as async DeepSeek-backed functions returning strict-JSON deltas.
  - Deterministic built-in runtime with `MAX_HOPS=30` cap; every node crash is trapped and traced.
  - Best-effort writes to `db.knowledge_graph`, `db.institutional_memory`, `db.hermes_evolution_log` (in Learning / Improvement / Evolution nodes).
- **Endpoints** (all under `/api/hermes/os/`):
  - `POST /cycle` — run one full Observe→Evolve pass on a supplied event payload.
  - `GET  /cycle/{cycle_id}` — fetch the persisted cycle (full stages + history).
  - `GET  /cycles?limit=&source=` — list recent cycles (lightweight, for Ops dashboard).
  - `GET  /nodes` — canonical 10-node order (for the future UI).
- **New collections** wired into `core/db.py:ensure_indexes`:
  - `db.hermes_os_cycles` (unique on `cycle_id`, recency + source indexes)
  - `db.knowledge_graph` (source/target/relation + recency)
  - `db.institutional_memory` (scope + tags + recency)
- **User decisions captured (2026-02-06):**
  - Strategy: build OS graph as a NEW separate graph (v2 stays untouched).
  - Trigger model: hook on every incoming event (channel webhook, document upload, task creation) — Phase 3.
  - Knowledge Graph storage: MongoDB collection.

### Verified
End-to-end curl run on a real LLM cycle:
- `POST /api/hermes/os/cycle` with a Russian "new client message" event → returned `stage=done`, `hops=10`, `error=null`, and all 10 stage slices populated with non-trivial DeepSeek output (observation entities, validation flagged `needs_review` with policy citations, reasoning produced 3 options + risks, routing chose `mixed` mode, monitoring/learning/improvement/evolution all wrote sensible content).
- `GET /api/hermes/os/cycle/{id}` returns the persisted full doc with 10 stages + 12 history events.
- `GET /api/hermes/os/cycles` lists recent cycles.

### Next phases (still pending)
- **Phase 2** — flesh out the 4-layer Hermes memory (Short-Term LRU, Operational reads, Knowledge Graph queries, Institutional best-practice retrieval) + plug them into the Context Assembly node.
- **Phase 3** — wire automatic triggers from channel webhook / document upload / task creation hooks into `run_os_cycle`.
- **Phase 4** — `HermesOSView.jsx` frontend: 10-node graph visualisation, cycle stream, KG explorer.
- Plus the earlier P0/P1 backlog (Data Access Guard, Real Approval Gate, SSE for GraphView, real Stripe checkout, Agent Passport UI).

---

## v1.16.1 — Hermes Operating Architecture (Phase 2: 4-layer memory, 2026-02-06)

### What ships in Phase 2
- **`backend/core/hermes_memory.py`** — new module exposing all 4 layers behind a tiny, async-friendly façade:
  - **Layer 1 — Short-Term Memory (STM):** in-process `_LRUCache` (1024 items, 1h default TTL). `stm_remember_cycle()` is called at the end of every OS cycle and caches `(cycle_id, event_kind, summary, ts)` under both `recent_cycles:user:<id>` and `recent_cycles:company:<id>` keys (top 5 / top 10 buckets).
  - **Layer 2 — Operational Memory (OPS):** `ops_lookup(user_id, company_id, session_id)` reads `client_profiles`, `tasks` (`status != done`), `roi_history` and `requests` in parallel (`asyncio.gather`) with per-section best-effort error trapping. ObjectIds / datetimes scrubbed for JSON.
  - **Layer 3 — Knowledge Graph (KG):** `kg_neighbors(entities)` returns one-hop edges; `kg_add_edge(src, tgt, relation)` is **idempotent** via `update_one(..., upsert=True)` on the `(source, target, relation)` triple — repeated cycles never bloat the graph.
  - **Layer 4 — Institutional Memory (INST):** `inst_recall(tags, scope)` + `inst_record(text, tags, scope)` over `db.institutional_memory`.
  - **`assemble_context(event, observation)`** runs OPS + KG + INST in parallel + reads STM synchronously → returns a single normalised bundle with `totals` block.
- **`agents/hermes_os_graph.py` updates:**
  - `context_assembly_node` now calls `hmem.assemble_context()`. Its `routing.reason` exposes the layer counters (`stm=… ops=… kg=… inst=…`) — great for the future UI.
  - `learning_node` writes lessons via `hmem.inst_record()` and edges via `hmem.kg_add_edge()`. Also: **deterministic KG fallback** — even when the LLM returns empty `kg_edges`, every observed entity is wired to `company_id` (`observed:<event_kind>`) and `user_id` (`mentioned:<event_kind>`). The KG always grows on every cycle as long as Observation found at least one entity.
  - `run_os_cycle` final block calls `stm_remember_cycle()` so the next cycle for the same user/company sees the previous one in STM with zero Mongo hops.
- **New endpoints (read-only inspection):**
  - `GET /api/hermes/memory/stats` — counters across all 4 layers.
  - `GET /api/hermes/memory/short-term?user_id=&company_id=` — cached recent cycle summaries.
  - `GET /api/hermes/memory/knowledge-graph?entity=&limit=` — one-hop neighbours (or most-recent edges if no entity given).
  - `GET /api/hermes/memory/institutional?scope=&tag=&limit=` — lessons-learned feed.

### Verified
- Ran 3 sequential cycles for the same `user_id=client_leroy / company_id=nxt8_demo_corp`.
- Cycle 3 Context Assembly reported `stm=1 kg=10 inst=0 ops=0` — STM correctly surfaced Cycle 2's summary; KG returned Cycle 2's deterministic edges (`client_leroy → bundled_offer "requested"`, `nxt8_demo_corp → client_leroy "observed:new_client_message"`, …); OPS empty because the test user has no real client_profile / tasks rows yet (façade returns empty slice — graceful degradation working).
- `GET /api/hermes/memory/stats`: `stm.items=2`, `kg.edges_total=16`, `inst.lessons_total=2`, `ops.cycles_persisted=5`.
- `GET /api/hermes/memory/institutional` returned two real DeepSeek-extracted lessons with tags (`financial_guardrails`, `upsell`, `client_leroy`) and a Russian-business-context narrative — proof of end-to-end lesson capture.

### Pending next phases
- **Phase 3 (P0):** wire auto-triggers from `/api/channels/webhook/{channel_id}`, document upload, task creation hooks into `run_os_cycle`.
- **Phase 4 (P1):** `HermesOSView.jsx` — graph viz, cycle stream, KG explorer (consume the new `/memory/*` endpoints).
- Plus the earlier P0/P1 backlog (Data Access Guard, Real Approval Gate, SSE for GraphView, real Stripe checkout, Agent Passport UI).


---

## v1.16.2 — Hermes OS Live Mode (SSE streaming, 2026-02-06)

### What ships
- **`run_os_cycle(..., on_node=...)`** — the runtime now accepts an optional async callback that fires after every node. The callback receives `(node_name, state)` and may be sync or async; exceptions inside it are swallowed so streaming consumers can never break a cycle.
- **`POST /api/hermes/os/cycle/stream`** — new SSE endpoint. Returns `text/event-stream` with proxy-safe headers (`X-Accel-Buffering: no`, `Cache-Control: no-cache, no-transform`).
  - One `event: start` line at cycle entry.
  - One `event: <node_name>` line per completed node containing **only that node's slice** of state + `routing` info — not the full 30 KB state. Frontend can paint each node as it "lights up".
  - One terminal `event: done` line with `{cycle_id, stage, hops, error, finished_at}`.
- Implementation detail: an `asyncio.Queue` decouples the cycle task from the response generator; if the client disconnects mid-stream, the cycle task is cancelled in the `finally` block.

### Verified
End-to-end curl `-N -s -X POST .../hermes/os/cycle/stream` on a real Russian client inquiry → received **12 SSE events** (`start`, 10 nodes, `done`) over ~21 s, each carrying genuine DeepSeek output for that stage. The `learning` node saved 3 lessons + 10 KG edges visible in the stream payload. Final `done` event reported `stage=done, hops=10, error=null`.

### Pending next phases
- **Phase 3 (P0):** auto-trigger the cycle from channel webhook / document upload / task creation hooks.
- **Phase 4 (P1):** `HermesOSView.jsx` — frontend that consumes `/cycle/stream` and animates the 10-node graph live.
- Plus the earlier P0/P1 backlog (Data Access Guard, Real Approval Gate, real Stripe, Agent Passport UI, SSE for legacy `GraphView`).


---

## v1.16.3 — Chat paperclip / universal attachments (2026-02-06)

### What ships
- **`backend/agents/attachments.py`** — universal ingest module.
  - Classifies each upload by extension/mime into `document` | `image` | `table` | `other`.
  - Documents (`.pdf/.docx/.txt/.md`) → delegate to existing `documents.ingest_document` (Compliance LLM, severity, findings, MemPalace).
  - Images (`.png/.jpg/.jpeg/.webp/.gif`) → save to `/app/backend/uploads/attachments/` + call **OpenAI `gpt-4o-mini` Vision** via the existing `OPENAI_API_KEY` (1 short factual caption + 3–6 tags).
  - Other files → saved as-is.
  - Persists a single row per attachment in `db.attachments`.
  - `build_hermes_context_block(records)` → short system-message block Hermes sees on the next turn so it can reference uploads naturally.
- **Endpoints (server.py):**
  - `POST /api/attachments/upload` — multipart upload, returns chip-friendly record.
  - `GET  /api/attachments/{id}` — JSON metadata.
  - `GET  /api/attachments/{id}/raw` — original bytes (used by the UI for image previews).
- **`HermesChatRequest` extended with `attachment_ids: List[str]`**. The `/api/hermes/chat` handler now hydrates each attachment via the attachments module and prepends a system-message block describing them BEFORE the existing message list, so Hermes can reason about them on the same turn.
- **Frontend (`HomeView.jsx`):**
  - New Lucide `Paperclip` button to the left of the textarea (`data-testid=home-chat-attach-btn`).
  - Hidden `<input type=file multiple accept="image/*,.pdf,.docx,.txt,.md,.csv,.xlsx">`.
  - Selected files upload **immediately and in parallel** via `api.attachmentUpload()`. Each one renders as a chip above the textarea (`data-testid=home-chat-composer-chip`) with: icon (file/image/spinner/alert), filename (truncated), size, ✕ remove.
  - On **Send**, only `status="ready"` attachments are included; their IDs ride along in the `attachment_ids` field, and the user bubble shows their chips inline (images become 180px thumbnails linking to `/raw`, documents become small badges).
  - i18n keys added: `home.hermes.attach` (EN/RU).
- **`frontend/src/lib/api.js`** got `attachmentUpload(file, opts)` + `attachmentRawUrl(id)` helpers.

### Verified
End-to-end Playwright test:
1. Created `/tmp/test_doc.txt` with Russian contract text.
2. Loaded HomeView → confirmed paperclip + hidden file input mount.
3. Set the file via the hidden input → chip appears with spinner → flips to ready (Compliance LLM completes).
4. Sent message "Проанализируй риски этого договора одним предложением" with the chip attached.
5. Hermes replied: *"The contract carries critical risks: unlimited liability, no quality guarantees, and a unilateral termination clause — all of which could expose the company to significant financial and legal harm."* — exactly the three findings (liability=critical, termination=high, payment=medium) the Compliance LLM had extracted from the same document. End-to-end attachment context injection is live.

### Notes
- Per-attachment limit: 15 MB. Hermes sees max 8 attachments per turn (rest are silently dropped from the context block).
- Files persist on disk under `/app/backend/uploads/attachments/` — same lifecycle as the documents pipeline.
- Vision call uses the project's existing `OPENAI_API_KEY` (direct OpenAI SDK), matching the existing voice STT/TTS pattern.


---

## v1.16.4 — HermesOSView (live 10-node graph UI), 2026-02-06

### What ships
- **`frontend/src/components/views/HermesOSView.jsx`** — new view that consumes the `POST /api/hermes/os/cycle/stream` SSE endpoint built in v1.16.2.
  - **10-node grid** (`Eye / Compass / ShieldCheck / Brain / GitFork / Cpu / Radar / Lightbulb / Sparkles / Rocket`). Each card has 4 visual states: `idle / active / done / error`. Active node glows turquoise with a loader; completed nodes flip to emerald check; errored ones turn red.
  - **Live per-node summary text** extracted from the streamed slice (e.g. Observe shows `slice.summary`, Validate shows `STATUS — reason`, Routing shows `MODE → assignees`, Learn shows `N lessons, N KG edges`).
  - **3 preset events** for one-click triggering: `new_client_message`, `contract_review`, `internal_task`. "Run live" button starts the SSE stream.
  - **Memory stats strip** (Short-Term / Operational / Knowledge Graph / Institutional) refreshes after each run.
  - **Side panels with tabs**: Recent cycles list (clickable, shows id + kind + source + hops + time), Knowledge Graph table (source → relation → target), Institutional Memory feed (scope + tags + text).
- **`api.js` extension** — 6 new helpers: `hermesOsNodes`, `hermesOsCycles`, `hermesOsCycleGet`, `hermesOsMemoryStats`, `hermesOsMemoryKG`, `hermesOsMemoryInst`, plus the streaming `hermesOsStream(payload, onEvent)` which uses fetch + ReadableStream + a small SSE block parser (handles `event:` + multi-line `data:` per W3C spec).
- **Nav wiring** — added `Activity`-iconed `OS` entry between GRAPH and AGENTS in both `SideNav` and `BottomNav`. App router has `case "os" → <HermesOSView />`.

### Verified
End-to-end Playwright run on the deployed preview:
1. Clicked sidenav OS → view rendered with 11 testids found (1 grid + 10 nodes).
2. Clicked **Run live** → over ~25 s the stream painted nodes one by one: Observe lit, then Context (`stm=0 ops=0 kg=0 inst=0`), Validate flagged `NEEDS_REVIEW`, Reason produced a goal, Routing chose `SELF → hermes`, Execute logged the action, Monitor/Learn/Improve/Evolve completed with summaries.
3. Final screenshot shows all 10 nodes done (green checks) and the brand-new cycle `cac778c0` at the top of Recent Cycles, KG counter jumped from 26 → 33 edges.

### Remaining for the user's listed backlog
- Data Access Guard (backend enforcement of `manifests.data_access`)
- Real Approval Gate (`db.pending_approvals` + UI)
- Real Stripe checkout (replace static `nxt8.pro/checkout` link)
- Agent Passport UI (manifest modal in AgentsView)

These were not bundled into this step on purpose — the OS UI on its own is a meaningful unit to verify; the rest are independent and can be sequenced one-by-one.


---

## v1.16.5 — Real Stripe Checkout (replaces static link), 2026-02-06

### What ships
- **`backend/agents/payments.py`** — module wrapping the `emergentintegrations.payments.stripe.checkout.StripeCheckout` library.
  - Fixed `PLANS` catalogue defined backend-side ONLY (per security checklist): `personal $9`, `team $14`, `operations $19`, `headquarters $24`. Amount × quantity computed by backend; frontend cannot manipulate price.
  - `create_session()` builds `success_url=<origin>/payment/return?session_id={CHECKOUT_SESSION_ID}` and `cancel_url=<origin>/payment/cancel?plan=<id>` from the supplied `origin` (window.location.origin), creates the Stripe Checkout Session via the emergent Stripe proxy, persists a pending `db.payment_transactions` row, and returns `{url, session_id, transaction_id}`.
  - `get_status()` polls Stripe directly with `stripe.checkout.Session.retrieve()`, mirroring the library's `stripe.api_base = "https://integrations.emergentagent.com/stripe"` routing for the `sk_test_emergent` placeholder key. **Graceful degradation**: when the emergent Stripe proxy answers "No such checkout.session" for a retrieve call (known limitation — proxy currently forwards CREATE but not RETRIEVE), the endpoint returns the last persisted row state with `fallback: "stripe_retrieve_unavailable"` so the UI doesn't break. Webhook stays the authoritative path.
  - `handle_webhook()` calls the library's `handle_webhook` and persists `payment_status` updates.
  - `plan_catalog()` exposes the plans list for the frontend pricing cards.
- **New endpoints in `server.py`:**
  - `GET  /api/payments/plans`
  - `POST /api/payments/checkout/session` — accepts `{plan_id, quantity, origin, user_id?, company_id?}`.
  - `GET  /api/payments/checkout/status/{session_id}` — polled by the frontend.
  - `POST /api/webhook/stripe` — Stripe → us push (verified by the library).
- **New collection** `db.payment_transactions` with unique index on `session_id`.
- **Frontend:**
  - Replaced `CHECKOUT_BASE = "https://nxt8.pro/checkout"` in `HomeView.jsx` with `continueToCheckout(planId)` that calls `api.checkoutSessionCreate({plan_id, quantity:1, origin: window.location.origin})` and redirects the **same tab** to the returned Stripe-hosted `url`. Falls back to `nxt8:checkout-error` event if creation fails, so OnboardingFlow can show an inline error.
  - Added `PLAN_ID_MAP` to translate UI plan slugs (`pilot`) to backend IDs (`personal` for the lightest tier).
  - **`api.js`**: `checkoutPlans`, `checkoutSessionCreate`, `checkoutStatus` helpers.
  - **New view `PaymentReturnView.jsx`** wired into `App.js` via pathname check `startsWith("/payment/return")`. Renders **standalone** (no header / sidenav so the user is never confused mid-flow). Polls `/api/payments/checkout/status/<sid>` up to 12 attempts every 2.5 s; switches to `paid / expired / timeout / error` states with clear copy. When the polling hits the fallback path, surfaces "Live retrieval via Stripe proxy is delayed — relying on the webhook" so the user knows the system is OK.
- **Env** — `STRIPE_API_KEY=sk_test_emergent` appended to `/app/backend/.env`. No real Stripe account required for dev.

### Verified
- `POST /api/payments/checkout/session` with `{plan_id:"personal", quantity:3, origin: backend_url}` → 200 OK, returns `cs_test_a1ZAu0…` URL pointing at `checkout.stripe.com`. `db.payment_transactions` row created with `status=initiated, payment_status=pending, amount=27.0`.
- Browser test on the preview: navigated to `/payment/return?session_id=cs_test_...` → standalone view rendered (no main shell), spinner showed `Polling Stripe (attempt 5/12)`, fallback notice surfaced as expected.
- Browser test of the create-session flow from page console: `fetch('/api/payments/checkout/session', ...)` returned `{status:200, hasUrl:true, urlPrefix:"https://checkout.stripe.com/c/pay/cs_tes...", sessionId:"cs_test_..."}`. The home pricing CTAs (`home-tariff-cta-*` testids) now follow this path through the onboarding modal before redirecting.

### Notes
- **Known limitation**: Stripe retrieve via the emergent proxy returns "No such checkout.session" — the polling endpoint degrades gracefully and the webhook reconciles the final state. This is acceptable for dev / test-mode; in production a real Stripe key would make retrieve work directly.
- The user only needs to send their origin (`window.location.origin`); amounts are NEVER accepted from the client.


---

## v1.16.6 — HermesOSView connector lines (2026-02-06)

Added thin SVG connector lines between the 10 nodes in `HermesOSView.jsx`.

- **9 edges** drawn between consecutive nodes (Observe → Context → … → Evolve). Edge geometry is computed from each node's `getBoundingClientRect()` relative to the grid container, so the layout follows the responsive `grid-cols-2 / md:3 / xl:5` wrap automatically (horizontal lines within a row, diagonal exits across row breaks). Recomputed on mount, on `resize`, and after every `nodeState/activeNode` change.
- **Three edge states** with distinct styling:
  - `idle`: 1px dashed slate, dimmed arrow head.
  - `active` (target node currently running): 2px solid turquoise with `drop-shadow` glow + `@keyframes os-dash-flow` (`stroke-dashoffset: -20` over 0.8s linear infinite) — the dashes literally crawl along the line, showing direction of flow.
  - `done` (both endpoints completed): emerald, no dash, brighter arrow head.
- Three SVG `<marker>` definitions wire arrow heads to each kind. The SVG sits in a `pointer-events-none z-0` layer behind the cards (which are on `z-10`).
- `NodeCard` is now a `React.forwardRef` so the parent can attach refs for geometry queries without spreading additional props.
- Animation keyframes added to `App.css` (`@keyframes os-dash-flow`).

### Verified
Browser test: 9 `os-edge-*` elements present with valid coordinates (Route→Execute correctly diagonal: `x1=1228, x2=131, y1=62, y2=74`). During a live run the kinds array transitions correctly:
`[done, done, active, idle, idle, idle, idle, idle, idle]` (Hermes on Reason) →
`[done, done, done, done, done, done, done, done, done]` (cycle complete).


---

## v1.16.7 — Stripe direct key (no proxy), 2026-02-06

User supplied a real Stripe **test secret key** `sk_test_51TeSzT...`. Replaced `sk_test_emergent` in `/app/backend/.env`.

- **What changed in code:** none of the routing logic — `payments.get_status` only mirrors `stripe.api_base` to the emergent proxy when the key literally contains `sk_test_emergent`. With a real key it now hits Stripe directly.
- **Metadata handling hardened:** Stripe SDK's `StripeObject` for the `metadata` field can break a naive `dict(meta_raw)` call. Now we try `to_dict_recursive()` first, then iterate `.keys()`, then fall back to `dict()`. Also we **merge** the freshly-returned Stripe metadata with the one we stored locally at create-time, so the UI sees full `plan_id / plan_name / quantity / user_id / company_id / source` even if Stripe happens to return an empty bag on the first retrieve.
- **Docstring updated:** the graceful-degradation path is now documented as a true network-failure fallback, not a workaround for the emergent proxy.

### Verified
- `POST /api/payments/checkout/session` for `operations × 4` → `cs_test_a1vSTv6...` URL on real `checkout.stripe.com`, amount $76.
- `GET /api/payments/checkout/status/{sid}` returned `status=open / payment_status=unpaid / amount_total=7600 (cents)` with **full** metadata block (`plan_id, plan_name, quantity, user_id, company_id, source`). **No `fallback` field** — direct Stripe path is live.


---

## v1.17.0 — i18n: 10 languages + auto-detect + cookie banner (2026-02-06)

### Languages
Added 8 new locales to NXT8: **ES, FR, DE, PT, IT, ZH, JA, TR**. Total now: EN, RU + 8 = **10 languages**, ~340 keys per language ≈ 3.4k translated strings.

- **Translation method**: bulk-translated EN dictionary via DeepSeek (`/app/scripts/translate_i18n.py` + `merge_translations.py`) in batches of 40 keys with strict rules ("preserve {variables}", "keep NXT8/Hermes/AI/ROI/KPI/MemPalace verbatim", "match length & professional tone"). For UPPERCASE nav labels we asked for short uppercase equivalents in target language (e.g. ja "送信", de "SENDEN").
- **`translations.js`** grew from 800 lines to ~5100 lines, ~180 KB. Lint-clean.
- **`SUPPORTED_LANGS`** extended to all 10 codes.
- **`BurgerMenu` language switcher** lists all 10 with native names (English, Русский, Español, Français, Deutsch, Português, Italiano, 中文, 日本語, Türkçe).

### Auto-detect by browser locale
`LanguageContext.detectLang()` now:
1. honours stored override from `localStorage.nxt8.lang` (set when user manually picks a language);
2. otherwise walks `navigator.languages` (or `navigator.language`), takes BCP-47 → 2-letter code, returns the first match in `SUPPORTED_LANGS`;
3. falls back to `DEFAULT_LANG = "en"`.

Verified end-to-end via Playwright with `navigator.language` mocked to `es-ES, fr-FR, de-DE, ja-JP, zh-CN, tr-TR, it-IT, pt-BR`. Every locale rendered the full home view, chat welcome message, Send button, and cookie banner in the correct language without manual switching.

### Cookie banner
- **`components/CookieBanner.jsx`** — thin bottom plaque, non-blocking, two buttons: "Necessary only" / "Accept". Saves consent under `localStorage.nxt8.cookie-consent` with timestamp; never re-appears for that visitor. Forward-compatible — once you add analytics later, the `analytics` flag in stored consent is already there.
- **`components/views/LegalViews.jsx`** — standalone `/privacy` and `/terms` pages (no app shell). 5 privacy paragraphs + 4 ToS paragraphs, all `t()`-keyed for the 10 languages. Reference: GDPR, UK DPA, 152-ФЗ, mention Stripe / OpenAI / DeepSeek processors, privacy@nxt8.pro contact.
- New translation keys: `cookies.{body,policy_link,accept,necessary}`, `legal.{back,last_updated}`, `legal.privacy.{title,p1..p5}`, `legal.terms.{title,p1..p4}` — translated to all 10 languages via DeepSeek (`/app/scripts/add_cookies_legal_keys.py`).
- **App.js routing**: added `isPrivacyPage = startsWith("/privacy")`, `isTermsPage = startsWith("/terms")`, all rendered standalone (no header/sidenav).

### Voice
Voice already receives `language: lang` in `voiceConverseStream` / `hermesChat` calls. Whisper STT auto-handles all 10 added languages; OpenAI TTS voice ("alloy") speaks the response in the same language. No code change required — existing pipeline picks up the new `lang` value automatically.

### Verified (Playwright, 7 of 8 new languages)
For each locale, fresh browser context with localStorage cleared and `navigator.language` mocked to its BCP-47 code:

| Locale | Chat opener | Send button | Cookie banner |
|---|---|---|---|
| ja | こんにちは！私はHermes — NXT8のメインコーディネーターです | 送信 | アプリの動作維持に必要な機能ストレージ… |
| zh | 您好！我是 Hermes — NXT8 主协调员 | 发送 | 我们使用功能性存储来维持应用运行… |
| de | Hallo! Ich bin Hermes — der Hauptkoordinator von NXT8 | SENDEN | Wir verwenden funktionale Speicherung… |
| tr | Merhaba! Ben Hermes — ana NXT8 koordinatörü | GÖNDER | Uygulamanın çalışmasını sağlamak… |
| fr | Bonjour ! Je suis Hermes — le coordinateur principal de NXT8 | ENVOYER | Nous utilisons un stockage fonctionnel… |
| it | Ciao! Sono Hermes — il coordinatore principale di NXT8 | INVIA | Utilizziamo storage funzionale… |
| pt | Olá! Sou Hermes — o coordenador principal do NXT8 | ENVIAR | Usamos armazenamento funcional… |

ES separately verified with full home-page screenshot ("Sistema de IA operativa para la empresa moderna" + chat opener + cookie banner in Spanish).

### Notes
- Translations stored in `/tmp/translations_batch.json` (one-off, can be deleted).
- Helper scripts kept under `/app/scripts/` for re-runs when new keys are added.
- Arabic and Hindi intentionally skipped — RTL/Devanagari work is its own project.


---

## v1.18.0 — Memory Continuity (M1+M5) — 2026-06-04

### What was wrong (found via business simulation audit `/app/test_reports/business_simulation_audit.md`)

The 27-step real B2B simulation revealed memory was effectively broken for repeat visitors:
- Frontend hardcoded `user_id: "home_visitor"` for **all** visitors → system couldn't tell users apart.
- `HermesChatRequest` (the main chat endpoint used by the frontend) **silently ignored** the client's `session_id` and generated a fresh `sid = f"hermes_{uuid4()...}"` on every call. Sessions never accumulated.
- `db.sessions` had a 24h TTL purge that deleted **every** session indiscriminately.
- Result: any returning customer was treated as brand new — terrible for B2B demos.

### Fixes shipped (~1.5h)

**M1 — Persistent per-browser visitor identity**
- Frontend: `getOrCreateUserId()` in `HomeView.jsx` generates and stores `u_<base36-timestamp><rand>` in `localStorage["nxt8.user_id"]`. Used for all three call sites (`hermesChat`, `voiceConverseStream`, `attachmentUpload`). Pre-warmed in `useEffect` so it exists before the first action.
- Backend: `memory.append_message(session_id, role, content, user_id=...)` now stores `user_id` on the `db.sessions` document.
- Wired through `orchestrator.route`, `/api/chat/stream`, `/api/voice/converse`, `/api/voice/converse_stream`, `/api/hermes/chat`, `/api/hermes/ultra`.

**M5 — TTL exemption for known users**
- `cleanup_expired_sessions` now purges **only** sessions without a `user_id` field. Authenticated/persistent users keep their full chat history forever.

**Bonus fix — critical baseline bug**
- `HermesChatRequest` now accepts `session_id` (previously ignored). `/api/hermes/chat` honours it instead of generating a throw-away id, and echoes `session_id` in the response so the client can re-use it.
- This single change is what makes the rest of memory actually work end-to-end.

### Verification

- `db.sessions` document for `home_mpz3c08lgym9av` now contains both messages and `user_id: u_mpz3c09tsi6xc7ck`.
- Cross-turn continuity tested via curl: 2nd turn correctly references "Иван, Acme, SSO Okta, 50 пользователей, к пятнице" from turn 1.
- TTL cleanup test: 1 known-user session marked 48h old survived, 2 anonymous sessions of the same age were purged.

### What's still NOT done (M2/M3/M4/M6 deferred at user's request)

- Auto-extract facts from chat into `db.memories` (TF-IDF search currently only finds seed data).
- Auto-create `db.client_profiles` from first chat contact.
- Cross-device memory pull: `memory.search(user_id=X)` is not yet injected into `get_optimal_context`.
- Knowledge-graph edges still only written from Hermes OS Cycle, not from regular chat.

### Other findings from the audit (still open, prioritised for next pass)

P0 (production blockers):
- Tariff IDs mismatch: `manifests.py` uses `basic/simple/pro/enterprise`, `/api/payments/plans` returns `personal/team/operations/headquarters`. Tier-gating is broken.
- API contract drift: `/api/graph/v2/run` requires `task` (frontend sends `message`), `/api/payments/checkout/session` requires `origin`, `/api/cross-dept/coordinate` requires `query`. All return 422 silently.
- ROI dashboard hallucinates: fantom `human_escalation` cost of $14.58/h makes every hour show -100% ROI.
- `escalation_rate = 48.6%` (target 20%): pipeline-hooks thresholds in `_pipeline_hooks.py` are too aggressive — 100% of `knowledge`/`roi`/`mentor` intents get auto-escalated even at confidence > 0.8.
- Data Access Guard is **not enforced in code** (only in LLM-level manifest reading). Real middleware on `core/access_guard.py` still pending.
- Real Approval Gate (`db.pending_approvals` + executor + UI) still pending. `evolution_journal` has 21 proposed → 3 approved → 0 done.

P1:
- Hermes OS Cycle takes ~22s for a 10-node cycle (close to Cloudflare 30s timeout).
- 5.8% `mock_rate`: silent placeholder leaks into prod when DeepSeek/OpenRouter wobble. Should hard-fail to 503 instead.
- Alert dedup: 3 identical "warning: hourly ROI -100%" within 30s. Needs state-based dedup.
- Stripe webhook signature verification not audited.

### Files touched (M1+M5)
- `backend/agents/memory.py` — `append_message(user_id=...)`, `cleanup_expired_sessions` user_id-aware
- `backend/agents/orchestrator.py` — propagate user_id to append_message
- `backend/server.py` — `HermesChatRequest.session_id`, `/api/hermes/chat` reuses sid, propagate user_id everywhere
- `frontend/src/components/views/HomeView.jsx` — `getOrCreateUserId()`, pre-warm in useEffect, replace 3× hardcoded "home_visitor"
- `scripts/simulate_business.sh` — 27-step business simulation harness
- `test_reports/business_simulation_audit.md` — full audit report


---

## v1.19.0 — Onboarding v2 (9-question carousel) — 2026-06-04

### ТЗ (from user)
Rebuild the onboarding survey as a per-question carousel, 9 questions across
4 blocks, with a short Hermes insight after every answer, an analysing screen,
then a **5-block** personal Hermes reply with a dynamic CTA driven by urgency
(hot/warm/cold). Add a primary "Test NXT8" CTA on the home page.

### What shipped (~2h)

**Frontend — `OnboardingFlow.jsx` (full rewrite)**
- 9 questions: `industry`, `team_size`, `management_structure`,
  `communication_channels` (multi), `process_system`, `knowledge_storage`,
  `pain_points` (multi, max=3, FIFO eviction), `goal_90days`, `urgency`
- Carousel slide-in animation (`slideInRight` / `slideInLeft` keyframes)
- Progress bar `n/10 · n%`, block tag per question
- Insight banner with Hermes branding after every single-select
- Multi-select counter `0/3 … 3/3`
- Contact form: name + phone + telegram + **email** (optional)
- Submit gated on: `name.length >= 2 && (phone>=4 || telegram>=2)`
- Animated `ProcessingScreen` with 4 dynamic step messages
- `HermesReplyScreen` renders **5 blocks** + dynamic CTA by urgency

**Frontend — `HomeView.jsx`**
- New `<TestCTA>` section above HermesChat with primary hero CTA
  ("Test NXT8" / "Протестировать NXT8") — dispatches `nxt8:open-onboarding`
  event with `planId = ""` (free test mode)
- Onboarding modal `z-[90]` to clear cookie-banner `z-[80]`

**Backend — `agents/onboarding.py`**
- `save_profile`: accepts new fields (`management_structure`,
  `communication_channels`, `process_system`, `knowledge_storage`,
  `pain_points` list, `email`); keeps legacy mirrors (`pain_primary`,
  `pain_secondary`, `tools_current`) populated automatically for
  backwards-compat with older clients still on the v1 schema
- `build_brief`: picks professions from `pain_points[0..2]`, adds Ops
  anchor if missing; CTA driven by `URGENCY_CTAS`
- `PROFESSIONS`: extended with mappings for all 10 new pain points
  (owner_overloaded, no_visibility, manual_work, no_numbers, cant_scale,
  weak_finance_control, documents_overhead)
- `INSIGHTS`: added static entries for `management_structure`,
  `communication_channels`, `process_system`, `knowledge_storage`,
  `pain_points`, and refreshed `goal_90days` to new ТЗ keys
- `URGENCY_CTAS`: copy aligned to ТЗ
  - hot  → "Начать работу с Hermes" / "Start working with Hermes"
  - warm → "Получить персональное демо" / "Get a personalised demo"
  - cold → "Следить за развитием NXT8" / "Follow NXT8's progress"
- `REPLY_SCHEMA_HINT` + `_system_prompt_for_reply` + `_fallback_reply` +
  LLM validator: now require **5 blocks** — `intro`, `block1_understood`,
  `block2_team`, `block3_in_30_days`, `block4_potential`, `block5_cta`
- `max_tokens` bumped 700 → 900 for the extra block

**Backend — `server.py`**
- `OnboardingProfileRequest`: added v2 fields; old fields made optional
  (with empty defaults) so legacy clients still validate

**i18n — `translations.js`**
- Replaced the whole `onb.*` block in EN + RU with the new schema (~110 keys)
- Other 8 languages auto-fall-back to EN (LanguageContext supports it)
- Added `home.test_cta.{title,subtitle,button}` for the new hero CTA

### Test results
- **Backend**: 16/16 pytest pass — funnel, insight static + LLM RU fallback,
  verify-code (888/123/ab), profile save with/without code, missing/empty
  industry → 400/422, brief+hermes_reply with all 6 keys including
  `block4_potential` + `block5_cta`, profile persistence with brief, 404
  case, CTA-by-urgency parametrised for warm + cold, new 9-Q schema
  acceptance with all new fields persisting to Mongo.
- **Frontend**: 23/23 Playwright pass — full carousel, all 9 questions,
  multi-select FIFO cap, insight after each pick, processing screen with
  4 steps, final reply with 5 blocks, 3 team cards, hot-urgency CTA copy.
- **E2E curl**: `intro` ("Иван, я внимательно изучил вашу ситуацию."),
  block1_understood (full paragraph), 3 personalised professions in
  block2_team, 3 concrete 30-day items in block3, block4_potential
  ("у вас есть все предпосылки для масштабирования…"),
  block5_cta call-to-action — all populated by LLM.

### Files touched (v1.19.0)
- `backend/agents/onboarding.py` — schema v2 + PROFESSIONS x14 + INSIGHTS x5 + 5-block reply
- `backend/server.py` — `OnboardingProfileRequest` v2 fields
- `frontend/src/components/OnboardingFlow.jsx` — full rewrite (≈600 lines)
- `frontend/src/components/views/HomeView.jsx` — `<TestCTA>` hero section
- `frontend/src/i18n/translations.js` — EN + RU onboarding keys + home.test_cta.*

### Still open from prior audits (not blocking onboarding)
- Tariff IDs mismatch (manifests vs Stripe plans)
- API contract drift in `/api/graph/v2/run` (`task` vs `message`)
- ROI dashboard fantom `human_escalation` cost ($14.58/h)
- `escalation_rate` 49% — pipeline-hook thresholds too aggressive
- Data Access Guard not enforced in code
- Real Approval Gate (`db.pending_approvals` + executor + UI)
- Hermes OS Cycle 22s — close to Cloudflare 30s timeout
- 5.8% silent mock-leakage from LLM provider wobbles
- 4-Layer Memory M2/M3/M4/M6 (chat→memories, client_profile auto-create, cross-device search, KG from chat)


---

## v1.20.0 — Voice: Fish Audio как primary TTS — 2026-06-04

### User request
"меняем голос на фишаудио. этот оставим как запасной вариант.
91cbccc8152f4c23901857b0ada4715a"

### What shipped

**Backend — `agents/voice.py`**
- New `_fish_synthesize(text, lang)` — direct `httpx.AsyncClient` POST to
  `https://api.fish.audio/v1/tts` with `Authorization: Bearer`, `model: s1`
  header, JSON body `{text, format: mp3, mp3_bitrate: 128, latency: normal,
  chunk_length: 200}`, optional `reference_id` for custom voice models.
- `synthesize()` now calls Fish Audio first; on **any** failure (no key, 4xx/5xx,
  transport error, empty audio) it transparently falls back to the existing
  OpenAI / Emergent path. Caller never sees a 502 during the migration.
- `FISH_BUILTIN_VOICE` per-language map kept empty by default so Fish Audio's
  S1 model auto-detects the language. Override via `FISH_DEFAULT_VOICE_ID`
  env var once we pick a custom voice model from fish.audio's library.

**Backend — `.env`**
- `FISH_API_KEY=91cbccc8152f4c23901857b0ada4715a` (user-provided)
- `FISH_TTS_MODEL=s1`
- `FISH_DEFAULT_VOICE_ID=` (empty — Fish picks default voice for S1)

### Verification
- ✅ Valid Fish key → HTTP 200, ~95 KB MP3 audio, log:
  `TTS via Fish Audio: 95293 bytes`. Confirmed `content-type: audio/mpeg`.
- ✅ Invalid Fish key (simulated 401) → automatic OpenAI fallback, HTTP 200,
  ~37 KB MP3. Log: `Fish Audio HTTP 401: Invalid Token → falling back to OpenAI`.
- ✅ Restored Fish key → traffic returns to Fish Audio.

### Notes
- All four TTS-using endpoints (`/api/voice/tts`, `/api/voice/converse`,
  `/api/voice/converse_stream`, voice chunks in `voice_converse_stream`)
  automatically use the new primary path because they all call
  `voice_agent.synthesize()`.
- OpenAI `instructions` / persona-tone parameter still works on the fallback
  path but is **not** sent to Fish Audio. To replicate that on Fish, we can
  later create a custom voice model from sample recordings and store its
  `reference_id` in `FISH_DEFAULT_VOICE_ID`.

### Files touched
- `backend/agents/voice.py` (Fish primary + fallback wiring, ~80 new lines)
- `backend/.env` (3 new keys: `FISH_API_KEY`, `FISH_TTS_MODEL`, `FISH_DEFAULT_VOICE_ID`)


---

## v1.21.0 — Voice: Brad Pitt + Streaming + Cache — 2026-06-04

### User request
- Использовать модель Brad Pitt `d9247a00779649adbe7f4fdde2ac11c8`
- Настройки: деловой, профессиональный, живой, внимательный, задумчивый на паузах
- Streaming для быстрого ответа
- Экономия на повторяющихся фразах через кэш

### What shipped

**1. Brad Pitt voice model bound** — `.env`:
```
FISH_DEFAULT_VOICE_ID=d9247a00779649adbe7f4fdde2ac11c8
```
Applies automatically to every TTS call across all 4 voice endpoints.

**2. Prosody — "business, professional, lively, thoughtful pauses"**
- `_fish_payload()` now sets:
  - `latency: "balanced"` — favours TTFB (good for streaming chat replies)
  - `chunk_length: 200` — natural pause cadence
  - `normalize: true` — keeps punctuation pauses (the "thoughtful" feel)
  - `prosody: { speed: 0.95, volume: 0 }` — slightly slower than natural = "measured"

**3. Streaming endpoint — `/api/voice/tts/stream`**
- New `fish_synthesize_stream()` async generator in `voice.py` uses
  `httpx.AsyncClient.stream()` and `aiter_bytes(chunk_size=4096)` to relay
  MP3 chunks as Fish Audio produces them.
- Server endpoint wraps it in FastAPI `StreamingResponse` with
  `media_type="audio/mpeg"` and `X-Accel-Buffering: no` so Nginx/Cloudflare
  don't buffer.
- Graceful degradation: if Fish stream fails, the producer falls through
  to a single-chunk `voice_agent.synthesize()` call (OpenAI fallback path).
- **Measured TTFB**: 41 ms vs 1660 ms wall time for full audio
  (≈40× faster perceived start-of-speech).

**4. Repeating-phrase cache — `db.tts_cache`**
- `_cache_get` / `_cache_set` hash `(model + voice_id + normalised_text)`
  with SHA-256, store the audio as BSON Binary in Mongo.
- Only caches phrases ≤500 chars (short, repeatable lines like "ок",
  "минутку", "понял, делаю"). Long-form replies are not cached.
- TTL index on `created_at`: documents auto-expire after 30 days.
- Tracks `hits` count + `last_hit_at` for ROI analysis.
- **Measured speed-up**: 1221 ms → 171 ms (~7× faster, zero credits used).
- Cache is **per-voice** — switching `FISH_DEFAULT_VOICE_ID` invalidates
  cache automatically by design.

### Verification (curl, all 200 OK)
1. First TTS call: `Fish 200 → 46 KB MP3 → cached`, wall 1221 ms
2. Second identical call: `cache HIT → 46 KB MP3`, wall 171 ms (7× faster)
3. Streaming with new text: `audio/mpeg streamed`, TTFB 41 ms, 81 KB total
4. Mongo `tts_cache` collection: 1 doc, voice `d9247a00779649`, hits=1

### Files touched
- `backend/.env` — `FISH_DEFAULT_VOICE_ID=d9247a00779649adbe7f4fdde2ac11c8`
- `backend/agents/voice.py` — `_fish_payload()`, `_cache_get/_set`,
  `fish_synthesize_stream()`, prosody defaults (~150 new lines)
- `backend/server.py` — `/api/voice/tts/stream` endpoint (~40 new lines)

### Open follow-ups
- Frontend doesn't yet hit `/api/voice/tts/stream` — the existing voice
  flow still uses non-streaming `/api/voice/tts`. Wire it in when we want
  real perceived-latency wins for chat replies. (Trivial: swap fetch URL,
  feed `MediaSource` API for progressive playback.)
- Add a `?nocache=1` query param if we ever need to bust the cache
  manually (currently no business need — TTL handles staleness).


---

## v1.22.0 — JOKER benched (feature-flag off) — 2026-06-04

### User request
"убираем Джокера пока на скамейку запасных. вернём позже в проект"

### What shipped
- New env flag `JOKER_ENABLED=false` in `backend/.env`. All Joker code paths
  (`agents/joker.py`, `agents/classifier.py`, `db.joker_audit`,
  `MANIFESTS["joker"]`) are **kept intact** — just gated.
- `agents/hermes.py` — Joker pre-route block now wrapped in
  `if joker_enabled:`. When off, every turn (including jokes / small-talk /
  emoji-only) goes through the normal Hermes path.
- `agents/manifests.py` — `all_persona_ids()` and `list_all_manifests()`
  now hide the Joker manifest from public API consumers when
  `JOKER_ENABLED=false`. Frontend agent-list and passport modal won't
  show Joker.
- `/api/joker/stats` endpoint kept alive so historical stats still queryable.

### Verification
- `/api/agents/manifests` count: 15 → **14** (no joker entry).
- Joke phrase `"расскажи анекдот про программистов"` →
  `provider=deepseek_direct, routed_to=None` (Hermes, not sandbox).
- Flip `JOKER_ENABLED=true` → re-enables instantly: same phrase routes back
  to `provider=joker_sandbox, routed_to=joker`. **Zero code edits needed
  to return Joker** — just env flip + backend restart.
- Business request (ROI question) unaffected.

### Files touched
- `backend/.env` — `JOKER_ENABLED=false`
- `backend/agents/hermes.py` — gated pre-route block
- `backend/agents/manifests.py` — `all_persona_ids()` + `list_all_manifests()` filter


---

## v1.23.0 — Hermes Team Grounding (антигаллюцинация) — 2026-06-04

### Problem found
Hermes отвечал «Bookkeeper умеет: record_transaction, record_invoice,
reconcile_account, generate_tax_summary…» (16 функций). Реально в манифесте
Bookkeeper'а — **4 функции** (cost/revenue/ROI телеметрия AI), ничего из
бухгалтерского учёта нет. На допросе клиента про любого агента Hermes
**галлюцинировал реалистично, но неверно**. Это критичный риск доверия
на онбординге: клиент получит план "Подключим Bookkeeper для счетов" → в
продукте этого нет → пилот провалится.

### Root cause
В системном промпте Hermes был ТОЛЬКО его собственный manifest.
Манифесты остальных 7 агентов в контексте отсутствовали — Hermes отвечал
по общему здравому смыслу ("обычно агент с именем Bookkeeper делает X").

### What shipped

**1. `render_team_for_prompt()` в `agents/manifests.py`**
- Компактная сводка всех 8 агентов: name + role + specialty + 4-5 реальных
  функций + до 6 имён реальных инструментов + read/write коллекции +
  подчинение + authority level + tariff_tier.
- ~5 КБ / ~1.2 K токенов — пренебрежимо мало.
- Жирная инструкция в начале: «используй ТОЛЬКО этот блок, не выдумывай».

**2. Системный промпт Hermes — `agents/hermes.py`**
- `_system_prompt()` теперь включает `render_team_for_prompt('hermes', include_self=False)`
  после собственного manifest. Hermes видит все 7 коллег с реальными
  спеками каждый раз.

**3. Grounded onboarding — `agents/onboarding.py`**
- `generate_hermes_reply()` теперь передаёт team-roster как **второй**
  system message перед user_blob с инструкцией: "используй эти манифесты
  как единственный источник правды для block2_team — не выдумывай
  новых агентов или функций".
- Теперь `block2_team` в персональном Hermes-ответе использует **реальные
  имена** агентов (`client_manager`, `project_coord` и т.д.) с задачами,
  привязанными к их фактическим функциям, а не абстрактные роли.

### Verification (after fix)
- "Какие функции у Bookkeeper?" → **точно 4 функции** из манифеста
  (cost/revenue/ROI, разбивка cost, отрицательный ROI, сводка). Длина
  ответа упала с 4570 → 252 chars (нет воды).
- "К каким коллекциям имеет доступ Compliance?" → точные **read**:
  documents, memories, contradictions, alerts, requests, audit_log;
  **write**: только audit_log. 100% совпадает с манифестом.
- Онбординг RU edu-сегмент: `block2_team` теперь содержит
  «Менеджер по клиентам (client_manager)» и «Координатор проектов
  (project_coord)» — реальные id из MANIFESTS, не абстрактные роли.

### Files touched
- `backend/agents/manifests.py` — `render_team_for_prompt()` (~60 строк)
- `backend/agents/hermes.py` — `_system_prompt()` подключает team-roster
- `backend/agents/onboarding.py` — `generate_hermes_reply()` 2-й system
  message с team-grounding инструкцией


---

## v1.24.0 — Streaming TTS на фронте + расширенный голосовой лимит — 2026-06-04

### User asks
1. Подключить `/api/voice/tts/stream` к фронту через MediaSource.
2. Поднять голосовой лимит с 220→500 chars / 4 предложений.

### What shipped

**Backend — `server.py`**
- `VOICE_REPLY_MAX_CHARS`: 220 → **500**
- `VOICE_REPLY_MAX_SENTENCES`: 2 → **4**
- `VOICE_SYSTEM_HINT` переписан: вместо «максимум 2-3 предложения» теперь
  «по умолчанию 3-4 предложения, но если требует развёрнутого пояснения —
  отвечай столько, сколько нужно, не обрывай на полуслове».

**Frontend — новый `lib/playStreamedTts.js`**
- Прогрессивное воспроизведение через **MediaSource API**:
  fetch → `ReadableStream` → SourceBuffer chunks → `<audio>`. Звук
  начинается сразу после первого 4 KB-чанка Fish Audio (~87 ms TTFB
  в проде против ~1.6 s для полного MP3).
- Fallback на полный Blob → `<audio>` для браузеров без поддержки
  `audio/mpeg` в MediaSource (Firefox / старые билды).
- Возвращает контроллер с `stop()` для прерывания на середине.

**Frontend — `HomeView.jsx` HermesChat**
- Импорт `playStreamedTts`.
- Новые state: `speakingIdx` (индекс озвучиваемого сообщения),
  `speakCtlRef` (контроллер для остановки).
- Кнопка `🔊 play / ⏹ stop` под каждым assistant-сообщением
  (`data-testid="home-msg-speak-{i}"`). Toggle между play/stop.
- Cleanup при unmount компонента.

**i18n — EN+RU**
- `home.hermes.speak` = "play" / "озвучить"
- `home.hermes.speaking` = "stop" / "стоп"
- Остальные 8 языков fall-back на EN.

### Verification
- Backend: `VOICE_REPLY_MAX_CHARS=500`, `VOICE_REPLY_MAX_SENTENCES=4` подтверждено.
- Streaming endpoint: HTTP 200, **TTFB 87 ms**, content-type=audio/mpeg, 142 KB total.
- Frontend smoke: после ответа Hermes появляется `home-msg-speak-N`,
  клик переключает label `play` → `stop`, аудио играет, второй клик
  останавливает.
- ESLint clean, Python lint clean.

### Files touched
- `backend/server.py` — голосовые константы + VOICE_SYSTEM_HINT
- `frontend/src/lib/playStreamedTts.js` — новый модуль (~115 строк)
- `frontend/src/components/views/HomeView.jsx` — speak-button + state
- `frontend/src/i18n/translations.js` — 2 новых ключа в EN + RU


---

## v1.25.0 — Onboarding → Permanent Company Context — 2026-06-04

### User request
"Гермес должен глубоко обработать анкету, понять как именно будет строиться
дальнейшая работа всех отделов. ответ без воды и выдумки. данные сохраняются
в манифест компании и дальнейшая работа идёт с постоянным учётом этих данных.
от ответа Гермеса напрямую зависит захочет ли клиент подключиться."

### What shipped

**1. Deep-analysis prompt — `_system_prompt_for_reply()` в `agents/onboarding.py`**
- 7 жёстких правил: zero marketing fluff, ground in real manifests + literal
  survey answers, name the exact channels + pain points the client wrote,
  block2_team uses ONLY real NXT8 agent ids, block3 = 3-4 concrete department
  actions referencing real `db.*` collections, block4 = honest (no 10× claims),
  exact length per block.
- `max_tokens` 900 → **1400** (нужно для развёрнутых блоков по отделам)
- `temperature` 0.5 → **0.4** (меньше выдумок)

**2. Company manifest persistence — `agents/onboarding.py`**
- `persist_company_manifest(profile)` — записывает компактный manifest в
  новую коллекцию `db.company_manifests`, ключи: `tg:<username>`,
  `ph:<digits>`, `em:<email>`, `profile:<uuid>`. Любой из ключей найдёт
  компанию в будущем — устойчиво к смене устройства/сессии.
- `get_company_manifest(user_id)` — best-effort lookup по трём ключам.
- `render_company_manifest_block(manifest, lang)` — компактный 10-строчный
  блок для инъекции в system prompt (RU/EN).
- `save_profile` теперь зеркалит ответы в company_manifests прозрачно.

**3. Auto-load on every Hermes turn — `agents/hermes.py`**
- В `enhanced_chat()` сразу после базовых system messages вставляется
  `render_company_manifest_block()` если `get_company_manifest(user_id)`
  что-то нашёл. С инструкцией: "обязательный контекст для каждого ответа,
  не задавай повторно вопросы".

### Verification (live E2E)
Анкета: онлайн-школа, 6-20 чел, owner_only, WhatsApp+Instagram+email, хаос
в чатах, знания у сотрудников, pain=[leads_lost, owner_overloaded,
no_visibility], goal=free_my_time, urgency=hot, Мария / @maria_edu /
maria@school.io.

**Hermes reply** (`source: llm`):
- Intro: "Мария, я прочитал вашу анкету и вижу, что вы управляете
  образовательным бизнесом **в одиночку**, утопая в **WhatsApp, Instagram
  и email**" — буквально слова клиента
- Block 1: точный диагноз "заявки тонут в чатах, перегружены операционкой"
- Block 2: **4 РЕАЛЬНЫХ агента** — client_manager (для WhatsApp+Instagram
  лидов), project_coord (bridging), analyst (воронка), compliance
  (договоры с учениками — важно для edu!)
- Block 3: 4 действия с упоминанием `db.requests` — не общие фразы
- Block 4: ЧЕСТНО "путь небыстрый, но реалистичный" (нет 10× claims)
- Block 5: персональное "Готовы начать с фиксации заявок?"

**Persistence**: 3 ключа записаны в `db.company_manifests`
(`tg:maria_edu`, `ph:79991234567`, `em:maria@school.io`) с полным контекстом.

**Auto-load**: следующий чат с тем же user_id (`tg:maria_edu`) и
сообщением "С чего начнём прямо сегодня?" — Hermes сразу обращается по
имени "Мария", предлагает фиксы под её ситуацию (просроченные follow-up
по лидам, compliance для договоров), в конце "Мария, с какого действия
начнём?". Контекст не теряется между сессиями.

### Files touched
- `backend/agents/onboarding.py` — 7-rule deep prompt + manifest persist +
  lookup + render helpers (~140 строк)
- `backend/agents/hermes.py` — auto-inject company manifest в
  `enhanced_chat()` (~20 строк)


---

## v1.26.0 — Streaming LLM + Streaming TTS (real-time talk) — 2026-06-04

### Goal
Turn the chat from "write → wait → hear" into a real-time conversation.
First sentence audio should play while the LLM is still generating the
second sentence.

### What shipped

**1. Backend — `/api/hermes/talk` (new SSE endpoint)** in `server.py`
- Chains DeepSeek `chat_stream()` → `_flush_sentence()` buffer → Fish Audio
  `voice_agent.synthesize()` → base64-encoded MP3 frames over SSE.
- Frame format: `event: meta` / `event: text {chunk}` / `event: voice
  {i, audio_b64, text}` / `event: done {latency_ms, sentences}`.
- Grounded: pulls the company manifest via `get_company_manifest(user_id)`
  and the same Hermes system prompt + team roster as `/hermes/chat`, so
  spoken replies are as personalised as written ones.
- `_flush_sentence()` drains the token buffer at every sentence boundary
  (.!?…) and skips fragments shorter than 12 chars to avoid choppy TTS.

**2. Frontend — `lib/hermesTalk.js` (new client)**
- Parses interleaved SSE events from a single `fetch` + `getReader` loop.
- Queues incoming MP3 sentence-blobs into one HTMLAudioElement playlist,
  plays them gaplessly in order while text continues to stream.
- Emits 4 events: `onText`, `onVoice`, `onDone`, `onError`. Returns `stop()`
  to abort mid-stream and flush the audio queue.

**3. Frontend — HermesChat `talk-mode` toggle** in `HomeView.jsx`
- New `Volume2`-icon button next to the Send button — toggles talk mode.
- When ON: send() takes the streaming path, appends an empty assistant
  bubble and fills it token-by-token while sentences are spoken.
- When OFF: existing `/api/hermes/chat` path runs unchanged.

**4. i18n** — added `home.hermes.talk.button` and `home.hermes.talk.tooltip`
in EN + RU. Other 8 languages fall back to EN automatically.

### Verification (live E2E, RU "поможешь моему стартапу")
| Metric | Without streaming | With streaming chain |
|--------|------------------:|---------------------:|
| First text on screen | ~8.5 s | **1.5 s** (5.7× faster) |
| First audio in ears   | ~8.5 s | **3.6 s** (2.4× faster) |
| Sentences delivered   | 1 blob | 3 progressive blobs |
| Total latency         | ~8.5 s | 8.5 s (identical end-to-end, but UX-perceived 2-5× faster) |

Screenshot confirmed: TALK button highlighted bright cyan, user bubble
visible, Hermes bubble already shows first sentence (170+ chars) with a
`PLAY` chip below, and the "hermes is thinking…" indicator still active —
proving text + audio are streaming in parallel with the rest of the reply
still being generated.

### Files touched
- `backend/server.py` — `/api/hermes/talk` (~120 lines), `_flush_sentence`
- `frontend/src/lib/hermesTalk.js` — new SSE client (~110 lines)
- `frontend/src/components/views/HomeView.jsx` — talk-mode state, send()
  branch, toggle button (~70 lines diff)
- `frontend/src/i18n/translations.js` — 2 new keys in EN + RU

### Known small note
The first sentence still depends on Fish Audio synthesizing ~2 seconds
of MP3 before the audio chunk is sent (Fish does not yet stream within
a single sentence). If Fish ever exposes per-sentence partial streaming,
we can shave another ~1-1.5 s off the first-audio TTFB by piping its
internal chunks through directly.

