"""Tests for the manual Hermes self-audit API handler."""

from __future__ import annotations

import asyncio

import server


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_hermes_self_audit_run_returns_consolidated_payload(monkeypatch):
    async def _fake_health(args):
        assert args["company_id"] == "tenant_manual_audit"
        assert args["window"] == 200
        return {"ok": True, "avg_confidence": 0.82}

    async def _fake_benchmark(args):
        assert args["company_id"] == "tenant_manual_audit"
        assert "главный инструмент" in args["query"]
        return {"ok": True, "total_personas": 7, "passed": 7, "failed": 0}

    class _User:
        company_id = "tenant_manual_audit"

    monkeypatch.setattr(server, "scan_system_health", _fake_health)
    monkeypatch.setattr(server, "run_persona_benchmark", _fake_benchmark)

    res = _run(server.hermes_self_audit_run(user=_User()))
    assert res["ok"] is True
    assert res["company_id"] == "tenant_manual_audit"
    assert res["health"]["avg_confidence"] == 0.82
    assert res["benchmark"]["passed"] == 7
    assert "Telegram alerts" in res["message"]