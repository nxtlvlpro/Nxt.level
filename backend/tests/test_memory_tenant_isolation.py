"""Memory Sprint · M1: TF-IDF + sessions tenant isolation.

These tests run directly against the engine (no HTTP), with real Mongo.
Each test cleans up after itself.
"""

import asyncio

from agents.memory import get_memory
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


_TAG = "audit_m1"


async def _cleanup(tenants):
    db = get_db()
    await db.memories.delete_many({"metadata.audit_tag": _TAG})
    await db.sessions.delete_many({"session_id": {"$regex": "^sess_m1_"}})
    # also reset the engine cache for these tenants so a fresh test starts clean
    eng = get_memory()
    for t in tenants:
        eng._tfidf_cache.pop(t, None)
    eng._tfidf_cache.pop(None, None)


def test_append_message_writes_company_id_at_root():
    """db.sessions doc must carry company_id at the top level."""

    async def _go():
        await _cleanup([])
        mem = get_memory()
        await mem.append_message(
            "sess_m1_root_a", "user", "secret A: 99999",
            user_id="u_m1_a", company_id="tenant_m1_a",
        )
        db = get_db()
        doc = await db.sessions.find_one({"session_id": "sess_m1_root_a"}, {"_id": 0})
        try:
            assert doc is not None
            assert doc["company_id"] == "tenant_m1_a"
            assert doc["user_id"] == "u_m1_a"
            assert len(doc["messages"]) == 1
        finally:
            await db.sessions.delete_one({"session_id": "sess_m1_root_a"})

    _run(_go())


def test_store_memory_writes_company_id_at_root():
    """db.memories doc must carry company_id at the top level (not buried in metadata)."""

    async def _go():
        await _cleanup(["tenant_m1_store"])
        mem = get_memory()
        mid = await mem.store_memory(
            "policy for store test",
            memory_type="corporate",
            metadata={"audit_tag": _TAG},
            company_id="tenant_m1_store",
        )
        db = get_db()
        doc = await db.memories.find_one({"id": mid}, {"_id": 0})
        try:
            assert doc is not None
            assert doc["company_id"] == "tenant_m1_store"
            # ensure not also accidentally written in metadata
            assert "company_id" not in (doc.get("metadata") or {})
        finally:
            await db.memories.delete_one({"id": mid})

    _run(_go())


def test_tfidf_search_returns_only_own_tenant():
    """The /memory/search leak case from the audit must be closed.

    Tenant A stores "salary policy A". Tenant B stores "salary policy B".
    A query for "salary policy" from tenant_A must return ONLY A's row.
    """

    async def _go():
        await _cleanup(["tenant_m1_iso_a", "tenant_m1_iso_b"])
        mem = get_memory()
        a = await mem.store_memory(
            "Salary policy A: bonus 20%",
            metadata={"audit_tag": _TAG},
            company_id="tenant_m1_iso_a",
        )
        b = await mem.store_memory(
            "Salary policy B: bonus 5%",
            metadata={"audit_tag": _TAG},
            company_id="tenant_m1_iso_b",
        )
        try:
            res_a = await mem.search("salary policy", top_k=10,
                                     company_id="tenant_m1_iso_a")
            res_b = await mem.search("salary policy", top_k=10,
                                     company_id="tenant_m1_iso_b")
            ids_a = {r["id"] for r in res_a}
            ids_b = {r["id"] for r in res_b}
            assert a in ids_a and b not in ids_a, (
                f"tenant A leaked B: {ids_a}"
            )
            assert b in ids_b and a not in ids_b, (
                f"tenant B leaked A: {ids_b}"
            )
        finally:
            db = get_db()
            await db.memories.delete_many({"id": {"$in": [a, b]}})

    _run(_go())


def test_null_company_id_does_not_leak_to_tenants():
    """Legacy NULL-tagged memories must NOT show up in a tenant query."""

    async def _go():
        await _cleanup(["tenant_m1_null"])
        mem = get_memory()
        # legacy / global doc (no company_id)
        legacy = await mem.store_memory(
            "Legacy global note xyz_unique_token",
            metadata={"audit_tag": _TAG},
            company_id=None,
        )
        # tenant-specific
        owned = await mem.store_memory(
            "Tenant owns xyz_unique_token",
            metadata={"audit_tag": _TAG},
            company_id="tenant_m1_null",
        )
        try:
            res_tenant = await mem.search("xyz_unique_token", top_k=10,
                                          company_id="tenant_m1_null")
            ids = {r["id"] for r in res_tenant}
            assert owned in ids
            assert legacy not in ids, f"legacy leaked into tenant: {ids}"

            # And NULL-pool sees only the legacy one
            res_null = await mem.search("xyz_unique_token", top_k=10,
                                        company_id=None)
            ids_null = {r["id"] for r in res_null}
            assert legacy in ids_null
            assert owned not in ids_null
        finally:
            db = get_db()
            await db.memories.delete_many({"id": {"$in": [legacy, owned]}})

    _run(_go())


def test_cache_invalidation_per_tenant():
    """A write in tenant A must NOT invalidate tenant B's cache."""

    async def _go():
        await _cleanup(["tenant_m1_cache_a", "tenant_m1_cache_b"])
        mem = get_memory()
        # seed both tenants
        a1 = await mem.store_memory(
            "First A cache_token_m1", metadata={"audit_tag": _TAG},
            company_id="tenant_m1_cache_a",
        )
        b1 = await mem.store_memory(
            "First B cache_token_m1", metadata={"audit_tag": _TAG},
            company_id="tenant_m1_cache_b",
        )
        # warm both caches
        await mem.search("cache_token_m1", company_id="tenant_m1_cache_a")
        await mem.search("cache_token_m1", company_id="tenant_m1_cache_b")
        cache_b_before = mem._tfidf_cache.get("tenant_m1_cache_b")
        assert cache_b_before is not None
        # write to A
        a2 = await mem.store_memory(
            "Second A cache_token_m1", metadata={"audit_tag": _TAG},
            company_id="tenant_m1_cache_a",
        )
        # B's cache must still be the same OBJECT
        try:
            assert mem._tfidf_cache.get("tenant_m1_cache_b") is cache_b_before, (
                "tenant B cache was wrongly invalidated by a write to tenant A"
            )
            # A's cache was invalidated (None means re-fetched on next search)
            assert mem._tfidf_cache.get("tenant_m1_cache_a") is None
        finally:
            db = get_db()
            await db.memories.delete_many({"id": {"$in": [a1, a2, b1]}})

    _run(_go())


def test_get_optimal_context_is_isolated():
    """get_optimal_context wraps search and must not leak between tenants."""

    async def _go():
        await _cleanup(["tenant_m1_ctx_a", "tenant_m1_ctx_b"])
        mem = get_memory()
        a = await mem.store_memory(
            "Confidential A: Tesla deal m1ctx_token", metadata={"audit_tag": _TAG},
            company_id="tenant_m1_ctx_a",
        )
        b = await mem.store_memory(
            "Confidential B: Layoff plan m1ctx_token", metadata={"audit_tag": _TAG},
            company_id="tenant_m1_ctx_b",
        )
        # build context as tenant A
        await mem.append_message(
            "sess_m1_ctx_a", "user", "tell me about m1ctx_token",
            user_id="u_ctx_a", company_id="tenant_m1_ctx_a",
        )
        ctx_a = await mem.get_optimal_context(
            "m1ctx_token", "sess_m1_ctx_a",
            company_id="tenant_m1_ctx_a",
        )
        try:
            ctx_text = ctx_a["context"]
            assert "Tesla deal m1ctx_token" in ctx_text
            assert "Layoff plan m1ctx_token" not in ctx_text, (
                "tenant B confidential leaked into tenant A context: "
                + ctx_text[:200]
            )
        finally:
            db = get_db()
            await db.memories.delete_many({"id": {"$in": [a, b]}})
            await db.sessions.delete_one({"session_id": "sess_m1_ctx_a"})

    _run(_go())
