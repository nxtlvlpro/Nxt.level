"""
NXT8 Ultra orchestrator on LangGraph.

Graph layout:
    supervisor → [router] → END | hermes | tools | human_approval
    hermes / tools / human_approval → supervisor

Router rules:
- autonomy_level=read_only AND hermes already answered → END
- requires_human_approval=True AND not yet approved → human_approval (one-shot)
- last assistant message has tool_calls (and not yet executed) → tools
- iterations >= MAX_ITER → END
- no assistant yet → hermes
- otherwise → END

Tool calls are surfaced by the LLM as JSON inside the assistant message; we
parse them safely. (DeepSeek :free does not natively emit OpenAI-style
function_call objects, so we use a deterministic JSON convention.)

Graceful fallback: if langgraph isn't importable, `run_nxt8_ultra` returns
`hermes_coo_chat(...)` result directly.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from typing_extensions import Annotated, TypedDict

logger = logging.getLogger("nxt8.graph")

MAX_ITER = 3

try:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver  # langgraph >=1.0
except Exception:  # noqa: BLE001
    try:
        from langgraph.checkpoint.memory import MemorySaver  # type: ignore
    except Exception:  # noqa: BLE001
        MemorySaver = None  # type: ignore

try:
    from langgraph.graph import END, StateGraph
    from langgraph.graph.message import add_messages

    LANGGRAPH_OK = True
except Exception as e:  # noqa: BLE001
    LANGGRAPH_OK = False
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore
    add_messages = lambda a, b: (a or []) + (b or [])  # type: ignore # noqa: E731
    logger.warning("LangGraph не удалось загрузить: %s", e)

from agents.hermes_max_tools_and_coo import HERMES_TOOLS, hermes_coo_chat


# =====================================================================
# State
# =====================================================================


class AgentState(TypedDict, total=False):
    messages: Annotated[List[Dict[str, Any]], add_messages]
    company_id: str
    user_id: Optional[str]
    session_id: str
    autonomy_level: str
    confidence: float
    requires_human_approval: bool
    iterations: int
    pending_tool_calls: List[Dict[str, Any]]
    tool_traces: List[Dict[str, Any]]
    approved: bool
    tools_just_executed: bool
    tokens_total: int
    mock: bool


# =====================================================================
# Tool-call extraction from assistant content
# =====================================================================

_TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\"tool\".*?\})\s*```", re.DOTALL | re.IGNORECASE
)


def _extract_tool_calls(content: str) -> List[Dict[str, Any]]:
    """Find ```json {"tool":"name","args":{...}}``` blocks; return parsed calls."""
    if not content:
        return []
    calls: List[Dict[str, Any]] = []
    for match in _TOOL_JSON_RE.findall(content):
        try:
            obj = json.loads(match)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("tool") in HERMES_TOOLS:
            calls.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "name": obj["tool"],
                    "args": obj.get("args") or {},
                }
            )
    return calls


# =====================================================================
# Nodes
# =====================================================================


async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    # No state mutation — router decides next hop
    return {}


async def hermes_node(state: AgentState) -> Dict[str, Any]:
    resp = await hermes_coo_chat(
        state.get("messages", []),
        state.get("company_id", "default"),
        state.get("autonomy_level", "assistant"),
    )
    content = resp.get("content", "")
    tool_calls = _extract_tool_calls(content)

    # Critical-action gate: in controlled_automation, write tools require approval
    critical = {"create_task", "update_task", "create_cross_department_bridge"}
    requires_approval = (
        state.get("autonomy_level") == "controlled_automation"
        and any(tc["name"] in critical for tc in tool_calls)
        and not state.get("approved")
    )

    assistant_msg = {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
    }
    return {
        "messages": [assistant_msg],
        "confidence": resp.get("confidence", 0.7),
        "iterations": state.get("iterations", 0) + 1,
        "pending_tool_calls": tool_calls,
        "requires_human_approval": requires_approval,
        # Reset the tools-just-executed flag — Hermes has now consumed
        # the tool results (if any) and produced its next message.
        "tools_just_executed": False,
        "tokens_total": int(state.get("tokens_total", 0) or 0) + int(resp.get("tokens_total", 0) or 0),
        "mock": bool(state.get("mock")) or bool(resp.get("mock")),
    }


async def tools_node(state: AgentState) -> Dict[str, Any]:
    pending = state.get("pending_tool_calls") or []
    if not pending:
        return {"pending_tool_calls": []}
    traces = list(state.get("tool_traces") or [])
    tool_messages: List[Dict[str, Any]] = []
    company_id = state.get("company_id", "default")
    for tc in pending:
        name = tc.get("name")
        args = dict(tc.get("args") or {})
        args.setdefault("company_id", company_id)
        fn = HERMES_TOOLS.get(name)
        if not fn:
            result = {"ok": False, "error": f"unknown tool: {name}"}
        else:
            try:
                result = await fn(args)
            except Exception as e:  # noqa: BLE001
                logger.exception("tool %s failed", name)
                result = {"ok": False, "error": str(e)}
        traces.append({"name": name, "args": args, "result": result})
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
    return {
        "messages": tool_messages,
        "pending_tool_calls": [],
        "tool_traces": traces,
        # Signal the router to bounce back into Hermes so the LLM can
        # incorporate tool results into a proper final answer (fixes the
        # "user sees raw ```json block" bug).
        "tools_just_executed": True,
    }


async def human_approval_node(state: AgentState) -> Dict[str, Any]:
    """Pilot stub: surface the pending tool calls and clear approval flag.
    Real production would block here for an out-of-band approval signal."""
    pending = state.get("pending_tool_calls") or []
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "⚠ Human approval required for "
                    f"{len(pending)} critical action(s): "
                    f"{', '.join(tc.get('name', '?') for tc in pending)}."
                ),
            }
        ],
        "requires_human_approval": True,
        "pending_tool_calls": [],
    }


# =====================================================================
# Router
# =====================================================================


def _router(state: AgentState):
    iterations = state.get("iterations", 0)
    autonomy = state.get("autonomy_level", "assistant")
    if iterations >= MAX_ITER:
        return END
    if state.get("requires_human_approval") and not state.get("approved"):
        return "human_approval"
    if state.get("pending_tool_calls"):
        return "tools"
    # FIX (architect audit P0-2): after tools executed, return to Hermes so
    # the LLM can produce a proper summary that includes tool results.
    # Without this, user sees raw assistant message with ```json blocks
    # instead of "Создал задачу X. Ожидаемый эффект…".
    if state.get("tools_just_executed"):
        return "hermes"
    if autonomy == "read_only" and iterations >= 1:
        return END
    if iterations == 0:
        return "hermes"
    return END


# =====================================================================
# Build graph
# =====================================================================


def _build_graph():
    if not LANGGRAPH_OK or StateGraph is None:
        return None
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("hermes", hermes_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("human_approval", human_approval_node)

    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        _router,
        {
            "hermes": "hermes",
            "tools": "tools",
            "human_approval": "human_approval",
            END: END,
        },
    )
    workflow.add_edge("hermes", "supervisor")
    workflow.add_edge("tools", "supervisor")
    workflow.add_edge("human_approval", "supervisor")

    if MemorySaver is not None:
        return workflow.compile(checkpointer=MemorySaver())
    return workflow.compile()


ultra_graph = _build_graph()
if ultra_graph is not None:
    logger.info("Ultra LangGraph compiled (MAX_ITER=%s)", MAX_ITER)
else:
    logger.warning("Ultra LangGraph NOT compiled — Ultra endpoint will fallback")


# =====================================================================
# Public entrypoint
# =====================================================================


async def run_nxt8_ultra(
    message: str,
    company_id: str = "default",
    user_id: str = "anonymous",
    session_id: Optional[str] = None,
    autonomy_level: str = "assistant",
) -> Dict[str, Any]:
    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"

    if ultra_graph is None:
        resp = await hermes_coo_chat(
            [{"role": "user", "content": message}], company_id, autonomy_level
        )
        return {
            **resp,
            "thread_id": sid,
            "fallback": "no_langgraph",
            "tool_traces": [],
        }

    try:
        config = {"configurable": {"thread_id": sid}}
        initial: AgentState = {
            "messages": [{"role": "user", "content": message}],
            "company_id": company_id,
            "user_id": user_id,
            "session_id": sid,
            "autonomy_level": autonomy_level,
            "confidence": 0.0,
            "requires_human_approval": False,
            "iterations": 0,
            "pending_tool_calls": [],
            "tool_traces": [],
            "approved": False,
            "tools_just_executed": False,
        }
        result: Dict[str, Any] = await ultra_graph.ainvoke(initial, config)
        # Pull the last assistant message content
        msgs = result.get("messages") or []
        content = ""
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "assistant":
                content = m.get("content", "")
                break
            # langgraph may wrap messages with .content attribute objects
            mc = getattr(m, "content", None)
            mr = getattr(m, "type", None) or getattr(m, "role", None)
            if mc and mr in ("ai", "assistant"):
                content = mc
                break

        return {
            "content": content,
            "autonomy_level": autonomy_level,
            "thread_id": sid,
            "confidence": result.get("confidence", 0.7),
            "iterations": result.get("iterations", 0),
            "tool_traces": result.get("tool_traces") or [],
            "requires_human_approval": bool(result.get("requires_human_approval")),
            "tokens_total": int(result.get("tokens_total", 0) or 0),
            "mock": bool(result.get("mock")),
            "success": True,
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("LangGraph run failed: %s", e)
        resp = await hermes_coo_chat(
            [{"role": "user", "content": message}], company_id, autonomy_level
        )
        return {
            **resp,
            "thread_id": sid,
            "fallback": "langgraph_error",
            "error": str(e),
            "tool_traces": [],
        }
