"""Sprint A · Fix 2: finalize_llm_turn + voice ROI + stream token counting.

Validates:
1. /api/chat/stream — usage_out hook captures real stream tokens (not just
   the 10-token intent classifier).
2. /api/hermes/talk — finalize_llm_turn writes a db.requests row + db.costs
   row for voice traffic (previously the ENTIRE voice channel was missing).
3. finalize_llm_turn propagates `company_id` into costs/requests/alerts.
"""

import asyncio
import os

import pytest
from agents import roi as r
from agents._pipeline_hooks import finalize_llm_turn
from core.db import get_db
from core.deepseek import get_deepseek


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------------------------------------------------
# 1. finalize_llm_turn tenant-tags every collateral collection
# --------------------------------------------------------------------
def test_finalize_llm_turn_tags_company_id_on_cost_and_audit():
    """When `company_id` is passed to the hook, the resulting db.costs row
    AND the db.requests audit row both carry that tag.
    """

    async def _go():
        db = get_db()
        session_id = "test_sess_fix2_tag"
        user_id = "test_user_fix2"
        company_id = "tenant_fix2_tag"
        # Clean slate
        await db.costs.delete_many({"company_id": company_id})
        await db.requests.delete_many({"company_id": company_id})
        try:
            res = await finalize_llm_turn(
                channel="test_channel",
                agent="test_agent",
                user_id=user_id,
                session_id=session_id,
                message="hello",
                response_text="hi there from test",
                tokens_total=12345,
                deepseek_confidence=0.85,
                evidence_count=2,
                past_responses=[],
                memory_context=["doc1"],
                intent="general",
                agent_chain=["test_agent"],
                mock=False,
                latency_ms=42,
                company_id=company_id,
            )
            assert res.get("request_id")

            # costs row
            cost = await db.costs.find_one(
                {"agent": "test_agent", "company_id": company_id,
                 "cost_type": "deepseek_api"},
                {"_id": 0},
            )
            assert cost is not None
            assert cost["company_id"] == company_id
            assert cost["amount_usd"] > 0  # tokens_total > 0 → real cost

            # audit row
            req = await db.requests.find_one(
                {"session_id": session_id, "company_id": company_id},
                {"_id": 0},
            )
            assert req is not None
            assert req["company_id"] == company_id
            assert req["tokens_total"] == 12345
        finally:
            await db.costs.delete_many({"company_id": company_id})
            await db.requests.delete_many({"company_id": company_id})

    _run(_go())


# --------------------------------------------------------------------
# 2. ROI snapshot now includes voice/talk traffic
# --------------------------------------------------------------------
def test_voice_traffic_reaches_roi_dashboard():
    """Simulate the hermes_talk hook call. The cost should appear in
    `calculate_hourly_roi(company_id=...)`.
    """

    async def _go():
        db = get_db()
        company_id = "tenant_voice_roi"
        await db.costs.delete_many({"company_id": company_id})
        await db.requests.delete_many({"company_id": company_id})
        try:
            await finalize_llm_turn(
                channel="talk",
                agent="hermes_talk",
                user_id="u_v",
                session_id="sess_voice_roi",
                message="привет",
                response_text="здравствуй! как дела?",
                tokens_total=2000,
                deepseek_confidence=0.78,
                intent="voice",
                latency_ms=550,
                company_id=company_id,
            )
            snap = await r.calculate_hourly_roi(company_id=company_id)
            # Must surface hermes_talk in the per-agent cost breakdown.
            assert "hermes_talk" in snap["by_agent_cost"]
            assert snap["total_cost"] > 0
        finally:
            await db.costs.delete_many({"company_id": company_id})
            await db.requests.delete_many({"company_id": company_id})

    _run(_go())


# --------------------------------------------------------------------
# 3. /chat/stream usage_out hook returns real tokens (live LLM)
# --------------------------------------------------------------------
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
    reason="Live LLM call: set RUN_LIVE_LLM_TESTS=1 to enable",
)
def test_chat_stream_usage_out_captures_real_tokens():
    """Live test: call the streaming endpoint via the client and verify
    the usage_out dict is populated."""

    async def _go():
        client = get_deepseek()
        usage: dict = {}
        chunks: list = []
        async for delta in client.chat_stream(
            messages=[
                {"role": "system", "content": "Reply with exactly: OK."},
                {"role": "user", "content": "Say OK"},
            ],
            temperature=0.0,
            max_tokens=10,
            usage_out=usage,
        ):
            chunks.append(delta)
        # Only assert on real providers — mock path also populates the dict
        # but with a heuristic value.
        assert usage.get("total_tokens", 0) > 0
        assert "".join(chunks).strip() != ""

    _run(_go())
