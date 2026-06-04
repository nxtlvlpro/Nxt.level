"""
NXT8 Hermes Operating Architecture — 10-node continuous StateGraph.

This is **NOT** a one-shot task executor (that role belongs to
`hermes_graph_v2.py`). This graph models Hermes as the company's
operating system: every event in the business triggers one Observe →
Understand → Validate → Reason → Route → Execute → Monitor → Learn →
Improve → Evolve cycle.

Each node:
- Reads the current GraphState (a dict, mutated in-place + returned).
- Writes its slice (state["observation"], state["context"], ...).
- Sets state["routing"]["next"] explicitly. The runtime honours that.

The runtime is a deterministic built-in loop with a MAX_HOPS cap so a
misbehaving LLM call cannot stall the system. Every node failure is
trapped and traced in `state["history"]` — the cycle always terminates.

Public API:
    run_os_cycle(event: dict, *, persist: bool = True) -> GraphState

Where `event` is the trigger payload (e.g. an incoming channel
webhook, a new document upload, a new task). The graph attaches a
fresh cycle_id, runs all 10 nodes, persists the final state in
`db.hermes_os_cycles`, and returns it for the caller / UI.

Phase 1 scope:
- 10 nodes implemented with DeepSeek-backed reasoning via shared LLM
  helper.
- Persistence in a single new collection (`hermes_os_cycles`).
- A *skeleton* knowledge-graph write in the Learning node — Phase 2
  will flesh out the full 4-layer memory.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.deepseek import get_deepseek
from core.db import get_db
from core import hermes_memory as hmem
from agents.agent_charter import CHARTER

logger = logging.getLogger("nxt8.hermes_os")


# =====================================================================
# State schema
# =====================================================================


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initial_state(event: Dict[str, Any]) -> Dict[str, Any]:
    """Bootstrap a cycle state from a triggering event.

    The event is expected to be a dict with at minimum:
      - source: "channel_webhook" | "document_upload" | "task_created"
                | "manual" | "scheduler" | ...
      - kind:   freeform event category (e.g. "new_client_message")
      - payload: arbitrary domain object
      - user_id, company_id, lang: optional metadata
    """
    return {
        "cycle_id":   str(uuid.uuid4()),
        "started_at": _now(),
        "event": {
            "source":     event.get("source", "manual"),
            "kind":       event.get("kind", "generic"),
            "payload":    event.get("payload") or {},
            "user_id":    event.get("user_id"),
            "company_id": event.get("company_id"),
            "lang":       event.get("lang", "ru"),
            "received_at": _now(),
        },
        # 10 stages (one per node):
        "observation":   {},     # §1 Observation Node
        "context":       {},     # §2 Context Assembly
        "validation":    {},     # §3 Constitution Validation
        "reasoning":     {},     # §4 Reasoning
        "routing_plan":  {},     # §5 Agent Routing
        "execution":     {},     # §6 Execution
        "monitoring":    {},     # §7 Monitoring
        "learning":      {},     # §8 Learning
        "improvement":   {},     # §9 Improvement
        "evolution":     {},     # §10 Evolution

        "routing": {
            "current": "start",
            "next":    "observation",
            "reason":  "cycle entry",
        },
        "status": {
            "stage": "init",
            "error": None,
        },
        "history": [],   # audit trail
    }


def _trace(state: Dict[str, Any], node: str, msg: str) -> None:
    state.setdefault("history", []).append({
        "node": node,
        "msg":  msg,
        "ts":   _now(),
    })


# =====================================================================
# LLM helper (shared across all 10 nodes)
# =====================================================================

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", (text or "").strip())


async def _llm_node_call(
    system_prompt: str,
    user_blob: Dict[str, Any],
    *,
    max_tokens: int = 400,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """One DeepSeek call returning JSON. Returns {} on any failure so the
    cycle never crashes on a bad LLM response."""
    try:
        ds = get_deepseek()
        resp = await ds.chat(
            messages=[
                {"role": "system", "content": f"{CHARTER}\n\n{system_prompt}"},
                {"role": "user",   "content": json.dumps(user_blob, ensure_ascii=False, default=str)},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            request_logprobs=False,
        )
        raw = _strip_fences(resp.get("content", ""))
        return json.loads(raw) if raw else {}
    except Exception as e:  # noqa: BLE001
        logger.warning("hermes_os llm call failed: %s", e)
        return {}


# =====================================================================
# §1 Observation Node
# =====================================================================

OBSERVATION_PROMPT = (
    "You are the OBSERVATION node of the NXT8 Hermes Operating Graph.\n"
    "Your sole job is to extract the OBJECTIVE FACTS from the triggering "
    "event. Do NOT interpret, do NOT recommend, do NOT solve anything.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "summary": "string — one sentence factual summary",\n'
    '  "entities": [\n'
    '    {"type": "person|company|project|document|product|other",\n'
    '     "value": "string",\n'
    '     "role":  "string — e.g. sender, mentioned, attached"}\n'
    "  ],\n"
    '  "signals": ["string", ...],\n'
    '  "raw_text_fragments": ["string", ...]\n'
    "}"
)


async def observation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "observation", "extracting raw facts")
    state["status"]["stage"] = "observation"

    out = await _llm_node_call(
        system_prompt=OBSERVATION_PROMPT,
        user_blob={"event": state["event"]},
        max_tokens=350,
        temperature=0.1,
    )
    state["observation"] = {
        "summary":   out.get("summary") or "",
        "entities":  list(out.get("entities") or []),
        "signals":   list(out.get("signals") or []),
        "raw":       list(out.get("raw_text_fragments") or []),
        "produced_at": _now(),
    }
    state["routing"] = {"current": "observation", "next": "context_assembly",
                        "reason": "facts collected"}
    return state


# =====================================================================
# §2 Context Assembly Node
# =====================================================================


async def context_assembly_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pull related context from all 4 memory layers in parallel:
    Short-Term (in-process LRU), Operational (Mongo facade), Knowledge
    Graph (entity neighbours), Institutional (lessons learned).
    """
    _trace(state, "context_assembly", "building 4-layer working context")
    state["status"]["stage"] = "context_assembly"

    bundle = await hmem.assemble_context(
        event=state["event"],
        observation=state["observation"],
        ops_limit=5,
        kg_limit=15,
        inst_limit=5,
    )
    state["context"] = bundle
    totals = bundle.get("totals", {})
    state["routing"] = {
        "current": "context_assembly",
        "next":    "constitution_validation",
        "reason":  (f"stm={totals.get('stm_cycles',0)} "
                    f"ops={totals.get('ops_records',0)} "
                    f"kg={totals.get('kg_edges',0)} "
                    f"inst={totals.get('inst_lessons',0)}"),
    }
    return state


# =====================================================================
# §3 Constitution Validation Node
# =====================================================================

CONSTITUTION_PROMPT = (
    "You are the CONSTITUTION VALIDATION node of the NXT8 Hermes Operating "
    "Graph. Check whether the event + entities + context are compliant with "
    "the company constitution. Flag violations of: authority, policy, "
    "security, GDPR / personal-data, role boundaries, financial guardrails.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "status": "compliant" | "needs_review" | "violation",\n'
    '  "violations": ["string", ...],\n'
    '  "policies_applied": ["string", ...],\n'
    '  "required_approvals": ["role:hermes", "role:legal", ...],\n'
    '  "reason": "string — one sentence"\n'
    "}"
)


async def constitution_validation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "constitution_validation", "policy & boundary check")
    state["status"]["stage"] = "constitution_validation"

    out = await _llm_node_call(
        system_prompt=CONSTITUTION_PROMPT,
        user_blob={
            "event":       state["event"],
            "observation": state["observation"],
            "context_keys": list(state["context"].keys()),
        },
        max_tokens=300,
        temperature=0.0,
    )
    status = (out.get("status") or "compliant").lower()
    if status not in ("compliant", "needs_review", "violation"):
        status = "compliant"

    state["validation"] = {
        "status":             status,
        "violations":         list(out.get("violations") or []),
        "policies_applied":   list(out.get("policies_applied") or []),
        "required_approvals": list(out.get("required_approvals") or []),
        "reason":             out.get("reason") or "",
        "checked_at":         _now(),
    }

    if status == "violation":
        # Skip reasoning/execution — go straight to learning so we still
        # record what happened and how the system reacted.
        state["routing"] = {"current": "constitution_validation", "next": "learning",
                            "reason": "violation — bypass reasoning/execution"}
    else:
        state["routing"] = {"current": "constitution_validation", "next": "reasoning",
                            "reason": f"validation {status}"}
    return state


# =====================================================================
# §4 Reasoning Node
# =====================================================================

REASONING_PROMPT = (
    "You are the REASONING node of the NXT8 Hermes Operating Graph.\n"
    "Given the validated observation + context, analyse: the underlying "
    "problem, the goal, the risks, and the possible courses of action. "
    "Be terse and decision-oriented.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "problem":  "string — what is actually happening",\n'
    '  "goal":     "string — what success looks like",\n'
    '  "risks":    ["string", ...],\n'
    '  "options": [\n'
    '    {"id": "o1", "action": "string", "impact": "low|medium|high",\n'
    '     "owner_hint": "self|agent:<id>|human"}\n'
    "  ],\n"
    '  "recommended_option_id": "o1"\n'
    "}"
)


async def reasoning_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "reasoning", "analysing situation")
    state["status"]["stage"] = "reasoning"

    out = await _llm_node_call(
        system_prompt=REASONING_PROMPT,
        user_blob={
            "observation": state["observation"],
            "validation":  state["validation"],
            "context_keys": list(state["context"].keys()),
        },
        max_tokens=500,
        temperature=0.3,
    )
    options = list(out.get("options") or [])
    if not options:
        options = [{"id": "o1",
                    "action": f"Acknowledge event '{state['event'].get('kind')}'",
                    "impact": "low",
                    "owner_hint": "self"}]

    state["reasoning"] = {
        "problem":  out.get("problem") or "",
        "goal":     out.get("goal") or "",
        "risks":    list(out.get("risks") or []),
        "options":  options,
        "recommended_option_id": out.get("recommended_option_id") or options[0]["id"],
        "reasoned_at": _now(),
    }
    state["routing"] = {"current": "reasoning", "next": "agent_routing",
                        "reason": f"{len(options)} option(s) generated"}
    return state


# =====================================================================
# §5 Agent Routing Node
# =====================================================================

ROUTING_PROMPT = (
    "You are the AGENT ROUTING node of the NXT8 Hermes Operating Graph.\n"
    "Decide who must perform the recommended action. Choose ONE of:\n"
    "  - 'self'              (Hermes handles directly)\n"
    "  - 'agent:<agent_id>'  (delegate to a single specialised agent)\n"
    "  - 'agent_group'       (coordinated multi-agent run)\n"
    "  - 'human'             (escalate to a person)\n"
    "  - 'mixed'             (agents do parts, human approves)\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "mode": "self|agent|agent_group|human|mixed",\n'
    '  "assignees": ["string", ...],\n'
    '  "rationale": "string — one sentence"\n'
    "}"
)


async def agent_routing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "agent_routing", "choosing executor")
    state["status"]["stage"] = "agent_routing"

    reasoning = state["reasoning"]
    chosen_option = next(
        (o for o in reasoning["options"]
         if o.get("id") == reasoning["recommended_option_id"]),
        reasoning["options"][0],
    )

    out = await _llm_node_call(
        system_prompt=ROUTING_PROMPT,
        user_blob={
            "option": chosen_option,
            "goal":   reasoning["goal"],
            "risks":  reasoning["risks"],
            "required_approvals": state["validation"]["required_approvals"],
        },
        max_tokens=200,
        temperature=0.2,
    )
    mode = (out.get("mode") or chosen_option.get("owner_hint") or "self").lower()
    if mode.startswith("agent:"):
        assignees = [mode.split(":", 1)[1]]
        mode = "agent"
    else:
        assignees = list(out.get("assignees") or [])

    state["routing_plan"] = {
        "mode":      mode,
        "assignees": assignees,
        "rationale": out.get("rationale") or "",
        "option_id": chosen_option.get("id"),
        "routed_at": _now(),
    }
    state["routing"] = {"current": "agent_routing", "next": "execution",
                        "reason": f"route → {mode}"}
    return state


# =====================================================================
# §6 Execution Node
# =====================================================================


async def execution_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Phase 1: log the intended action only. Real downstream invocation
    (creating tasks, posting messages, launching agents) is wired in
    Phase 2 once the Access Guard is in place."""
    _trace(state, "execution", "logging intended action")
    state["status"]["stage"] = "execution"

    plan = state["routing_plan"]
    reasoning = state["reasoning"]
    chosen_option = next(
        (o for o in reasoning["options"]
         if o.get("id") == plan.get("option_id")),
        reasoning["options"][0],
    )

    state["execution"] = {
        "mode":      plan.get("mode"),
        "assignees": plan.get("assignees", []),
        "action":    chosen_option.get("action"),
        "impact":    chosen_option.get("impact", "low"),
        "status":    "logged",     # Phase 1 stops at logged
        "ts":        _now(),
        # Phase 2 will populate these:
        "task_id":   None,
        "result":    None,
    }
    state["routing"] = {"current": "execution", "next": "monitoring",
                        "reason": "action logged for downstream wiring"}
    return state


# =====================================================================
# §7 Monitoring Node
# =====================================================================

MONITORING_PROMPT = (
    "You are the MONITORING node of the NXT8 Hermes Operating Graph.\n"
    "Predict what KPIs / signals to watch for the action that was just "
    "executed (or logged). Keep it short — the executor will use this list "
    "to gate the next status report.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "kpis": ["string", ...],\n'
    '  "deadlines": ["string — ISO timestamp or interval"],\n'
    '  "deviation_signals": ["string", ...]\n'
    "}"
)


async def monitoring_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "monitoring", "setting up watchers")
    state["status"]["stage"] = "monitoring"

    out = await _llm_node_call(
        system_prompt=MONITORING_PROMPT,
        user_blob={
            "execution": state["execution"],
            "goal":      state["reasoning"]["goal"],
        },
        max_tokens=200,
        temperature=0.2,
    )
    state["monitoring"] = {
        "kpis":              list(out.get("kpis") or []),
        "deadlines":         list(out.get("deadlines") or []),
        "deviation_signals": list(out.get("deviation_signals") or []),
        "watched_since":     _now(),
    }
    state["routing"] = {"current": "monitoring", "next": "learning",
                        "reason": "watchers registered"}
    return state


# =====================================================================
# §8 Learning Node
# =====================================================================

LEARNING_PROMPT = (
    "You are the LEARNING node of the NXT8 Hermes Operating Graph.\n"
    "Distil the organisational lesson from this cycle. Be specific. Avoid "
    "generic advice. If nothing notable happened, return an empty 'lessons' "
    "array — do not invent.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "lessons": [\n'
    '    {"text": "string", "tags": ["string", ...], "scope": "process|client|agent|knowledge"}\n'
    "  ],\n"
    '  "kg_edges": [\n'
    '    {"source": "string", "target": "string", "relation": "string"}\n'
    "  ]\n"
    "}"
)


async def learning_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "learning", "extracting lessons")
    state["status"]["stage"] = "learning"

    out = await _llm_node_call(
        system_prompt=LEARNING_PROMPT,
        user_blob={
            "event":      state["event"],
            "observation": state["observation"],
            "reasoning":  state["reasoning"],
            "execution":  state["execution"],
            "monitoring": state["monitoring"],
            "validation": state["validation"],
        },
        max_tokens=400,
        temperature=0.4,
    )
    lessons = list(out.get("lessons") or [])
    kg_edges = list(out.get("kg_edges") or [])

    # Deterministic fallback: even if the LLM proposes no edges, the
    # observed entities ARE knowledge worth recording. Wire each entity
    # to the company_id / user_id with a `mentioned_in_event` relation.
    company_id = state["event"].get("company_id")
    user_id    = state["event"].get("user_id")
    event_kind = state["event"].get("kind") or "event"
    for ent in (state["observation"].get("entities") or [])[:8]:
        value = (ent.get("value") or "").strip()
        if not value:
            continue
        if company_id:
            kg_edges.append({"source": company_id, "target": value,
                             "relation": f"observed:{event_kind}"})
        if user_id and value != user_id:
            kg_edges.append({"source": user_id, "target": value,
                             "relation": f"mentioned:{event_kind}"})

    # Persist lessons + KG edges via the memory facade (best-effort).
    saved_inst = 0
    saved_kg = 0
    for lesson in lessons:
        text = (lesson.get("text") or "").strip()
        if not text:
            continue
        rid = await hmem.inst_record(
            text,
            tags=list(lesson.get("tags") or []),
            scope=lesson.get("scope", "process"),
            cycle_id=state["cycle_id"],
        )
        if rid:
            saved_inst += 1
    for e in kg_edges:
        src = (e.get("source") or "").strip()
        tgt = (e.get("target") or "").strip()
        if not (src and tgt):
            continue
        eid = await hmem.kg_add_edge(src, tgt, e.get("relation") or "related",
                                     cycle_id=state["cycle_id"])
        if eid:
            saved_kg += 1

    state["learning"] = {
        "lessons":     lessons,
        "kg_edges":    kg_edges,
        "saved_inst":  saved_inst,
        "saved_kg":    saved_kg,
        "saved_count": saved_inst + saved_kg,
        "learned_at":  _now(),
    }
    state["routing"] = {"current": "learning", "next": "improvement",
                        "reason": f"{len(lessons)} lesson(s) saved"}
    return state


# =====================================================================
# §9 Improvement Node
# =====================================================================

IMPROVEMENT_PROMPT = (
    "You are the IMPROVEMENT node of the NXT8 Hermes Operating Graph.\n"
    "Scan for: repeated errors, employee overload, redundant approvals, "
    "inefficient processes, gaps in the company constitution. Propose ONLY "
    "improvements that are directly suggested by THIS cycle's evidence.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "recommendations": [\n'
    '    {"category": "process|policy|tooling|training|automation",\n'
    '     "text": "string",\n'
    '     "expected_impact": "low|medium|high"}\n'
    "  ]\n"
    "}"
)


async def improvement_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "improvement", "scanning for improvements")
    state["status"]["stage"] = "improvement"

    out = await _llm_node_call(
        system_prompt=IMPROVEMENT_PROMPT,
        user_blob={
            "validation": state["validation"],
            "reasoning":  state["reasoning"],
            "learning":   state["learning"],
            "execution":  state["execution"],
        },
        max_tokens=350,
        temperature=0.4,
    )
    recs = list(out.get("recommendations") or [])

    # Persist as evolution-log candidates of category "process_improvement"
    try:
        if recs:
            db = get_db()
            await db.hermes_evolution_log.insert_many([{
                "id":           str(uuid.uuid4()),
                "cycle_id":     state["cycle_id"],
                "category":     r.get("category", "process"),
                "title":        (r.get("text") or "")[:120],
                "desc":         r.get("text") or "",
                "impact":       r.get("expected_impact", "low"),
                "status":       "proposed",
                "created_at":   _now(),
                "source":       "improvement_node",
            } for r in recs if r.get("text")])
    except Exception as e:  # noqa: BLE001
        logger.warning("improvement persistence failed: %s", e)

    state["improvement"] = {
        "recommendations": recs,
        "saved_count":     len(recs),
        "scanned_at":      _now(),
    }
    state["routing"] = {"current": "improvement", "next": "evolution",
                        "reason": f"{len(recs)} recommendation(s)"}
    return state


# =====================================================================
# §10 Evolution Node
# =====================================================================

EVOLUTION_PROMPT = (
    "You are the EVOLUTION node of the NXT8 Hermes Operating Graph.\n"
    "Assess whether the system itself needs structural change: new agents, "
    "new integrations, architectural shifts, or platform limits to lift. "
    "Be conservative — only flag what THIS cycle actually evidences.\n\n"
    "Output STRICT JSON only:\n"
    "{\n"
    '  "self_assessment": "string — one sentence",\n'
    '  "platform_limits": ["string", ...],\n'
    '  "roadmap_proposals": [\n'
    '    {"category": "new_agent|new_integration|architecture",\n'
    '     "title": "string",\n'
    '     "desc":  "string"}\n'
    "  ]\n"
    "}"
)


async def evolution_node(state: Dict[str, Any]) -> Dict[str, Any]:
    _trace(state, "evolution", "self-evolution checkpoint")
    state["status"]["stage"] = "evolution"

    out = await _llm_node_call(
        system_prompt=EVOLUTION_PROMPT,
        user_blob={
            "improvement": state["improvement"],
            "learning":    state["learning"],
            "validation":  state["validation"],
            "event_kind":  state["event"].get("kind"),
        },
        max_tokens=350,
        temperature=0.5,
    )
    proposals = list(out.get("roadmap_proposals") or [])

    try:
        if proposals:
            db = get_db()
            await db.hermes_evolution_log.insert_many([{
                "id":         str(uuid.uuid4()),
                "cycle_id":   state["cycle_id"],
                "category":   p.get("category", "architecture"),
                "title":      (p.get("title") or "")[:120],
                "desc":       p.get("desc") or "",
                "impact":     "medium",
                "status":     "roadmap",
                "created_at": _now(),
                "source":     "evolution_node",
            } for p in proposals if p.get("title")])
    except Exception as e:  # noqa: BLE001
        logger.warning("evolution persistence failed: %s", e)

    state["evolution"] = {
        "self_assessment":   out.get("self_assessment") or "",
        "platform_limits":   list(out.get("platform_limits") or []),
        "roadmap_proposals": proposals,
        "evolved_at":        _now(),
    }
    state["status"]["stage"] = "done"
    state["routing"] = {"current": "evolution", "next": "end",
                        "reason": "cycle complete"}
    return state


# =====================================================================
# Runtime
# =====================================================================


NODES: Dict[str, Callable[..., Any]] = {
    "observation":             observation_node,
    "context_assembly":        context_assembly_node,
    "constitution_validation": constitution_validation_node,
    "reasoning":               reasoning_node,
    "agent_routing":           agent_routing_node,
    "execution":               execution_node,
    "monitoring":              monitoring_node,
    "learning":                learning_node,
    "improvement":             improvement_node,
    "evolution":               evolution_node,
}

NODE_ORDER = [
    "observation", "context_assembly", "constitution_validation",
    "reasoning", "agent_routing", "execution",
    "monitoring", "learning", "improvement", "evolution",
]

MAX_HOPS = 30


async def _run_node(name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    fn = NODES.get(name)
    if fn is None:
        raise RuntimeError(f"unknown node: {name}")
    return (await fn(state)) or state


async def run_os_cycle(
    event: Dict[str, Any],
    *,
    persist: bool = True,
) -> Dict[str, Any]:
    """Run one full Observe→Evolve cycle on the given event.

    Returns the final state dict.  When `persist=True`, the final state
    is also written to `db.hermes_os_cycles` keyed by `cycle_id`.
    """
    state = _initial_state(event or {})
    _trace(state, "graph", "cycle start")

    hops = 0
    while True:
        nxt = (state.get("routing") or {}).get("next") or "end"
        if nxt in (None, "", "end"):
            _trace(state, "graph", f"cycle end (stage={state['status']['stage']})")
            break
        if hops >= MAX_HOPS:
            state["status"]["stage"] = "error"
            state["status"]["error"] = {"code": "hop_limit",
                                        "reason": f"exceeded {MAX_HOPS} hops"}
            _trace(state, "graph", "STOP — hop limit")
            break
        try:
            state = await _run_node(nxt, state)
        except Exception as e:  # noqa: BLE001
            logger.exception("hermes_os node %s crashed: %s", nxt, e)
            state["status"]["stage"] = "error"
            state["status"]["error"] = {"code": "node_crash",
                                        "node": nxt, "reason": str(e)}
            state["routing"] = {"current": nxt, "next": "end",
                                "reason": "node crashed"}
        hops += 1

    state["finished_at"] = _now()
    state["hops"] = hops

    # Cache a compact summary into Short-Term Memory so the NEXT cycle for
    # the same user/company can see what just happened in O(1).
    try:
        hmem.stm_remember_cycle(
            cycle_id=state["cycle_id"],
            user_id=state["event"].get("user_id"),
            company_id=state["event"].get("company_id"),
            event_kind=state["event"].get("kind", "generic"),
            summary=state.get("observation", {}).get("summary", ""),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("stm_remember_cycle failed: %s", e)

    if persist:
        try:
            db = get_db()
            await db.hermes_os_cycles.insert_one({
                "cycle_id":   state["cycle_id"],
                "event":      state["event"],
                "status":     state["status"],
                "stages": {
                    "observation":   state["observation"],
                    "context":       state["context"],
                    "validation":    state["validation"],
                    "reasoning":     state["reasoning"],
                    "routing_plan":  state["routing_plan"],
                    "execution":     state["execution"],
                    "monitoring":    state["monitoring"],
                    "learning":      state["learning"],
                    "improvement":   state["improvement"],
                    "evolution":     state["evolution"],
                },
                "history":     state["history"],
                "started_at":  state["started_at"],
                "finished_at": state["finished_at"],
                "hops":        hops,
            })
        except Exception as e:  # noqa: BLE001
            logger.warning("hermes_os persistence failed: %s", e)

    return state


def list_node_order() -> List[str]:
    return list(NODE_ORDER)
