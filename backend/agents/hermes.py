"""
Hermes — unified COO Agent (v1.6.0 unification).

This module is the SINGLE source of truth for Hermes COO behaviour. It
replaces the two legacy modules that diverged historically:

  * agents/hermes_coo.py            (6 tools, OpenAI tool-calling format,
                                     required external gateway @ :8642)
  * agents/hermes_max_tools_and_coo.py
                                    (10 tools, fenced-JSON format,
                                     used by LangGraph Ultra orchestrator)

Per user choice (2026-05-20) the unified module standardises on the
**fenced-JSON tool-calling convention** because it works directly with
DeepSeek (no external gateway required) and is what the LangGraph
orchestrator already parses.

Unified collection: tasks + followups are now stored in a single MongoDB
collection `db.tasks` distinguished by the `kind` field
(`"task"` | `"followup"`). Legacy `db.followups` is still queried on read
for backward compatibility — new writes go to `db.tasks` only.

Public surface (back-compat re-exports live in
`agents/hermes_coo.py` and `agents/hermes_max_tools_and_coo.py`):

  HERMES_TOOLS        — dict[name -> async tool callable]
  hermes_chat()       — DeepSeek call with fenced-JSON tool loop
  enhanced_chat()     — alias for hermes_chat() (legacy name)
  hermes_coo_chat()   — alias for hermes_chat() (legacy name, simpler signature)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.hermes")

DEFAULT_COMPANY = "default"
MAX_TOOL_ITERATIONS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Tool implementations
# =====================================================================


async def _t_search_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import memory as memory_agent
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "empty query", "results": []}
    top_k = int(args.get("top_k") or 5)
    mem = memory_agent.get_memory()
    results = await mem.search(query=query, top_k=top_k)
    return {"ok": True, "count": len(results), "results": results,
            "company_id": args.get("company_id", DEFAULT_COMPANY)}


async def _t_create_task(args: Dict[str, Any]) -> Dict[str, Any]:
    title = (args.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "title is required"}
    doc = {
        "id": str(uuid.uuid4()),
        "kind": args.get("kind", "task"),  # "task" | "followup"
        "company_id": args.get("company_id", DEFAULT_COMPANY),
        "title": title,
        "description": args.get("description", ""),
        "assignee": args.get("assignee"),
        "department": args.get("department"),
        "priority": args.get("priority", "medium"),
        "status": "open",
        "due_at": args.get("due_at"),
        "created_at": _now(),
        "source": "hermes",
        "related_contact": args.get("contact_id"),
        "related_deal": args.get("deal_id"),
    }
    await get_db().tasks.insert_one(doc)
    logger.info("Hermes created %s: %s", doc["kind"], title)
    return {"ok": True, "task_id": doc["id"], "kind": doc["kind"], "title": title}


async def _t_update_task(args: Dict[str, Any]) -> Dict[str, Any]:
    task_id = args.get("task_id")
    if not task_id:
        return {"ok": False, "error": "task_id required"}
    update = {k: v for k, v in args.items() if k not in ("task_id", "company_id")}
    if not update:
        return {"ok": False, "error": "no fields to update"}
    update["updated_at"] = _now()
    result = await get_db().tasks.update_one({"id": task_id}, {"$set": update})
    return {
        "ok": result.modified_count > 0,
        "task_id": task_id,
        "matched": result.matched_count,
        "modified": result.modified_count,
    }


async def _t_create_followup(args: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compat alias: creates a `kind=followup` task in db.tasks."""
    title = (args.get("title") or "").strip()
    message = (args.get("message") or "").strip()
    recipients = args.get("recipients") or []
    if not title or not message or not recipients:
        return {"ok": False, "error": "title, message, recipients are required"}
    priority = args.get("priority") or "medium"
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    due_days = int(args.get("due_in_days") or 3)
    due_at = (datetime.now(timezone.utc) + timedelta(days=due_days)).isoformat()
    payload = {
        "kind": "followup",
        "company_id": args.get("company_id", DEFAULT_COMPANY),
        "title": title,
        "description": message,
        "department": None,
        "priority": priority,
        "due_at": due_at,
        "assignee": recipients[0] if recipients else None,
    }
    res = await _t_create_task(payload)
    if res.get("ok"):
        res["followup_id"] = res.pop("task_id")
        res["due_at"] = due_at
        res["recipients"] = list(recipients)
    return res


async def _t_monitor_sla_violations(args: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    company_id = args.get("company_id", DEFAULT_COMPANY)
    cursor = get_db().tasks.find(
        {"company_id": company_id, "status": "open",
         "due_at": {"$ne": None, "$lt": now}},
        {"_id": 0, "id": 1, "title": 1, "priority": 1, "due_at": 1, "kind": 1},
    )
    items = await cursor.to_list(length=50)
    critical = [t for t in items if t.get("priority") == "high"]
    return {"ok": True, "violations": len(items), "critical": critical,
            "sample": items[:10]}


async def _t_detect_bottlenecks(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import diagnostics as diagnostics_agent
    department = (args.get("department") or "all").lower()
    diag = await diagnostics_agent.summary(window=200)
    contradictions = await diagnostics_agent.list_contradictions(limit=10)
    company_id = args.get("company_id", DEFAULT_COMPANY)
    db = get_db()
    # Read from unified tasks + legacy followups (back-compat)
    pending_new = await db.tasks.find(
        {"company_id": company_id, "kind": "followup", "status": "open"},
        {"_id": 0},
    ).sort("due_at", 1).to_list(length=20)
    pending_legacy = await db.followups.find(
        {"company_id": company_id, "status": "open"},
        {"_id": 0},
    ).sort("due_at", 1).to_list(length=20)
    pending = pending_new + pending_legacy
    return {"ok": True, "company_id": company_id, "department": department,
            "health": diag, "recent_contradictions": contradictions,
            "open_followups_count": len(pending),
            "open_followups_sample": pending[:5]}


async def _t_generate_daily_digest(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import diagnostics as diagnostics_agent
    recipient = args.get("recipient_user_id") or "unknown"
    period = args.get("period") or "daily"
    company_id = args.get("company_id", DEFAULT_COMPANY)
    hours = 24 if period == "daily" else 24 * 7
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    db = get_db()
    requests = await db.requests.find(
        {"created_at": {"$gte": cutoff}},
        {"_id": 0, "intent": 1, "confidence": 1, "should_escalate": 1, "message": 1},
    ).sort("created_at", -1).limit(200).to_list(length=200)
    escalations = [r for r in requests if r.get("should_escalate")]
    low_conf = [r for r in requests if (r.get("confidence") or 0) < 0.5]
    open_followups = await db.tasks.find(
        {"company_id": company_id, "kind": "followup", "status": "open"},
        {"_id": 0},
    ).sort("priority", 1).to_list(length=20)
    open_followups += await db.followups.find(
        {"company_id": company_id, "status": "open"}, {"_id": 0},
    ).sort("priority", 1).to_list(length=20)
    diag = await diagnostics_agent.summary(window=200)
    return {"ok": True, "period": period, "company_id": company_id,
            "recipient_user_id": recipient,
            "totals": {"requests": len(requests),
                       "escalations": len(escalations),
                       "low_confidence": len(low_conf),
                       "open_followups": len(open_followups)},
            "health": diag, "open_followups_top": open_followups[:5],
            "generated_at": _now()}


async def _t_create_cross_department_bridge(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_args = {
        **args,
        "title": f"Bridge: {args.get('from_dept', '?')} → {args.get('to_dept', '?')}",
        "department": args.get("to_dept"),
        "description": args.get("description")
        or f"Кросс-функциональная координация {args.get('from_dept')} → {args.get('to_dept')}",
        "kind": "task",
    }
    return await _t_create_task(bridge_args)


async def _t_mempalace_search(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import mempalace_bridge as mempalace_agent
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "empty query", "results": []}
    top_k = int(args.get("top_k") or 5)
    bridge = mempalace_agent.get_mempalace()
    results = await bridge.search(query=query, wing=args.get("wing"),
                                  room=args.get("room"), top_k=top_k)
    return {"ok": True, "count": len(results), "results": results}


async def _t_mempalace_store(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import mempalace_bridge as mempalace_agent
    content = (args.get("content") or "").strip()
    if not content:
        return {"ok": False, "error": "empty content"}
    bridge = mempalace_agent.get_mempalace()
    return await bridge.store(
        content=content,
        wing=args.get("wing") or "internal",
        room=args.get("room") or "general",
        metadata={"company_id": args.get("company_id"), "via": "hermes_tool"},
        source="hermes",
    )


# ---- legacy stub tools (still mock=True until real impl) -----------


async def _t_generate_communication_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "summary": args.get("summary", ""),
            "suggested_next_action": args.get("suggested_next_action"),
            "mock": True}


async def _t_suggest_next_best_action(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True,
            "action": args.get("action") or "Follow-up через 48 часов",
            "confidence": 0.9, "context": args.get("context"), "mock": True}


async def _t_find_opportunities_in_contact(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "contact_id": args.get("contact_id"),
            "opportunities": [
                {"type": "upsell", "potential": "15000-30000 USD",
                 "confidence": 0.7}
            ],
            "mock": True}


async def _t_suggest_reply_template(args: Dict[str, Any]) -> Dict[str, Any]:
    tone = (args.get("tone") or "professional").lower()
    templates = {
        "professional": "Здравствуйте! Спасибо за обращение — подготовим ответ в течение 24 часов.",
        "friendly": "Привет! Спасибо, что написали — скоро вернёмся с деталями.",
        "concise": "Принято. Ответим в течение 24ч.",
    }
    return {"ok": True, "template": templates.get(tone, templates["professional"]),
            "tone": tone, "mock": True}


async def _t_evaluate_action_roi(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from agents import roi as roi_agent
        if hasattr(roi_agent, "assess_action_impact"):
            return await roi_agent.assess_action_impact(args)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "estimated_roi": "high", "value": "12000 USD",
            "horizon_days": 30, "mock": True}


# =====================================================================
# Unified tool registry
# =====================================================================


HERMES_TOOLS: Dict[str, Any] = {
    # Core real-side-effect tools
    "search_memory": _t_search_memory,
    "create_task": _t_create_task,
    "update_task": _t_update_task,
    "create_followup": _t_create_followup,
    "create_cross_department_bridge": _t_create_cross_department_bridge,
    "monitor_sla_violations": _t_monitor_sla_violations,
    "detect_bottlenecks": _t_detect_bottlenecks,
    "generate_daily_digest": _t_generate_daily_digest,
    "mempalace_search": _t_mempalace_search,
    "mempalace_store": _t_mempalace_store,
    # Legacy stub tools (mock=True; honored by tests/test_hermes_ultra.py)
    "generate_communication_summary": _t_generate_communication_summary,
    "suggest_next_best_action": _t_suggest_next_best_action,
    "find_opportunities_in_contact": _t_find_opportunities_in_contact,
    "suggest_reply_template": _t_suggest_reply_template,
    "evaluate_action_roi": _t_evaluate_action_roi,
}


_TOOLS_DOC = (
    "Доступные инструменты (вызывать строго fenced-JSON):\n"
    "- `search_memory(query, top_k?)` — поиск по корп. памяти\n"
    "- `create_task(title, description?, department?, priority?, due_at?, kind?)` — задача\n"
    "- `update_task(task_id, status?, priority?, ...)` — обновить\n"
    "- `create_followup(title, message, recipients, priority?, due_in_days?)` — follow-up задача\n"
    "- `create_cross_department_bridge(from_dept, to_dept, description?)` — мост между отделами\n"
    "- `monitor_sla_violations()` — просроченные задачи\n"
    "- `detect_bottlenecks(department?)` — здоровье процессов\n"
    "- `generate_daily_digest(recipient_user_id, period?)` — оперативный дайджест\n"
    "- `mempalace_search(query, wing?, room?, top_k?)` — долговременная память\n"
    "- `mempalace_store(content, wing?, room?)` — записать факт\n"
    "- `suggest_reply_template(tone)` — шаблон ответа\n"
    "- `suggest_next_best_action(action?, context?)` — NBA\n"
    "- `find_opportunities_in_contact(contact_id)` — апсейл\n"
    "- `evaluate_action_roi(action)` — оценка ROI\n"
    "- `generate_communication_summary(summary)` — резюме переписки"
)


# =====================================================================
# Tool-call extraction (fenced-JSON convention)
# =====================================================================

_TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\"tool\".*?\})\s*```", re.DOTALL | re.IGNORECASE
)


def extract_tool_calls(content: str) -> List[Dict[str, Any]]:
    if not content:
        return []
    calls: List[Dict[str, Any]] = []
    for match in _TOOL_JSON_RE.findall(content):
        try:
            obj = json.loads(match)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("tool") in HERMES_TOOLS:
            calls.append({"id": str(uuid.uuid4())[:8],
                          "name": obj["tool"], "args": obj.get("args") or {}})
    return calls


# =====================================================================
# Chat function (single unified entry point)
# =====================================================================


def _system_prompt(mode: str = "operational", autonomy: str = "assistant") -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        "Ты — Hermes, Chief Operating Officer Agent NXT8.PRO. Сердце операционной "
        "системы компании.\n\n"
        f"Режим: {mode}; Автономность: {autonomy.upper()}; Дата: {today}\n\n"
        "Твои обязанности:\n"
        "- Выявлять bottleneck'и и блоки между отделами\n"
        "- Делать follow-up по задачам, сделкам и коммуникациям\n"
        "- Предлагать Next Best Action в реальном времени\n"
        "- Кросс-департаментная координация и SLA-мониторинг\n"
        "- Генерировать operational digests для руководителей\n\n"
        "Формат ответа:\n"
        "1) Summary; 2) Что важно; 3) Действия (с приоритетом); 4) Ожидаемый эффект.\n\n"
        "Если нужен инструмент — вызови его строго в формате fenced-JSON:\n"
        "```json\n"
        '{"tool":"<name>","args":{...}}\n'
        "```\n"
        "Можно несколько блоков подряд. После выполнения тебе вернут результат, "
        "и ты сделаешь финальный структурированный ответ.\n"
        "Не выполняй критические действия (create_*, update_*, *_bridge) без "
        "подтверждения, если autonomy != controlled_automation.\n\n"
        f"{_TOOLS_DOC}"
    )


async def hermes_chat(
    messages: List[Dict[str, Any]],
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "operational",
    autonomy_level: str = "assistant",
    temperature: float = 0.3,
    model: Optional[str] = None,  # accepted for back-compat, ignored
) -> Dict[str, Any]:
    """Unified Hermes chat: DeepSeek + fenced-JSON tool loop.

    Replaces legacy `hermes_coo.enhanced_chat` and `hermes_max...hermes_coo_chat`.
    """
    company = (company_id or DEFAULT_COMPANY).strip() or DEFAULT_COMPANY
    full_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(mode, autonomy_level)},
        {"role": "system", "content": (
            f"Контекст вызова: company_id={company}, user_id={user_id or 'unknown'}, "
            f"mode={mode}, autonomy={autonomy_level}.")},
    ]
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or "user"
        content = m.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False) if content else ""
        if role not in ("system", "user", "assistant"):
            role = "user"
        full_messages.append({"role": role, "content": content})

    deepseek = get_deepseek()
    tool_traces: List[Dict[str, Any]] = []
    last_content = ""
    iterations = 0
    confidence = 0.7
    mock = False
    tokens_total = 0
    provider = None

    for iteration in range(MAX_TOOL_ITERATIONS + 1):
        iterations = iteration + 1
        resp = await deepseek.chat(messages=full_messages,
                                   temperature=temperature, max_tokens=2048)
        last_content = (resp.get("content") or "").strip()
        confidence = float(resp.get("confidence") or 0.7)
        mock = mock or bool(resp.get("mock"))
        tokens_total += int(resp.get("tokens_total") or 0)
        provider = resp.get("provider") or provider

        if iteration >= MAX_TOOL_ITERATIONS:
            break

        tool_calls = extract_tool_calls(last_content)
        if not tool_calls:
            break

        full_messages.append({"role": "assistant", "content": last_content})
        for tc in tool_calls:
            name = tc["name"]
            args = dict(tc.get("args") or {})
            args.setdefault("company_id", company)
            fn = HERMES_TOOLS.get(name)
            try:
                result = await fn(args) if fn else {"ok": False, "error": f"unknown tool: {name}"}
            except Exception as e:  # noqa: BLE001
                logger.exception("hermes tool %s failed", name)
                result = {"ok": False, "error": str(e)}
            tool_traces.append({"name": name, "args": args, "result": result})
            full_messages.append({
                "role": "system",
                "content": f"## Результат `{name}`\n```json\n{json.dumps(result, ensure_ascii=False)[:1500]}\n```",
            })

    return {
        "content": last_content,
        "tool_calls": tool_traces,
        "iterations": iterations,
        "company_id": company,
        "confidence": confidence,
        "mock": mock,
        "tokens_total": tokens_total,
        "provider": provider,
        "autonomy_level": autonomy_level,
    }


# =====================================================================
# Back-compat aliases (do NOT use in new code)
# =====================================================================


async def enhanced_chat(
    messages: List[Dict[str, Any]],
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "operational",
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Legacy alias for `hermes_chat` (formerly in agents/hermes_coo.py)."""
    return await hermes_chat(
        messages=messages, company_id=company_id, user_id=user_id,
        mode=mode, temperature=temperature, model=model,
    )


async def hermes_coo_chat(
    messages: List[Dict[str, Any]],
    company_id: str = DEFAULT_COMPANY,
    autonomy_level: str = "assistant",
) -> Dict[str, Any]:
    """Legacy alias for `hermes_chat` (formerly in agents/hermes_max_tools_and_coo.py).

    Returns the same shape the LangGraph orchestrator expects:
        content, autonomy_level, confidence, mock, tokens_total
    """
    res = await hermes_chat(
        messages=messages, company_id=company_id, mode="operational",
        autonomy_level=autonomy_level, temperature=0.3,
    )
    return {
        "content": res["content"],
        "autonomy_level": autonomy_level,
        "confidence": res["confidence"],
        "mock": res["mock"],
        "tokens_total": res["tokens_total"],
        "tool_calls": res.get("tool_calls", []),
    }
