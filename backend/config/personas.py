from __future__ import annotations

from typing import Any, Dict, List, Optional


def list_personas(
    personas: Dict[str, Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    min_plan_for,
) -> List[Dict[str, Any]]:
    allowed = set(plan["personas"])
    items: List[Dict[str, Any]] = []
    for pid, cfg in personas.items():
        items.append(
            {
                "id": pid,
                "name": cfg["name"],
                "role": cfg["role"],
                "description": cfg["description"],
                "icon": cfg.get("icon"),
                "color": cfg.get("color"),
                "tools_count": len(cfg["allowed_tools"]),
                "available_on_plan": pid in allowed,
                "min_plan": min_plan_for(pid),
            }
        )
    return items
