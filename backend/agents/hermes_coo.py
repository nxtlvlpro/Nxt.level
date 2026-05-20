"""
DEPRECATED: kept only for backward import compatibility.

The actual Hermes COO implementation has moved to `agents/hermes.py`
(unified module, fenced-JSON tool-calling, single source of truth).

This module re-exports the unified public surface so existing imports
keep working (server.py, tests, persona layer).
"""
from __future__ import annotations

from agents.hermes import (  # noqa: F401
    HERMES_TOOLS,
    enhanced_chat,
    hermes_chat,
    hermes_coo_chat,
)
