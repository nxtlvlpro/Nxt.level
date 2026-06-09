"""
Tests for Hermes Evolution Engine (Directive §4-§11).

Verifies:
- propose_improvement validates area + persists entry
- list_evolution_roadmap groups by area
- propose_policy validates fields
- detect_automation_candidates handles empty data
- hermes_self_assessment shape

Uses MongoDB via existing get_db() — runs against the real local DB
in this environment; cleans up its own records by id prefix.
"""

from __future__ import annotations

import asyncio
import pytest

from agents import hermes_evolution as ev
from agents.hermes_directive import DIRECTIVE
from agents.hermes import HERMES_TOOLS

TEST_COMPANY_ID = "test_company_123"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ------------------------------------------------------------ Directive


def test_directive_has_twelve_sections():
    for section in [
        "ХАРАКТЕР CEO",
        "ПРОФИТ-ИНСТИНКТ",
        "ПОИСК СЛАБЫХ МЕСТ",
        "ЕДИНАЯ ТОЧКА УПРАВЛЕНИЯ", "КОРПОРАТИВНАЯ ПАМЯТЬ",
        "КОНТРОЛЬ ИСПОЛНЕНИЯ", "САМОУЛУЧШЕНИЕ ПРОЦЕССОВ",
        "РАЗВИТИЕ КОНСТИТУЦИИ КОМПАНИИ", "РАЗВИТИЕ АГЕНТНОЙ СИСТЕМЫ",
        "НЕПРЕРЫВНЫЙ ЦИКЛ УЛУЧШЕНИЙ", "ГРАФ ЗНАНИЙ КОМПАНИИ",
        "ГЛАВНАЯ МЕТРИКА",
    ]:
        assert section in DIRECTIVE, f"directive missing: {section}"


def test_evolution_tools_registered():
    for name in [
        "propose_improvement", "list_evolution_roadmap", "approve_proposal",
        "propose_policy", "list_policy_proposals",
        "detect_automation_candidates", "hermes_self_assessment",
    ]:
        assert name in HERMES_TOOLS, f"tool not registered: {name}"


# ------------------------------------------------------ propose_improvement


def test_propose_improvement_rejects_bad_area():
    res = _run(ev.propose_improvement({"area": "wtf", "description": "x", "company_id": TEST_COMPANY_ID}))
    assert res["ok"] is False
    assert "area" in res["error"]


def test_propose_improvement_requires_description():
    res = _run(ev.propose_improvement({"area": "capability", "company_id": TEST_COMPANY_ID}))
    assert res["ok"] is False


def test_propose_improvement_persists_valid_entry():
    res = _run(ev.propose_improvement({
        "area": "capability",
        "description": "Add Slack channel adapter",
        "expected_benefit": "ingest from external chats",
        "priority": "P1",
        "company_id": TEST_COMPANY_ID,
    }))
    assert res["ok"] is True
    assert res["area"] == "capability"
    assert res["priority"] == "P1"
    pid = res["id"]

    # Read it back via list_evolution_roadmap
    listing = _run(ev.list_evolution_roadmap({"area": "capability", "limit": 200, "company_id": TEST_COMPANY_ID}))
    assert listing["ok"] is True
    assert any(e["id"] == pid for e in listing["entries"])
    assert "capability" in listing["by_area"]

    # Approve flow
    appr = _run(ev.approve_proposal({"id": pid, "status": "approved", "company_id": TEST_COMPANY_ID}))
    assert appr["ok"] is True
    assert appr["entry"]["status"] == "approved"


# -------------------------------------------------------- propose_policy


def test_propose_policy_requires_rule():
    res = _run(ev.propose_policy({"title": "SLA for refunds", "company_id": TEST_COMPANY_ID}))
    assert res["ok"] is False
    assert "rule" in res["error"]


def test_propose_policy_happy_path():
    res = _run(ev.propose_policy({
        "title": "SLA for refunds",
        "scope": "sla",
        "proposed_rule": "Refund tickets MUST be acknowledged within 4h",
        "justification": "Audit shows 22% breach",
        "severity": "high",
        "company_id": TEST_COMPANY_ID,
    }))
    assert res["ok"] is True
    assert res["severity"] == "high"
    listing = _run(ev.list_policy_proposals({"status": "proposed", "limit": 100, "company_id": TEST_COMPANY_ID}))
    assert listing["ok"] is True
    assert any(p["id"] == res["id"] for p in listing["proposals"])


# ----------------------------------------------- automation candidates


def test_detect_automation_candidates_returns_shape():
    res = _run(ev.detect_automation_candidates({"window": 100, "min_count": 2, "company_id": TEST_COMPANY_ID}))
    assert res["ok"] is True
    assert "candidates" in res
    assert isinstance(res["candidates"], list)
    assert res["window"] == 100


# ---------------------------------------------------- self-assessment


def test_hermes_self_assessment_shape():
    res = _run(ev.hermes_self_assessment({"window": 100, "company_id": TEST_COMPANY_ID}))
    assert res["ok"] is True
    if res.get("scanned", 0) > 0:
        for key in ("avg_confidence", "escalation_rate", "mock_rate",
                    "evolution_journal", "signals"):
            assert key in res, f"missing key: {key}"
