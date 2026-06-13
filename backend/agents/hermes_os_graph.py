"""Compatibility shim for the legacy OS graph during Phase 1 cleanup."""

from __future__ import annotations

from agents.legacy import hermes_os_graph_legacy as _legacy

run_os_cycle = _legacy.run_os_cycle
list_node_order = _legacy.list_node_order


def __getattr__(name: str):
    return getattr(_legacy, name)


