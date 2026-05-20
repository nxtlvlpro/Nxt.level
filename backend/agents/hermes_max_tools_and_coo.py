"""
DEPRECATED: kept only for backward import compatibility.

The Hermes Max tool registry and the `hermes_coo_chat` LLM call have
been unified into `agents/hermes.py`. This module re-exports the
unified public surface so:

  * `nxt8_langgraph_ultra.py` imports `HERMES_TOOLS, hermes_coo_chat`
  * `tests/test_hermes_ultra.py` imports `HERMES_TOOLS`
  * `agents/personas.py`        imports `HERMES_TOOLS`

…all keep working without modification.
"""
from __future__ import annotations

from agents.hermes import (  # noqa: F401
    HERMES_TOOLS,
    hermes_chat,
    hermes_coo_chat,
)
