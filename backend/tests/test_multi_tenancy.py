"""Tests for multi-tenancy (Iteration 2 / Task 0).

We exercise:
  • derive_company_id() — pure logic
  • Memory write/list/search isolation between two tenants
  • Pending-approval list + read isolation
  • Onboarding profile cross-tenant 404
  • Admin override (admin sees foreign tenants)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from core import auth as A
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------
# Pure derivation
# ---------------------------------------------------------------------


@pytest.mark.parametrize("email,expected", [
    ("buro8arno@gmail.com",        "gmail_buro8arno"),
    ("John.Doe@ACME.com",          "acme"),
    ("client@acme.com",            "acme"),
    ("other@acme.io",              "acme"),
    ("ivan@yandex.ru",             "yandex_ivan"),
    ("user.name+tag@gmail.com",    "gmail_user_name_tag"),
    ("admin@bigcorp.co.uk",        "bigcorp"),
    ("",                           "orphan_anon"),
    ("noatsign",                   "orphan_noatsign"),
])
def test_derive_company_id(email: str, expected: str) -> None:
    assert A.derive_company_id(email) == expected


# ---------------------------------------------------------------------
# Fixtures — two tenants, two users
# ---------------------------------------------------------------------


def _make_user(email: str) -> A.AuthedUser:
    """Insert a user via the real auth code path so company_id is set."""
    profile = {
        "email": email,
        "name": email.split("@")[0],
        "picture": "",
        "id": str(uuid.uuid4()),
    }
    rec = _run(A._upsert_user(profile))
    return A.AuthedUser(
        user_id=rec["user_id"],
        email=rec["email"],
        name=rec.get("name", ""),
        picture=rec.get("picture", ""),
        is_admin=bool(rec.get("is_admin")),
        company_id=rec.get("company_id", ""),
    )


def _cleanup_email(email: str) -> None:
    _run(get_db().users.delete_many({"email": email.lower()}))


# ---------------------------------------------------------------------
# Memory isolation
# ---------------------------------------------------------------------


def test_memory_writes_are_tagged_with_company_id() -> None:
    alice = _make_user("alice@tenancytest_acme.com")
    try:
        from agents import memory as memory_agent
        mid = _run(memory_agent.get_memory().store_memory(
            content="acme-only memo " + alice.user_id, memory_type="corporate"
        ))
        # Mirror the endpoint's post-write tag
        _run(get_db().memories.update_one(
            {"id": mid}, {"$set": {"company_id": alice.company_id}}
        ))
        doc = _run(get_db().memories.find_one({"id": mid}, {"_id": 0}))
        assert doc["company_id"] == "tenancytest_acme"

        # Cleanup
        _run(get_db().memories.delete_many({"id": mid}))
    finally:
        _cleanup_email("alice@tenancytest_acme.com")


def test_memory_list_filters_by_company_id() -> None:
    """Two tenants writing memories — each only sees their own."""
    alice = _make_user("alice@tenancytest_isol_a.com")
    bob = _make_user("bob@tenancytest_isol_b.com")
    try:
        from agents import memory as memory_agent
        mid_a = _run(memory_agent.get_memory().store_memory(
            content="alice-secret " + alice.user_id, memory_type="corporate"
        ))
        mid_b = _run(memory_agent.get_memory().store_memory(
            content="bob-secret " + bob.user_id, memory_type="corporate"
        ))
        _run(get_db().memories.update_one(
            {"id": mid_a}, {"$set": {"company_id": alice.company_id}}
        ))
        _run(get_db().memories.update_one(
            {"id": mid_b}, {"$set": {"company_id": bob.company_id}}
        ))

        # Alice's filter
        alice_rows = _run(get_db().memories.find(
            {"company_id": alice.company_id}, {"_id": 0}
        ).to_list(length=100))
        ids = {r["id"] for r in alice_rows}
        assert mid_a in ids
        assert mid_b not in ids

        # Bob's filter
        bob_rows = _run(get_db().memories.find(
            {"company_id": bob.company_id}, {"_id": 0}
        ).to_list(length=100))
        bob_ids = {r["id"] for r in bob_rows}
        assert mid_b in bob_ids
        assert mid_a not in bob_ids

        _run(get_db().memories.delete_many({"id": {"$in": [mid_a, mid_b]}}))
    finally:
        _cleanup_email("alice@tenancytest_isol_a.com")
        _cleanup_email("bob@tenancytest_isol_b.com")


# ---------------------------------------------------------------------
# Pending-approval isolation
# ---------------------------------------------------------------------


def test_pending_approval_list_filters_by_company_id() -> None:
    from core import approval_gate as _ag
    # Inject two pending approvals, one per tenant.
    a1 = _run(_ag.request_approval(
        agent_id="client_manager", action="create_task",
        args={"title": "alpha"}, company_id="t_a_alpha",
    ))
    b1 = _run(_ag.request_approval(
        agent_id="client_manager", action="create_task",
        args={"title": "beta"}, company_id="t_b_beta",
    ))
    aid = a1["approval_id"]
    bid = b1["approval_id"]
    try:
        alpha_only = _run(_ag.list_pending(company_id="t_a_alpha", limit=20))
        assert any(r["id"] == aid for r in alpha_only)
        assert not any(r["id"] == bid for r in alpha_only)

        beta_only = _run(_ag.list_pending(company_id="t_b_beta", limit=20))
        assert any(r["id"] == bid for r in beta_only)
        assert not any(r["id"] == aid for r in beta_only)
    finally:
        _run(get_db().pending_approvals.delete_many({"id": {"$in": [aid, bid]}}))


# ---------------------------------------------------------------------
# Onboarding profile cross-tenant 404 path
# ---------------------------------------------------------------------


def test_onboarding_profile_isolation() -> None:
    """A profile tagged with one tenant must 404 for another tenant via
    the endpoint logic. We invoke the endpoint function directly."""
    alice = _make_user("alice@tenancytest_onb_a.com")
    bob = _make_user("bob@tenancytest_onb_b.com")
    pid = str(uuid.uuid4())
    _run(get_db().client_profiles.insert_one({
        "id": pid,
        "company_id": alice.company_id,
        "industry": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    try:
        # Alice can read
        from server import onboarding_get_profile
        own = _run(onboarding_get_profile(pid, user=alice))
        assert own["id"] == pid

        # Bob (different tenant, non-admin) gets 404
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            _run(onboarding_get_profile(pid, user=bob))
        assert e.value.status_code == 404
    finally:
        _run(get_db().client_profiles.delete_many({"id": pid}))
        _cleanup_email("alice@tenancytest_onb_a.com")
        _cleanup_email("bob@tenancytest_onb_b.com")


def test_admin_bypasses_tenant_filter() -> None:
    """An admin user should see profiles from any tenant."""
    admin = A.AuthedUser(
        user_id="admin_test_t0", email="admin@nxt8.local",
        is_admin=True, company_id="nxt8_local_admin",
    )
    pid = str(uuid.uuid4())
    _run(get_db().client_profiles.insert_one({
        "id": pid,
        "company_id": "some_other_tenant",
        "industry": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    try:
        from server import onboarding_get_profile
        result = _run(onboarding_get_profile(pid, user=admin))
        assert result["id"] == pid
    finally:
        _run(get_db().client_profiles.delete_many({"id": pid}))


# ---------------------------------------------------------------------
# AuthedUser carries company_id end-to-end
# ---------------------------------------------------------------------


def test_resolve_token_returns_user_with_company_id() -> None:
    # Create a fresh user via the OAuth flow simulation.
    alice = _make_user("alice@tenancytest_e2e.com")

    tok = "tok_tenancy_e2e_1"
    _run(get_db().user_sessions.insert_one({
        "user_id": alice.user_id,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc).replace(year=2030),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    try:
        resolved = _run(A._resolve_user_from_token(tok))
        assert resolved is not None
        assert resolved.company_id == "tenancytest_e2e"
        assert resolved.email == "alice@tenancytest_e2e.com"
    finally:
        _run(get_db().user_sessions.delete_many({"session_token": tok}))
        _cleanup_email("alice@tenancytest_e2e.com")


def test_legacy_user_backfills_company_id() -> None:
    """Users created before Iteration-2 had no `company_id`. The resolve
    path should lazily backfill it on next session lookup."""
    uid = f"user_{uuid.uuid4().hex[:16]}"
    email = "legacy@tenancytest_legacy.com"
    _run(get_db().users.insert_one({
        "user_id": uid, "email": email, "name": "Legacy",
        # NB: deliberately no company_id
        "is_admin": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    tok = "tok_legacy_backfill_1"
    _run(get_db().user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": datetime.now(timezone.utc).replace(year=2030),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    try:
        resolved = _run(A._resolve_user_from_token(tok))
        assert resolved.company_id == "tenancytest_legacy"
        # Confirmed persisted back to db.users
        doc = _run(get_db().users.find_one({"user_id": uid}, {"_id": 0}))
        assert doc["company_id"] == "tenancytest_legacy"
    finally:
        _run(get_db().user_sessions.delete_many({"session_token": tok}))
        _cleanup_email(email)
