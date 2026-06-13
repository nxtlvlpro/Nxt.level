import asyncio

from core import scheduler


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_run_analyst_scan_for_all_invokes_run_persona(monkeypatch):
    calls = []

    async def _fake_list_active_tenants(*, force=False):
        return ["tenant_a", "tenant_b"]

    async def _fake_run_persona(**kwargs):
        calls.append(kwargs)
        return {"success": True}

    monkeypatch.setattr(scheduler, "list_active_tenants", _fake_list_active_tenants)
    monkeypatch.setattr("agents.personas.run_persona", _fake_run_persona)

    _run(scheduler._run_analyst_scan_for_all())

    assert len(calls) == 2
    assert all(call["persona_id"] == "analyst" for call in calls)
    assert {call["company_id"] for call in calls} == {"tenant_a", "tenant_b"}
    assert all(call["user_id"] == "system_analyst_scan" for call in calls)


def test_start_registers_analyst_self_scan_job(monkeypatch):
    class _FakeScheduler:
        def __init__(self, timezone=None):
            self.jobs = []

        def add_job(self, func, trigger, **kwargs):
            self.jobs.append(kwargs)

        def start(self):
            return None

        def shutdown(self, wait=False):
            return None

    monkeypatch.setattr(scheduler, "_scheduler", None)
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", _FakeScheduler)
    monkeypatch.setattr(scheduler, "PULSE_ENABLED", False)
    monkeypatch.setattr(scheduler, "DIGEST_ENABLED", False)
    monkeypatch.setattr(scheduler, "SESSION_CLEANUP_ENABLED", False)
    monkeypatch.setattr(scheduler, "ANALYST_SELF_SCAN_ENABLED", True)
    monkeypatch.setattr(scheduler, "ANALYST_SELF_SCAN_INTERVAL_HOURS", 6)

    scheduler.start()

    assert scheduler.get_scheduler() is not None
    job_ids = {job["id"] for job in scheduler.get_scheduler().jobs}
    assert "analyst_self_scan" in job_ids

    _run(scheduler.shutdown())