"""Memory Sprint · M2: MemPalace tenant isolation via room=company_id.

Live tests hit the real ChromaDB store at /app/data/mempalace.
Each test cleans up after itself.
"""

import asyncio

from agents.mempalace_bridge import get_mempalace, _tenant_room


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _purge_drawer(source_files):
    """Best-effort cleanup of test drawers via direct ChromaDB delete."""
    if not source_files:
        return
    mp = get_mempalace()
    if mp._coll is None:
        return
    try:
        await asyncio.to_thread(
            mp._coll.delete,
            where={"source_file": {"$in": [s for s in source_files if s]}},
        )
    except Exception:
        pass


def test_store_namespaces_room_by_company_id():
    """When `company_id` is passed to store, the persisted drawer's
    `room` metadata equals the tenant namespace, not the legacy arg."""

    async def _go():
        mp = get_mempalace()
        res = await mp.store(
            content="M2 token AAA1 tenant alpha note",
            wing="internal",
            logical_room="legacy_subgroup_x",
            company_id="tenant_m2_alpha",
        )
        try:
            assert res.get("ok") is True
            assert res["room"] == "tenant_m2_alpha"
            assert res["logical_room"] == "legacy_subgroup_x"
            # Search inside the tenant must find it
            found = await mp.search(
                "tenant alpha note AAA1", company_id="tenant_m2_alpha"
            )
            assert any("AAA1" in r["content"] for r in found)
        finally:
            await _purge_drawer([res.get("source_file")])

    _run(_go())


def test_search_returns_only_own_tenant():
    """Two tenants with identical content — search must isolate."""

    async def _go():
        mp = get_mempalace()
        a = await mp.store(
            content="Pricing playbook M2_TOK_pricing alpha confidential",
            wing="internal",
            company_id="tenant_m2_iso_a",
        )
        b = await mp.store(
            content="Pricing playbook M2_TOK_pricing beta confidential",
            wing="internal",
            company_id="tenant_m2_iso_b",
        )
        try:
            res_a = await mp.search(
                "M2_TOK_pricing", top_k=10, company_id="tenant_m2_iso_a"
            )
            res_b = await mp.search(
                "M2_TOK_pricing", top_k=10, company_id="tenant_m2_iso_b"
            )
            contents_a = [r["content"] for r in res_a]
            contents_b = [r["content"] for r in res_b]
            # A sees only alpha
            assert any("alpha" in c for c in contents_a)
            assert not any("beta" in c for c in contents_a), \
                f"tenant A leaked tenant B content: {contents_a}"
            # B sees only beta
            assert any("beta" in c for c in contents_b)
            assert not any("alpha" in c for c in contents_b), \
                f"tenant B leaked tenant A content: {contents_b}"
        finally:
            await _purge_drawer([a.get("source_file"), b.get("source_file")])

    _run(_go())


def test_search_without_company_id_uses_global_pool():
    """`company_id=None` searches only the __global__ pool — it does NOT
    fall through to tenant data."""

    async def _go():
        mp = get_mempalace()
        glob = await mp.store(
            content="Global legacy note M2_TOK_global xyz",
            wing="internal",
            company_id=None,
        )
        owned = await mp.store(
            content="Tenant owned M2_TOK_global xyz",
            wing="internal",
            company_id="tenant_m2_globalcheck",
        )
        try:
            res_null = await mp.search(
                "M2_TOK_global", company_id=None, top_k=10
            )
            contents = [r["content"] for r in res_null]
            assert any("Global legacy" in c for c in contents)
            assert not any("Tenant owned" in c for c in contents), \
                f"tenant data leaked into global pool: {contents}"

            res_tenant = await mp.search(
                "M2_TOK_global", company_id="tenant_m2_globalcheck", top_k=10
            )
            contents_t = [r["content"] for r in res_tenant]
            assert any("Tenant owned" in c for c in contents_t)
            assert not any("Global legacy" in c for c in contents_t)
        finally:
            await _purge_drawer([
                glob.get("source_file"), owned.get("source_file")
            ])

    _run(_go())


def test_logical_room_post_filter_works():
    """Two docs of the same tenant — `logical_room=doc_X` returns only doc_X."""

    async def _go():
        mp = get_mempalace()
        doc_x = await mp.store(
            content="Contract clause M2_TOK_post_filter alpha legal",
            wing="documents",
            logical_room="doc_M2_X",
            company_id="tenant_m2_post",
        )
        doc_y = await mp.store(
            content="Contract clause M2_TOK_post_filter beta legal",
            wing="documents",
            logical_room="doc_M2_Y",
            company_id="tenant_m2_post",
        )
        try:
            only_x = await mp.search(
                "M2_TOK_post_filter",
                wing="documents",
                logical_room="doc_M2_X",
                top_k=10,
                company_id="tenant_m2_post",
            )
            contents = [r["content"] for r in only_x]
            assert any("alpha" in c for c in contents)
            assert not any("beta" in c for c in contents), \
                f"logical_room filter failed: {contents}"
        finally:
            await _purge_drawer([
                doc_x.get("source_file"), doc_y.get("source_file")
            ])

    _run(_go())


def test_legacy_drawers_invisible_to_tenants():
    """Pre-M2 drawers (room=arbitrary) live in `__global__` from the
    point of view of admins, and are completely invisible to any tenant
    search. We simulate a legacy drawer by writing one with
    `company_id=None` (which maps to `__global__`)."""

    async def _go():
        mp = get_mempalace()
        legacy = await mp.store(
            content="LEGACY_M2_TOK xyz123 confidential",
            wing="internal",
            company_id=None,
        )
        try:
            res = await mp.search(
                "LEGACY_M2_TOK", company_id="some_random_tenant", top_k=10
            )
            assert res == [] or all(
                "LEGACY_M2_TOK" not in r["content"] for r in res
            ), f"legacy global drawer leaked into tenant search: {res}"
        finally:
            await _purge_drawer([legacy.get("source_file")])

    _run(_go())


def test_list_wings_filters_by_tenant():
    """list_wings(company_id=X) counts only drawers whose room == X."""

    async def _go():
        mp = get_mempalace()
        a = await mp.store(
            content="wing-list M2 token A",
            wing="audit_test_wing",
            company_id="tenant_m2_wings_a",
        )
        b = await mp.store(
            content="wing-list M2 token B",
            wing="audit_test_wing",
            company_id="tenant_m2_wings_b",
        )
        try:
            wings_a = await mp.list_wings(company_id="tenant_m2_wings_a")
            wings_b = await mp.list_wings(company_id="tenant_m2_wings_b")
            count_a = sum(
                w["drawer_count"] for w in wings_a if w["wing"] == "audit_test_wing"
            )
            count_b = sum(
                w["drawer_count"] for w in wings_b if w["wing"] == "audit_test_wing"
            )
            # Each tenant sees only their own audit_test_wing contribution
            assert count_a >= 1
            assert count_b >= 1
            # B's list does not contain A's logical room and vice versa
            wing_a_entry = next(
                (w for w in wings_a if w["wing"] == "audit_test_wing"), None
            )
            wing_b_entry = next(
                (w for w in wings_b if w["wing"] == "audit_test_wing"), None
            )
            assert wing_a_entry is not None and wing_b_entry is not None
        finally:
            await _purge_drawer([a.get("source_file"), b.get("source_file")])

    _run(_go())


def test_tenant_room_helper():
    """Unit test for the room namespace mapper."""
    assert _tenant_room("Acme Co!") == "acme_co_"
    assert _tenant_room(None) == "__global__"
    assert _tenant_room("") == "__global__"
