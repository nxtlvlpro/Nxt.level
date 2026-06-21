from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


# Legacy → canonical alias map. Surface alias for default fallback.
PLAN_ALIASES: Dict[str, str] = {
    "basic": "personal",
    "simple": "team",
    "pro": "operations",
    "enterprise": "headquarters",
    "hq": "headquarters",
    "pilot": "personal",
}


def build_canonical_plans(persona_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    return {
        "personal": {
            "name": "Personal",
            "price_usd": 9,
            "personas": ["hermes"],
        },
        "team": {
            "name": "Team",
            "price_usd": 14,
            "personas": ["hermes", "hr_mentor", "client_manager"],
        },
        "operations": {
            "name": "Operations",
            "price_usd": 19,
            "personas": [
                "hermes", "hr_mentor", "client_manager",
                "bookkeeper", "marketer", "compliance",
            ],
        },
        "headquarters": {
            "name": "Headquarters",
            "price_usd": 24,
            "personas": list(persona_ids),
        },
    }


def canonicalize_plan_id(
    plan_id: Optional[str],
    canonical_plans: Dict[str, Dict[str, Any]],
    *,
    default_plan_id: str = "headquarters",
) -> str:
    pid = (plan_id or default_plan_id).lower()
    pid = PLAN_ALIASES.get(pid, pid)
    if pid not in canonical_plans:
        pid = default_plan_id
    return pid


def build_public_plans(
    canonical_plans: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    return {
        **canonical_plans,
        **{alias: canonical_plans[canon] for alias, canon in PLAN_ALIASES.items()},
    }


def get_plan(
    plan_id: Optional[str],
    canonical_plans: Dict[str, Dict[str, Any]],
    *,
    default_plan_id: str = "headquarters",
) -> Dict[str, Any]:
    pid = canonicalize_plan_id(plan_id, canonical_plans, default_plan_id=default_plan_id)
    return {"id": pid, **canonical_plans[pid]}


def min_plan_for(
    persona_id: str,
    canonical_plans: Dict[str, Dict[str, Any]],
) -> str:
    for plan_id in ("personal", "team", "operations", "headquarters"):
        if persona_id in canonical_plans[plan_id]["personas"]:
            return plan_id
    return "headquarters"
