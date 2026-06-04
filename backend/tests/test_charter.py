"""
Tests for NXT8 Agent Charter — the two universal principles:
1) proactive business value
2) strict no-hallucination + web_search fallback
"""

from __future__ import annotations

import pytest

from agents.agent_charter import CHARTER, with_charter
from agents import manifests as M


def test_charter_contains_business_value_principle():
    assert "ПРОАКТИВНЫЙ ПОИСК БИЗНЕС-ЦЕННОСТИ" in CHARTER
    for keyword in ("выручк", "сэкономить", "процесс", "риск"):
        assert keyword in CHARTER.lower(), f"charter missing keyword: {keyword}"


def test_charter_contains_no_hallucination_principle():
    assert "СТРОГИЙ ЗАПРЕТ НА ВЫМЫСЕЛ" in CHARTER
    assert "web_search" in CHARTER
    assert "Не знаю" in CHARTER


def test_charter_contains_source_principle():
    assert "ИСТОЧНИК" in CHARTER
    for marker in ("(memory)", "(web:", "(doc:"):
        assert marker in CHARTER, f"charter missing source marker: {marker}"


def test_with_charter_prepends_to_prompt():
    out = with_charter("Ты — bookkeeper.")
    assert out.startswith("## КОДЕКС NXT8")
    assert out.endswith("Ты — bookkeeper.")


def test_with_charter_empty_input():
    assert with_charter("") == CHARTER


@pytest.mark.parametrize("pid", list(M.MANIFESTS.keys()))
def test_all_personas_have_web_tools_or_wildcard(pid):
    """Every persona must be able to either web-search OR delegate (Hermes has *)."""
    tools = M.MANIFESTS[pid].get("tools")
    if tools == "*":
        return  # Hermes — wildcard access
    assert "web_search" in tools and "fetch_url" in tools, \
        f"{pid} missing web research tools: {tools}"
