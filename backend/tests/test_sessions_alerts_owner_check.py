import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from core.auth import AuthedUser
from core.db import TenantAwareCRUD, get_db
from server import get_session, list_alerts


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture
def seeded_security_docs():
    async def _seed():
        db = get_db()
        sessions = TenantAwareCRUD(db.sessions, force_admin=True)
        alerts = TenantAwareCRUD(db.alerts, force_admin=True)

        await sessions.delete_many({"session_id": {"$in": ["sess_owner_demo", "sess_other_demo", "sess_other_tenant"]}})
        await alerts.delete_many({"id": {"$in": ["alert_demo_1", "alert_other_1"]}})

        now = datetime.now(timezone.utc).isoformat()
        await sessions.insert_one({
            "session_id": "sess_owner_demo",
            "user_id": "u_demo",
            "company_id": "demo",
            "messages": [{"role": "user", "content": "hello", "ts": now}],
            "created_at": now,
            "updated_at": now,
        })
        await sessions.insert_one({
            "session_id": "sess_other_demo",
            "user_id": "u_other",
            "company_id": "demo",
            "messages": [{"role": "user", "content": "other", "ts": now}],
            "created_at": now,
            "updated_at": now,
        })
        await sessions.insert_one({
            "session_id": "sess_other_tenant",
            "user_id": "u_x",
            "company_id": "otherco",
            "messages": [{"role": "user", "content": "secret", "ts": now}],
            "created_at": now,
            "updated_at": now,
        })

        await alerts.insert_one({
            "id": "alert_demo_1",
            "company_id": "demo",
            "severity": "info",
            "message": "demo alert",
            "created_at": now,
        })
        await alerts.insert_one({
            "id": "alert_other_1",
            "company_id": "otherco",
            "severity": "critical",
            "message": "other alert",
            "created_at": now,
        })

    _run(_seed())
    yield


def test_get_session_allows_owner(seeded_security_docs):
    user = AuthedUser(user_id="u_demo", email="u_demo@nxt8.test", is_admin=False, company_id="demo")
    res = _run(get_session("sess_owner_demo", user))
    assert res["session_id"] == "sess_owner_demo"
    assert len(res["messages"]) == 1


def test_get_session_forbids_other_user_same_company(seeded_security_docs):
    user = AuthedUser(user_id="u_demo", email="u_demo@nxt8.test", is_admin=False, company_id="demo")
    with pytest.raises(HTTPException) as exc:
        _run(get_session("sess_other_demo", user))
    assert exc.value.status_code == 403


def test_get_session_hides_other_tenant(seeded_security_docs):
    user = AuthedUser(user_id="u_demo", email="u_demo@nxt8.test", is_admin=False, company_id="demo")
    with pytest.raises(HTTPException) as exc:
        _run(get_session("sess_other_tenant", user))
    assert exc.value.status_code == 404


def test_get_session_admin_can_read_any(seeded_security_docs):
    admin = AuthedUser(user_id="admin", email="admin@nxt8.test", is_admin=True, company_id="demo")
    res = _run(get_session("sess_other_tenant", admin))
    assert res["session_id"] == "sess_other_tenant"


def test_alerts_filtered_by_company(seeded_security_docs):
    user = AuthedUser(user_id="u_demo", email="u_demo@nxt8.test", is_admin=False, company_id="demo")
    res = _run(list_alerts(50, user))
    ids = {a["id"] for a in res["alerts"]}
    assert "alert_demo_1" in ids
    assert "alert_other_1" not in ids


def test_alerts_admin_sees_all(seeded_security_docs):
    admin = AuthedUser(user_id="admin", email="admin@nxt8.test", is_admin=True, company_id="demo")
    res = _run(list_alerts(50, admin))
    ids = {a["id"] for a in res["alerts"]}
    assert "alert_demo_1" in ids
    assert "alert_other_1" in ids