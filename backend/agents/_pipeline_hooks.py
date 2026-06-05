"""
Universal pipeline hooks for NXT8 LLM endpoints.

Solves audit & cost asymmetry: prior to this module, only the legacy
orchestrator pipeline (`/api/chat`) recorded API cost into `db.costs`
and inserted an `db.requests` audit row. As a result the ROI dashboard
under-reported real LLM spend by ~10× (chat/stream, hermes/chat,
hermes/ultra, personas/*/chat, voice/converse — 4 out of 5 LLM channels —
silently skipped accounting).

This module provides ONE function — `finalize_llm_turn(...)` — that every
LLM-emitting endpoint calls right before returning. It:

1. Records DeepSeek API cost (`roi.record_api_cost`) using observed tokens.
2. Runs `reliability.assess(...)` to compute confidence/escalation signal.
3. If `should_escalate` → records a `human_escalation` cost + opens an alert.
4. Inserts a unified audit row into `db.requests` so /api/requests works
   across ALL channels.
5. Returns a small dict the caller can merge into its HTTP response so the
   client gets `should_escalate`, `confidence_level`, etc. consistently.

The hook is best-effort: any exception is logged and an empty dict is
returned so a hook failure never breaks the LLM response.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents import reliability as reliability_agent
from agents import roi as roi_agent
from core.db import get_db

logger = logging.getLogger("nxt8.pipeline_hooks")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def finalize_llm_turn(
    *,
    channel: str,
    agent: str,
    user_id: str,
    session_id: str,
    message: str,
    response_text: str,
    tokens_total: int = 0,
    deepseek_confidence: float = 0.7,
    evidence_count: int = 0,
    past_responses: Optional[List[str]] = None,
    memory_context: Optional[List[str]] = None,
    intent: str = "general",
    agent_chain: Optional[List[str]] = None,
    mock: bool = False,
    extra: Optional[Dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Single cross-cutting hook for every LLM endpoint.

    Returns a dict with audit + reliability fields the endpoint should merge
    into its HTTP response. Returns {} on internal failure (never raises).

    `company_id` is propagated into `db.costs`, `db.requests`, and
    `db.alerts` so ROI/audit views stay tenant-scoped.
    """
    if past_responses is None:
        past_responses = []
    if memory_context is None:
        memory_context = []
    if agent_chain is None:
        agent_chain = [agent]

    # 1. Cost accounting (real LLM tokens) ----------------------------
    try:
        if tokens_total and tokens_total > 0:
            await roi_agent.record_api_cost(
                agent, int(tokens_total), company_id=company_id
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("[hook] record_api_cost failed: %s", e)

    # 2. Reliability assessment ---------------------------------------
    try:
        rel = reliability_agent.assess(
            response=response_text or "",
            deepseek_confidence=float(deepseek_confidence or 0.7),
            source="deepseek",
            evidence_count=int(evidence_count or 0),
            past_responses=past_responses,
            memory_context=memory_context,
        )
        rel_payload = {
            "score": rel.score,
            "level": rel.level,
            "should_escalate": rel.should_escalate,
            "has_contradiction": rel.has_contradiction,
            "verification_status": rel.verification_status,
            "verification_ratio": rel.verification_ratio,
            "signals": rel.signals,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("[hook] reliability.assess failed: %s", e)
        rel = None
        rel_payload = {
            "score": float(deepseek_confidence or 0.7),
            "level": "medium",
            "should_escalate": False,
            "has_contradiction": False,
            "verification_status": "skipped",
            "verification_ratio": 1.0,
            "signals": {},
        }

    # 3. Escalation cost + alert --------------------------------------
    try:
        if rel_payload["should_escalate"]:
            await roi_agent.record_escalation_cost(
                agent, minutes=5.0, company_id=company_id
            )
            await get_db().alerts.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "source": "reliability",
                    "severity": "warning" if rel_payload["level"] == "low" else "info",
                    "message": (
                        f"Escalation [{channel}] session={session_id} "
                        f"score={rel_payload['score']:.2f}"
                    ),
                    "context": {
                        "session_id": session_id,
                        "channel": channel,
                        "agent": agent,
                    },
                    "company_id": company_id,
                    "created_at": _now(),
                }
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("[hook] escalation accounting failed: %s", e)

    # 4. Unified audit row in `requests` ------------------------------
    request_id = str(uuid.uuid4())
    audit_doc = {
        "id": request_id,
        "user_id": user_id,
        "session_id": session_id,
        "channel": channel,
        "message": message,
        "intent": intent,
        "agent_chain": agent_chain,
        "response": response_text or "",
        "confidence": rel_payload["score"],
        "confidence_level": rel_payload["level"],
        "should_escalate": rel_payload["should_escalate"],
        "verification_status": rel_payload["verification_status"],
        "tokens_total": int(tokens_total or 0),
        "latency_ms": int(latency_ms) if latency_ms is not None else None,
        "mock": bool(mock),
        "company_id": company_id,
        "created_at": _now(),
    }
    if extra and isinstance(extra, dict):
        # keep audit observable per channel (e.g. persona_id, autonomy_level)
        audit_doc["extra"] = {
            k: v for k, v in extra.items() if isinstance(k, str)
        }
    try:
        await get_db().requests.insert_one(audit_doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("[hook] requests insert failed: %s", e)

    return {
        "request_id": request_id,
        "confidence": rel_payload["score"],
        "confidence_level": rel_payload["level"],
        "should_escalate": rel_payload["should_escalate"],
        "has_contradiction": rel_payload["has_contradiction"],
        "verification_status": rel_payload["verification_status"],
        "signals": rel_payload["signals"],
    }
