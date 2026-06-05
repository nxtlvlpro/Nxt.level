"""Tenant isolation: ROI reads/writes must be scoped by company_id.

Sprint A · Fix 1
"""

import asyncio

from agents import roi as r
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _cleanup(tenant_ids):
    db = get_db()
    await db.costs.delete_many({"company_id": {"$in": tenant_ids}})
    await db.deals.delete_many({"company_id": {"$in": tenant_ids}})
    await db.interactions.delete_many({"company_id": {"$in": tenant_ids}})
    await db.roi_history.delete_many({"company_id": {"$in": tenant_ids}})


def test_cost_recording_tags_company_id():
    """A recorded API cost must carry the tenant tag."""
    async def _go():
        rec = await r.record_api_cost("agent_a", tokens=10000, company_id="tenant_x")
        try:
            assert rec["company_id"] == "tenant_x"
        finally:
            await get_db().costs.delete_one({"id": rec["id"]})
    _run(_go())


def test_dashboard_isolates_tenants():
    """Tenant A's dashboard must not include tenant B's costs."""
    async def _go():
        await _cleanup(["tenant_a_iso", "tenant_b_iso"])
        # tenant A — big cost
        a1 = await r.record_api_cost(
            "agent_alpha", tokens=200000, company_id="tenant_a_iso"
        )
        # tenant B — tiny cost
        b1 = await r.record_api_cost(
            "agent_beta", tokens=1000, company_id="tenant_b_iso"
        )
        try:
            snap_a = await r.calculate_hourly_roi(company_id="tenant_a_iso")
            snap_b = await r.calculate_hourly_roi(company_id="tenant_b_iso")
            # A only sees alpha; B only sees beta
            assert "agent_alpha" in snap_a["by_agent_cost"]
            assert "agent_beta" not in snap_a["by_agent_cost"]
            assert "agent_beta" in snap_b["by_agent_cost"]
            assert "agent_alpha" not in snap_b["by_agent_cost"]
            # cost magnitudes match per-tenant only
            assert snap_a["total_cost"] > snap_b["total_cost"]
        finally:
            await get_db().costs.delete_one({"id": a1["id"]})
            await get_db().costs.delete_one({"id": b1["id"]})
            await _cleanup(["tenant_a_iso", "tenant_b_iso"])
    _run(_go())


def test_admin_view_aggregates_all_tenants():
    """A `company_id=None` query must aggregate across tenants (admin view)."""
    async def _go():
        await _cleanup(["tenant_a_adm", "tenant_b_adm"])
        a1 = await r.record_api_cost(
            "agent_admin1", tokens=100000, company_id="tenant_a_adm"
        )
        b1 = await r.record_api_cost(
            "agent_admin2", tokens=100000, company_id="tenant_b_adm"
        )
        try:
            snap_admin = await r.calculate_hourly_roi(company_id=None)
            assert "agent_admin1" in snap_admin["by_agent_cost"]
            assert "agent_admin2" in snap_admin["by_agent_cost"]
        finally:
            await get_db().costs.delete_one({"id": a1["id"]})
            await get_db().costs.delete_one({"id": b1["id"]})
            await _cleanup(["tenant_a_adm", "tenant_b_adm"])
    _run(_go())


def test_revenue_attribution_isolated_per_tenant():
    """A tenant's deal+interactions revenue must not bleed into another tenant."""
    async def _go():
        await _cleanup(["tenant_rev_a", "tenant_rev_b"])
        # Tenant A: full deal cycle
        await r.record_interaction(
            "deal_iso_a", "agent_sales_a", company_id="tenant_rev_a"
        )
        await r.record_deal(
            "deal_iso_a", value_usd=1000.0, team="sales",
            company_id="tenant_rev_a",
        )
        # Tenant B: full deal cycle
        await r.record_interaction(
            "deal_iso_b", "agent_sales_b", company_id="tenant_rev_b"
        )
        await r.record_deal(
            "deal_iso_b", value_usd=2500.0, team="sales",
            company_id="tenant_rev_b",
        )
        try:
            snap_a = await r.calculate_hourly_roi(company_id="tenant_rev_a")
            snap_b = await r.calculate_hourly_roi(company_id="tenant_rev_b")
            assert "agent_sales_a" in snap_a["by_agent_revenue"]
            assert "agent_sales_b" not in snap_a["by_agent_revenue"]
            assert "agent_sales_b" in snap_b["by_agent_revenue"]
            assert "agent_sales_a" not in snap_b["by_agent_revenue"]
        finally:
            await _cleanup(["tenant_rev_a", "tenant_rev_b"])
    _run(_go())


def test_roi_history_keyed_per_tenant():
    """Two tenants taking a snapshot in the same hour must not overwrite."""
    async def _go():
        await _cleanup(["tenant_hist_a", "tenant_hist_b"])
        a1 = await r.record_api_cost(
            "agent_h_a", tokens=50000, company_id="tenant_hist_a"
        )
        b1 = await r.record_api_cost(
            "agent_h_b", tokens=20000, company_id="tenant_hist_b"
        )
        try:
            snap_a = await r.calculate_hourly_roi(company_id="tenant_hist_a")
            snap_b = await r.calculate_hourly_roi(company_id="tenant_hist_b")
            db = get_db()
            row_a = await db.roi_history.find_one(
                {"hour_end": snap_a["hour_end"], "company_id": "tenant_hist_a"},
                {"_id": 0},
            )
            row_b = await db.roi_history.find_one(
                {"hour_end": snap_b["hour_end"], "company_id": "tenant_hist_b"},
                {"_id": 0},
            )
            assert row_a is not None and row_b is not None
            assert "agent_h_a" in row_a["by_agent_cost"]
            assert "agent_h_b" in row_b["by_agent_cost"]
            assert "agent_h_b" not in row_a["by_agent_cost"]
            assert "agent_h_a" not in row_b["by_agent_cost"]
        finally:
            await get_db().costs.delete_one({"id": a1["id"]})
            await get_db().costs.delete_one({"id": b1["id"]})
            await _cleanup(["tenant_hist_a", "tenant_hist_b"])
    _run(_go())
