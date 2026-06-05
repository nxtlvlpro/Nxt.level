"""Tests for the Emergent OAuth + session middleware.

External HTTP to demobackend.emergentagent.com is mocked via httpx.
We exercise: /auth/session exchange, /auth/me, /auth/logout, expired
session rejection, admin token bypass, and the global middleware gate.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core import auth as A
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch):
    monkeypatch.setenv("NXT8_ADMIN_EMAILS", "admin@nxt8.test, other@nxt8.test")
    monkeypatch.setenv("SEED_ADMIN_TOKEN", "test_seed_token_xyz")
    yield


def _fake_oauth_response(email: str = "user@nxt8.test", token: str = "tok_xxx") -> Dict[str, Any]:
    return {
        "id": "google_subj_1",
        "email": email,
        "name": "Test User",
        "picture": "https://example.com/a.png",
        "session_token": token,
    }


def _mock_httpx_get(payload: Dict[str, Any], status: int = 200):
    class _R:
        def __init__(self) -> None:
            self.status_code = status
            self.content = b"{}" if payload else b""
            self.text = ""

        def json(self) -> Dict[str, Any]:
            return payload

    class _Client:
        def __init__(self, *a, **kw) -> None:
            pass

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *a) -> None:
            return None

        async def get(self, url: str, headers=None):
            return _R()

    return _Client


# ---------------------------------------------------------------------
# Public path matching
# ---------------------------------------------------------------------


def test_is_public_path_whitelist() -> None:
    assert A.is_public_path("/api/health") is True
    assert A.is_public_path("/api/health/") is True
    assert A.is_public_path("/api/auth/session") is True
    assert A.is_public_path("/api/auth/me") is True
    assert A.is_public_path("/api/share/abc") is True
    assert A.is_public_path("/api/share/abc/og.png") is True
    assert A.is_public_path("/api/s/abc") is True
    assert A.is_public_path("/api/telegram/webhook/xyz") is True
    assert A.is_public_path("/api/whatsapp/webhook/xyz") is True
    assert A.is_public_path("/api/webhook/stripe") is True
    # NOT public:
    assert A.is_public_path("/api/seed") is False
    assert A.is_public_path("/api/telegram/connect") is False
    assert A.is_public_path("/api/whatsapp/status") is False
    assert A.is_public_path("/api/chat") is False


# ---------------------------------------------------------------------
# Session exchange
# ---------------------------------------------------------------------


def test_auth_session_exchange_creates_user_and_session() -> None:
    """POST /auth/session: given a valid Emergent session_id, upsert
    db.users, insert db.user_sessions, return the user."""
    from fastapi import Response

    payload = _fake_oauth_response(email="brand_new@nxt8.test", token="tok_new_1")
    with patch.object(httpx, "AsyncClient", _mock_httpx_get(payload)):
        res = Response()
        out = _run(A.auth_session(response=res, x_session_id="sess_id_1"))

    assert out["ok"] is True
    assert out["user"]["email"] == "brand_new@nxt8.test"
    assert out["user"]["is_admin"] is False
    assert out["session_token"] == "tok_new_1"

    # DB invariants
    u = _run(get_db().users.find_one({"email": "brand_new@nxt8.test"}, {"_id": 0}))
    assert u and u["user_id"].startswith("user_")
    sess = _run(get_db().user_sessions.find_one({"session_token": "tok_new_1"}, {"_id": 0}))
    assert sess and sess["user_id"] == u["user_id"]

    # Cookie set
    cookie = res.headers.get("set-cookie", "")
    assert "session_token=tok_new_1" in cookie
    assert "HttpOnly" in cookie

    # cleanup
    _run(get_db().user_sessions.delete_many({"session_token": "tok_new_1"}))
    _run(get_db().users.delete_many({"email": "brand_new@nxt8.test"}))


def test_auth_session_admin_email_gets_admin_flag() -> None:
    from fastapi import Response

    payload = _fake_oauth_response(email="admin@nxt8.test", token="tok_admin_1")
    with patch.object(httpx, "AsyncClient", _mock_httpx_get(payload)):
        out = _run(A.auth_session(response=Response(), x_session_id="sess_admin"))

    assert out["user"]["is_admin"] is True

    _run(get_db().user_sessions.delete_many({"session_token": "tok_admin_1"}))
    _run(get_db().users.delete_many({"email": "admin@nxt8.test"}))


def test_auth_session_missing_header_400() -> None:
    from fastapi import HTTPException, Response

    with pytest.raises(HTTPException) as e:
        _run(A.auth_session(response=Response(), x_session_id=None))
    assert e.value.status_code == 400


def test_auth_session_emergent_rejects_401() -> None:
    from fastapi import HTTPException, Response

    with patch.object(httpx, "AsyncClient", _mock_httpx_get({}, status=401)):
        with pytest.raises(HTTPException) as e:
            _run(A.auth_session(response=Response(), x_session_id="bad"))
    assert e.value.status_code == 401


# ---------------------------------------------------------------------
# require_user / require_admin
# ---------------------------------------------------------------------


def _create_user_with_session(email: str, token: str, admin: bool = False) -> str:
    """Insert a user + a fresh 7-day session directly. Returns user_id."""
    import uuid
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    _run(get_db().users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Tester",
        "picture": "",
        "is_admin": admin,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    _run(get_db().user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    return user_id


def _cleanup_user(email: str, token: str) -> None:
    _run(get_db().user_sessions.delete_many({"session_token": token}))
    _run(get_db().users.delete_many({"email": email}))


def test_require_user_accepts_cookie() -> None:
    uid = _create_user_with_session("u_cookie@nxt8.test", "tok_cookie_1")
    try:
        user = _run(A.require_user(session_token="tok_cookie_1", authorization=None))
        assert user.user_id == uid
        assert user.email == "u_cookie@nxt8.test"
    finally:
        _cleanup_user("u_cookie@nxt8.test", "tok_cookie_1")


def test_require_user_accepts_bearer() -> None:
    uid = _create_user_with_session("u_bearer@nxt8.test", "tok_bearer_1")
    try:
        user = _run(A.require_user(session_token=None, authorization="Bearer tok_bearer_1"))
        assert user.user_id == uid
    finally:
        _cleanup_user("u_bearer@nxt8.test", "tok_bearer_1")


def test_require_user_rejects_missing_token() -> None:
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        _run(A.require_user(session_token=None, authorization=None))
    assert e.value.status_code == 401


def test_require_user_rejects_unknown_token() -> None:
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        _run(A.require_user(session_token="ghost_token", authorization=None))
    assert e.value.status_code == 401


def test_require_user_rejects_expired_session() -> None:
    import uuid
    from fastapi import HTTPException

    uid = f"user_{uuid.uuid4().hex[:16]}"
    tok = "tok_expired_1"
    _run(get_db().users.insert_one({
        "user_id": uid, "email": "expired@nxt8.test", "name": "X",
        "is_admin": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    _run(get_db().user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    try:
        with pytest.raises(HTTPException) as e:
            _run(A.require_user(session_token=tok, authorization=None))
        assert e.value.status_code == 401
    finally:
        _cleanup_user("expired@nxt8.test", tok)


def test_require_admin_via_seed_token() -> None:
    user = _run(A.require_admin(
        session_token=None, authorization=None,
        x_admin_token="test_seed_token_xyz",
    ))
    assert user.is_admin is True
    assert user.user_id == "admin:service"


def test_require_admin_via_seed_token_wrong() -> None:
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        _run(A.require_admin(
            session_token=None, authorization=None,
            x_admin_token="WRONG",
        ))
    assert e.value.status_code == 401


def test_require_admin_via_user_email() -> None:
    uid = _create_user_with_session("admin@nxt8.test", "tok_admin_3", admin=True)
    try:
        user = _run(A.require_admin(
            session_token="tok_admin_3", authorization=None, x_admin_token=None
        ))
        assert user.is_admin is True
        assert user.email == "admin@nxt8.test"
    finally:
        _cleanup_user("admin@nxt8.test", "tok_admin_3")


def test_require_admin_blocks_regular_user() -> None:
    from fastapi import HTTPException
    _create_user_with_session("nonadmin@nxt8.test", "tok_normal_1", admin=False)
    try:
        with pytest.raises(HTTPException) as e:
            _run(A.require_admin(
                session_token="tok_normal_1", authorization=None, x_admin_token=None
            ))
        assert e.value.status_code == 403
    finally:
        _cleanup_user("nonadmin@nxt8.test", "tok_normal_1")


# ---------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------


def test_logout_deletes_session_and_clears_cookie() -> None:
    from fastapi import Response

    uid = _create_user_with_session("u_logout@nxt8.test", "tok_logout_1")
    user = _run(A.require_user(session_token="tok_logout_1", authorization=None))

    res = Response()
    out = _run(A.auth_logout(response=res, user=user))
    assert out["ok"] is True
    assert out["removed"] >= 1

    # Session is now gone
    sess = _run(get_db().user_sessions.find_one({"session_token": "tok_logout_1"}))
    assert sess is None

    # cleanup
    _run(get_db().users.delete_many({"email": "u_logout@nxt8.test"}))
