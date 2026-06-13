"""Compatibility shim for the legacy graph v2 during Phase 1 cleanup."""

from __future__ import annotations

from agents.legacy import hermes_graph_v2_legacy as _legacy

run_graph_v2 = _legacy.run_graph_v2


def __getattr__(name: str):
    return getattr(_legacy, name)


