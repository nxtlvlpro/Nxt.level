# NXT8 Phase 1 Verification Checklist

> Minimal executable checklist for Phase 1 migration only: `PLAN_ALIASES`, `PLANS`, `get_plan`, `_min_plan_for`. This is a verification artifact only. No extraction, no code changes, no new implementations.

## PRE-MIGRATION CHECKS

### 1. Current imports inventory

- [ ] Confirm `backend/agents/personas.py` still exports:
  - [ ] `PLANS = _legacy.PLANS`
  - [ ] `get_plan = _legacy.get_plan`
- [ ] Confirm `_min_plan_for` is still referenced via `_legacy._min_plan_for(...)` in `backend/agents/personas.py`.
- [ ] Confirm `backend/server.py` still reads:
  - [ ] `personas_agent.get_plan(plan_id)`
  - [ ] `personas_agent.PLANS.items()`
- [ ] Confirm no additional hidden imports of `PLAN_ALIASES`, `PLANS`, `get_plan`, `_min_plan_for` appeared since the architecture audit.

### 2. Current callers inventory

- [ ] Record current callers of `get_plan`:
  - [ ] `backend/server.py` via `/api/personas`
  - [ ] plan unification tests
- [ ] Record current readers of `PLANS`:
  - [ ] `backend/server.py` via `/api/personas` payload
  - [ ] plan unification tests
- [ ] Record current callers/readers of `_min_plan_for`:
  - [ ] `backend/agents/personas.py` plan gate path
  - [ ] plan unification tests
- [ ] Confirm `PLAN_ALIASES` is only used inside plan resolution logic.

### 3. Snapshot of exported symbols

- [ ] Snapshot current values/shapes for:
  - [ ] `PLANS.keys()`
  - [ ] `get_plan(None)`
  - [ ] `get_plan("basic")`
  - [ ] `get_plan("simple")`
  - [ ] `get_plan("pro")`
  - [ ] `get_plan("enterprise")`
  - [ ] `get_plan("hq")`
  - [ ] `get_plan("pilot")`
- [ ] Snapshot `_min_plan_for(persona_id)` for all 8 persona ids.

### 4. Snapshot of plan resolution behavior

- [ ] Record canonical behavior for known aliases.
- [ ] Record fallback behavior for `None` / unknown values.
- [ ] Record that public `PLANS` currently exposes both canonical and legacy keys.

## EXTRACTION CHECKS

### 1. Symbol moved

- [ ] `PLAN_ALIASES` moved to target module.
- [ ] `PLANS` moved to target module.
- [ ] `get_plan` moved to target module.
- [ ] `_min_plan_for` moved to target module.

### 2. Imports updated

- [ ] All callers now import/read these symbols from the new source only.
- [ ] No stale direct reads remain from `personas_legacy.py` for the moved symbols.
- [ ] `backend/agents/personas.py` export surface still matches pre-migration expectations.

### 3. No duplicate definitions

- [ ] There is exactly one authoritative definition of `PLAN_ALIASES`.
- [ ] There is exactly one authoritative definition of `PLANS`.
- [ ] There is exactly one authoritative definition of `get_plan`.
- [ ] There is exactly one authoritative definition of `_min_plan_for`.
- [ ] Legacy file does not remain a competing runtime source for these symbols.

### 4. No behavior changes

- [ ] Public key set of `PLANS` is unchanged.
- [ ] Canonical plan ids are unchanged.
- [ ] Legacy alias resolution is unchanged.
- [ ] Unknown-plan fallback is unchanged.
- [ ] Persona-to-plan mapping is unchanged.

## RUNTIME VERIFICATION

### Required plan resolution checks

For each item below, compare **before vs after** and require exact semantic equivalence:

- [ ] `get_plan("free")`
- [ ] `get_plan("starter")`
- [ ] `get_plan("growth")`
- [ ] `get_plan("pro")`
- [ ] `get_plan("enterprise")`

### Verify explicitly

- [ ] plan aliases
- [ ] canonical names
- [ ] unknown plan behavior
- [ ] fallback behavior

### Expected interpretation for PASS

- [ ] `pro` still resolves exactly as before.
- [ ] `enterprise` still resolves exactly as before.
- [ ] `free`, `starter`, `growth` still behave exactly as before (including fallback if they are currently unmapped).
- [ ] Unknown plan handling does not silently change target plan.

## PERSONA VERIFICATION

For each persona id below verify both pre-migration and post-migration result equality:

### `analyst`
- [ ] `_min_plan_for("analyst")` unchanged
- [ ] plan lookup path for `analyst` unchanged
- [ ] no change in returned required plan for `analyst`

### `bookkeeper`
- [ ] `_min_plan_for("bookkeeper")` unchanged
- [ ] plan lookup path for `bookkeeper` unchanged
- [ ] no change in returned required plan for `bookkeeper`

### `client_manager`
- [ ] `_min_plan_for("client_manager")` unchanged
- [ ] plan lookup path for `client_manager` unchanged
- [ ] no change in returned required plan for `client_manager`

### `compliance`
- [ ] `_min_plan_for("compliance")` unchanged
- [ ] plan lookup path for `compliance` unchanged
- [ ] no change in returned required plan for `compliance`

### `hermes`
- [ ] `_min_plan_for("hermes")` unchanged
- [ ] plan lookup path for `hermes` unchanged
- [ ] no change in returned required plan for `hermes`

### `hr_mentor`
- [ ] `_min_plan_for("hr_mentor")` unchanged
- [ ] plan lookup path for `hr_mentor` unchanged
- [ ] no change in returned required plan for `hr_mentor`

### `marketer`
- [ ] `_min_plan_for("marketer")` unchanged
- [ ] plan lookup path for `marketer` unchanged
- [ ] no change in returned required plan for `marketer`

### `project_coord`
- [ ] `_min_plan_for("project_coord")` unchanged
- [ ] plan lookup path for `project_coord` unchanged
- [ ] no change in returned required plan for `project_coord`

## POST-DEPLOY CHECKS

### 1. server startup
- [ ] Backend starts without import errors.
- [ ] No startup exception related to moved plan symbols.

### 2. personas listing endpoint
- [ ] `GET /api/personas` returns 200.
- [ ] `plan`, `plans`, and `personas` payload sections are unchanged in shape.
- [ ] `plans` still include expected canonical + legacy exposure behavior.

### 3. persona chat endpoint
- [ ] `POST /api/personas/{persona_id}/chat` still enforces tariff gate identically.
- [ ] No regression in `required_plan` messaging.

### 4. scheduler startup
- [ ] Scheduler starts normally.
- [ ] No plan-resolution related exception appears during scheduler init.

### 5. inter_agent startup
- [ ] Inter-agent import path still loads successfully.
- [ ] No plan symbol import breakage propagates into agent startup.

## ROLLBACK CRITERIA

Immediate rollback if any of the following is true:

- [ ] `PLANS.keys()` changed unexpectedly
- [ ] any canonical/legacy alias resolves to a different plan than before
- [ ] `get_plan(None)` changed behavior
- [ ] unknown plan fallback changed
- [ ] `_min_plan_for(persona_id)` changed for any of the 8 personas
- [ ] `/api/personas` payload changed unexpectedly
- [ ] tariff gate behavior changed on persona chat endpoint
- [ ] backend import/startup failure appears
- [ ] scheduler startup fails
- [ ] inter-agent import/startup fails

## PASS / FAIL CRITERIA

### PASS
- [ ] All PRE-MIGRATION CHECKS captured
- [ ] All EXTRACTION CHECKS satisfied
- [ ] All RUNTIME VERIFICATION checks match pre-migration behavior
- [ ] All PERSONA VERIFICATION checks match pre-migration behavior
- [ ] All POST-DEPLOY CHECKS pass
- [ ] No ROLLBACK CRITERIA triggered

### FAIL
- [ ] Any one of the above checks fails
- [ ] Any rollback criterion is triggered

## Final decision

- [ ] **PASS**
- [ ] **FAIL**

## Evidence to capture

- [ ] pre/post serialized outputs of `get_plan(...)` for all checklist inputs
- [ ] pre/post serialized outputs of `_min_plan_for(...)` for all 8 personas
- [ ] pre/post snapshot of `PLANS.keys()`
- [ ] pre/post `GET /api/personas` response payload
- [ ] startup logs for backend and scheduler
- [ ] any diff or note explaining why `free/starter/growth` are mapped or fallbacking
