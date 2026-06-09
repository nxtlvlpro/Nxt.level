"""Regression tests for the inter-agent communication layer."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend is importable when this file is run with pytest from repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_hermes_tools_contains_inter_agent():
    from agents.hermes import HERMES_TOOLS
    assert "delegate_to_agent" in HERMES_TOOLS
    assert "escalate_to_hermes" in HERMES_TOOLS
    assert "ask_colleague" in HERMES_TOOLS


def test_subordinates_have_escalate_and_ask():
    from agents.personas import PERSONAS
    subordinates = [k for k in PERSONAS if k != "hermes"]
    assert subordinates, "no subordinates registered"
    for sid in subordinates:
        allowed = set(PERSONAS[sid].get("allowed_tools") or [])
        assert "escalate_to_hermes" in allowed, f"{sid} missing escalate_to_hermes"
        assert "ask_colleague" in allowed, f"{sid} missing ask_colleague"


def test_hermes_role_is_ceo():
    from agents.manifests import get_manifest
    from agents.personas import PERSONAS
    m = get_manifest("hermes")
    assert "CEO" in (m.get("role") or "").upper()
    assert "CEO" in (PERSONAS["hermes"]["role"] or "").upper()


def test_delegate_rejects_non_hermes_caller():
    from agents.inter_agent import delegate_to_agent

    async def run():
        res = await delegate_to_agent({
            "from_agent": "bookkeeper",
            "agent_id": "analyst",
            "task": "test",
        })
        return res

    res = asyncio.get_event_loop().run_until_complete(run())
    assert res["ok"] is False
    assert "hermes" in res["error"].lower()


def test_ask_colleague_rejects_self_and_hermes():
    from agents.inter_agent import ask_colleague

    async def run():
        # self-ask
        r1 = await ask_colleague({
            "from_agent": "bookkeeper",
            "agent_id": "bookkeeper",
            "question": "x",
        })
        # ask hermes
        r2 = await ask_colleague({
            "from_agent": "bookkeeper",
            "agent_id": "hermes",
            "question": "x",
        })
        # hermes asking peer
        r3 = await ask_colleague({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "question": "x",
        })
        return r1, r2, r3

    r1, r2, r3 = asyncio.get_event_loop().run_until_complete(run())
    assert r1["ok"] is False
    assert r2["ok"] is False
    assert r3["ok"] is False


def test_delegate_depth_resets_after_success(monkeypatch):
    import agents.personas as personas
    from agents import inter_agent

    async def fake_run_persona(**kwargs):
        assert inter_agent.delegation_depth.get() == 1
        return {
            "content": "Delegated OK",
            "confidence": 0.91,
            "tokens_total": 17,
            "tool_traces": [],
        }

    async def fake_log_dialogue(**kwargs):
        return "dlg_depth_ok"

    monkeypatch.setattr(personas, "run_persona", fake_run_persona)
    monkeypatch.setattr(inter_agent, "_log_dialogue", fake_log_dialogue)

    async def run():
        before = inter_agent.delegation_depth.get()
        res = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "Проведи короткий анализ.",
            "company_id": "test_company",
            "user_id": "test_user",
        })
        after = inter_agent.delegation_depth.get()
        return before, res, after

    before, res, after = asyncio.run(run())
    assert before == 0
    assert res["ok"] is True
    assert res["response"] == "Delegated OK"
    assert after == 0


def test_delegate_depth_resets_after_exception(monkeypatch):
    import agents.personas as personas
    from agents import inter_agent

    async def fake_run_persona(**kwargs):
        assert inter_agent.delegation_depth.get() == 1
        raise RuntimeError("boom")

    monkeypatch.setattr(personas, "run_persona", fake_run_persona)

    async def run():
        before = inter_agent.delegation_depth.get()
        res = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "Сломайся контролируемо.",
            "company_id": "test_company",
            "user_id": "test_user",
        })
        after = inter_agent.delegation_depth.get()
        return before, res, after

    before, res, after = asyncio.run(run())
    assert before == 0
    assert res["ok"] is False
    assert "delegation_failed" in res["error"]
    assert after == 0


def test_ask_colleague_depth_resets_after_exception(monkeypatch):
    import agents.personas as personas
    from agents import inter_agent

    async def fake_run_persona(**kwargs):
        assert inter_agent.delegation_depth.get() == 1
        raise RuntimeError("peer boom")

    monkeypatch.setattr(personas, "run_persona", fake_run_persona)

    async def run():
        before = inter_agent.delegation_depth.get()
        res = await inter_agent.ask_colleague({
            "from_agent": "bookkeeper",
            "agent_id": "analyst",
            "question": "Что думаешь?",
            "company_id": "test_company",
            "user_id": "test_user",
        })
        after = inter_agent.delegation_depth.get()
        return before, res, after

    before, res, after = asyncio.run(run())
    assert before == 0
    assert res["ok"] is False
    assert "ask_failed" in res["error"]
    assert after == 0


def test_depth_limit_blocks_delegate_and_ask():
    from agents import inter_agent

    async def run():
        token = inter_agent.delegation_depth.set(inter_agent.MAX_DELEGATION_DEPTH)
        try:
            delegate_res = await inter_agent.delegate_to_agent({
                "from_agent": "hermes",
                "agent_id": "analyst",
                "task": "test",
                "company_id": "test_company",
            })
            ask_res = await inter_agent.ask_colleague({
                "from_agent": "bookkeeper",
                "agent_id": "analyst",
                "question": "test",
                "company_id": "test_company",
            })
            depth_inside = inter_agent.delegation_depth.get()
            return delegate_res, ask_res, depth_inside
        finally:
            inter_agent.delegation_depth.reset(token)

    delegate_res, ask_res, depth_inside = asyncio.run(run())
    assert delegate_res["ok"] is False
    assert ask_res["ok"] is False
    assert "Max delegation depth (3) reached" == delegate_res["error"]
    assert "Max delegation depth (3) reached" == ask_res["error"]
    assert depth_inside == inter_agent.MAX_DELEGATION_DEPTH


if __name__ == "__main__":
    test_hermes_tools_contains_inter_agent()
    test_subordinates_have_escalate_and_ask()
    test_hermes_role_is_ceo()
    test_delegate_rejects_non_hermes_caller()
    test_ask_colleague_rejects_self_and_hermes()
    print("ALL OK")
