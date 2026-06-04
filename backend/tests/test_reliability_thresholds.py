"""Regression tests for reliability thresholds (tuned 2026-02-06)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_no_escalation_on_normal_answer_with_no_memory():
    """A confident, on-topic answer with NO memory_context must NOT escalate."""
    from agents.reliability import assess
    res = assess(
        response="Hermes — это CEO операционной системы NXT8. Он координирует команду из семи специализированных агентов и принимает финальные решения.",
        deepseek_confidence=0.75,
        memory_context=[],
        past_responses=[],
    )
    assert res.should_escalate is False, f"unexpected escalation: {res}"
    assert res.verification_status == "skipped"


def test_low_confidence_still_escalates():
    """Genuinely shaky answers (score < 0.45) MUST still escalate."""
    from agents.reliability import assess
    res = assess(
        response="не знаю точно, может быть, наверное.",
        deepseek_confidence=0.05,
        evidence_count=0,
        source="unknown",
        memory_context=[],
        past_responses=[],
    )
    assert res.should_escalate is True, f"expected escalate, got {res}"


def test_contradiction_alone_does_not_escalate():
    """A single topical-overlap mismatch with healthy confidence must not escalate."""
    from agents.reliability import assess
    res = assess(
        response="Тариф Pro стоит $19 в месяц и включает шесть агентов.",
        deepseek_confidence=0.8,
        past_responses=["Pro tier provides access to 6 agents."],
        memory_context=[],
    )
    assert res.should_escalate is False


def test_majority_hallucination_escalates():
    """When most statements have zero anchoring AND no verified, escalate."""
    from agents.reliability import assess
    res = assess(
        response=(
            "Случайный факт раз. "
            "Случайный факт два. "
            "Случайный факт три. "
            "Случайный факт четыре."
        ),
        deepseek_confidence=0.7,
        memory_context=[
            "Совсем про другое: погода в Москве",
            "Цены на нефть",
        ],
    )
    # all statements low-sim against memory, none verified → hallucination
    assert res.verification_status == "hallucination"
    assert res.should_escalate is True


if __name__ == "__main__":
    test_no_escalation_on_normal_answer_with_no_memory()
    test_low_confidence_still_escalates()
    test_contradiction_alone_does_not_escalate()
    test_majority_hallucination_escalates()
    print("ALL OK")
