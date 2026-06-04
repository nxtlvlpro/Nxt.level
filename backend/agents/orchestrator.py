"""
Orchestrator Agent for NXT8 (Module 3, central).

Single entry-point for all chat traffic. Per ТЗ pipeline:
1. memory.get_optimal_context  → build short+long context
2. deepseek classify intent
3. specialised processing (knowledge / task / mentor / roi / general)
4. reliability.assess (confidence + contradictions + hallucination)
5. record cost (deepseek tokens) + memory.append_message
6. persist request audit
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents import memory as memory_agent
from agents import reliability as reliability_agent
from agents import roi as roi_agent
from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.orchestrator")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


INTENT_AGENT_MAP = {
    "knowledge": "memory",
    "task": "orchestrator",
    "mentor": "mentor",
    "roi": "roi",
    "voice": "voice",
    "general": "orchestrator",
}


SYSTEM_PROMPT = (
    "Ты NXT8 — AI-операционная система компании. Отвечай по делу, на русском, "
    "ссылайся на корпоративный контекст когда он есть. Не выдумывай факты. "
    "Если не уверен — скажи об этом и предложи эскалацию."
)

CLASSIFY_SYSTEM = (
    "Classify the user's request into ONE of: knowledge, task, mentor, roi, voice, general. "
    "Respond with ONLY the category name."
)


async def route(
    user_id: str,
    session_id: str,
    message: str,
    channel: str = "web",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.time()
    deepseek = get_deepseek()
    mem = memory_agent.get_memory()
    request_id = str(uuid.uuid4())

    # 1. record user message in short-term memory
    await mem.append_message(session_id, "user", message, user_id=user_id)

    # 2. build context (short + long term)
    ctx = await mem.get_optimal_context(message, session_id, max_chars=6000)

    # 3. classify intent
    intent_resp = await deepseek.chat(
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0.0,
        max_tokens=10,
        request_logprobs=False,
    )
    raw_intent = (intent_resp.get("content") or "general").strip().lower().split()[0]
    intent = raw_intent if raw_intent in INTENT_AGENT_MAP else "general"
    target_agent = INTENT_AGENT_MAP[intent]

    await roi_agent.record_api_cost(
        "orchestrator", intent_resp.get("tokens_total", 0)
    )

    # 4. specialised dispatch
    answer = await _generate_answer(
        intent=intent,
        message=message,
        context_str=ctx["context"],
        deepseek=deepseek,
    )

    await roi_agent.record_api_cost(target_agent, answer.get("tokens_total", 0))

    # 5. reliability assessment
    past = [
        m["content"]
        for m in (await mem.get_session(session_id, limit=10))
        if m.get("role") == "assistant"
    ]
    mem_ctx_texts = [r.get("content", "") for r in ctx.get("retrieved", [])]
    rel = reliability_agent.assess(
        response=answer.get("content", ""),
        deepseek_confidence=answer.get("confidence", 0.7),
        source="deepseek",
        evidence_count=len(mem_ctx_texts),
        past_responses=past,
        memory_context=mem_ctx_texts,
    )

    # 6. escalation cost if needed
    if rel.should_escalate:
        await roi_agent.record_escalation_cost(target_agent, minutes=5.0)
        await get_db().alerts.insert_one({
            "id": str(uuid.uuid4()),
            "source": "reliability",
            "severity": "warning" if rel.level == "low" else "info",
            "message": f"Escalation triggered for session {session_id} (score={rel.score})",
            "context": {"session_id": session_id, "request_id": request_id},
            "created_at": _now(),
        })

    # 7. record assistant message in short-term memory
    await mem.append_message(session_id, "assistant", answer.get("content", ""), user_id=user_id)

    latency_ms = int((time.time() - t0) * 1000)

    # 8. persist request audit
    audit = {
        "id": request_id,
        "user_id": user_id,
        "session_id": session_id,
        "channel": channel,
        "message": message,
        "intent": intent,
        "agent_chain": ["orchestrator", target_agent],
        "response": answer.get("content", ""),
        "confidence": rel.score,
        "confidence_level": rel.level,
        "should_escalate": rel.should_escalate,
        "verification_status": rel.verification_status,
        "tokens_total": answer.get("tokens_total", 0) + intent_resp.get("tokens_total", 0),
        "latency_ms": latency_ms,
        "mock": bool(answer.get("mock") or intent_resp.get("mock")),
        "created_at": _now(),
    }
    await get_db().requests.insert_one(audit)

    return {
        "request_id": request_id,
        "content": answer.get("content", ""),
        "intent": intent,
        "agent_chain": audit["agent_chain"],
        "confidence": rel.score,
        "confidence_level": rel.level,
        "should_escalate": rel.should_escalate,
        "has_contradiction": rel.has_contradiction,
        "verification_status": rel.verification_status,
        "signals": rel.signals,
        "latency_ms": latency_ms,
        "memory_used": {
            "short_term_chars": ctx.get("short_term_chars", 0),
            "long_term_items": ctx.get("long_term_items", 0),
        },
        "mock": audit["mock"],
        "timestamp": audit["created_at"],
    }


async def _generate_answer(
    intent: str, message: str, context_str: str, deepseek
) -> Dict[str, Any]:
    sys_extra = {
        "knowledge": "User asks about company knowledge. Use provided context strictly.",
        "task": "User wants to schedule / track a task. Be concrete and actionable.",
        "mentor": "User asks about employee performance. Summarise patterns and recommend actions.",
        "roi": "User asks about ROI / costs. Summarise numbers from context, be precise.",
        "voice": "Voice channel — keep response short and clear (1-2 sentences).",
        "general": "Reply helpfully using provided context if relevant.",
    }.get(intent, "Reply helpfully.")

    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{sys_extra}"},
        {"role": "system", "content": f"## Context\n{context_str}"},
        {"role": "user", "content": message},
    ]
    return await deepseek.chat(
        messages=messages,
        temperature=0.5 if intent in ("knowledge", "roi") else 0.7,
        max_tokens=1024,
    )


async def list_recent_requests(limit: int = 20) -> List[Dict[str, Any]]:
    db = get_db()
    return await db.requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)


async def list_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    db = get_db()
    return await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
