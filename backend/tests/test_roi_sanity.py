"""ROI sanity: no phantom escalation costs + pilot-phase semantics."""

import asyncio

from agents import roi as r


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------- escalation cost
def test_auto_escalation_records_zero_cost():
    """The reliability layer flags should_escalate=True often, but no human
    is actually handling those — we must NOT count $35/hr cost there."""

    async def _go():
        rec = await r.record_escalation_cost(
            "test_phantom_agent", minutes=5.0, escalation_id="esc_x"
        )
        try:
            assert rec["amount_usd"] == 0.0
            assert rec["metadata"]["human_handled"] is False
            assert rec["metadata"]["flag"] == "auto_escalation_signal"
        finally:
            from core.db import get_db
            await get_db().costs.delete_one({"id": rec["id"]})

    _run(_go())


def test_human_handled_escalation_records_real_cost():
    """When the escalation is actually picked up by a human, count it."""

    async def _go():
        rec = await r.record_escalation_cost(
            "test_real_agent", minutes=10.0,
            human_handled=True, escalation_id="esc_y",
        )
        try:
            expected = 10.0 * (35.0 / 60.0)
            assert abs(rec["amount_usd"] - expected) < 1e-6
            assert rec["metadata"]["human_handled"] is True
            assert rec["metadata"].get("flag") != "auto_escalation_signal"
        finally:
            from core.db import get_db
            await get_db().costs.delete_one({"id": rec["id"]})

    _run(_go())


# ---------------------------------------------------- pilot phase
def test_hourly_roi_phase_pilot_when_no_revenue():
    """Pilot phase = cost > 0, revenue = 0. ROI must be None, not -1.0,
    and the alert must NOT fire."""

    async def _go():
        from core.db import get_db
        # seed a small deepseek cost so total_cost > 0
        seed = await r._record_cost(
            "deepseek_api", "test_pilot_agent",
            amount_usd=0.01, quantity=20000, unit="tokens",
            metadata={"model": "deepseek-chat"},
        )
        try:
            snap = await r.calculate_hourly_roi()
            assert snap["phase"] in ("pilot", "live")
            if snap["total_revenue"] == 0:
                assert snap["phase"] == "pilot"
                assert snap["roi"] is None
                assert snap["alert"] is None
            else:
                assert snap["phase"] == "live"
        finally:
            await get_db().costs.delete_one({"id": seed["id"]})

    _run(_go())
