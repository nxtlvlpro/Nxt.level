"""
Profit Intelligence (ROI) Engine for NXT8 (Module 7).

Per ТЗ:
- Cost sources: deepseek_api ($0.50/1M tokens), compute ($0.05/cpu-hour),
                human_escalation ($35/hour, avg 5min)
- Revenue attribution: time-decay over 7-day window
                       weight = 1 / (days_before_deal + 1)
- ROI formula: (revenue_last_hour - cost_last_hour) / cost_last_hour
- Update cadence: hourly (near real-time)
- Alerts:
    hourly_roi < -0.1            → warning
    agent.roi < -0.3 for 3h      → critical (would pause agent)

Tenant isolation (Sprint A · Fix 1):
- Every cost/deal/interaction/roi_history doc carries `company_id`.
- All aggregation helpers accept `company_id: Optional[str]`. `None` means
  "no tenant filter" (admin / global view). A string value scopes the
  aggregation to that tenant only.
- `roi_history` is now keyed by `(hour_end, company_id)` so tenants do not
  overwrite each other's hourly snapshot.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.roi")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- cost tracking ----------


COST_PER_1M_TOKENS = 0.50
COST_PER_CPU_HOUR = 0.05
ESCALATION_USD_PER_MIN = 35.0 / 60.0


async def record_api_cost(
    agent: str,
    tokens: int,
    model: str = "deepseek-chat",
    *,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    amount = (tokens / 1_000_000.0) * COST_PER_1M_TOKENS
    return await _record_cost(
        "deepseek_api", agent, amount, tokens, "tokens", {"model": model},
        company_id=company_id,
    )


async def record_compute_cost(
    agent: str,
    cpu_seconds: float,
    *,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    amount = (cpu_seconds / 3600.0) * COST_PER_CPU_HOUR
    return await _record_cost(
        "compute", agent, amount, cpu_seconds, "cpu_seconds", {},
        company_id=company_id,
    )


async def record_escalation_cost(
    agent: str,
    minutes: float = 5.0,
    *,
    human_handled: bool = False,
    escalation_id: Optional[str] = None,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a human-escalation cost.

    NB: in the original ТЗ this fired every time the reliability layer
    flagged `should_escalate=True`. That produced ~$2.92 of phantom cost
    per call even when no human ever touched the conversation, and the
    dashboard showed −100% ROI on every hour.

    Now we only count the cost when the escalation is actually picked up
    by a human (`human_handled=True`). Auto-only escalations register a
    *signal* (cost=0, metadata.flag=auto_escalation_signal) so the
    dashboard still sees the event but it does not pollute ROI.
    """
    amount = (minutes * ESCALATION_USD_PER_MIN) if human_handled else 0.0
    metadata: Dict[str, Any] = {
        "human_handled": bool(human_handled),
        "escalation_id": escalation_id,
    }
    if not human_handled:
        metadata["flag"] = "auto_escalation_signal"
    return await _record_cost(
        "human_escalation", agent, amount, minutes, "minutes", metadata,
        company_id=company_id,
    )


async def _record_cost(
    cost_type: str,
    agent: str,
    amount_usd: float,
    quantity: float,
    unit: str,
    metadata: Dict[str, Any],
    *,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "id": str(uuid.uuid4()),
        "cost_type": cost_type,
        "agent": agent,
        "amount_usd": float(amount_usd),
        "quantity": float(quantity),
        "unit": unit,
        "metadata": metadata,
        "company_id": company_id,
        "created_at": _now(),
    }
    await db.costs.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------- revenue attribution ----------


async def record_deal(
    deal_id: str,
    value_usd: float,
    team: str,
    closed_at: Optional[str] = None,
    *,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "deal_id": deal_id,
        "value_usd": float(value_usd),
        "team": team,
        "closed_at": closed_at or _now(),
        "company_id": company_id,
        "created_at": _now(),
    }
    await db.deals.update_one({"deal_id": deal_id}, {"$set": doc}, upsert=True)
    await attribute_deal(deal_id)
    return doc


async def record_interaction(
    deal_id: str,
    agent: str,
    interaction_type: str = "touch",
    *,
    company_id: Optional[str] = None,
) -> None:
    db = get_db()
    await db.interactions.insert_one({
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "agent": agent,
        "interaction_type": interaction_type,
        "interaction_time": _now(),
        "attributed_revenue": None,
        "company_id": company_id,
    })


async def attribute_deal(deal_id: str, window_days: int = 7) -> Dict[str, float]:
    db = get_db()
    deal = await db.deals.find_one({"deal_id": deal_id}, {"_id": 0})
    if not deal:
        return {}
    closed = datetime.fromisoformat(deal["closed_at"].replace("Z", "+00:00"))
    interactions = await db.interactions.find(
        {"deal_id": deal_id}, {"_id": 0}
    ).to_list(length=1000)
    if not interactions:
        return {}

    weights: Dict[str, float] = {}
    total = 0.0
    for it in interactions:
        try:
            t = datetime.fromisoformat(it["interaction_time"].replace("Z", "+00:00"))
        except Exception:
            continue
        days_before = max(0.0, (closed - t).total_seconds() / 86400)
        if days_before > window_days:
            continue
        w = 1.0 / (days_before + 1.0)
        weights[it["agent"]] = weights.get(it["agent"], 0.0) + w
        total += w

    attribution: Dict[str, float] = {}
    if total > 0:
        for agent, w in weights.items():
            attributed = float(deal["value_usd"]) * (w / total)
            attribution[agent] = round(attributed, 4)

    # persist
    for agent, revenue in attribution.items():
        await db.interactions.update_many(
            {"deal_id": deal_id, "agent": agent},
            {"$set": {"attributed_revenue": revenue}},
        )
    return attribution


# ---------- aggregated views ----------


def _tenant_match(company_id: Optional[str]) -> Dict[str, Any]:
    """Return a Mongo `$match` fragment scoping to a tenant when `company_id`
    is provided. `None` returns an empty dict (no tenant filter)."""
    if company_id is None:
        return {}
    return {"company_id": company_id}


async def _sum_costs_since(
    since_iso: str, company_id: Optional[str] = None
) -> Dict[str, Any]:
    db = get_db()
    match: Dict[str, Any] = {"created_at": {"$gte": since_iso}}
    match.update(_tenant_match(company_id))
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"type": "$cost_type", "agent": "$agent"},
            "total": {"$sum": "$amount_usd"},
        }},
    ]
    rows = await db.costs.aggregate(pipeline).to_list(length=1000)
    by_type: Dict[str, float] = {}
    by_agent: Dict[str, float] = {}
    total = 0.0
    for r in rows:
        t = r["_id"]["type"]
        a = r["_id"]["agent"]
        v = float(r["total"])
        total += v
        by_type[t] = by_type.get(t, 0.0) + v
        by_agent[a] = by_agent.get(a, 0.0) + v
    return {"total": round(total, 4), "by_type": by_type, "by_agent": by_agent}


async def _sum_revenue_since(
    since_iso: str, company_id: Optional[str] = None
) -> Dict[str, Any]:
    db = get_db()
    match: Dict[str, Any] = {
        "interaction_time": {"$gte": since_iso},
        "attributed_revenue": {"$ne": None},
    }
    match.update(_tenant_match(company_id))
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$agent", "total": {"$sum": "$attributed_revenue"}}},
    ]
    rows = await db.interactions.aggregate(pipeline).to_list(length=1000)
    by_agent: Dict[str, float] = {}
    total = 0.0
    for r in rows:
        v = float(r["total"])
        by_agent[r["_id"]] = v
        total += v
    return {"total": round(total, 4), "by_agent": by_agent}


async def calculate_hourly_roi(
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=1)
    costs = await _sum_costs_since(start.isoformat(), company_id=company_id)
    revenue = await _sum_revenue_since(start.isoformat(), company_id=company_id)
    total_cost = costs["total"]
    total_revenue = revenue["total"]

    # Determine the phase so the UI knows how to render this number.
    #
    #   "no_activity"   — nothing happened this hour (no costs, no revenue)
    #   "pilot"         — there are costs but no attributed revenue yet
    #                     (e.g. company hasn't recorded any closed deals).
    #                     ROI is mathematically -100% but operationally
    #                     meaningless — surface as "pilot" instead of alert.
    #   "live"          — costs > 0 AND revenue > 0 → real ROI signal.
    if total_cost == 0 and total_revenue == 0:
        phase = "no_activity"
        roi: Optional[float] = None
    elif total_revenue == 0:
        phase = "pilot"
        roi = None     # don't surface a misleading −100% in this phase
    elif total_cost == 0:
        # Revenue without cost — usually a back-dated deal whose interactions
        # were recorded before cost-tracking was wired. Treat as "live" but
        # avoid div-by-zero; ROI is effectively "infinite" → surface as None
        # and let the dashboard render "—" instead of a crash.
        phase = "live"
        roi = None
    else:
        phase = "live"
        roi = (total_revenue - total_cost) / total_cost

    alert = None
    # Alert only when we have a real ROI signal AND it's below threshold.
    if phase == "live" and roi is not None and roi < -0.1:
        alert = f"warning: hourly ROI {roi:.2%} below -10%"

    by_agent: Dict[str, Optional[float]] = {}
    if phase == "live":
        for agent, agent_cost in costs["by_agent"].items():
            agent_rev = revenue["by_agent"].get(agent, 0.0)
            by_agent[agent] = (
                round((agent_rev - agent_cost) / agent_cost, 4)
                if agent_cost > 0 else None
            )
    else:
        # Suppress per-agent ROI rows during pilot/no_activity — they
        # would all read −100% and clutter the dashboard.
        by_agent = {a: None for a in costs["by_agent"].keys()}

    snapshot = {
        "hour_start": start.isoformat(),
        "hour_end": end.isoformat(),
        "phase": phase,
        "roi": round(roi, 4) if roi is not None else None,
        "total_cost": total_cost,
        "total_revenue": total_revenue,
        "by_type_cost": costs["by_type"],
        "by_agent_cost": costs["by_agent"],
        "by_agent_revenue": revenue["by_agent"],
        "by_agent_roi": by_agent,
        "alert": alert,
        "company_id": company_id,
        "created_at": _now(),
    }

    db = get_db()
    # Keyed by (hour_end, company_id) so tenant snapshots are independent.
    await db.roi_history.update_one(
        {"hour_end": snapshot["hour_end"], "company_id": company_id},
        {"$set": snapshot},
        upsert=True,
    )
    if alert:
        await db.alerts.insert_one(
            {"id": str(uuid.uuid4()), "source": "roi", "severity": "warning",
             "message": alert, "company_id": company_id, "created_at": _now()}
        )
    return snapshot


async def roi_trend(
    hours: int = 24, company_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query: Dict[str, Any] = {"hour_end": {"$gte": cutoff}}
    query.update(_tenant_match(company_id))
    return await db.roi_history.find(
        query, {"_id": 0}
    ).sort("hour_end", -1).to_list(length=hours + 4)


async def dashboard_summary(
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    snap = await calculate_hourly_roi(company_id=company_id)
    trend = await roi_trend(24, company_id=company_id)
    return {"current_hour": snap, "trend_24h": trend}
