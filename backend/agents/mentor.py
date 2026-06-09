"""
Mentor Engine for NXT8 (Module 6).

Per ТЗ:
- 5 levels: junior, mid, senior, lead, strategist (criteria defined in LEVELS)
- Metrics: accuracy, speed, escalation_rate, error_repeat
- Weak patterns: low_accuracy, high_escalation, repeating_errors
- Recommendation schema matches ТЗ exactly.
"""

from __future__ import annotations

import logging
import math
import statistics
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.mentor")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


LEVELS: Dict[str, Dict[str, Any]] = {
    "junior": {
        "name": "Junior",
        "criteria": "experience < 6 months OR requires_review > 50%",
        "targets": {"accuracy": 0.7, "speed": 1.5, "escalation_rate": 0.3, "error_repeat": 0},
        "weights": {"accuracy": 0.4, "speed": 0.2, "escalation_rate": 0.3, "error_repeat": 0.1},
    },
    "mid": {
        "name": "Mid",
        "criteria": "experience 6-24 months OR requires_review 20-50%",
        "targets": {"accuracy": 0.85, "speed": 1.0, "escalation_rate": 0.15, "error_repeat": 0},
        "weights": {"accuracy": 0.4, "speed": 0.25, "escalation_rate": 0.25, "error_repeat": 0.1},
    },
    "senior": {
        "name": "Senior",
        "criteria": "experience 2-5 years OR requires_review < 20%",
        "targets": {"accuracy": 0.92, "speed": 0.8, "escalation_rate": 0.05, "error_repeat": 0},
        "weights": {"accuracy": 0.45, "speed": 0.3, "escalation_rate": 0.15, "error_repeat": 0.1},
    },
    "lead": {
        "name": "Lead",
        "criteria": "experience 5+ years AND reviews others",
        "targets": {"accuracy": 0.96, "speed": 0.6, "escalation_rate": 0.02, "error_repeat": 0},
        "weights": {"accuracy": 0.5, "speed": 0.25, "escalation_rate": 0.15, "error_repeat": 0.1},
    },
    "strategist": {
        "name": "Strategist",
        "criteria": "cross-functional AND participates in planning",
        "targets": {"accuracy": 0.98, "speed": 0.5, "escalation_rate": 0.01, "error_repeat": 0},
        "weights": {"accuracy": 0.4, "speed": 0.2, "escalation_rate": 0.2, "error_repeat": 0.2},
    },
}


SUGGESTED_ACTIONS = {
    "low_accuracy": "Schedule targeted training session. Review last 10 failed tasks. Pair with senior mentor for 2 weeks.",
    "high_escalation": "Apply confidence-first triage. Escalate only when reliability score < 0.5. Schedule 1:1 with manager.",
    "repeating_errors": "Build per-task checklist. Enable automated validation on this task class.",
}


def _percentile(values: List[float], pct: int) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    k = (len(arr) - 1) * (pct / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return arr[f]
    return arr[f] + (arr[c] - arr[f]) * (k - f)


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


# ---------- profile management ----------


async def upsert_employee(employee: Dict[str, Any], company_id: str) -> Dict[str, Any]:
    db = get_db()
    eid = employee.get("employee_id") or str(uuid.uuid4())
    doc = {
        "employee_id": eid,
        "company_id": company_id,
        "name": employee.get("name", "Unnamed"),
        "department": employee.get("department", "general"),
        "level": employee.get("level", "junior"),
        "experience_months": int(employee.get("experience_months", 0)),
        "hire_date": employee.get("hire_date", _now()),
        "manager_id": employee.get("manager_id"),
        "skills": employee.get("skills", []),
        "updated_at": _now(),
    }
    await db.employees.update_one(
        {"employee_id": eid, "company_id": company_id},
        {"$set": doc, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )
    return doc


async def list_employees(company_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    return await db.employees.find({"company_id": company_id}, {"_id": 0}).to_list(length=500)


async def record_performance(metrics: Dict[str, Any], company_id: str) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "id": str(uuid.uuid4()),
        "employee_id": metrics["employee_id"],
        "company_id": company_id,
        "period_start": metrics.get("period_start", _now()),
        "period_end": metrics.get("period_end", _now()),
        "accuracy": float(metrics.get("accuracy", 0.0)),
        "speed": float(metrics.get("speed", 1.0)),
        "escalation_rate": float(metrics.get("escalation_rate", 0.0)),
        "error_repeat": int(metrics.get("error_repeat", 0)),
        "tasks_completed": int(metrics.get("tasks_completed", 0)),
        "tasks_reviewed": int(metrics.get("tasks_reviewed", 0)),
        "recorded_at": _now(),
    }
    await db.performance.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def performance_history(employee_id: str, company_id: str, weeks: int = 4) -> List[Dict[str, Any]]:
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
    cursor = db.performance.find(
        {"employee_id": employee_id, "company_id": company_id, "recorded_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("period_end", -1)
    return await cursor.to_list(length=200)


# ---------- weak pattern detection ----------


async def _level_stats(level_id: str) -> Dict[str, Any]:
    db = get_db()
    pipeline = [
        {"$lookup": {
            "from": "employees", "localField": "employee_id",
            "foreignField": "employee_id", "as": "emp",
        }},
        {"$unwind": "$emp"},
        {"$match": {"emp.level": level_id}},
        {"$project": {"_id": 0, "accuracy": 1, "escalation_rate": 1, "error_repeat": 1}},
    ]
    rows = await db.performance.aggregate(pipeline).to_list(length=2000)
    acc = [r["accuracy"] for r in rows if "accuracy" in r]
    esc = [r["escalation_rate"] for r in rows if "escalation_rate" in r]
    return {
        "n": len(rows),
        "accuracy_p30": _percentile(acc, 30) if acc else LEVELS[level_id]["targets"]["accuracy"] * 0.85,
        "escalation_mean": statistics.fmean(esc) if esc else LEVELS[level_id]["targets"]["escalation_rate"],
        "escalation_std": _std(esc),
    }


async def detect_weak_patterns(employee_id: str, company_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    emp = await db.employees.find_one({"employee_id": employee_id, "company_id": company_id}, {"_id": 0})
    if not emp:
        return []
    history = await performance_history(employee_id, company_id, weeks=4)
    if not history:
        return []
    latest = history[0]
    stats = await _level_stats(emp["level"])
    patterns: List[Dict[str, Any]] = []

    # 1. low_accuracy : below 30th percentile of level
    if latest["accuracy"] < stats["accuracy_p30"]:
        patterns.append({
            "pattern": "low_accuracy",
            "details": f"Accuracy {latest['accuracy']:.2%} below level p30 ({stats['accuracy_p30']:.2%})",
            "confidence": 0.78,
        })

    # 2. high_escalation : > mean + 1*std
    threshold = stats["escalation_mean"] + stats["escalation_std"]
    if latest["escalation_rate"] > threshold > 0:
        patterns.append({
            "pattern": "high_escalation",
            "details": f"Escalation {latest['escalation_rate']:.2%} above level avg+1σ ({threshold:.2%})",
            "confidence": 0.82,
        })

    # 3. repeating_errors : >=3 in last 30 days
    cutoff_30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    repeat_total = sum(
        h.get("error_repeat", 0) for h in history if h.get("recorded_at", "") >= cutoff_30
    )
    if repeat_total >= 3:
        patterns.append({
            "pattern": "repeating_errors",
            "details": f"{repeat_total} repeating errors in last 30 days",
            "confidence": 0.88,
        })

    # persist detection
    for p in patterns:
        await db.weak_patterns.insert_one({
            "id": str(uuid.uuid4()),
            "employee_id": employee_id,
            "company_id": company_id,
            "pattern": p["pattern"],
            "details": p["details"],
            "confidence": p["confidence"],
            "detected_at": _now(),
            "resolved": False,
        })

    return patterns


async def generate_recommendation(
    employee_id: str, pattern: str, company_id: str
) -> Dict[str, Any]:
    db = get_db()
    emp = await db.employees.find_one({"employee_id": employee_id, "company_id": company_id}, {"_id": 0})
    level = emp["level"] if emp else "unknown"
    return {
        "employee_id": employee_id,
        "level": level,
        "weak_pattern": pattern,
        "confidence": 0.8,
        "suggested_action": SUGGESTED_ACTIONS.get(pattern, "Review with manager"),
        "link_to_doc": f"/docs/mentor/{pattern}",
        "timestamp": _now(),
    }


async def employee_summary(employee_id: str, company_id: str) -> Dict[str, Any]:
    db = get_db()
    emp = await db.employees.find_one({"employee_id": employee_id, "company_id": company_id}, {"_id": 0})
    if not emp:
        return {"error": "not_found"}
    history = await performance_history(employee_id, company_id, weeks=12)
    patterns = await db.weak_patterns.find(
        {"employee_id": employee_id, "company_id": company_id, "resolved": False}, {"_id": 0}
    ).sort("detected_at", -1).to_list(length=20)
    return {"employee": emp, "history": history, "open_patterns": patterns}


async def list_open_patterns(company_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    db = get_db()
    return await db.weak_patterns.find(
        {"resolved": False, "company_id": company_id}, {"_id": 0}
    ).sort("detected_at", -1).to_list(length=limit)
