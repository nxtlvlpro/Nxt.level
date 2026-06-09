"""
NXT8 — Data Access Guard.
Enforces the data_access matrix defined in agents/manifests.py and skill YAMLs.
Called from nxt8_graph.py before executing any tool.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from agents import manifests as M

logger = logging.getLogger("nxt8.access_guard")

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_TOOL_COLLECTION_MAP: dict[str, tuple[str, str]] = {
    # Read-heavy tools
    "search_memory": ("memories", "read"),
    "mempalace_search": ("memories", "read"),
    "monitor_sla_violations": ("tasks", "read"),
    "evaluate_action_roi": ("roi_history", "read"),
    "detect_bottlenecks": ("tasks", "read"),
    "find_opportunities_in_contact": ("interactions", "read"),
    "generate_daily_digest": ("interactions", "read"),
    "generate_communication_summary": ("interactions", "read"),
    "suggest_next_best_action": ("interactions", "read"),
    "suggest_reply_template": ("interactions", "read"),
    # Write-heavy tools
    "create_task": ("tasks", "write"),
    "update_task": ("tasks", "write"),
    "create_followup": ("tasks", "write"),
    "create_cross_department_bridge": ("tasks", "write"),
    "propose_improvement": ("hermes_evolution_log", "write"),
    "propose_policy": ("policy_proposals", "write"),
    "approve_proposal": ("hermes_evolution_log", "write"),
    "record_interaction": ("interactions", "write"),
    "record_deal": ("deals", "write"),
    "mempalace_store": ("memories", "write"),
    # Inter-agent / logical writes
    "delegate_to_agent": ("agent_dialogues", "write"),
    "escalate_to_hermes": ("agent_dialogues", "write"),
    "ask_colleague": ("agent_dialogues", "write"),
    # External
    "web_search": ("external", "read"),
    "fetch_url": ("external", "read"),
}


def _load_skill_meta(skill_id: str) -> dict[str, Any]:
    skill_path = _SKILLS_DIR / f"{skill_id}.md"
    if not skill_path.exists():
        return {}
    content = skill_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _data_access(skill_id: str) -> dict[str, Any]:
    manifest = M.get_manifest(skill_id)
    if manifest:
        return manifest.get("data_access") or {}
    return _load_skill_meta(skill_id).get("data_access") or {}


def _can_read(skill_id: str, collection: str) -> bool:
    manifest = M.get_manifest(skill_id)
    if manifest:
        return M.can_read(skill_id, collection) or M.can_read(skill_id, "*")
    reads = set((_data_access(skill_id).get("read") or []))
    return "*" in reads or collection in reads


def _can_write(skill_id: str, collection: str) -> bool:
    manifest = M.get_manifest(skill_id)
    if manifest:
        return M.can_write(skill_id, collection) or M.can_write(skill_id, "*")
    writes = set((_data_access(skill_id).get("write") or []))
    return "*" in writes or collection in writes


def check_access(skill_id: str, tool_name: str) -> tuple[bool, str]:
    mapping = _TOOL_COLLECTION_MAP.get(tool_name)
    if not mapping:
        return True, ""

    collection, access_type = mapping

    if collection == "external":
        return True, ""

    if access_type == "read":
        if not _can_read(skill_id, collection):
            reason = f"Access Denied: {skill_id} is not allowed to READ from '{collection}' (Guard rule)"
            logger.warning("GUARD: %s", reason)
            return False, reason
    elif access_type == "write":
        if not _can_write(skill_id, collection):
            reason = f"Access Denied: {skill_id} is not allowed to WRITE to '{collection}' (Guard rule)"
            logger.warning("GUARD: %s", reason)
            return False, reason

    return True, ""