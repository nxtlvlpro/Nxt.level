"""
NXT8 — Pulse Engine (background tenant-level KPI watcher).

Called by `core.scheduler` every `PULSE_INTERVAL_MINUTES`. For each
active tenant we:
  1. Snapshot current KPI (interactions/deals/roi/approvals).
  2. Compare with the previous snapshot.
  3. Apply trigger rules → emit nudges through `core.approval_gate`.
  4. Spam-guard: max PULSE_MAX_NUDGES_PER_DAY per tenant.

Every nudge is a regular `pending_approval` so the owner sees it in
the existing UI + receives a push in Telegram/WhatsApp.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.db import TenantAwareCRUD, get_db

logger = logging.getLogger("nxt8.pulse")

MAX_NUDGES_PER_DAY = int(os.environ.get("PULSE_MAX_NUDGES_PER_DAY") or 3)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------
# KPI snapshot
# ---------------------------------------------------------------------


async def compute_kpi(company_id: str) -> Dict[str, Any]:
    db = get_db()
    interactions = TenantAwareCRUD(db.interactions, company_id=company_id)
    deals = TenantAwareCRUD(db.deals, company_id=company_id)
    approvals = TenantAwareCRUD(db.pending_approvals, company_id=company_id)
    now = _now()
    day_ago = now - timedelta(hours=24)
    hour_ago = now - timedelta(hours=1)

    try:
        interactions_24h = await interactions.count_documents(
            {"company_id": company_id, "timestamp": {"$gte": _iso(day_ago)}}
        )
    except Exception:  # noqa: BLE001
        interactions_24h = 0
    try:
        deals_24h = await deals.count_documents(
            {"company_id": company_id, "closed_at": {"$gte": _iso(day_ago)}}
        )
        new_deals_last_hour = await deals.count_documents(
            {"company_id": company_id, "closed_at": {"$gte": _iso(hour_ago)}}
        )
    except Exception:  # noqa: BLE001
        deals_24h = 0
        new_deals_last_hour = 0
    try:
        roi_usd_24h_cursor = deals.aggregate([
            {"$match": {"company_id": company_id, "closed_at": {"$gte": _iso(day_ago)}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_usd"}}},
        ])
        roi_rows = await roi_usd_24h_cursor.to_list(length=1)
        roi_usd_24h = float((roi_rows[0] if roi_rows else {}).get("total") or 0.0)
    except Exception:  # noqa: BLE001
        roi_usd_24h = 0.0
    try:
        pending_count = await approvals.count_documents(
            {"company_id": company_id, "status": "pending"}
        )
        stale_pending = await approvals.count_documents({
            "company_id": company_id, "status": "pending",
            "created_at": {"$lte": _iso(now - timedelta(hours=2))},
        })
    except Exception:  # noqa: BLE001
        pending_count = 0
        stale_pending = 0

    return {
        "interactions_24h": int(interactions_24h),
        "deals_24h": int(deals_24h),
        "new_deals_last_hour": int(new_deals_last_hour),
        "roi_usd_24h": float(roi_usd_24h),
        "pending_count": int(pending_count),
        "stale_pending": int(stale_pending),
    }


async def _save_snapshot(company_id: str, kpi: Dict[str, Any]) -> str:
    snapshots = TenantAwareCRUD(get_db().pulse_snapshots, company_id=company_id)
    import uuid
    sid = f"snap_{uuid.uuid4().hex[:16]}"
    await snapshots.insert_one({
        "snapshot_id": sid,
        "company_id": company_id,
        "taken_at": _iso(_now()),
        "kpi": kpi,
    })
    return sid


async def _previous_snapshot(company_id: str) -> Optional[Dict[str, Any]]:
    snapshots = TenantAwareCRUD(get_db().pulse_snapshots, company_id=company_id)
    docs = await (
        snapshots.find({"company_id": company_id}, {"_id": 0})
        .sort("taken_at", -1)
        .limit(2)
        .to_list(length=2)
    )
    # docs[0] is the one we just saved; docs[1] is the previous tick.
    return docs[1] if len(docs) >= 2 else None


async def _nudges_today(company_id: str) -> int:
    approvals = TenantAwareCRUD(get_db().pending_approvals, company_id=company_id)
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        return await approvals.count_documents({
            "company_id": company_id,
            "action": "nudge_user",
            "created_at": {"$gte": _iso(today_start)},
        })
    except Exception:  # noqa: BLE001
        return 0


# ---------------------------------------------------------------------
# Trigger rules
# ---------------------------------------------------------------------


def _roi_delta_pct(now_kpi: Dict[str, Any], prev_kpi: Dict[str, Any]) -> float:
    a = float(now_kpi.get("roi_usd_24h", 0.0))
    b = float(prev_kpi.get("roi_usd_24h", 0.0))
    if b <= 0.01:
        return 0.0 if a <= 0.01 else 100.0
    return ((a - b) / b) * 100.0


async def _emit_nudge(
    company_id: str,
    rationale: str,
    args: Dict[str, Any],
    *,
    agent_id: str = "hermes",
) -> Optional[str]:
    """Push a soft `nudge_user` action through the approval-gate. Owner
    approves → action runs. Owner rejects → noop."""
    try:
        from core import approval_gate as _ag
        res = await _ag.request_approval(
            agent_id=agent_id,
            action="nudge_user",
            args=args,
            company_id=company_id,
            user_id=None,
            rationale=rationale,
        )
        return res.get("approval_id") if isinstance(res, dict) else None
    except Exception as e:  # noqa: BLE001
        logger.warning("pulse emit_nudge failed: %s", e)
        return None


# ---------------------------------------------------------------------
# Pulse tick
# ---------------------------------------------------------------------


async def pulse_tick(company_id: str) -> Dict[str, Any]:
    """Execute one Pulse tick for a single tenant. Returns a stats dict
    so the scheduler can aggregate."""
    kpi = await compute_kpi(company_id)
    await _save_snapshot(company_id, kpi)
    prev = await _previous_snapshot(company_id)

    nudges: List[str] = []
    skipped: List[str] = []

    # Stale pending — straight push, NOT a nudge (we already have a UI
    # surface for these and a push channel via approval_gate).
    # This deliberately doesn't count toward the daily-nudge cap.
    # (Actual delivery is best-effort — `notify_pending_approval` is
    # triggered when approvals were first created; reminders for
    # 2-hour-old ones are a P1 follow-up.)

    if not prev:
        return {
            "company_id": company_id, "kpi": kpi,
            "nudges": 0, "reason": "no_prev_snapshot",
        }

    cap = await _nudges_today(company_id)
    can_emit = cap < MAX_NUDGES_PER_DAY

    delta = _roi_delta_pct(kpi, prev["kpi"])

    if can_emit and delta >= 10.0 and kpi["roi_usd_24h"] > 0:
        nid = await _emit_nudge(
            company_id,
            rationale=f"ROI вырос на {delta:+.1f}% за час — самое время закрепить успех.",
            args={
                "message": (
                    "🚀 ROI вырос на {:+.1f}% за последний час. "
                    "Я предлагаю запустить nurture-кампанию для активных клиентов "
                    "и зафиксировать рост."
                ).format(delta),
                "kind": "roi_up",
                "metric": {"delta_pct": delta, "now": kpi["roi_usd_24h"]},
            },
        )
        if nid:
            nudges.append(nid)
            cap += 1
            can_emit = cap < MAX_NUDGES_PER_DAY

    if can_emit and delta <= -10.0:
        nid = await _emit_nudge(
            company_id,
            rationale=f"ROI просел на {delta:+.1f}% за час.",
            args={
                "message": (
                    "📉 ROI просел на {:+.1f}% за час. Я могу разобрать причины и "
                    "предложить план восстановления."
                ).format(delta),
                "kind": "roi_down",
                "metric": {"delta_pct": delta, "now": kpi["roi_usd_24h"]},
            },
        )
        if nid:
            nudges.append(nid)
            cap += 1
            can_emit = cap < MAX_NUDGES_PER_DAY

    if can_emit and kpi["interactions_24h"] == 0:
        nid = await _emit_nudge(
            company_id,
            rationale="За 24 часа не было ни одного взаимодействия с клиентами.",
            args={
                "message": (
                    "💤 24 часа без активности с клиентами. "
                    "Marketer готов запустить nurture-кампанию для тёплых лидов."
                ),
                "kind": "no_activity",
            },
            agent_id="marketer",
        )
        if nid:
            nudges.append(nid)

    if can_emit and cap >= MAX_NUDGES_PER_DAY:
        skipped.append("spam_guard_max_nudges")

    return {
        "company_id": company_id, "kpi": kpi, "delta_roi_pct": delta,
        "nudges": len(nudges), "nudge_ids": nudges, "skipped": skipped,
    }
