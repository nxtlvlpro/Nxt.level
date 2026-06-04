"""
NXT8 — Demo Tour ("Test Drive") analytics.

A floating checklist on the landing page walks first-time visitors through
five concrete scenarios. We persist every step transition (start, complete,
skip, dismiss) so we can answer:

  • Which scenarios do visitors actually finish?
  • Where do they drop off?
  • What's the conversion from "tour started" → "all done"?

Anonymous: identified only by `client_id` (uuid generated client-side and
kept in localStorage). No PII, no auth required.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.tour")


# ---------- canonical step catalogue ----------
#
# IDs are stable — never rename them, or historical funnels break.
STEPS: List[Dict[str, str]] = [
    {
        "id": "ask_hermes",
        "title": "Спроси Hermes",
        "hint":  "Открой чат с CEO и задай реальный вопрос про бизнес",
        "anchor": "home-hermes-chat",
    },
    {
        "id": "view_pricing",
        "title": "Посмотри тарифы",
        "hint":  "4 плана, от $9 до $24/сотрудник. Без скрытых платежей",
        "anchor": "home-tariff-personal",
    },
    {
        "id": "open_agents",
        "title": "Открой команду агентов",
        "hint":  "8 специалистов с разными мандатами и тулами",
        "anchor": "nav-agents",
    },
    {
        "id": "open_dialogues",
        "title": "Inter-Agent диалоги",
        "hint":  "Реальная связь команды: Hermes делегирует, агенты эскалируют",
        "anchor": "agents-dialogues-card",
    },
    {
        "id": "open_approvals",
        "title": "Approval Gate",
        "hint":  "Каждое high-impact решение агентов ждёт твоего «ОК»",
        "anchor": "agents-pending-approvals-card",
    },
]

VALID_STEP_IDS = {s["id"] for s in STEPS}
VALID_EVENTS = {"start", "complete", "skip", "dismiss"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def catalogue() -> Dict[str, Any]:
    return {"steps": STEPS, "count": len(STEPS)}


async def record_event(
    *,
    client_id: str,
    step_id: Optional[str],
    event: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a single tour event."""
    event = (event or "").lower()
    if event not in VALID_EVENTS:
        raise ValueError(f"unknown event: {event}")
    if event in {"start", "complete", "skip"} and step_id not in VALID_STEP_IDS:
        raise ValueError(f"unknown step_id: {step_id}")

    doc = {
        "id":        str(uuid.uuid4()),
        "client_id": (client_id or "anon").strip()[:64] or "anon",
        "step_id":   step_id,
        "event":     event,
        "metadata":  metadata or {},
        "created_at": _now(),
    }
    try:
        await get_db().tour_events.insert_one(doc)
    except Exception as e:  # noqa: BLE001
        logger.exception("tour event persist failed: %s", e)
        return {"ok": False, "error": str(e)}
    return {"ok": True, "event_id": doc["id"]}


async def ensure_indexes() -> None:
    db = get_db()
    await db.tour_events.create_index([("client_id", 1), ("created_at", -1)])
    await db.tour_events.create_index([("step_id", 1), ("event", 1)])
    await db.tour_events.create_index([("created_at", -1)])


# ---------- funnel ----------
async def funnel(window_hours: int = 168) -> Dict[str, Any]:
    """Per-step funnel for the last `window_hours` (default 7 days)."""
    db = get_db()
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(hours=window_hours)
    ).isoformat()

    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": {"step": "$step_id", "event": "$event"},
            "count": {"$sum": 1},
            "uniq": {"$addToSet": "$client_id"},
        }},
    ]
    rows = await db.tour_events.aggregate(pipeline).to_list(length=200)

    per_step: Dict[str, Dict[str, int]] = {
        s["id"]: {
            "title": s["title"],
            "start": 0, "complete": 0, "skip": 0,
            "uniq_start": 0, "uniq_complete": 0,
        } for s in STEPS
    }
    dismiss = 0
    uniq_visitors_set: set[str] = set()
    for r in rows:
        step = r["_id"].get("step")
        event = r["_id"].get("event")
        count = int(r["count"])
        uniq = set(r.get("uniq") or [])
        uniq_visitors_set.update(uniq)
        if event == "dismiss":
            dismiss += count
            continue
        if step in per_step and event in ("start", "complete", "skip"):
            per_step[step][event] += count
            if event == "start":
                per_step[step]["uniq_start"] += len(uniq)
            elif event == "complete":
                per_step[step]["uniq_complete"] += len(uniq)

    ordered = []
    for s in STEPS:
        bucket = per_step[s["id"]]
        starts = bucket["start"] or 0
        completes = bucket["complete"] or 0
        rate = (completes / starts) if starts > 0 else None
        ordered.append({
            "step_id":       s["id"],
            "title":         bucket["title"],
            "starts":        starts,
            "completes":     completes,
            "skips":         bucket["skip"],
            "uniq_starts":   bucket["uniq_start"],
            "uniq_completes":bucket["uniq_complete"],
            "completion_rate": round(rate, 3) if rate is not None else None,
        })
    return {
        "ok":           True,
        "window_hours": window_hours,
        "uniq_visitors":len(uniq_visitors_set),
        "dismiss_count":dismiss,
        "steps":        ordered,
    }
