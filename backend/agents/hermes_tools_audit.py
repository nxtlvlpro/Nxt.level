"""Hermes self-audit tools.

Read-only diagnostics and isolated sandbox benchmarks for Hermes.
These tools do not auto-apply changes and do not persist benchmark
results into evolution journals or other audit collections.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.db import TenantAwareCRUD, get_db

SANDBOX_COMPANY_ID = "audit_sandbox"
DEFAULT_BENCHMARK_QUERY = (
    "Кратко опиши свою роль и назови один главный инструмент. "
    "Не вызывай инструменты и не создавай записи."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(v: Any, default: int) -> int:
    try:
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            digits = "".join(ch for ch in v if ch.isdigit())
            return int(digits) if digits else default
    except Exception:  # noqa: BLE001
        pass
    return default


def _get_persona_runtime():
    from agents.personas import SKILL_ROUTED_PERSONAS, run_persona

    return SKILL_ROUTED_PERSONAS, run_persona


async def scan_system_health(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read-only health summary for the current tenant."""
    company_id = (args.get("company_id") or "").strip()
    if not company_id:
        return {"ok": False, "error": "company_id is required"}

    window = max(50, min(_safe_int(args.get("window"), 200), 1000))
    requests_crud = TenantAwareCRUD(get_db().requests, company_id=company_id)
    contradictions_crud = TenantAwareCRUD(get_db().contradictions, company_id=company_id)

    reqs = await requests_crud.find(
        {},
        {
            "_id": 0,
            "confidence": 1,
            "should_escalate": 1,
            "latency_ms": 1,
            "mock": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1).limit(window).to_list(length=window)

    scanned = len(reqs)
    confidences = [float(r.get("confidence") or 0.0) for r in reqs]
    latencies = [float(r.get("latency_ms") or 0.0) for r in reqs if r.get("latency_ms") is not None]
    escalations = sum(1 for r in reqs if r.get("should_escalate"))
    mock_hits = sum(1 for r in reqs if r.get("mock"))
    low_conf_hits = sum(1 for r in reqs if float(r.get("confidence") or 0.0) < 0.7)
    contradiction_count = await contradictions_crud.count_documents({})

    return {
        "ok": True,
        "company_id": company_id,
        "scanned": scanned,
        "avg_confidence": round(sum(confidences) / max(scanned, 1), 3),
        "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 1),
        "escalation_rate": round(escalations / max(scanned, 1), 3),
        "mock_rate": round(mock_hits / max(scanned, 1), 3),
        "low_confidence_rate": round(low_conf_hits / max(scanned, 1), 3),
        "contradiction_count": int(contradiction_count or 0),
        "timestamp": _now(),
    }


async def run_persona_benchmark(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run one synthetic, isolated query per subordinate routed persona."""
    company_id = (args.get("company_id") or SANDBOX_COMPANY_ID).strip() or SANDBOX_COMPANY_ID
    query = (args.get("query") or DEFAULT_BENCHMARK_QUERY).strip() or DEFAULT_BENCHMARK_QUERY
    skill_routed_personas, run_persona = _get_persona_runtime()
    personas = sorted(pid for pid in skill_routed_personas if pid != "hermes")
    results: List[Dict[str, Any]] = []

    for pid in personas:
        session_id = f"audit_{pid}_{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        try:
            res = await run_persona(
                persona_id=pid,
                message=query,
                company_id=company_id,
                user_id="hermes_audit",
                session_id=session_id,
                plan_id="enterprise",
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            results.append({
                "persona": pid,
                "success": bool(res.get("success")),
                "confidence": res.get("confidence", 0),
                "latency_ms": latency_ms,
                "provider": res.get("provider"),
                "session_id": session_id,
            })
        except Exception as e:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            if "MONGO_URL" in str(e):
                results.append({
                    "persona": pid,
                    "success": False,
                    "error": "DB unavailable in sandbox mode",
                    "provider": "nxt8_graph",
                    "mock": True,
                    "latency_ms": latency_ms,
                    "session_id": session_id,
                })
                continue
            results.append({
                "persona": pid,
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms,
                "session_id": session_id,
            })

    passed = sum(1 for row in results if row.get("success"))
    return {
        "ok": True,
        "company_id": company_id,
        "sandbox": True,
        "query": query,
        "total_personas": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "benchmark": results,
        "timestamp": _now(),
    }