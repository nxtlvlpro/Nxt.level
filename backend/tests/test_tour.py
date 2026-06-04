"""Demo Tour analytics — catalogue, event recording, funnel sanity."""

import asyncio
import uuid

from core import tour as t
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------- catalogue
def test_catalogue_has_five_canonical_steps():
    cat = t.catalogue()
    assert cat["count"] == 5
    ids = [s["id"] for s in cat["steps"]]
    assert ids == [
        "ask_hermes", "view_pricing", "open_agents",
        "open_dialogues", "open_approvals",
    ]
    # Every step has a frontend anchor (data-testid target).
    for s in cat["steps"]:
        assert s.get("anchor"), s
        assert s.get("title"), s
        assert s.get("hint"), s


# ---------------------------------------------------- events
def test_record_event_validates_input():
    async def _go():
        cid = f"test_{uuid.uuid4().hex[:6]}"
        # unknown event
        try:
            await t.record_event(client_id=cid, step_id="ask_hermes", event="lol")
        except ValueError as e:
            assert "unknown event" in str(e)
        else:
            raise AssertionError("expected ValueError")
        # unknown step (for non-dismiss events)
        try:
            await t.record_event(client_id=cid, step_id="not_a_step", event="start")
        except ValueError as e:
            assert "unknown step_id" in str(e)
        else:
            raise AssertionError("expected ValueError")
    _run(_go())


def test_record_event_persists():
    async def _go():
        cid = f"test_{uuid.uuid4().hex[:8]}"
        try:
            r = await t.record_event(
                client_id=cid, step_id="ask_hermes", event="start"
            )
            assert r["ok"] is True
            r2 = await t.record_event(
                client_id=cid, step_id="ask_hermes", event="complete"
            )
            assert r2["ok"] is True
            # dismiss without step_id is allowed
            r3 = await t.record_event(client_id=cid, step_id=None, event="dismiss")
            assert r3["ok"] is True
        finally:
            await get_db().tour_events.delete_many({"client_id": cid})
    _run(_go())


# ---------------------------------------------------- funnel
def test_funnel_shape_and_completion_rate():
    async def _go():
        cid_a = f"test_{uuid.uuid4().hex[:8]}_a"
        cid_b = f"test_{uuid.uuid4().hex[:8]}_b"
        try:
            # Two starts, one complete on ask_hermes → 50% rate
            await t.record_event(client_id=cid_a, step_id="ask_hermes", event="start")
            await t.record_event(client_id=cid_b, step_id="ask_hermes", event="start")
            await t.record_event(client_id=cid_a, step_id="ask_hermes", event="complete")

            data = await t.funnel(window_hours=1)
            assert data["ok"] is True
            ask = next(s for s in data["steps"] if s["step_id"] == "ask_hermes")
            assert ask["starts"] >= 2
            assert ask["completes"] >= 1
            assert ask["completion_rate"] is not None
            # rate must be in [0, 1]
            assert 0.0 <= ask["completion_rate"] <= 1.0
        finally:
            await get_db().tour_events.delete_many(
                {"client_id": {"$in": [cid_a, cid_b]}}
            )
    _run(_go())
