"""
Hermes Evolution — self-improvement engine.

Implements directive sections 4, 5, 6, 7, 10, 11:
- propose_improvement   — Hermes writes into `db.hermes_evolution_log`
- propose_policy        — Hermes writes into `db.policy_proposals`
- list_evolution_roadmap — read journal grouped by area
- detect_automation_candidates — scan `db.requests` for repeating intents
- hermes_self_assessment — read own KPIs from diagnostics + requests
- approve_proposal      — human/Hermes flips status from `proposed` → `approved`

Tools surfaced as `HERMES_TOOLS` entries so Hermes can call them in a
fenced-JSON tool block during a normal chat turn.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.db import TenantAwareCRUD, get_db

logger = logging.getLogger("nxt8.hermes_evolution")

VALID_AREAS = {
    "capability", "agent", "integration", "architecture",
    "product", "process", "policy",
}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}


def _safe_int(v: Any, default: int) -> int:
    """Lenient int parser: "200", 200, "7d" → fallback to default."""
    try:
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip()
            digits = "".join(c for c in s if c.isdigit())
            return int(digits) if digits else default
    except Exception as e:
        logger.warning("Suppressed error during integer coercion: %s", type(e).__name__)
    return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Evolution Journal (sections 10, 11)
# =====================================================================


async def propose_improvement(args: Dict[str, Any]) -> Dict[str, Any]:
    """Hermes self-development entry. Writes to `db.hermes_evolution_log`.

    Required: area, description (problem statement).
    Recommended: expected_benefit, business_impact, priority.
    """
    area = (args.get("area") or "").lower().strip()
    description = (args.get("description") or args.get("problem") or "").strip()
    if area not in VALID_AREAS:
        return {"ok": False, "error": f"area must be one of {sorted(VALID_AREAS)}"}
    if not description:
        return {"ok": False, "error": "description (problem) is required"}

    priority = (args.get("priority") or "P2").upper()
    if priority not in VALID_PRIORITIES:
        priority = "P2"

    entry = {
        "id":               str(uuid.uuid4()),
        "area":             area,
        "title":            (args.get("title") or description[:80]).strip(),
        "description":      description,
        "expected_benefit": (args.get("expected_benefit") or "").strip(),
        "business_impact":  (args.get("business_impact") or "").strip(),
        "priority":         priority,
        "status":           "proposed",   # proposed | approved | rejected | done
        "proposed_by":      args.get("proposed_by") or "hermes",
        "created_at":       _now(),
        "updated_at":       _now(),
    }
    await TenantAwareCRUD(get_db().hermes_evolution_log, company_id=args.get("company_id")).insert_one(entry)
    try:
        from core import telegram_bot as tg

        asyncio.create_task(tg.notify_improvement(entry))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to notify improvement: %s", e)
    entry.pop("_id", None)
    return {"ok": True, "id": entry["id"], "area": area, "title": entry["title"],
            "priority": priority, "status": "proposed"}


async def list_evolution_roadmap(args: Dict[str, Any]) -> Dict[str, Any]:
    """List Evolution Journal entries, optionally filtered by area / status.
    Groups by area when no area is specified."""
    crud = TenantAwareCRUD(get_db().hermes_evolution_log, company_id=args.get("company_id"))
    q: Dict[str, Any] = {}
    if args.get("area"):
        q["area"] = args["area"].lower()
    if args.get("status"):
        q["status"] = args["status"].lower()
    limit = _safe_int(args.get("limit"), 100)
    docs = await crud.find(q, {"_id": 0}).sort(
        "created_at", -1).to_list(length=limit)

    # Group by area for the roadmap view
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        grouped.setdefault(d.get("area", "other"), []).append(d)

    return {
        "ok": True,
        "count": len(docs),
        "entries": docs,
        "by_area": grouped,
    }


async def approve_proposal(args: Dict[str, Any]) -> Dict[str, Any]:
    """Move a proposal to approved / rejected / done. Human or Hermes can call."""
    pid = (args.get("id") or "").strip()
    new_status = (args.get("status") or "approved").lower()
    if new_status not in ("approved", "rejected", "done"):
        return {"ok": False, "error": "status must be approved | rejected | done"}
    if not pid:
        return {"ok": False, "error": "id required"}
    res = await TenantAwareCRUD(get_db().hermes_evolution_log, company_id=args.get("company_id"), force_admin=bool(args.get("force_admin"))).find_one_and_update(
        {"id": pid},
        {"$set": {"status": new_status, "updated_at": _now()}},
        projection={"_id": 0},
        return_document=True,
    )
    if not res:
        return {"ok": False, "error": "proposal not found"}
    return {"ok": True, "entry": res}


# =====================================================================
# Policy proposals (section 5)
# =====================================================================


async def propose_policy(args: Dict[str, Any]) -> Dict[str, Any]:
    """Hermes detects a missing rule and proposes a new policy.

    Required: title, scope (e.g. 'sla', 'escalation', 'data_handling',
    'refunds', 'communication').
    Recommended: proposed_rule, justification, severity.
    """
    title = (args.get("title") or "").strip()
    scope = (args.get("scope") or "").strip().lower()
    proposed_rule = (args.get("proposed_rule") or args.get("rule") or "").strip()
    if not title:
        return {"ok": False, "error": "title required"}
    if not proposed_rule:
        return {"ok": False, "error": "proposed_rule required"}

    entry = {
        "id":             str(uuid.uuid4()),
        "title":          title,
        "scope":          scope or "general",
        "proposed_rule":  proposed_rule,
        "justification":  (args.get("justification") or "").strip(),
        "severity":       (args.get("severity") or "medium").lower(),
        "status":         "proposed",
        "proposed_by":    args.get("proposed_by") or "hermes",
        "created_at":     _now(),
        "updated_at":     _now(),
    }
    await TenantAwareCRUD(get_db().policy_proposals, company_id=args.get("company_id")).insert_one(entry)
    try:
        from core import telegram_bot as tg

        asyncio.create_task(tg.notify_policy(entry))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to notify policy: %s", e)
    entry.pop("_id", None)
    return {"ok": True, "id": entry["id"], "title": title, "scope": entry["scope"],
            "severity": entry["severity"], "status": "proposed"}


async def list_policy_proposals(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read pending / all policy proposals."""
    crud = TenantAwareCRUD(get_db().policy_proposals, company_id=args.get("company_id"))
    q: Dict[str, Any] = {}
    if args.get("status"):
        q["status"] = args["status"].lower()
    limit = _safe_int(args.get("limit"), 50)
    docs = await crud.find(q, {"_id": 0}).sort(
        "created_at", -1).to_list(length=limit)
    return {"ok": True, "count": len(docs), "proposals": docs}


# =====================================================================
# Process improvement detector (section 4)
# =====================================================================


async def detect_automation_candidates(args: Dict[str, Any]) -> Dict[str, Any]:
    """Scan recent `db.requests` for repeating intents that are good
    candidates for full automation. Surfaces:
      - intent
      - count in window
      - avg_confidence (only safe to automate when >= 0.75)
      - escalation_rate (only safe when < 0.20)

    Args:
        window — int, recent N requests (default 500, capped 2000)
        min_count — minimum repeat count to qualify (default 3)
    """
    window = max(50, min(_safe_int(args.get("window"), 500), 2000))
    min_count = max(2, _safe_int(args.get("min_count"), 3))

    docs = await TenantAwareCRUD(get_db().requests, company_id=args.get("company_id")).find(
        {}, {"_id": 0, "intent": 1, "confidence": 1, "should_escalate": 1, "mock": 1}
    ).sort("created_at", -1).limit(window).to_list(length=window)

    by_intent: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        intent = (d.get("intent") or "general").strip().lower() or "general"
        slot = by_intent.setdefault(intent, {
            "intent": intent, "count": 0, "confidence_sum": 0.0,
            "escalations": 0, "mocks": 0,
        })
        slot["count"] += 1
        slot["confidence_sum"] += float(d.get("confidence") or 0.0)
        if d.get("should_escalate"):
            slot["escalations"] += 1
        if d.get("mock"):
            slot["mocks"] += 1

    candidates: List[Dict[str, Any]] = []
    for slot in by_intent.values():
        n = slot["count"]
        if n < min_count:
            continue
        avg_conf = slot["confidence_sum"] / n
        esc_rate = slot["escalations"] / n
        mock_rate = slot["mocks"] / n
        # Surface anything that repeats — recommendation differs by quality.
        recommendation = "ready_to_automate"
        if avg_conf < 0.75:
            recommendation = "improve_prompt_first"
        if esc_rate >= 0.20:
            recommendation = "improve_prompt_first"
        if mock_rate >= 0.10:
            recommendation = "fix_provider_first"
        candidates.append({
            "intent": slot["intent"],
            "count": n,
            "avg_confidence": round(avg_conf, 3),
            "escalation_rate": round(esc_rate, 3),
            "mock_rate": round(mock_rate, 3),
            "recommendation": recommendation,
        })

    candidates.sort(key=lambda x: (-x["count"], x["intent"]))
    return {
        "ok": True,
        "window": window,
        "min_count": min_count,
        "candidates": candidates[:20],
        "total_intents_seen": len(by_intent),
    }


# =====================================================================
# Self-assessment (section 7, 10)
# =====================================================================


async def hermes_self_assessment(args: Dict[str, Any]) -> Dict[str, Any]:
    """Hermes inspects HIS OWN operational metrics from db.requests +
    db.hermes_evolution_log + diagnostics.
    """
    window = max(50, min(_safe_int(args.get("window"), 200), 1000))
    company_id = args.get("company_id")
    requests_crud = TenantAwareCRUD(get_db().requests, company_id=company_id)
    evolution_crud = TenantAwareCRUD(get_db().hermes_evolution_log, company_id=company_id)

    docs = await requests_crud.find(
        {}, {"_id": 0, "confidence": 1, "should_escalate": 1, "mock": 1,
             "intent": 1, "agent_chain": 1}
    ).sort("created_at", -1).limit(window).to_list(length=window)

    n = len(docs)
    if n == 0:
        return {"ok": True, "scanned": 0, "note": "no requests yet"}

    avg_conf = sum(float(d.get("confidence") or 0.0) for d in docs) / n
    esc_rate = sum(1 for d in docs if d.get("should_escalate")) / n
    mock_rate = sum(1 for d in docs if d.get("mock")) / n
    intent_counts = Counter((d.get("intent") or "general") for d in docs).most_common(5)

    # Evolution journal stats
    proposed = await evolution_crud.count_documents({"status": "proposed"})
    approved = await evolution_crud.count_documents({"status": "approved"})
    done = await evolution_crud.count_documents({"status": "done"})
    by_area = await evolution_crud.aggregate([
        {"$group": {"_id": "$area", "count": {"$sum": 1}}}
    ]).to_list(length=20)

    # Honest signals
    signals: List[str] = []
    if avg_conf < 0.70:
        signals.append(f"⚠ avg_confidence={avg_conf:.2f} ниже целевых 0.70")
    if esc_rate > 0.20:
        signals.append(f"⚠ escalation_rate={esc_rate:.0%} выше целевых 20%")
    if mock_rate > 0.05:
        signals.append(f"⚠ mock_rate={mock_rate:.0%} — провайдер LLM нестабилен")
    if proposed >= 10:
        signals.append(f"📋 {proposed} proposed-эволюций ждут approval")
    if not signals:
        signals.append("✅ метрики в норме")

    return {
        "ok": True,
        "scanned": n,
        "avg_confidence": round(avg_conf, 3),
        "escalation_rate": round(esc_rate, 3),
        "mock_rate": round(mock_rate, 3),
        "top_intents": [{"intent": i, "count": c} for i, c in intent_counts],
        "evolution_journal": {
            "proposed": proposed,
            "approved": approved,
            "done": done,
            "by_area": {row["_id"]: row["count"] for row in by_area},
        },
        "signals": signals,
    }
