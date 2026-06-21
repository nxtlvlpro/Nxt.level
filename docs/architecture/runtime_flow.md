# NXT8 Runtime Flow

> Runtime flow inferred from static imports, FastAPI route composition, scheduler startup, and obvious entrypoint wiring. This is not a trace log; it is an architecture-level execution map.

## Primary backend boot path

1. `backend/server.py` loads `.env`, imports major agent/core modules, and creates the FastAPI app.
2. `lifespan()` runs startup routines:
   - `ensure_indexes()` from `core/db.py`
   - index/bootstrap helpers for auth, telegram, whatsapp, share, tour, onboarding
   - memory migration `core/migrations/m_tag_memory_with_company_id.py`
   - scheduler startup from `core/scheduler.py`
   - background ROI / cleanup task loop
3. `core/auth.install_auth_middleware(app)` gates `/api/*` requests except public routes.
4. `inject_company_context` middleware in `server.py` binds tenant context into `core/db.py` contextvars.
5. Requests are routed into API handlers inside `server.py`, which delegate into `agents/*`, `core/*`, and `channels/*`.

## Main request paths

### 1. FastAPI route layer
- File: `backend/server.py`
- Role: central composition root and oversized runtime coordinator (~4175 lines).
- Imports nearly all first-party runtime modules directly.

### 2. Authentication + tenant context
- `core/auth.py` resolves session from cookie / Bearer token and installs auth middleware.
- `core/db.py` stores request tenant context and wraps Mongo collections via `TenantAwareCollection` / `TenantAwareCRUD`.
- `core/company_context.py` is used from the persona layer for company-scoped behavior.

### 3. LLM orchestration
- `core/nxt8_graph.py` imports `agents/hermes.py`, `agents/prompt_policy_registry.py`, `core/access_guard.py`, `core/complexity_router.py`, and `core/deepseek.py`.
- `backend/nxt8_langgraph_ultra.py` is a second entrypoint into `agents/hermes_max_tools_and_coo.py`.
- `agents/hermes.py` is a central orchestrator hub with broad dependencies (directive, evolution, classifier, ROI, diagnostics, mempalace, etc.).

### 4. Persona runtime
- `agents/personas.py` is a **shim** that delegates into `agents/legacy/personas_legacy.py`.
- `agents/legacy/personas_legacy.py` remains the deep implementation hub for persona execution.
- Scheduler (`core/scheduler.py`) and inter-agent flows (`agents/inter_agent.py`) still depend on the shim + legacy chain.

### 5. Channels / external surfaces
- `channels/registry.py` imports `agents/hermes.py`, `agents/joker.py`, and `agents/personas.py`.
- `core/telegram_bot.py` and `core/whatsapp_bot.py` sit in a detected cycle with Hermes / approval / personas-related runtime modules.

### 6. Background flows
- `core/scheduler.py` imports `agents/digest.py`, `agents/memory.py`, `agents/personas.py`, `agents/pulse.py`, `core/db.py`, and `core/scheduler_lock.py`.
- This means scheduler-triggered persona work still traverses shim + legacy code paths.

## Runtime certainty notes

- **High confidence runtime:** files reachable from `backend/server.py` or `backend/nxt8_langgraph_ultra.py` via internal imports.
- **Medium confidence runtime:** files under `backend/` imported only by tests or only via legacy chains.
- **Low/no runtime confidence:** files not reachable from entrypoints, e.g. `core/memory_manager.py`, package `__init__.py` files.

## Detected shims

- `/app/backend/agents/hermes_graph_v2.py`
- `/app/backend/agents/hermes_os_graph.py`
- `/app/backend/agents/joker.py`
- `/app/backend/agents/orchestrator.py`
- `/app/backend/agents/personas.py`

## Detected legacy dependencies

- `/app/backend/agents/hermes_graph_v2.py` → `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
- `/app/backend/agents/hermes_os_graph.py` → `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
- `/app/backend/agents/joker.py` → `/app/backend/agents/legacy/joker_legacy.py`
- `/app/backend/agents/orchestrator.py` → `/app/backend/agents/legacy/orchestrator_legacy.py`
- `/app/backend/agents/personas.py` → `/app/backend/agents/legacy/personas_legacy.py`

## Detected likely non-runtime files inside backend runtime tree

- `/app/backend/agents/__init__.py`
- `/app/backend/agents/legacy/__init__.py`
- `/app/backend/core/__init__.py`
- `/app/backend/core/memory_manager.py`
- `/app/backend/core/migrations/__init__.py`

## Audit interpretation

1. The project has a **single dominant composition root**: `backend/server.py`.
2. Several modules named as current runtime entrypoints are in fact **shims over legacy implementations**.
3. The deepest runtime complexity is concentrated around Hermes/personas/approval/channel integration.
4. Static analysis detects one meaningful **cyclic import cluster** tying together Hermes, persona legacy, approval, and channel bots.
5. A small set of backend files appear structurally present but not runtime-reachable from known entrypoints.
