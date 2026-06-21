# Personas Migration Map

> Analysis-only audit for extracting the configuration layer from `backend/agents/legacy/personas_legacy.py` without changing NXT8 behavior.

## Executive Summary

- `personas.py` already owns the **primary execution path** for all 8 current personas via `nxt8_graph`, but it still depends on `personas_legacy.py` for configuration and fetcher registry.
- The highest-risk symbol is **`PERSONAS`**, because it is a shared mutable global and is **mutated at import time**.
- `PLANS`, `PLAN_ALIASES`, `get_plan`, and `_min_plan_for` are the cleanest extraction candidates.
- `_FETCHER_DISPATCH` and the six fetcher functions are separable, but they are still part of the **primary runtime path** because both `personas.py` and legacy `run_persona()` read them.
- The main migration hazard is not imports — it is **preserving import-time side effects** on `PERSONAS.system_prompt` and `PERSONAS.allowed_tools`.

## Symbol-by-symbol audit

### `PERSONAS`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:77`
2. **Кто импортирует:**
- `/app/backend/agents/personas.py:15` — `PERSONAS = _legacy.PERSONAS`
- `/app/backend/agents/inter_agent.py:111` — `from agents.personas import run_persona, PERSONAS`
- `/app/backend/agents/inter_agent.py:325` — `from agents.personas import run_persona, PERSONAS`
- `/app/backend/server.py:55` — `from agents import personas as personas_agent`
3. **Кто читает:**
- `/app/backend/agents/inter_agent.py:113` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:331` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:116` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:164` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:390` — `PERSONAS`
- `/app/backend/server.py:2792` — `personas_agent.PERSONAS`
- `/app/backend/tests/test_agent_prompt_safety_rules.py:19` — `PERSONAS`
- `/app/backend/tests/test_analyst_proactive_prompt.py:6` — `PERSONAS`
- `/app/backend/tests/test_inter_agent.py:25` — `PERSONAS`
- `/app/backend/tests/test_inter_agent.py:28` — `PERSONAS`
- `/app/backend/tests/test_inter_agent.py:38` — `PERSONAS`
- `/app/backend/tests/test_plan_unification.py:74` — `p.PERSONAS`
- `/app/backend/tests/test_prompt_policy_registry.py:21` — `PERSONAS`
- `/app/backend/tests/test_role_boundary_prompts.py:6` — `PERSONAS`
- `/app/backend/tests/test_role_boundary_prompts.py:14` — `PERSONAS`
4. **Кто вызывает:**
- _(none found)_
5. **Startup-only или Runtime:** **Startup + Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **YES — import-time mutation of `system_prompt` and `allowed_tools`**
8. **Уровень риска миграции:** **HIGH**
9. **Можно ли вынести независимо:** **NO**
10. **Предполагаемое новое расположение:** `config/personas.py`

**Rationale:** runtime config object; shared mutable global with import-time mutation.

### `PLANS`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:369`
2. **Кто импортирует:**
- `/app/backend/agents/personas.py:16` — `PLANS = _legacy.PLANS`
- `/app/backend/server.py:55` — `from agents import personas as personas_agent`
3. **Кто читает:**
- `/app/backend/server.py:2994` — `personas_agent.PLANS`
- `/app/backend/tests/test_plan_unification.py:31` — `p.PLANS`
- `/app/backend/tests/test_plan_unification.py:37` — `p.PLANS`
- `/app/backend/tests/test_plan_unification.py:57` — `p.PLANS`
4. **Кто вызывает:**
- _(none found)_
5. **Startup-only или Runtime:** **Startup + Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO direct side effect; value is derived from `_CANONICAL_PLANS` + `PLAN_ALIASES` at import time**
8. **Уровень риска миграции:** **MEDIUM**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `config/plans.py`

**Rationale:** derived public mapping with alias compatibility.

### `PLAN_ALIASES`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:349`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:361` — `pid = PLAN_ALIASES.get(pid, pid)`
- `/app/backend/agents/legacy/personas_legacy.py:371` — `{alias: _CANONICAL_PLANS[canon] for alias, canon in PLAN_ALIASES.items()}`
4. **Кто вызывает:**
- _(none found)_
5. **Startup-only или Runtime:** **Startup + Runtime**
6. **Primary path или Fallback path:** **Fallback path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `config/plans.py`

**Rationale:** pure alias table.

### `get_plan`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:375`
2. **Кто импортирует:**
- `/app/backend/agents/personas.py:18` — `get_plan = _legacy.get_plan`
- `/app/backend/server.py:55` — `from agents import personas as personas_agent`
3. **Кто читает:**
- `/app/backend/server.py:2989` — `personas_agent.get_plan`
- `/app/backend/tests/test_plan_unification.py:39` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:40` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:41` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:42` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:43` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:44` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:46` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:98` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:99` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:100` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:101` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:106` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:107` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:108` — `p.get_plan`
4. **Кто вызывает:**
- `/app/backend/server.py:2989` — `personas_agent.get_plan`
- `/app/backend/tests/test_plan_unification.py:39` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:40` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:41` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:42` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:43` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:44` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:46` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:98` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:99` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:100` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:101` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:106` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:107` — `p.get_plan`
- `/app/backend/tests/test_plan_unification.py:108` — `p.get_plan`
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `config/plans.py`

**Rationale:** pure resolver over plan tables.

### `list_personas`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:591`
2. **Кто импортирует:**
- `/app/backend/agents/personas.py:19` — `list_personas = _legacy.list_personas`
- `/app/backend/server.py:55` — `from agents import personas as personas_agent`
3. **Кто читает:**
- `/app/backend/server.py:2996` — `personas_agent.list_personas`
4. **Кто вызывает:**
- `/app/backend/server.py:2996` — `personas_agent.list_personas`
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **MEDIUM**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `config/personas.py`

**Rationale:** depends on PERSONAS + get_plan + _min_plan_for.

### `_min_plan_for`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:612`
2. **Кто импортирует:**
- `/app/backend/agents/personas.py:82` — `_legacy._min_plan_for(persona_id)`
3. **Кто читает:**
- `/app/backend/tests/test_plan_unification.py:65` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:66` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:67` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:68` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:69` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:70` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:71` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:72` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:75` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:92` — `p._min_plan_for`
4. **Кто вызывает:**
- `/app/backend/tests/test_plan_unification.py:65` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:66` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:67` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:68` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:69` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:70` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:71` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:72` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:75` — `p._min_plan_for`
- `/app/backend/tests/test_plan_unification.py:92` — `p._min_plan_for`
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `config/plans.py`

**Rationale:** pure lookup against canonical plans.

### `_FETCHER_DISPATCH`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:550`
2. **Кто импортирует:**
- `/app/backend/agents/personas.py:42` — `_legacy._FETCHER_DISPATCH.get(fetcher)`
3. **Кто читает:**
- `/app/backend/agents/personas.py:42` — `_legacy._FETCHER_DISPATCH.get(fetcher)`
- `/app/backend/agents/legacy/personas_legacy.py:657` — `fn = _FETCHER_DISPATCH.get(fetcher)`
4. **Кто вызывает:**
- _(none found)_
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **YES — registry assembled at import time**
8. **Уровень риска миграции:** **MEDIUM**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** registry of fetcher callables; referenced from shim + legacy path.

### `_fetch_mentor_overview`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:385`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:550` — `_FETCHER_DISPATCH[...] = _fetch_mentor_overview`
4. **Кто вызывает:**
- _(none found)_
- `backend/agents/legacy/personas_legacy.py:551` — registered into `_FETCHER_DISPATCH`
- `backend/agents/personas.py:42-49` — called indirectly through `_legacy._FETCHER_DISPATCH.get(fetcher)` in the current primary path
- `backend/agents/legacy/personas_legacy.py:657-663` — called indirectly through `_FETCHER_DISPATCH.get(fetcher)` in legacy fallback path
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** isolated fetcher function.

### `_fetch_diagnostics_summary`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:411`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:551` — `_FETCHER_DISPATCH[...] = _fetch_diagnostics_summary`
4. **Кто вызывает:**
- _(none found)_
- `backend/agents/legacy/personas_legacy.py:553` — registered into `_FETCHER_DISPATCH`
- `backend/agents/personas.py:42-49` — called indirectly through `_legacy._FETCHER_DISPATCH.get(fetcher)` in the current primary path
- `backend/agents/legacy/personas_legacy.py:657-663` — called indirectly through `_FETCHER_DISPATCH.get(fetcher)` in legacy fallback path
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** isolated fetcher function.

### `_fetch_roi_current`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:434`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:552` — `_FETCHER_DISPATCH[...] = _fetch_roi_current`
4. **Кто вызывает:**
- _(none found)_
- `backend/agents/legacy/personas_legacy.py:554` — registered into `_FETCHER_DISPATCH`
- `backend/agents/personas.py:42-49` — called indirectly through `_legacy._FETCHER_DISPATCH.get(fetcher)` in the current primary path
- `backend/agents/legacy/personas_legacy.py:657-663` — called indirectly through `_FETCHER_DISPATCH.get(fetcher)` in legacy fallback path
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** isolated fetcher function.

### `_fetch_roi_dashboard`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:453`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:553` — `_FETCHER_DISPATCH[...] = _fetch_roi_dashboard`
4. **Кто вызывает:**
- _(none found)_
- `backend/agents/legacy/personas_legacy.py:555` — registered into `_FETCHER_DISPATCH`
- `backend/agents/personas.py:42-49` — called indirectly through `_legacy._FETCHER_DISPATCH.get(fetcher)` in the current primary path
- `backend/agents/legacy/personas_legacy.py:657-663` — called indirectly through `_FETCHER_DISPATCH.get(fetcher)` in legacy fallback path
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** isolated fetcher function.

### `_fetch_market_intel`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:477`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:554` — `_FETCHER_DISPATCH[...] = _fetch_market_intel`
4. **Кто вызывает:**
- _(none found)_
- `backend/agents/legacy/personas_legacy.py:556` — registered into `_FETCHER_DISPATCH`
- `backend/agents/personas.py:42-49` — called indirectly through `_legacy._FETCHER_DISPATCH.get(fetcher)` in the current primary path
- `backend/agents/legacy/personas_legacy.py:657-663` — called indirectly through `_FETCHER_DISPATCH.get(fetcher)` in legacy fallback path
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **LOW**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** isolated fetcher function.

### `_fetch_compliance_context`

1. **Где определяется:** `backend/agents/legacy/personas_legacy.py:504`
2. **Кто импортирует:**
- _(none found)_
3. **Кто читает:**
- `/app/backend/agents/legacy/personas_legacy.py:555` — `_FETCHER_DISPATCH[...] = _fetch_compliance_context`
4. **Кто вызывает:**
- _(none found)_
- `backend/agents/legacy/personas_legacy.py:557` — registered into `_FETCHER_DISPATCH`
- `backend/agents/personas.py:42-49` — called indirectly through `_legacy._FETCHER_DISPATCH.get(fetcher)` in the current primary path
- `backend/agents/legacy/personas_legacy.py:657-663` — called indirectly through `_FETCHER_DISPATCH.get(fetcher)` in legacy fallback path
5. **Startup-only или Runtime:** **Runtime**
6. **Primary path или Fallback path:** **Primary path**
7. **Есть ли side effects:** **NO**
8. **Уровень риска миграции:** **MEDIUM**
9. **Можно ли вынести независимо:** **YES**
10. **Предполагаемое новое расположение:** `services/fetchers.py`

**Rationale:** fetches several stores and alerts/documents; broader coupling.

## PERSONAS object audit

### Где читается целиком

- `/app/backend/agents/inter_agent.py:113` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:331` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:116` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:164` — `PERSONAS`
- `/app/backend/agents/inter_agent.py:390` — `PERSONAS`
- `/app/backend/server.py:2792` — `personas_agent.PERSONAS`
- `/app/backend/tests/test_agent_prompt_safety_rules.py:19` — `PERSONAS`
- `/app/backend/tests/test_analyst_proactive_prompt.py:6` — `PERSONAS`
- `/app/backend/tests/test_inter_agent.py:25` — `PERSONAS`
- `/app/backend/tests/test_inter_agent.py:28` — `PERSONAS`
- `/app/backend/tests/test_inter_agent.py:38` — `PERSONAS`
- `/app/backend/tests/test_plan_unification.py:74` — `p.PERSONAS`
- `/app/backend/tests/test_prompt_policy_registry.py:21` — `PERSONAS`
- `/app/backend/tests/test_role_boundary_prompts.py:6` — `PERSONAS`
- `/app/backend/tests/test_role_boundary_prompts.py:14` — `PERSONAS`

### Где модифицируется

- `backend/agents/legacy/personas_legacy.py:289-295` — import-time mutation of `system_prompt` via `PERSONA_PROMPT_FRAGMENT_REGISTRY`
- `backend/agents/legacy/personas_legacy.py:301-308` — import-time mutation of `allowed_tools` for all subordinates

### Import-time mutation

- **Да.** `PERSONAS` создаётся как module-global dict and is mutated immediately during import.
- Mutation 1: append prompt fragments into `PERSONAS[_pid]["system_prompt"]` if fragment is not already present.
- Mutation 2: append `escalate_to_hermes` and `ask_colleague` into subordinate `allowed_tools`.

### Поля внутри PERSONAS

| Field | Где читается | Где модифицируется | Import-time mutation | allowed_tools change | system_prompt change | Notes |
|---|---|---|---|---|---|---|
| `id` | /app/backend/agents/attachments.py:169; /app/backend/agents/diagnostics.py:88; /app/backend/agents/diagnostics.py:89; /app/backend/agents/hermes_evolution.py:129 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/agents/legacy/personas_legacy.py:639; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28 | No | No | No | mostly static metadata; not a migration hotspot |
| `name` | /app/backend/agents/digest.py:244; /app/backend/agents/digest.py:275; /app/backend/agents/inter_agent.py:164; /app/backend/agents/inter_agent.py:390 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | No | No | No | runtime display + response metadata |
| `role` | /app/backend/agents/hermes.py:325; /app/backend/agents/hermes.py:1063; /app/backend/agents/hermes.py:1146; /app/backend/agents/legacy/orchestrator_legacy.py:110 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | No | No | No | runtime display + response metadata |
| `description` | /app/backend/agents/hermes.py:248; /app/backend/agents/hermes.py:525; /app/backend/agents/hermes_evolution.py:66; /app/backend/agents/legacy/personas_legacy.py:293 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | No | No | No | used in listing/live room metadata |
| `icon` | /app/backend/agents/legacy/personas_legacy.py:293; /app/backend/agents/legacy/personas_legacy.py:602; /app/backend/tests/test_agent_prompt_safety_rules.py:19; /app/backend/tests/test_prompt_policy_registry.py:21 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | No | No | No | listing/UI metadata |
| `color` | /app/backend/agents/legacy/personas_legacy.py:293; /app/backend/agents/legacy/personas_legacy.py:603; /app/backend/tests/test_agent_prompt_safety_rules.py:19; /app/backend/tests/test_prompt_policy_registry.py:21 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | No | No | No | listing/UI metadata |
| `allowed_tools` | /app/backend/agents/legacy/personas_legacy.py:293; /app/backend/agents/legacy/personas_legacy.py:604; /app/backend/agents/legacy/personas_legacy.py:702; /app/backend/agents/legacy/personas_legacy.py:790 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/agents/legacy/personas_legacy.py:304; /app/backend/agents/legacy/personas_legacy.py:308; /app/backend/tests/test_analyst_proactive_prompt.py:6 | Yes | Yes | No | runtime-critical allow-list |
| `system_prompt` | /app/backend/agents/legacy/personas_legacy.py:293; /app/backend/agents/legacy/personas_legacy.py:671; /app/backend/tests/test_agent_prompt_safety_rules.py:19; /app/backend/tests/test_prompt_policy_registry.py:21 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | Yes | No | Yes | runtime-critical prompt source |
| `data_fetchers` | /app/backend/agents/legacy/personas_legacy.py:293; /app/backend/agents/legacy/personas_legacy.py:644; /app/backend/agents/personas.py:36; /app/backend/tests/test_agent_prompt_safety_rules.py:19 | /app/backend/agents/legacy/personas_legacy.py:294; /app/backend/tests/test_analyst_proactive_prompt.py:6; /app/backend/tests/test_inter_agent.py:28; /app/backend/tests/test_role_boundary_prompts.py:6 | Indirect | No | No | runtime-critical fetcher routing |

### PERSONAS field facts

- `allowed_tools` is read in legacy `run_persona()` for tool allow-list enforcement and tool-doc rendering.
- `allowed_tools` is also mutated at import time for all non-Hermes personas.
- `system_prompt` is read in legacy `run_persona()` as fallback prompt source and mutated at import time with prompt fragments.
- `data_fetchers` is read in both the **primary path** (`personas.py::_build_skill_context_blocks`) and the **fallback path** (`personas_legacy.py::run_persona`).

## Import-Time Side Effects Audit

### 1. Prompt fragment injection

- Definition: `backend/agents/legacy/personas_legacy.py:289-295`
- Code path: iterate over `PERSONA_PROMPT_FRAGMENT_REGISTRY.items()`
- Effect: if fragment is absent, append it to `PERSONAS[_pid]["system_prompt"]`
- Type: **import-time mutation**
- Impact: changes effective prompt text before any persona runtime call

### 2. Inter-agent tool injection

- Definition: `backend/agents/legacy/personas_legacy.py:297-308`
- Constant introduced: `_INTER_AGENT_TOOLS_FOR_SUBORDINATES = ["escalate_to_hermes", "ask_colleague"]`
- Effect: append those tools into every subordinate persona `allowed_tools` list
- Type: **import-time mutation**
- Impact: broadens real runtime authority of subordinate personas

### 3. Plan table derivation

- Definition: `backend/agents/legacy/personas_legacy.py:322-372`
- Effect: build `_CANONICAL_PLANS`, `PLAN_ALIASES`, then derive public `PLANS` map with both canonical and legacy ids
- Type: import-time value construction (not mutation of external state)

### 4. Fetcher registry assembly

- Definition: `backend/agents/legacy/personas_legacy.py:550-558`
- Effect: create `_FETCHER_DISPATCH` map from string ids to live fetcher functions
- Includes a special placeholder entry: `"user_skill_profile": lambda: ""`
- Type: import-time registry construction

### 5. No other automatic registrations found

- No `importlib`-based self-registration found
- No signal bus / decorator registry found in this file
- Main import-time behavioral effects are confined to `PERSONAS` mutation and registry/table construction

## Safe extraction order by evidence

1. `PLAN_ALIASES` → safest
2. `_CANONICAL_PLANS` / `PLANS`
3. `get_plan` + `_min_plan_for`
4. `list_personas`
5. six fetcher functions
6. `_FETCHER_DISPATCH`
7. `PERSONAS` only after import-time side effects are preserved exactly

## Migration blockers to preserve behavior

- `PERSONAS` cannot be treated as static data today because import mutates it.
- `allowed_tools` mutation is behavior, not just config decoration.
- `system_prompt` mutation is behavior, not just static text storage.
- `data_fetchers` stay on the primary runtime path through `personas.py`.
- `PLANS` currently exposes both canonical and legacy aliases; extraction must preserve that compatibility shape.
