# NXT8 Phase 1 Extraction Order

> Planning-only artifact. No code changes, no extraction, no import rewiring, no refactor. This document defines a safe execution order for moving the configuration layer out of `backend/agents/legacy/personas_legacy.py` while preserving behavior.

## Global migration rules

- Every phase must be **deployable independently**.
- Every phase must have **its own verification**.
- Every phase must have **its own rollback**.
- No phase may silently change persona prompts, `allowed_tools`, or tariff gating semantics.
- Import-time behavior is part of runtime behavior for this module and must be treated as such.

## Symbol extraction table

| Symbol | Current Source | Target Module | Risk | Preconditions | Verification | Rollback |
|---|---|---|---|---|---|---|
| PLAN_ALIASES | backend/agents/legacy/personas_legacy.py | config/plans.py | LOW | Freeze canonical↔legacy alias mapping; confirm no hidden readers outside current audit. | Compare outputs of alias canonicalization for `basic/simple/pro/enterprise/hq/pilot` before vs after; re-run plan-related tests and `/api/personas?plan_id=*` snapshots. | Restore alias table to legacy file and point resolver back to original source. |
| PLANS | backend/agents/legacy/personas_legacy.py | config/plans.py | MEDIUM | Keep `_CANONICAL_PLANS` and `PLAN_ALIASES` semantics intact; preserve dual exposure of canonical + legacy keys. | Snapshot `PLANS.keys()` and `PLANS[plan_id]["personas"]` for all canonical/legacy ids; re-run `/api/personas` payload diff. | Revert public mapping to legacy module in one deploy if any key shape changes. |
| get_plan | backend/agents/legacy/personas_legacy.py | config/plans.py | LOW | Move only after plan tables are stable; preserve default fallback to `headquarters`. | Golden tests for `get_plan(None)` and all known aliases; verify tariff gate behavior on `/api/personas/{persona_id}/chat` remains unchanged. | Switch callers back to legacy resolver and redeploy. |
| _min_plan_for | backend/agents/legacy/personas_legacy.py | config/plans.py | LOW | Requires stable `_CANONICAL_PLANS` content; no persona coverage drift. | Compare cheapest-plan result for all 8 personas; re-run plan unification tests. | Return function to legacy module; no state migration required. |
| list_personas | backend/agents/legacy/personas_legacy.py | config/personas.py | MEDIUM | Requires stable `PERSONAS`, `get_plan`, `_min_plan_for`; payload shape must remain byte-equivalent. | Diff `/api/personas` JSON before/after for all plan ids; verify `available_on_plan`, `tools_count`, `min_plan`, ordering, icon/color fields. | Route listing logic back to legacy source immediately if payload diff appears. |
| fetcher functions | backend/agents/legacy/personas_legacy.py | services/fetchers.py | LOW→MEDIUM | Move pure fetchers first; preserve async signatures and current output text shape exactly. | For each fetcher, capture string output before/after against same DB state; verify primary path (`personas.py::_build_skill_context_blocks`) and fallback path (`legacy.run_persona`) both render identical context blocks. | Return function definitions to legacy file and restore registry bindings. |
| _FETCHER_DISPATCH | backend/agents/legacy/personas_legacy.py | services/fetchers.py | MEDIUM | Only after target fetcher functions exist and `user_skill_profile` placeholder behavior is preserved. | Verify dispatch keys set equality and callable binding identity for all fetchers; run both primary and fallback persona context assembly paths. | Restore registry dict in legacy file and repoint readers. |
| PERSONAS | backend/agents/legacy/personas_legacy.py | config/personas.py | HIGH | Must first externalize or reproduce import-time mutations deterministically: prompt fragment injection, subordinate `allowed_tools` injection, and any prompt override assumptions. Also requires stable fetcher and plan layers. | Deep verification: compare `PERSONAS` deep hash before/after import, compare `system_prompt` for all 8 personas, compare `allowed_tools` for all 8 personas, verify inter-agent behavior, `/api/personas`, live room metadata, and persona runtime success paths. | Single fastest rollback: move authoritative `PERSONAS` object back to legacy module and restore import-time mutation code there in one deploy. |

## Phase plan

### Phase 1 — Plan primitives

**Symbols:**
- `PLAN_ALIASES`
- `PLANS`
- `get_plan`
- `_min_plan_for`

**Why first:**
- Lowest behavior-coupling.
- No dependency on prompt mutation.
- Clear verification surface through `/api/personas` and plan tests.

**Deployability:**
- Deployable independently because these symbols are logically self-contained and feed stable read-only behavior.

**Verification:**
- Snapshot and diff:
  - `get_plan(None)`
  - `get_plan("basic"|"simple"|"pro"|"enterprise"|"hq"|"pilot")`
  - `PLANS.keys()`
  - each `PLANS[key]["personas"]`
- Re-run `/api/personas?plan_id=*` response diff.
- Re-run plan unification tests.

**Rollback:**
- Revert all plan symbol reads to legacy source and redeploy.

### Phase 2 — Persona listing surface

**Symbols:**
- `list_personas`

**Depends on:**
- Phase 1 complete and verified.
- `PERSONAS` remains authoritative in legacy source.

**Why separate:**
- Listing behavior is deployable on its own.
- It exercises plan logic + persona metadata without touching execution logic.

**Verification:**
- Compare `/api/personas` full JSON for all plan ids.
- Confirm unchanged values for: `id`, `name`, `role`, `description`, `icon`, `color`, `tools_count`, `available_on_plan`, `min_plan`.
- Confirm persona ordering remains identical.

**Rollback:**
- Point listing back to legacy `list_personas` and redeploy.

### Phase 3 — Fetcher layer

**Symbols:**
- `_fetch_mentor_overview`
- `_fetch_diagnostics_summary`
- `_fetch_roi_current`
- `_fetch_roi_dashboard`
- `_fetch_market_intel`
- `_fetch_compliance_context`
- `_FETCHER_DISPATCH`

**Depends on:**
- Phase 1–2 complete.
- `PERSONAS` still remains in legacy source.
- `data_fetchers` values unchanged.

**Why separate:**
- Fetchers are on the **primary runtime path** now via `personas.py::_build_skill_context_blocks`.
- They also remain on the fallback path via `legacy.run_persona`.
- This phase is deployable independently because it does not yet relocate `PERSONAS`.

**Verification:**
- For each fetcher, record output string against fixed DB state before/after.
- Verify dispatch keys set equality.
- Verify `personas.py` context-building output is unchanged for personas using fetchers:
  - `hr_mentor`
  - `analyst`
  - `bookkeeper`
  - `marketer`
  - `compliance`
- Verify fallback path still resolves fetchers identically.

**Rollback:**
- Restore fetcher definitions + `_FETCHER_DISPATCH` to legacy file and redeploy.

### Phase 4 — PERSONAS extraction

**Symbols:**
- `PERSONAS`

**Depends on:**
- Phase 1–3 complete and stable.
- Exact preservation of import-time side effects.
- Exact preservation of:
  - `system_prompt` final values
  - `allowed_tools` final values
  - `data_fetchers`
  - all 8 persona ids

**Why last:**
- This is the highest-risk symbol.
- It is mutable config with behavior encoded in import-time mutation.
- Moving it earlier would risk silent drift in prompts and tool authority.

**Verification:**
- Deep-compare final materialized `PERSONAS` object before/after import.
- For each persona verify unchanged:
  - `system_prompt`
  - `allowed_tools`
  - `data_fetchers`
  - `name/role/description/icon/color`
- Re-run:
  - `/api/personas`
  - `/api/personas/{persona_id}/chat` for representative personas
  - inter-agent peer flow using `PERSONAS` metadata
  - tests checking prompt safety / role boundaries / prompt registry

**Rollback:**
- Restore authoritative `PERSONAS` object and both import-time mutation loops to legacy source in one deploy.

## BLOCKERS

### 1. Import-time mutation on `PERSONAS`
- `backend/agents/legacy/personas_legacy.py:289-295` mutates `system_prompt` during import.
- `backend/agents/legacy/personas_legacy.py:301-308` mutates `allowed_tools` during import.
- Because this happens automatically, `PERSONAS` is not currently plain static config.

### 2. `system_prompt` injection is behavior, not decoration
- Prompt fragments from `PERSONA_PROMPT_FRAGMENT_REGISTRY` are appended at import time.
- Any extraction that changes ordering or duplication rules may silently change persona behavior.

### 3. `allowed_tools` injection changes authority surface
- Subordinate personas receive `escalate_to_hermes` and `ask_colleague` automatically at import time.
- This is not metadata-only; it affects real runtime permissions and reachable tool paths.

### 4. `PERSONAS` is used by multiple runtime surfaces
- `personas.py` reads it in primary runtime path.
- `inter_agent.py` reads it for validation and labels.
- `server.py` reads it for `/api/ops/live-agents`.
- Listing and tests read it directly as well.

### 5. `data_fetchers` are still on the primary path
- Even though legacy `run_persona()` is now fallback for current 8 personas, fetcher routing still flows through `_legacy._FETCHER_DISPATCH` in `personas.py`.

### 6. `PLANS` compatibility shape must remain dual
- `PLANS` currently exposes both canonical and legacy ids.
- Any extraction that leaves only canonical ids would break existing callers/tests.

## Recommended execution order summary

1. Phase 1 — plan primitives
2. Phase 2 — listing surface
3. Phase 3 — fetchers + registry
4. Phase 4 — `PERSONAS` last

## Fastest safe rollback principle

- Each phase should preserve a **single authoritative source** during rollout.
- The fastest rollback is always: restore reads to the previous authoritative source and redeploy that phase only.
