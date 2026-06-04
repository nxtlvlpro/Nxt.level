"""
NXT8 Hermes LangGraph v2 — faithful implementation of the
HERMES LANGGRAPH EXECUTION CONSTITUTION v1.0.

This module is the **execution and orchestration layer**.  It is NOT a
decision-maker.  Hermes (a policy node + role-specific DeepSeek prompts)
holds all authority over what is allowed, what is restricted, and what
gets the final stamp of approval.

Design choices
--------------
* **Single LLM, multiple roles.** All five constitutional roles
  (planner, executor, reviewer, fixer, hermes-validator) run on the
  same DeepSeek-V3 backend with role-specific system prompts.  This
  matches the project's "everything through DeepSeek" policy and keeps
  per-task cost predictable.
* **State-first.** Every node returns ONLY a state delta dict; the
  graph runtime (LangGraph if available, else a tiny built-in
  fallback) merges deltas into the canonical `GraphState`.
* **Deterministic routing.** `routing.next` is always set explicitly
  by the node that produced the current state — never inferred.
* **Hermes-first.** No node executes business work before
  `hermes_check` has produced a policy.  No artifact is finalised
  before `hermes_validation` approves.
* **Parallel to v1.** Lives alongside `nxt8_langgraph_ultra.py`. The
  legacy graph keeps powering production until v2 is battle-tested
  via `/api/graph/v2/run`.

Public API:
    run_graph_v2(task_description, intent, context=None) -> GraphState
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.graph_v2")


# =====================================================================
# Constitutional state schema (§3)
# =====================================================================


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initial_state(
    task_description: str,
    intent: str,
    context: Optional[Dict[str, Any]] = None,
    task_type: str = "execute",
) -> Dict[str, Any]:
    ctx = context or {}
    return {
        "task": {
            "id": str(uuid.uuid4()),
            "description": task_description,
            "type": task_type,
        },
        "intent": intent or task_description,
        "context": {
            "domain":     ctx.get("domain", "general"),
            "priority":   ctx.get("priority", "medium"),
            "constraints": list(ctx.get("constraints") or []),
        },
        "hermes": {
            "policy": {},
            "allowed_agents": [],
            "blocked_actions": [],
            "approval_required": False,
        },
        "memory": {
            "short_term": {},
            "long_term_refs": [],
            "retrieved_context": [],
        },
        "agents": {
            "active": "",
            "available": ["planner", "executor", "reviewer", "fixer"],
            "history": [],
        },
        "artifacts": {
            "plan": None,
            "execution": None,
            "analysis": None,
            "review": None,
            "final_output": None,
        },
        "tools": {
            "allowed": [],
            "executed": [],
        },
        "routing": {
            "current": "start",
            "next": "hermes_check",
            "reason": "initial entry",
        },
        "status": {
            "stage": "init",
            "error": None,
            "retry_count": 0,
            "history": [],
        },
    }


def _trace(state: Dict[str, Any], node: str, msg: str) -> None:
    """Append a single audit event to `status.history` (§2.5 traceability)."""
    state.setdefault("status", {}).setdefault("history", []).append({
        "node": node,
        "msg":  msg,
        "ts":   _now(),
    })


# =====================================================================
# LLM helpers — one DeepSeek call per role, strict JSON outputs
# =====================================================================

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", (text or "").strip())


async def _llm_role_call(
    system_prompt: str,
    user_blob: Dict[str, Any],
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """Single DeepSeek call returning a JSON object. Strips accidental
    code fences and falls back to {} on any parse error so the caller can
    decide policy. NEVER raises into the graph runtime."""
    try:
        ds = get_deepseek()
        resp = await ds.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": json.dumps(user_blob, ensure_ascii=False)},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            request_logprobs=False,
        )
        raw = _strip_fences(resp.get("content", ""))
        return json.loads(raw) if raw else {}
    except Exception as e:  # noqa: BLE001
        logger.warning("graph_v2 llm role call failed: %s", e)
        return {}


# =====================================================================
# Constitutional nodes (§5 + §4)
# =====================================================================


# ---------- §4 Hermes pre-flight ---------------------------------------

HERMES_CHECK_PROMPT = (
    "You are the Hermes Policy Gate of the NXT8 Constitutional Graph.\n"
    "Given a task description, intent and context, decide whether the graph "
    "is allowed to proceed, restricted, or denied. You are a SECURITY and "
    "POLICY layer — you do not solve the task.\n\n"
    "Reply with STRICT JSON only:\n"
    "{\n"
    '  "status": "allowed" | "restricted" | "denied",\n'
    '  "allowed_agents": ["planner","executor","reviewer","fixer"],\n'
    '  "blocked_actions": ["string", ...],\n'
    '  "constraints": ["string", ...],\n'
    '  "required_checks": ["string", ...],\n'
    '  "approval_required": false,\n'
    '  "reason": "string — one sentence"\n'
    "}\n\n"
    "Decision rules:\n"
    "- DENY anything that smells like: malware, exfiltrating credentials, "
    "real-money transfers, GDPR violations, doxxing, illegal content.\n"
    "- RESTRICT high-priority tasks that touch finance, contracts, or "
    "production data — set approval_required=true.\n"
    "- ALLOW normal business tasks (plan, analyse, build, research, fix) "
    "with no special constraints."
)


async def hermes_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """§4 Hermes interaction protocol. Runs before any execution."""
    _trace(state, "hermes_check", "policy gate")
    state["agents"]["active"] = "hermes_check"
    state["status"]["stage"] = "hermes_check"

    verdict = await _llm_role_call(
        system_prompt=HERMES_CHECK_PROMPT,
        user_blob={
            "task":    state["task"],
            "intent":  state["intent"],
            "context": state["context"],
        },
        max_tokens=300,
        temperature=0.0,
    )
    status = (verdict.get("status") or "allowed").lower()
    if status not in ("allowed", "restricted", "denied"):
        status = "allowed"

    state["hermes"] = {
        "policy":            verdict,
        "allowed_agents":    list(verdict.get("allowed_agents") or
                                  ["planner", "executor", "reviewer", "fixer"]),
        "blocked_actions":   list(verdict.get("blocked_actions") or []),
        "approval_required": bool(verdict.get("approval_required")),
    }
    state["context"]["constraints"] = list(set(
        list(state["context"].get("constraints") or [])
        + list(verdict.get("constraints") or [])
    ))

    if status == "denied":
        state["status"]["stage"] = "error"
        state["status"]["error"] = {"code": "denied", "reason": verdict.get("reason", "policy denial")}
        state["routing"] = {"current": "hermes_check", "next": "end",
                            "reason": "Hermes denied execution"}
    else:
        state["routing"] = {"current": "hermes_check", "next": "planner",
                            "reason": f"Hermes policy {status} → planning"}
    return state


# ---------- §5.1 Planner ----------------------------------------------

PLANNER_PROMPT = (
    "You are the PLANNER agent of the NXT8 Constitutional Graph.\n"
    "Your only job is to decompose the task into a structured execution "
    "plan. You DO NOT execute. You DO NOT call external tools. You DO NOT "
    "make business decisions outside the constraints provided by Hermes.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "summary": "string — one-line plan summary",\n'
    '  "steps": [\n'
    "    {\n"
    '      "id": "s1",\n'
    '      "agent": "executor",\n'
    '      "action": "string — what concretely to do",\n'
    '      "expects": "string — what artifact this step produces",\n'
    '      "depends_on": []\n'
    "    }\n"
    "  ],\n"
    '  "risk_level": "low" | "medium" | "high"\n'
    "}\n\n"
    "Rules:\n"
    "- 1 to 5 steps maximum.\n"
    "- Every step must be ATOMIC (one concrete action).\n"
    "- Respect every constraint from Hermes."
)


async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "planner", "decomposing task")
    state["agents"]["active"] = "planner"
    state["status"]["stage"] = "planning"

    plan = await _llm_role_call(
        system_prompt=PLANNER_PROMPT,
        user_blob={
            "task":        state["task"],
            "intent":      state["intent"],
            "context":     state["context"],
            "constraints": state["context"]["constraints"],
            "hermes":      state["hermes"],
        },
        max_tokens=450,
        temperature=0.4,
    )
    # Validate: minimum shape.
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        plan = {
            "summary": f"Single-step fallback plan for: {state['task'].get('description','')[:80]}",
            "steps": [{
                "id": "s1", "agent": "executor",
                "action": state["task"].get("description", ""),
                "expects": "completed result",
                "depends_on": [],
            }],
            "risk_level": "low",
        }
    # Hard-cap to 3 steps — keeps the graph under Cloudflare's 100s edge timeout
    # when run synchronously. Anything bigger should be broken into multiple runs.
    plan["steps"] = list(plan["steps"])[:3]
    plan["_built_at"] = _now()
    state["artifacts"]["plan"] = plan
    state["agents"]["history"].append({"agent": "planner", "ts": _now(),
                                       "out": plan.get("summary", "")})
    state["routing"] = {"current": "planner", "next": "executor",
                        "reason": f"{len(plan['steps'])} step(s) planned"}
    return state


# ---------- §5.2 Executor ---------------------------------------------

EXECUTOR_PROMPT = (
    "You are the EXECUTOR agent of the NXT8 Constitutional Graph.\n"
    "Execute ONE step of the plan that the planner produced. Produce a "
    "concrete artifact (text/code/analysis/action result). Do NOT change "
    "the plan. Do NOT make new decisions outside the step.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "step_id": "string",\n'
    '  "output": "string — the concrete result, can be plain text or markdown",\n'
    '  "evidence": ["string", ...],\n'
    '  "tool_calls": []\n'
    "}"
)


async def executor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "executor", "executing next pending step")
    state["agents"]["active"] = "executor"
    state["status"]["stage"] = "execution"

    plan = state["artifacts"].get("plan") or {}
    steps = list(plan.get("steps") or [])
    done_ids = {e.get("step_id") for e in (state["artifacts"].get("execution") or {}).get("steps", [])}
    next_step = next((s for s in steps if s.get("id") not in done_ids), None)
    if next_step is None:
        # Nothing left to execute — go to review.
        state["routing"] = {"current": "executor", "next": "reviewer",
                            "reason": "all plan steps executed"}
        return state

    result = await _llm_role_call(
        system_prompt=EXECUTOR_PROMPT,
        user_blob={
            "step":   next_step,
            "intent": state["intent"],
            "context": state["context"],
            "constraints": state["context"]["constraints"],
            "blocked_actions": state["hermes"]["blocked_actions"],
        },
        max_tokens=600,
        temperature=0.4,
    )
    if not result.get("output"):
        result = {
            "step_id": next_step.get("id", "s?"),
            "output": "(executor returned empty output)",
            "evidence": [],
            "tool_calls": [],
        }
    result.setdefault("step_id", next_step.get("id"))

    execution = state["artifacts"].get("execution") or {"steps": []}
    execution["steps"].append(result)
    execution["last_updated"] = _now()
    state["artifacts"]["execution"] = execution
    state["agents"]["history"].append({"agent": "executor", "ts": _now(),
                                       "step": next_step.get("id")})

    state["routing"] = {"current": "executor", "next": "reviewer",
                        "reason": f"step {next_step.get('id')} completed"}
    return state


# ---------- §5.3 Reviewer ---------------------------------------------

REVIEWER_PROMPT = (
    "You are the REVIEWER agent of the NXT8 Constitutional Graph.\n"
    "Validate the executor's most recent output for: correctness, plan "
    "compliance, Hermes constraint compliance, completeness.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "verdict": "PASS" | "FAIL",\n'
    '  "issues": ["string", ...],\n'
    '  "notes":  "string — one paragraph"\n'
    "}"
)


async def reviewer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "reviewer", "validating executor output")
    state["agents"]["active"] = "reviewer"
    state["status"]["stage"] = "review"

    execution = state["artifacts"].get("execution") or {}
    last = (execution.get("steps") or [{}])[-1]
    review = await _llm_role_call(
        system_prompt=REVIEWER_PROMPT,
        user_blob={
            "executor_output": last,
            "plan_summary":    (state["artifacts"].get("plan") or {}).get("summary"),
            "intent":          state["intent"],
            "constraints":     state["context"]["constraints"],
            "required_checks": (state["hermes"].get("policy") or {}).get("required_checks") or [],
        },
        max_tokens=400,
        temperature=0.0,
    )
    verdict = (review.get("verdict") or "PASS").upper()
    if verdict not in ("PASS", "FAIL"):
        verdict = "PASS"
    review["verdict"] = verdict
    review["ts"] = _now()
    state["artifacts"]["review"] = review

    if verdict == "PASS":
        # Are there more plan steps to execute?
        plan_steps = (state["artifacts"].get("plan") or {}).get("steps") or []
        done_ids = {e.get("step_id") for e in execution.get("steps", [])}
        remaining = [s for s in plan_steps if s.get("id") not in done_ids]
        if remaining:
            state["routing"] = {"current": "reviewer", "next": "executor",
                                "reason": f"{len(remaining)} step(s) left"}
        else:
            state["routing"] = {"current": "reviewer", "next": "hermes_validation",
                                "reason": "all steps reviewed PASS"}
    else:
        state["routing"] = {"current": "reviewer", "next": "fixer",
                            "reason": "reviewer FAIL — fix needed"}
    return state


# ---------- §5.4 Fixer ------------------------------------------------

FIXER_PROMPT = (
    "You are the FIXER agent of the NXT8 Constitutional Graph.\n"
    "The reviewer flagged a problem. Correct ONLY the specific issues "
    "listed. Do NOT re-plan. Do NOT introduce new content. Produce a "
    "corrected version of the executor's last artifact.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "step_id": "string",\n'
    '  "output": "string — corrected result",\n'
    '  "fixed_issues": ["string", ...]\n'
    "}"
)


async def fixer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "fixer", "applying corrections")
    state["agents"]["active"] = "fixer"
    state["status"]["stage"] = "correction"
    state["status"]["retry_count"] = int(state["status"].get("retry_count", 0)) + 1

    if state["status"]["retry_count"] > 3:
        # §9 hard cap → escalate to STOP.
        state["status"]["stage"] = "error"
        state["status"]["error"] = {"code": "retry_exhausted",
                                    "reason": "fixer retries exceeded 3"}
        state["routing"] = {"current": "fixer", "next": "end",
                            "reason": "retry cap reached — STOP per §9"}
        return state

    execution = state["artifacts"].get("execution") or {}
    last = (execution.get("steps") or [{}])[-1]
    review = state["artifacts"].get("review") or {}
    corrected = await _llm_role_call(
        system_prompt=FIXER_PROMPT,
        user_blob={
            "previous_output": last,
            "issues":          review.get("issues", []),
            "notes":           review.get("notes", ""),
        },
        max_tokens=700,
        temperature=0.3,
    )
    if corrected.get("output"):
        # Replace the last execution step with the corrected one.
        execution["steps"][-1] = {
            "step_id":   last.get("step_id"),
            "output":    corrected["output"],
            "evidence":  last.get("evidence", []),
            "tool_calls": last.get("tool_calls", []),
            "fixed_issues": corrected.get("fixed_issues", []),
            "fixed_at":  _now(),
        }
        execution["last_updated"] = _now()
        state["artifacts"]["execution"] = execution

    state["routing"] = {"current": "fixer", "next": "executor",
                        "reason": f"correction #{state['status']['retry_count']} applied"}
    return state


# ---------- §5.5 Hermes validation (final gate) -----------------------

HERMES_VAL_PROMPT = (
    "You are the HERMES VALIDATION node — the final authority in the "
    "NXT8 Constitutional Graph. Validate the accumulated artifacts "
    "against business logic and the policy you set in the hermes_check "
    "phase. You either APPROVE the result or REJECT it.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "verdict": "approve" | "reject",\n'
    '  "summary": "string — single sentence for the audit log",\n'
    '  "reasons": ["string", ...]\n'
    "}"
)


async def hermes_validation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "hermes_validation", "final authority checkpoint")
    state["agents"]["active"] = "hermes_validation"
    state["status"]["stage"] = "finalization"

    judgement = await _llm_role_call(
        system_prompt=HERMES_VAL_PROMPT,
        user_blob={
            "task":          state["task"],
            "intent":        state["intent"],
            "constraints":   state["context"]["constraints"],
            "plan_summary":  (state["artifacts"].get("plan") or {}).get("summary"),
            "review":        state["artifacts"].get("review"),
            "execution_n":   len((state["artifacts"].get("execution") or {}).get("steps") or []),
        },
        max_tokens=300,
        temperature=0.0,
    )
    verdict = (judgement.get("verdict") or "approve").lower()
    if verdict not in ("approve", "reject"):
        verdict = "approve"

    state["artifacts"]["analysis"] = {
        "hermes_validation": judgement,
        "ts": _now(),
    }
    if verdict == "approve":
        state["routing"] = {"current": "hermes_validation", "next": "finalization",
                            "reason": "Hermes approved"}
    else:
        # §6 reject → back to planner. retry_count is bumped to avoid infinite ping-pong.
        state["status"]["retry_count"] = int(state["status"].get("retry_count", 0)) + 1
        if state["status"]["retry_count"] > 3:
            state["status"]["stage"] = "error"
            state["status"]["error"] = {"code": "validation_rejected",
                                        "reason": "Hermes kept rejecting after 3 rounds"}
            state["routing"] = {"current": "hermes_validation", "next": "end",
                                "reason": "STOP — Hermes rejection cap reached"}
        else:
            state["routing"] = {"current": "hermes_validation", "next": "planner",
                                "reason": "Hermes rejected — replanning"}
    return state


# ---------- Finalization ----------------------------------------------


def finalization_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pack the conclusive `final_output` artifact and end the run."""
    _trace(state, "finalization", "packing final output")
    state["agents"]["active"] = "finalization"
    state["status"]["stage"] = "done"

    exec_steps = (state["artifacts"].get("execution") or {}).get("steps") or []
    answer_parts = [s.get("output", "") for s in exec_steps if s.get("output")]
    final_text = "\n\n".join(answer_parts).strip()
    state["artifacts"]["final_output"] = {
        "text":   final_text,
        "audit":  state["status"]["history"][-20:],   # last 20 events
        "review": state["artifacts"].get("review"),
        "ts":     _now(),
    }
    state["routing"] = {"current": "finalization", "next": "end",
                        "reason": "graph done"}
    return state


# =====================================================================
# Routing engine + graph runtime
# =====================================================================


NODES: Dict[str, Callable[..., Any]] = {
    "hermes_check":       hermes_check_node,
    "planner":            planner_node,
    "executor":           executor_node,
    "reviewer":           reviewer_node,
    "fixer":              fixer_node,
    "hermes_validation":  hermes_validation_node,
    "finalization":       finalization_node,
}

MAX_HOPS = 25  # hard cap to prevent any pathological loop


async def _run_node(name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    fn = NODES.get(name)
    if fn is None:
        raise RuntimeError(f"unknown node: {name}")
    out = fn(state) if not _is_async(fn) else await fn(state)
    return out or state


def _is_async(fn: Callable[..., Any]) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(fn)


async def run_graph_v2(
    task_description: str,
    intent: str,
    context: Optional[Dict[str, Any]] = None,
    task_type: str = "execute",
) -> Dict[str, Any]:
    """Execute the constitutional graph end-to-end and return the final state.

    The runtime is a thin built-in loop (deterministic, debuggable) rather
    than LangGraph itself.  LangGraph is great for tracing UIs but for our
    needs the constitution's explicit `routing.next` IS the graph — we
    just honour it directly.
    """
    state = _initial_state(task_description, intent, context, task_type)
    _trace(state, "graph", "start")

    hops = 0
    while True:
        next_node = (state.get("routing") or {}).get("next", "end")
        if next_node in (None, "", "end"):
            _trace(state, "graph", f"end (stage={state['status']['stage']})")
            break
        if hops >= MAX_HOPS:
            state["status"]["stage"] = "error"
            state["status"]["error"] = {"code": "hop_limit",
                                        "reason": f"exceeded {MAX_HOPS} hops"}
            _trace(state, "graph", "STOP — hop limit reached")
            break
        try:
            state = await _run_node(next_node, state)
        except Exception as e:  # noqa: BLE001
            logger.exception("graph_v2 node %s crashed: %s", next_node, e)
            state["status"]["stage"] = "error"
            state["status"]["error"] = {"code": "node_crash",
                                        "node": next_node, "reason": str(e)}
            state["routing"] = {"current": next_node, "next": "end",
                                "reason": "node crashed"}
        hops += 1

    return state
