"""Tests for the admin gate on /api/seed.

We exercise the require_admin Depends directly. Three valid paths
('X-Admin-Token', admin session), one rejection path (regular user),
and the un-authenticated case (handled by middleware in production).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core import auth as A
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("NXT8_ADMIN_EMAILS", "admin@nxt8.test")
    monkeypatch.setenv("SEED_ADMIN_TOKEN", "test_seed_token_xyz")
    yield


def _make_session(email: str, admin: bool, token: str) -> str:
    uid = f"user_{uuid.uuid4().hex[:16]}"
    _run(get_db().users.insert_one({
        "user_id": uid,
        "email": email,
        "name": "Tester",
        "is_admin": admin,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    _run(get_db().user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    return uid


def _cleanup(email: str, token: str) -> None:
    _run(get_db().user_sessions.delete_many({"session_token": token}))
    _run(get_db().users.delete_many({"email": email}))


# ---------------------------------------------------------------------
# /api/seed admin gate
# ---------------------------------------------------------------------


def test_seed_allows_service_token() -> None:
    """Correct `X-Admin-Token` resolves to a synthetic admin user."""
    user = _run(A.require_admin(
        session_token=None, authorization=None,
        x_admin_token="test_seed_token_xyz",
    ))
    assert user.is_admin is True
    assert user.email == "admin@service"


def test_seed_rejects_wrong_service_token() -> None:
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        _run(A.require_admin(
            session_token=None, authorization=None,
            x_admin_token="completely-wrong-token",
        ))
    assert e.value.status_code == 401


def test_seed_allows_admin_via_email_allowlist() -> None:
    tok = "tok_admin_via_email"
    _make_session("admin@nxt8.test", admin=True, token=tok)
    try:
        user = _run(A.require_admin(
            session_token=tok, authorization=None, x_admin_token=None,
        ))
        assert user.is_admin is True
        assert user.email == "admin@nxt8.test"
    finally:
        _cleanup("admin@nxt8.test", tok)


def test_seed_rejects_regular_authed_user_403() -> None:
    """Logged-in non-admin user is recognised but gets 403, not 401 —
    so the frontend doesn't bounce them to /login."""
    from fastapi import HTTPException
    tok = "tok_regular_user_seed"
    _make_session("regular_user@nxt8.test", admin=False, token=tok)
    try:
        with pytest.raises(HTTPException) as e:
            _run(A.require_admin(
                session_token=tok, authorization=None, x_admin_token=None,
            ))
        assert e.value.status_code == 403
        assert e.value.detail == "admin_only"
    finally:
        _cleanup("regular_user@nxt8.test", tok)


def test_seed_rejects_anonymous_401() -> None:
    """Anonymous caller (no cookie, no Bearer, no X-Admin-Token)."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        _run(A.require_admin(
            session_token=None, authorization=None, x_admin_token=None,
        ))
    assert e.value.status_code == 401


def test_seed_endpoint_runs_when_admin() -> None:
    """The endpoint body executes successfully under admin auth.
    We exercise `seed_demo` directly with a synthetic admin user."""
    from server import seed_demo
    admin = A.AuthedUser(
        user_id="admin:service",
        email="admin@service",
        name="Service",
        is_admin=True,
    )
    out = _run(seed_demo(_admin=admin))
    # Either "ok" (fresh DB) or "already_seeded" (idempotent rerun) — both fine.
    assert out.get("status") in {"ok", "already_seeded"}
    assert "memories" in out
