"""Share-My-Journey — viral marketing channel.

  • mint → share_id + headline persisted
  • record_open / track_conversion bump counters and append to share_events
  • stats: open_per_mint / conversion_per_open ratios
  • render_og_card_png returns a 1200×630 PNG
"""

import asyncio
import uuid

from core import share as s
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------- mint
def test_mint_share_persists():
    async def _go():
        cid = f"test_{uuid.uuid4().hex[:8]}"
        try:
            res = await s.mint_share(
                client_id=cid,
                completed_steps=["ask_hermes", "view_pricing"],
                headline="Я попробовал NXT8",
            )
            assert res["ok"] is True
            assert s.SHARE_ID_LEN == len(res["share_id"]) or len(res["share_id"]) >= 6
            rec = await s.get_share(res["share_id"])
            assert rec is not None
            assert rec["headline"] == "Я попробовал NXT8"
            assert rec["completed_steps"] == ["ask_hermes", "view_pricing"]
            assert int(rec["opens"]) == 0
            assert int(rec["conversions"]) == 0
        finally:
            await get_db().shares.delete_many({"client_id": cid})

    _run(_go())


def test_mint_truncates_long_headline():
    async def _go():
        cid = f"test_{uuid.uuid4().hex[:8]}"
        try:
            res = await s.mint_share(
                client_id=cid,
                headline="x" * 5000,
            )
            assert res["ok"] is True
            assert len(res["headline"]) <= s.MAX_HEADLINE_LEN
        finally:
            await get_db().shares.delete_many({"client_id": cid})

    _run(_go())


# ---------------------------------------------------- counters
def test_open_and_conversion_increment_counters():
    async def _go():
        cid = f"test_{uuid.uuid4().hex[:8]}"
        try:
            res = await s.mint_share(client_id=cid)
            sid = res["share_id"]

            r1 = await s.record_open(sid, ref="tg")
            assert r1["ok"] is True
            r2 = await s.record_open(sid, ref="x")
            assert r2["ok"] is True

            r3 = await s.track_conversion(sid, kind="checkout")
            assert r3["ok"] is True

            rec = await s.get_share(sid)
            assert int(rec["opens"]) == 2
            assert int(rec["conversions"]) == 1

            ev_count = await get_db().share_events.count_documents({"share_id": sid})
            assert ev_count == 3
        finally:
            await get_db().shares.delete_many({"client_id": cid})
            await get_db().share_events.delete_many({"share_id": res["share_id"]})

    _run(_go())


def test_record_open_rejects_bad_id():
    async def _go():
        bad = await s.record_open("../../etc/passwd")
        assert bad["ok"] is False
        bad2 = await s.record_open("not<existing>")
        assert bad2["ok"] is False

    _run(_go())


# ---------------------------------------------------- stats
def test_stats_shape():
    async def _go():
        res = await s.stats(window_hours=24)
        assert res["ok"] is True
        for k in ("minted", "opens", "conversions"):
            assert k in res
            assert isinstance(res[k], int)
        # ratios are None or a float in [0, 1+]
        for k in ("open_per_mint", "conversion_per_open"):
            v = res[k]
            assert v is None or isinstance(v, (int, float))

    _run(_go())


# ---------------------------------------------------- OG card
def test_render_og_card_returns_png_bytes():
    data = s.render_og_card_png(
        "Я попробовал NXT8 — AI-команда из 8 агентов для бизнеса",
        share_id="abc123",
    )
    # PNG magic: 89 50 4e 47 0d 0a 1a 0a
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # decode and check size
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data))
    assert im.size == (1200, 630)


def test_render_og_card_handles_empty_headline():
    data = s.render_og_card_png("", share_id="abc123")
    assert data[:4] == b"\x89PNG"
