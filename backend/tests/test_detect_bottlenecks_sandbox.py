import asyncio

from agents import diagnostics as diagnostics_agent
from agents import hermes


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_detect_bottlenecks_handles_missing_database(monkeypatch):
    async def _boom_summary(*args, **kwargs):
        raise KeyError("MONGO_URL")

    monkeypatch.setattr(diagnostics_agent, "summary", _boom_summary)

    res = _run(hermes._t_detect_bottlenecks({"company_id": "audit_preview"}))
    assert res == {
        "ok": False,
        "error": "diagnostics unavailable in current context",
        "warning_only": True,
        "details": "DB not configured (sandbox mode)",
    }