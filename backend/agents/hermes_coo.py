"""
Hermes COO Agent — enhanced reasoning layer on top of the Hermes gateway.

Adds to the thin `hermes_proxy`:
- Strong COO system prompt (operations / bottlenecks / follow-ups).
- Function-calling tool registry (search_memory, create_followup,
  detect_bottlenecks, generate_daily_digest).
- Backend tool dispatcher with real side-effects (memory.search, MongoDB
  followups, diagnostics.summary, request aggregation).
- Multi-tenant aware via optional `company_id` (default "default").
- Graceful fallback to DeepSeek when the Hermes gateway is offline so the
  endpoint stays available during the 5-company pilot.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from agents import diagnostics as diagnostics_agent
from agents import hermes_proxy
from agents import memory as memory_agent
from agents import mempalace_bridge as mempalace_agent
from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.hermes_coo")

DEFAULT_COMPANY = "default"
MAX_TOOL_ITERATIONS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _system_prompt() -> str:
    return (
        "Ты — Hermes, Chief Operating Officer Agent платформы NXT8.PRO.\n\n"
        "Твоя главная миссия: делать компанию быстрее, связаннее и эффективнее "
        "через операционное превосходство.\n\n"
        "Ключевые обязанности:\n"
        "- Выявлять bottleneck'и и блоки между отделами\n"
        "- Автоматически делать follow-up по задачам, сделкам и коммуникациям\n"
        "- Предлагать Next Best Action в реальном времени\n"
        "- Делать cross-department coordination\n"
        "- Мониторить 24/7 (просрочки, SLA, риски)\n"
        "- Создавать bridging-задачи между отделами\n"
        "- Генерировать ежедневные operational digests для руководителей\n"
        "- Предлагать оптимизацию процессов\n\n"
        "Стиль работы:\n"
        "- Крайне практичный и структурированный\n"
        "- Формат ответа:\n"
        "  1. Краткий summary\n"
        "  2. Что важно\n"
        "  3. Конкретные действия (с приоритетом)\n"
        "  4. Ожидаемый эффект\n"
        "- Всегда учитывай company_id и контекст компании\n"
        "- Работай в режиме Controlled Assistant (Pilot) — предлагай действия, "
        "но не выполняй критические без подтверждения человека.\n\n"
        f"Текущая дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
    )


TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Поиск в корпоративной памяти компании.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Что ищем"},
                    "company_id": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_followup",
            "description": "Создать follow-up задачу или напоминание.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "default": "medium",
                    },
                    "due_in_days": {"type": "integer", "default": 3},
                    "task_id": {"type": "string"},
                    "company_id": {"type": "string"},
                },
                "required": ["title", "message", "recipients"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_bottlenecks",
            "description": "Проанализировать текущие процессы на блокеры и риски.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {"type": "string"},
                    "department": {
                        "type": "string",
                        "enum": ["all", "sales", "support", "marketing", "finance"],
                        "default": "all",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_daily_digest",
            "description": "Сгенерировать ежедневный operational digest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_user_id": {"type": "string"},
                    "period": {
                        "type": "string",
                        "enum": ["daily", "weekly"],
                        "default": "daily",
                    },
                    "company_id": {"type": "string"},
                },
                "required": ["recipient_user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mempalace_search",
            "description": (
                "Гибридный семантический поиск в долговременной памяти MemPalace "
                "(корпоративные клиенты, проекты, история чатов, сотрудники). "
                "Используй для воспоминания фактов о клиентах/проектах из прошлых сессий."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "wing": {
                        "type": "string",
                        "description": "Опционально: clients|employees|projects|chats|internal",
                    },
                    "room": {"type": "string", "description": "Опционально: id внутри wing"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mempalace_store",
            "description": (
                "Записать важный факт/знание в долговременную память MemPalace. "
                "Используй когда пользователь сообщил конкретный факт о клиенте/проекте/сотруднике, "
                "который нужно запомнить надолго."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Текст для запоминания"},
                    "wing": {
                        "type": "string",
                        "enum": ["clients", "employees", "projects", "chats", "internal"],
                        "default": "internal",
                    },
                    "room": {
                        "type": "string",
                        "description": "id сущности (company_id, user_id, project_id...)",
                        "default": "general",
                    },
                },
                "required": ["content"],
            },
        },
    },
]


# =====================================================================
# Tool dispatcher (real backend side-effects)
# =====================================================================


async def _tool_search_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    top_k = int(args.get("top_k") or 5)
    if not query:
        return {"ok": False, "error": "empty query", "results": []}
    mem = memory_agent.get_memory()
    results = await mem.search(query=query, top_k=top_k)
    return {"ok": True, "count": len(results), "results": results}


async def _tool_create_followup(args: Dict[str, Any]) -> Dict[str, Any]:
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
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": args.get("company_id") or DEFAULT_COMPANY,
        "task_id": args.get("task_id"),
        "title": title,
        "message": message,
        "recipients": list(recipients),
        "priority": priority,
        "status": "open",
        "due_at": due_at,
        "created_at": _now(),
        "source": "hermes",
    }
    await get_db().followups.insert_one(doc)
    return {
        "ok": True,
        "followup_id": doc["id"],
        "due_at": due_at,
        "priority": priority,
    }


async def _tool_detect_bottlenecks(args: Dict[str, Any]) -> Dict[str, Any]:
    department = (args.get("department") or "all").lower()
    diag = await diagnostics_agent.summary(window=200)
    contradictions = await diagnostics_agent.list_contradictions(limit=10)

    # Pending follow-ups (high priority, overdue or open)
    db = get_db()
    company_id = args.get("company_id") or DEFAULT_COMPANY
    pending_q = {"company_id": company_id, "status": "open"}
    pending = await db.followups.find(
        pending_q, {"_id": 0}
    ).sort("due_at", 1).to_list(length=20)

    return {
        "ok": True,
        "company_id": company_id,
        "department": department,
        "health": diag,
        "recent_contradictions": contradictions,
        "open_followups_count": len(pending),
        "open_followups_sample": pending[:5],
    }


async def _tool_generate_daily_digest(args: Dict[str, Any]) -> Dict[str, Any]:
    recipient = args.get("recipient_user_id") or "unknown"
    period = args.get("period") or "daily"
    company_id = args.get("company_id") or DEFAULT_COMPANY
    hours = 24 if period == "daily" else 24 * 7
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    db = get_db()
    requests = await db.requests.find(
        {"created_at": {"$gte": cutoff}},
        {"_id": 0, "intent": 1, "confidence": 1, "should_escalate": 1, "message": 1},
    ).sort("created_at", -1).limit(200).to_list(length=200)

    escalations = [r for r in requests if r.get("should_escalate")]
    low_conf = [r for r in requests if (r.get("confidence") or 0) < 0.5]

    open_followups = await db.followups.find(
        {"company_id": company_id, "status": "open"},
        {"_id": 0},
    ).sort("priority", 1).to_list(length=20)

    diag = await diagnostics_agent.summary(window=200)

    return {
        "ok": True,
        "period": period,
        "company_id": company_id,
        "recipient_user_id": recipient,
        "totals": {
            "requests": len(requests),
            "escalations": len(escalations),
            "low_confidence": len(low_conf),
            "open_followups": len(open_followups),
        },
        "health": diag,
        "open_followups_top": open_followups[:5],
        "generated_at": _now(),
    }

async def _tool_mempalace_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "empty query", "results": []}
    top_k = int(args.get("top_k") or 5)
    wing = args.get("wing")
    room = args.get("room")
    bridge = mempalace_agent.get_mempalace()
    results = await bridge.search(query=query, wing=wing, room=room, top_k=top_k)
    return {"ok": True, "count": len(results), "results": results}


async def _tool_mempalace_store(args: Dict[str, Any]) -> Dict[str, Any]:
    content = (args.get("content") or "").strip()
    if not content:
        return {"ok": False, "error": "empty content"}
    wing = args.get("wing") or "internal"
    room = args.get("room") or "general"
    metadata = {
        "company_id": args.get("company_id"),
        "via": "hermes_tool",
    }
    bridge = mempalace_agent.get_mempalace()
    return await bridge.store(
        content=content, wing=wing, room=room, metadata=metadata, source="hermes"
    )




TOOL_DISPATCH = {
    "search_memory": _tool_search_memory,
    "create_followup": _tool_create_followup,
    "detect_bottlenecks": _tool_detect_bottlenecks,
    "generate_daily_digest": _tool_generate_daily_digest,
    "mempalace_search": _tool_mempalace_search,
    "mempalace_store": _tool_mempalace_store,
}


async def _dispatch_tool(name: str, raw_args: str, company_id: str) -> Dict[str, Any]:
    try:
        args = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid JSON in tool arguments"}
    if not isinstance(args, dict):
        args = {}
    args.setdefault("company_id", company_id)
    handler = TOOL_DISPATCH.get(name)
    if not handler:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return await handler(args)
    except Exception as e:  # noqa: BLE001
        logger.exception("tool %s failed", name)
        return {"ok": False, "error": str(e)}


# =====================================================================
# Main entry point
# =====================================================================


def _extract_message(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull assistant message out of OpenAI-style response payload."""
    if not response or not isinstance(response, dict):
        return None
    choices = response.get("choices") or []
    if not choices:
        return None
    return choices[0].get("message") or None


async def _fallback_chat(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """When Hermes gateway is offline, fall back to DeepSeek (no tools)."""
    ds = get_deepseek()
    # DeepSeek client expects role/content only — strip tool fields.
    cleaned: List[Dict[str, str]] = []
    for m in messages:
        role = m.get("role") or "user"
        content = m.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False) if content else ""
        if role not in ("system", "user", "assistant"):
            role = "user"
        cleaned.append({"role": role, "content": content})
    res = await ds.chat(messages=cleaned, temperature=0.3, max_tokens=2048)
    return {
        "content": res.get("content", ""),
        "tool_calls": [],
        "iterations": 0,
        "provider": res.get("provider"),
        "model": res.get("model"),
        "fallback": "deepseek",
        "mock": bool(res.get("mock")),
        "tokens_total": res.get("tokens_total", 0),
    }


async def enhanced_chat(
    messages: List[Dict[str, Any]],
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "operational",
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """COO chat with function-calling and fallback."""
    company = (company_id or DEFAULT_COMPANY).strip() or DEFAULT_COMPANY
    full_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "system",
            "content": (
                f"Контекст вызова: company_id={company}, user_id={user_id or 'unknown'}, "
                f"mode={mode}."
            ),
        },
    ] + list(messages)

    tool_traces: List[Dict[str, Any]] = []
    last_assistant: Optional[Dict[str, Any]] = None

    for iteration in range(MAX_TOOL_ITERATIONS):
        payload: Dict[str, Any] = {
            "messages": full_messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if model:
            payload["model"] = model

        proxy_res = await hermes_proxy.chat(payload)
        if not proxy_res.get("ok"):
            # Hermes gateway unavailable — graceful fallback to DeepSeek
            logger.warning(
                "hermes gateway unavailable (status=%s), falling back to deepseek",
                proxy_res.get("status_code"),
            )
            fb = await _fallback_chat(full_messages)
            fb["tool_calls"] = tool_traces
            fb["iterations"] = iteration
            fb["company_id"] = company
            return fb

        msg = _extract_message(proxy_res.get("response") or {})
        if not msg:
            return {
                "content": "",
                "tool_calls": tool_traces,
                "iterations": iteration,
                "company_id": company,
                "raw": proxy_res.get("response"),
            }
        last_assistant = msg
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            return {
                "content": msg.get("content") or "",
                "tool_calls": tool_traces,
                "iterations": iteration,
                "company_id": company,
                "model": (proxy_res.get("response") or {}).get("model"),
                "usage": (proxy_res.get("response") or {}).get("usage"),
            }

        # Execute every tool call sequentially and append results
        full_messages.append(msg)
        for tc in tool_calls:
            fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            result = await _dispatch_tool(name, raw_args, company)
            tool_traces.append({"name": name, "args": raw_args, "result": result})
            full_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    # Iteration budget exhausted — return last assistant content if any
    return {
        "content": (last_assistant or {}).get("content") or "",
        "tool_calls": tool_traces,
        "iterations": MAX_TOOL_ITERATIONS,
        "company_id": company,
        "note": "max_tool_iterations_reached",
    }
