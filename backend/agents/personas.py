"""Compatibility shim for the legacy persona layer during Phase 1 cleanup."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from agents.legacy import personas_legacy as _legacy
from agents import ai_mentor as _aim
from core.company_context import get_settings as get_company_settings, render_company_block
from core.db import TenantAwareCRUD, get_db
from core.nxt8_graph import nxt8_graph

PERSONAS = _legacy.PERSONAS
PLANS = _legacy.PLANS
MAX_ITER = _legacy.MAX_ITER
get_plan = _legacy.get_plan
list_personas = _legacy.list_personas

SKILL_ROUTED_PERSONAS = {
    "hr_mentor",
    "analyst",
    "client_manager",
    "bookkeeper",
    "marketer",
    "compliance",
    "project_coord",
    "hermes",
}


async def _build_skill_context_blocks(persona_id: str, company_id: str, user_id: str):
    blocks = []
    cfg = PERSONAS.get(persona_id) or {}
    for fetcher in cfg.get("data_fetchers") or []:
        if fetcher == "user_skill_profile":
            block = await _aim.build_user_skill_block(user_id or "anon", company_id or "default")
            if block:
                blocks.append(block)
            continue
        fn = _legacy._FETCHER_DISPATCH.get(fetcher)
        if not fn:
            continue
        try:
            if fetcher == "mentor_overview":
                block = await fn(company_id or "default")
            else:
                block = await fn()
        except Exception:
            block = ""
        if block:
            blocks.append(block)

    try:
        company_settings = await get_company_settings(company_id)
        company_block = render_company_block(company_settings)
        if company_block:
            blocks.append(company_block)
    except Exception:
        pass
    return blocks


async def _run_skill_persona(
    persona_id: str,
    message: str,
    company_id: str,
    user_id: str,
    session_id: str | None,
    plan_id: str | None,
):
    if persona_id not in PERSONAS:
        return {"success": False, "error": f"unknown persona: {persona_id}"}

    plan = get_plan(plan_id)
    if persona_id not in plan["personas"]:
        return {
            "success": False,
            "error": f"persona '{persona_id}' недоступна на тарифе '{plan['id']}'",
            "current_plan": plan["id"],
            "required_plan": _legacy._min_plan_for(persona_id),
        }

    sid = session_id or f"persona_{persona_id}_{uuid.uuid4().hex[:10]}"
    ctx_blocks = await _build_skill_context_blocks(persona_id, company_id, user_id)
    initial_messages = []
    if ctx_blocks:
        initial_messages.append({
            "role": "system",
            "content": "## Текущий контекст\n\n" + "\n\n".join(ctx_blocks),
        })
    initial_messages.append({"role": "user", "content": message})

    config = {"configurable": {"thread_id": sid}}
    result = await nxt8_graph.ainvoke(
        {
            "messages": initial_messages,
            "skill_id": persona_id,
            "company_id": company_id,
            "user_id": user_id,
            "session_id": sid,
        },
        config,
    )

    full_messages = result.get("messages") or []
    tool_traces = []
    for item in full_messages:
        if item.get("role") != "tool":
            continue
        tool_result = {}
        try:
            tool_result = json.loads(item.get("content") or "{}")
        except json.JSONDecodeError:
            tool_result = {"raw": item.get("content")}
        tool_traces.append({"name": item.get("name"), "args": {}, "result": tool_result})

    assistant_messages = [m for m in full_messages if m.get("role") == "assistant"]
    last_content = assistant_messages[-1].get("content", "") if assistant_messages else ""

    try:
        await TenantAwareCRUD(get_db().persona_requests, company_id=company_id).insert_one(
            {
                "id": str(uuid.uuid4()),
                "persona_id": persona_id,
                "company_id": company_id,
                "user_id": user_id,
                "session_id": sid,
                "plan_id": plan["id"],
                "message": message,
                "response": last_content,
                "tool_traces": tool_traces,
                "iterations": result.get("iterations", 1),
                "confidence": result.get("confidence", 0.7),
                "provider": "nxt8_graph",
                "mock": bool(result.get("mock", False)),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        pass

    return {
        "success": True,
        "persona_id": persona_id,
        "persona_name": PERSONAS[persona_id]["name"],
        "session_id": sid,
        "content": last_content,
        "tool_traces": tool_traces,
        "iterations": result.get("iterations", 1),
        "confidence": round(float(result.get("confidence", 0.7)), 4),
        "provider": "nxt8_graph",
        "mock": bool(result.get("mock", False)),
        "plan_id": plan["id"],
        "tokens_total": int(result.get("tokens_total", 0)),
    }


async def run_persona(
    persona_id: str,
    message: str,
    company_id: str = "default",
    user_id: str = "anonymous",
    session_id: str | None = None,
    plan_id: str | None = None,
):
    if persona_id not in SKILL_ROUTED_PERSONAS:
        return await _legacy.run_persona(
            persona_id=persona_id,
            message=message,
            company_id=company_id,
            user_id=user_id,
            session_id=session_id,
            plan_id=plan_id,
        )

    return await _run_skill_persona(
        persona_id=persona_id,
        message=message,
        company_id=company_id,
        user_id=user_id,
        session_id=session_id,
        plan_id=plan_id,
    )


def __getattr__(name: str):
    return getattr(_legacy, name)


