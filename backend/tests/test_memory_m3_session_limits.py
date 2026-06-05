"""Memory Sprint · M3: session size cap + TTL.

Verifies:
1. `append_message` caps the `messages[]` array at MAX_SESSION_MESSAGES.
2. Anonymous sessions get a BSON-Date `expires_at` ≈ now + 90 days.
3. Known-user sessions have NO `expires_at` (kept forever by design).
4. Promoting an anon session to a known user clears the prior `expires_at`.
5. `db.sessions.expires_at` has a TTL index (expireAfterSeconds=0).
6. `cleanup_expired_sessions` deletes stale anonymous sessions but
   preserves known-user sessions even when stale.
"""

import asyncio
from datetime import datetime, timezone, timedelta

from agents.memory import get_memory, MAX_SESSION_MESSAGES, SESSION_ANON_TTL_DAYS
from core.db import ensure_indexes, get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _cleanup_sessions():
    db = get_db()
    await db.sessions.delete_many({"session_id": {"$regex": "^sess_m3_"}})


def test_messages_array_is_capped_at_max():
    """Pushing > MAX_SESSION_MESSAGES retains only the most recent N."""

    async def _go():
        await _cleanup_sessions()
        mem = get_memory()
        sid = "sess_m3_cap_a"
        try:
            total = MAX_SESSION_MESSAGES + 25
            for i in range(total):
                await mem.append_message(
                    sid, "user", f"msg-{i:04d}",
                    user_id="anon_test", company_id="tenant_m3_a",
                )
            doc = await get_db().sessions.find_one({"session_id": sid}, {"_id": 0})
            assert doc is not None
            msgs = doc["messages"]
            assert len(msgs) == MAX_SESSION_MESSAGES, (
                f"expected len={MAX_SESSION_MESSAGES}, got {len(msgs)}"
            )
            # Must be the LAST N (FIFO eviction via $slice: -N)
            assert msgs[0]["content"] == f"msg-{25:04d}", msgs[0]["content"]
            assert msgs[-1]["content"] == f"msg-{total - 1:04d}", msgs[-1]["content"]
        finally:
            await _cleanup_sessions()

    _run(_go())


def test_anonymous_session_gets_expires_at():
    """Anonymous sessions must carry a BSON-Date `expires_at` ≈ now + 90d."""

    async def _go():
        await _cleanup_sessions()
        mem = get_memory()
        sid = "sess_m3_anon"
        try:
            await mem.append_message(
                sid, "user", "anon hello",
                user_id="anon_xyz", company_id=None,
            )
            doc = await get_db().sessions.find_one({"session_id": sid}, {"_id": 0})
            assert doc is not None, "session not created"
            exp = doc.get("expires_at")
            assert exp is not None, "anonymous session missing expires_at"
            assert isinstance(exp, datetime), (
                f"expires_at must be BSON Date, got {type(exp).__name__}"
            )
            # roughly now + 90d (within 1 day tolerance for clock skew)
            target = datetime.now(timezone.utc) + timedelta(days=SESSION_ANON_TTL_DAYS)
            exp_utc = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
            diff = abs((exp_utc - target).total_seconds())
            assert diff < 86400, f"expires_at off by {diff}s"
        finally:
            await _cleanup_sessions()

    _run(_go())


def test_known_user_session_has_no_expires_at():
    """Known-user sessions must NEVER get `expires_at` written."""

    async def _go():
        await _cleanup_sessions()
        mem = get_memory()
        sid = "sess_m3_known"
        try:
            await mem.append_message(
                sid, "user", "known hello",
                user_id="u_stable_42", company_id="tenant_m3_b",
            )
            doc = await get_db().sessions.find_one({"session_id": sid}, {"_id": 0})
            assert doc is not None
            assert doc.get("user_id") == "u_stable_42"
            assert "expires_at" not in doc, (
                f"known user must not have expires_at: {doc.get('expires_at')}"
            )
        finally:
            await _cleanup_sessions()

    _run(_go())


def test_anon_to_known_promotion_clears_expires_at():
    """First message anon → 2nd as known user must clear expires_at."""

    async def _go():
        await _cleanup_sessions()
        mem = get_memory()
        sid = "sess_m3_promote"
        try:
            await mem.append_message(
                sid, "user", "hello",
                user_id="home_visitor_x", company_id=None,
            )
            doc1 = await get_db().sessions.find_one({"session_id": sid}, {"_id": 0})
            assert doc1.get("expires_at") is not None

            await mem.append_message(
                sid, "user", "I'm logged in now",
                user_id="u_real_user", company_id="tenant_m3_c",
            )
            doc2 = await get_db().sessions.find_one({"session_id": sid}, {"_id": 0})
            assert doc2.get("user_id") == "u_real_user"
            assert "expires_at" not in doc2, (
                "expires_at must be unset when user becomes known"
            )
        finally:
            await _cleanup_sessions()

    _run(_go())


def test_ttl_index_exists_on_sessions_expires_at():
    """A TTL index on `sessions.expires_at` must exist after ensure_indexes."""

    async def _go():
        await ensure_indexes()
        info = await get_db().sessions.index_information()
        ttl_indexes = {
            name: meta
            for name, meta in info.items()
            if any(k == "expires_at" for k, _ in meta.get("key", []))
        }
        assert ttl_indexes, f"no expires_at index found in {list(info.keys())}"
        # Must have expireAfterSeconds defined (TTL)
        ttl = next(
            (meta for meta in ttl_indexes.values()
             if "expireAfterSeconds" in meta),
            None,
        )
        assert ttl is not None, f"no TTL on expires_at: {ttl_indexes}"
        assert ttl["expireAfterSeconds"] == 0, (
            f"expected expireAfterSeconds=0, got {ttl['expireAfterSeconds']}"
        )

    _run(_go())


def test_cleanup_expired_sessions_purges_anon_only():
    """`cleanup_expired_sessions` deletes stale anon sessions but keeps known ones."""

    async def _go():
        await _cleanup_sessions()
        db = get_db()
        mem = get_memory()
        stale_iso = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        # 1) stale anonymous — must be deleted
        await db.sessions.insert_one({
            "session_id": "sess_m3_stale_anon",
            "messages": [{"role": "user", "content": "old"}],
            "updated_at": stale_iso,
            "created_at": stale_iso,
        })
        # 2) stale known user — must be kept
        await db.sessions.insert_one({
            "session_id": "sess_m3_stale_known",
            "messages": [{"role": "user", "content": "old"}],
            "user_id": "u_keepme",
            "updated_at": stale_iso,
            "created_at": stale_iso,
        })
        # 3) fresh anonymous — must be kept
        fresh_iso = datetime.now(timezone.utc).isoformat()
        await db.sessions.insert_one({
            "session_id": "sess_m3_fresh_anon",
            "messages": [{"role": "user", "content": "new"}],
            "updated_at": fresh_iso,
            "created_at": fresh_iso,
        })
        try:
            deleted = await mem.cleanup_expired_sessions()
            assert deleted >= 1, f"expected ≥1 deleted, got {deleted}"
            assert await db.sessions.find_one(
                {"session_id": "sess_m3_stale_anon"}) is None
            assert await db.sessions.find_one(
                {"session_id": "sess_m3_stale_known"}) is not None
            assert await db.sessions.find_one(
                {"session_id": "sess_m3_fresh_anon"}) is not None
        finally:
            await _cleanup_sessions()

    _run(_go())


def test_scheduler_session_cleanup_job_registered():
    """core.scheduler must register a `session_cleanup` job when enabled."""
    import os
    os.environ["SESSION_CLEANUP_ENABLED"] = "true"
    # Force module reload so the env flag is picked up.
    import importlib
    from core import scheduler as sch_mod
    importlib.reload(sch_mod)
    sch_mod.start()
    try:
        sch = sch_mod.get_scheduler()
        assert sch is not None
        job_ids = {j.id for j in sch.get_jobs()}
        assert "session_cleanup" in job_ids, f"missing job in {job_ids}"
    finally:
        # don't shutdown the global scheduler — server lifecycle owns it.
        pass
