"""
Hermes Max Tools + Ultra COO Agent (v1.3.0-ultra).

Adapted from user-provided design to match NXT8's existing API surface:
- memory.append_message (no metadata kwarg)
- memory.search (top_k, no company_id filter — propagated for traces only)
- DeepSeek client via core.deepseek.get_deepseek()
- All "stub" tools tagged with mock=True for pilot transparency.

Tools dispatched manually by hermes_coo Ultra graph (see nxt8_langgraph_ultra.py).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger("nxt8.hermes_max")

DEFAULT_COMPANY = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Tools (each returns {"ok": bool, ...}). Stub-tools include mock=True.
# =====================================================================


async def search_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from agents import memory as memory_agent
        mem = memory_agent.get_memory()
        company_id = args.get("company_id", DEFAULT_COMPANY)
        results = await mem.search(
            query=args.get("query", ""),
            top_k=int(args.get("top_k", 20)),
        )
        return {
            "ok": True,
            "count": len(results),
            "results": results,
            "company_id": company_id,
        }
    except Exception as e:  # noqa: BLE001
        logger.error("search_memory error: %s", e)
        return {"ok": False, "error": str(e)}


async def create_task(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from core.db import get_db
        doc = {
            "id": str(uuid.uuid4()),
            "company_id": args.get("company_id", DEFAULT_COMPANY),
            "title": args.get("title"),
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
        if not doc["title"]:
            return {"ok": False, "error": "title is required"}
        await get_db().tasks.insert_one(doc)
        logger.info("Hermes created task: %s", doc["title"])
        return {"ok": True, "task_id": doc["id"], "title": doc["title"]}
    except Exception as e:  # noqa: BLE001
        logger.error("create_task error: %s", e)
        return {"ok": False, "error": str(e)}


async def update_task(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from core.db import get_db
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
    except Exception as e:  # noqa: BLE001
        logger.error("update_task error: %s", e)
        return {"ok": False, "error": str(e)}


async def generate_communication_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    """Stub: returns the summary the LLM has already produced."""
    return {
        "ok": True,
        "summary": args.get("summary", ""),
        "suggested_next_action": args.get("suggested_next_action"),
        "mock": True,
    }


async def suggest_next_best_action(args: Dict[str, Any]) -> Dict[str, Any]:
    """Stub: pilot-default Next Best Action."""
    return {
        "ok": True,
        "action": args.get("action") or "Follow-up через 48 часов",
        "confidence": 0.9,
        "context": args.get("context"),
        "mock": True,
    }


async def find_opportunities_in_contact(args: Dict[str, Any]) -> Dict[str, Any]:
    """Stub: returns an example upsell opportunity."""
    return {
        "ok": True,
        "contact_id": args.get("contact_id"),
        "opportunities": [
            {"type": "upsell", "potential": "15000-30000 USD", "confidence": 0.7}
        ],
        "mock": True,
    }


async def create_cross_department_bridge(args: Dict[str, Any]) -> Dict[str, Any]:
    """Real: creates a bridging task between two departments."""
    bridge_args = {
        **args,
        "title": f"Bridge: {args.get('from_dept', '?')} → {args.get('to_dept', '?')}",
        "department": args.get("to_dept"),
        "description": args.get("description")
        or f"Кросс-функциональная координация {args.get('from_dept')} → {args.get('to_dept')}",
    }
    return await create_task(bridge_args)


async def monitor_sla_violations(args: Dict[str, Any]) -> Dict[str, Any]:
    """Real (lightweight): scan tasks past due_at."""
    try:
        from core.db import get_db
        now = _now()
        company_id = args.get("company_id", DEFAULT_COMPANY)
        cursor = get_db().tasks.find(
            {
                "company_id": company_id,
                "status": "open",
                "due_at": {"$ne": None, "$lt": now},
            },
            {"_id": 0, "id": 1, "title": 1, "priority": 1, "due_at": 1},
        )
        items = await cursor.to_list(length=50)
        critical = [t for t in items if t.get("priority") == "high"]
        return {
            "ok": True,
            "violations": len(items),
            "critical": critical,
            "sample": items[:10],
        }
    except Exception as e:  # noqa: BLE001
        logger.error("monitor_sla_violations error: %s", e)
        return {"ok": False, "error": str(e)}


async def suggest_reply_template(args: Dict[str, Any]) -> Dict[str, Any]:
    """Stub: simple template by tone."""
    tone = (args.get("tone") or "professional").lower()
    templates = {
        "professional": "Здравствуйте! Спасибо за обращение — подготовим ответ в течение 24 часов.",
        "friendly": "Привет! Спасибо, что написали — скоро вернёмся с деталями.",
        "concise": "Принято. Ответим в течение 24ч.",
    }
    return {
        "ok": True,
        "template": templates.get(tone, templates["professional"]),
        "tone": tone,
        "mock": True,
    }


async def evaluate_action_roi(args: Dict[str, Any]) -> Dict[str, Any]:
    """Try roi_agent.assess_action_impact, else stub."""
    try:
        from agents import roi as roi_agent
        if hasattr(roi_agent, "assess_action_impact"):
            return await roi_agent.assess_action_impact(args)
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "estimated_roi": "high",
        "value": "12000 USD",
        "horizon_days": 30,
        "mock": True,
    }


HERMES_TOOLS: Dict[str, Any] = {
    "search_memory": search_memory,
    "create_task": create_task,
    "update_task": update_task,
    "generate_communication_summary": generate_communication_summary,
    "suggest_next_best_action": suggest_next_best_action,
    "find_opportunities_in_contact": find_opportunities_in_contact,
    "create_cross_department_bridge": create_cross_department_bridge,
    "monitor_sla_violations": monitor_sla_violations,
    "suggest_reply_template": suggest_reply_template,
    "evaluate_action_roi": evaluate_action_roi,
}


# =====================================================================
# Hermes COO Ultra — single-shot LLM call with strong COO prompt
# =====================================================================


COO_SYSTEM_TEMPLATE = (
    "Ты — Hermes, Chief Operating Officer Agent NXT8.PRO.\n\n"
    "Текущий режим: {mode}\n"
    "Текущая дата: {today}\n\n"
    "Ты — мощный операционный интеллект компании. Ты анализируешь, "
    "координируешь, создаёшь задачи, находишь возможности и ускоряешь "
    "все процессы.\n\n"
    "Формат ответа:\n"
    "1. Краткий summary\n"
    "2. Что важно\n"
    "3. Конкретные действия (с приоритетом)\n"
    "4. Ожидаемый эффект\n\n"
    "Если автономия позволяет — предлагай вызовы инструментов (create_task, "
    "monitor_sla_violations, evaluate_action_roi и т.д.). Не выполняй "
    "критические действия без подтверждения человека.\n\n"
    "ФОРМАТ ВЫЗОВА ИНСТРУМЕНТА (строго JSON в fenced-блоке):\n"
    "```json\n"
    "{{\"tool\":\"create_task\",\"args\":{{\"title\":\"...\",\"department\":\"sales\",\"priority\":\"high\",\"due_at\":\"YYYY-MM-DD\"}}}}\n"
    "```\n"
    "Можно несколько блоков подряд. Доступные tool: search_memory, create_task, "
    "update_task, generate_communication_summary, suggest_next_best_action, "
    "find_opportunities_in_contact, create_cross_department_bridge, "
    "monitor_sla_violations, suggest_reply_template, evaluate_action_roi.\n"
)


async def hermes_coo_chat(
    messages: List[Dict[str, Any]],
    company_id: str = DEFAULT_COMPANY,
    autonomy_level: str = "assistant",
) -> Dict[str, Any]:
    system_prompt = COO_SYSTEM_TEMPLATE.format(
        mode=autonomy_level.upper(),
        today=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    context_msg = {
        "role": "system",
        "content": f"company_id={company_id}, autonomy={autonomy_level}",
    }
    full_messages = [
        {"role": "system", "content": system_prompt},
        context_msg,
    ] + [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant")
    ]

    try:
        from core.deepseek import get_deepseek
        ds = get_deepseek()
        response = await ds.chat(messages=full_messages, temperature=0.3, max_tokens=2048)
        return {
            "content": response.get("content", ""),
            "autonomy_level": autonomy_level,
            "confidence": float(response.get("confidence", 0.7)),
            "mock": bool(response.get("mock")),
            "tokens_total": response.get("tokens_total", 0),
        }
    except Exception as e:  # noqa: BLE001
        logger.error("hermes_coo_chat error: %s", e)
        return {
            "content": "Ошибка Hermes.",
            "autonomy_level": autonomy_level,
            "confidence": 0.4,
            "error": str(e),
        }
