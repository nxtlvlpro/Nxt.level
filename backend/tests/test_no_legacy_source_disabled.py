import os

import pytest


ACTIVE_MODULES = [
    "backend/agents/personas.py",
    "backend/agents/joker.py",
    "backend/agents/orchestrator.py",
    "backend/agents/hermes_os_graph.py",
    "backend/agents/hermes_graph_v2.py",
]


@pytest.mark.parametrize("module", ACTIVE_MODULES)
def test_no_legacy_source_disabled(module):
    if not os.path.exists(module):
        pytest.skip(f"File {module} does not exist")

    with open(module, "r", encoding="utf-8") as f:
        content = f.read()

    assert "LEGACY_SOURCE_DISABLED" not in content, (
        f"Found LEGACY_SOURCE_DISABLED in {module}. Use /archived/ for legacy code."
    )