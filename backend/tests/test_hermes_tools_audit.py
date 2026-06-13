"""Tests for Hermes self-audit tools."""

from __future__ import annotations

import asyncio

from agents import hermes_tools_audit as audit


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_scan_system_health_returns_expected_shape(monkeypatch):
    class _FakeCursor:
        def __init__(self, docs):
            self.docs = docs

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        async def to_list(self, length=None):
            return self.docs[:length]

    class _FakeCrud:
        def __init__(self, collection, company_id=None, force_admin=False):
            self.collection = collection

        def find(self, *args, **kwargs):
            if self.collection == "requests":
                return _FakeCursor([
                    {"confidence": 0.9, "latency_ms": 120, "should_escalate": False, "mock": False},
                    {"confidence": 0.5, "latency_ms": 200, "should_escalate": True, "mock": True},
                ])
            return _FakeCursor([])

        async def count_documents(self, query):
            return 3

    class _FakeDB:
        requests = "requests"
        contradictions = "contradictions"

    monkeypatch.setattr(audit, "TenantAwareCRUD", _FakeCrud)
    monkeypatch.setattr(audit, "get_db", lambda: _FakeDB())

    res = _run(audit.scan_system_health({"company_id": "tenant_a", "window": 200}))
    assert res["ok"] is True
    assert res["company_id"] == "tenant_a"
    assert res["scanned"] == 2
    assert res["avg_confidence"] == 0.7
    assert res["escalation_rate"] == 0.5
    assert res["mock_rate"] == 0.5
    assert res["contradiction_count"] == 3


def test_run_persona_benchmark_uses_subordinates_only(monkeypatch):
    calls = []

    async def _fake_run_persona(**kwargs):
        calls.append(kwargs)
        return {"success": True, "confidence": 0.88, "provider": "nxt8_graph"}

    monkeypatch.setattr(
        audit,
        "_get_persona_runtime",
        lambda: ({"hermes", "analyst", "marketer"}, _fake_run_persona),
    )

    res = _run(audit.run_persona_benchmark({"company_id": "tenant_b"}))
    assert res["ok"] is True
    assert res["total_personas"] == 2
    assert res["passed"] == 2
    assert {row["persona"] for row in res["benchmark"]} == {"analyst", "marketer"}
    assert all(call["user_id"] == "hermes_audit" for call in calls)
    assert all(call["session_id"].startswith("audit_") for call in calls)
    assert all(call["persona_id"] != "hermes" for call in calls)


def test_run_persona_benchmark_handles_missing_mongo_url(monkeypatch):
    async def _fake_run_persona(**kwargs):
        if kwargs["persona_id"] == "hr_mentor":
            raise KeyError("MONGO_URL")
        return {"success": True, "confidence": 0.9, "provider": "nxt8_graph"}

    monkeypatch.setattr(
        audit,
        "_get_persona_runtime",
        lambda: ({"hermes", "hr_mentor", "analyst"}, _fake_run_persona),
    )

    res = _run(audit.run_persona_benchmark({"company_id": "tenant_c"}))
    assert res["ok"] is True
    assert res["failed"] == 1
    failing = next(row for row in res["benchmark"] if row["persona"] == "hr_mentor")
    assert failing["success"] is False
    assert failing["error"] == "DB unavailable in sandbox mode"
    assert failing["provider"] == "nxt8_graph"
    assert failing["mock"] is True