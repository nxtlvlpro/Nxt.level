"""Regression tests for complexity router heuristics."""

from __future__ import annotations

import asyncio

from core import complexity_router as router
from core import nxt8_graph


def test_pick_model_keeps_simple_analyst_ping_on_cheap_model():
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": "Ping"}],
        intent="analyst",
    )
    assert chosen == router.MODEL_CHEAP


def test_pick_model_routes_financial_analyst_request_to_reasoner():
    router.reset_stats()
    chosen = router.pick_model(
        [{
            "role": "user",
            "content": "Сделай cohort-анализ по MRR, CAC, LTV и churn, сравни 3 сценария ценообразования и посчитай payback period.",
        }],
        intent="analyst",
    )
    assert chosen == router.MODEL_REASONER


def test_pick_model_routes_code_debug_request_to_reasoner():
    router.reset_stats()
    chosen = router.pick_model(
        [{
            "role": "user",
            "content": "Найди root cause по stack trace, предложи refactor SQL query и объясни архитектурный trade-off.",
        }],
        intent="analyst",
    )
    assert chosen == router.MODEL_REASONER


def test_execute_node_passes_router_choice_to_deepseek(monkeypatch):
    seen = {}

    async def _fake_chat(**kwargs):
        seen["model_override"] = kwargs.get("model_override")
        return {"content": "ok", "tokens_total": 7, "confidence": 0.9, "mock": False}

    class _FakeDS:
        chat = staticmethod(_fake_chat)

    monkeypatch.setattr(nxt8_graph, "load_skill", lambda skill_id: ("system prompt", {"allowed_tools": []}))
    monkeypatch.setattr(nxt8_graph, "get_deepseek", lambda: _FakeDS())
    monkeypatch.setattr(nxt8_graph, "pick_model", lambda **kwargs: router.MODEL_REASONER)

    async def _run():
        return await nxt8_graph.execute_node({
            "skill_id": "analyst",
            "messages": [{"role": "user", "content": "Посчитай юнит-экономику"}],
            "tokens_total": 0,
        })

    res = asyncio.get_event_loop().run_until_complete(_run())
    assert seen["model_override"] == router.MODEL_REASONER
    assert res["confidence"] == 0.9