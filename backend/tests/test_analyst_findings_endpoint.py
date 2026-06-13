import asyncio

import server


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_analyst_findings_endpoint_returns_latest_rows(monkeypatch):
    class _FakeCursor:
        def __init__(self, rows):
            self.rows = rows

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        async def to_list(self, length=None):
            return self.rows[:length]

    class _FakeCRUD:
        def __init__(self, collection, company_id=None, force_admin=False):
            self.company_id = company_id

        def find(self, *args, **kwargs):
            return _FakeCursor([
                {"id": "f1", "tenant_id": "tenant_a", "summary": "confidence drop"},
                {"id": "f2", "tenant_id": "tenant_a", "summary": "mock rate high"},
            ])

    class _User:
        company_id = "tenant_a"

    monkeypatch.setattr(server, "TenantAwareCRUD", _FakeCRUD)

    res = _run(server.analyst_findings_list(limit=10, user=_User()))
    assert res["ok"] is True
    assert res["count"] == 2
    assert res["findings"][0]["id"] == "f1"