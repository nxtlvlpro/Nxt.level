import asyncio

import server


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _User:
    company_id = "tenant_a"
    user_id = "owner_a"


def test_analyst_findings_resolve_marks_resolved(monkeypatch):
    updates = []

    class _FakeCRUD:
        def __init__(self, collection, company_id=None, force_admin=False):
            self.company_id = company_id

        async def find_one(self, query, projection=None):
            return {"id": "f1", "company_id": self.company_id, "resolved": False}

        async def update_one(self, query, update, *args, **kwargs):
            updates.append((query, update))

    monkeypatch.setattr(server, "TenantAwareCRUD", _FakeCRUD)

    res = _run(server.analyst_findings_resolve("f1", user=_User()))
    assert res["ok"] is True
    assert res["resolved"] is True
    assert updates[0][0] == {"id": "f1"}


def test_analyst_findings_escalate_creates_task_and_escalation(monkeypatch):
    updates = []

    class _FakeCRUD:
        def __init__(self, collection, company_id=None, force_admin=False):
            self.company_id = company_id

        async def find_one(self, query, projection=None):
            return {
                "id": "f1",
                "company_id": self.company_id,
                "type": "contradiction",
                "summary": "Противоречивые ответы",
                "details": "Есть рост противоречий между агентами",
                "urgency": "high",
            }

        async def update_one(self, query, update, *args, **kwargs):
            updates.append((query, update))

    async def _fake_create_task(args):
        return {"ok": True, "task": {"id": "task_123"}}

    async def _fake_escalate(args):
        return {"ok": True, "escalation_id": "esc_123"}

    monkeypatch.setattr(server, "TenantAwareCRUD", _FakeCRUD)
    monkeypatch.setattr("agents.hermes._t_create_task", _fake_create_task)
    monkeypatch.setattr("agents.inter_agent.escalate_to_hermes", _fake_escalate)

    res = _run(server.analyst_findings_escalate("f1", user=_User()))
    assert res["ok"] is True
    assert res["task_id"] == "task_123"
    assert res["escalation_id"] == "esc_123"
    assert updates[0][0] == {"id": "f1"}