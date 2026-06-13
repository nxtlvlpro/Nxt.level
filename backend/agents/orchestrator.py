"""Compatibility shim for the legacy orchestrator during Phase 1 cleanup."""

from __future__ import annotations

from agents.legacy import orchestrator_legacy as _legacy

route = _legacy.route
list_recent_requests = _legacy.list_recent_requests
list_alerts = _legacy.list_alerts


def __getattr__(name: str):
    return getattr(_legacy, name)


