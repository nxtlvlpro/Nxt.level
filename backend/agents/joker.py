"""Compatibility shim for the legacy JOKER sandbox during Phase 1 cleanup."""

from __future__ import annotations

from agents.legacy import joker_legacy as _legacy

respond = _legacy.respond
stats = _legacy.stats


def __getattr__(name: str):
    return getattr(_legacy, name)


