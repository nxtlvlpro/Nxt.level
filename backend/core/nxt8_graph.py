from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agents import hermes_graph_v2 as graph_v2_agent
from agents import hermes_os_graph as os_graph_agent

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def list_skills() -> List[str]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        p.name for p in SKILLS_DIR.glob("*.md")
        if p.is_file() and not p.name.startswith(".")
    )


async def run_task(
    task_description: str,
    intent: str,
    context: Optional[Dict[str, Any]] = None,
    task_type: str = "execute",
) -> Dict[str, Any]:
    return await graph_v2_agent.run_graph_v2(
        task_description=task_description,
        intent=intent,
        context=context,
        task_type=task_type,
    )


async def run_cycle(
    event: Dict[str, Any],
    *,
    persist: bool = True,
    on_node=None,
) -> Dict[str, Any]:
    return await os_graph_agent.run_os_cycle(
        event,
        persist=persist,
        on_node=on_node,
    )
