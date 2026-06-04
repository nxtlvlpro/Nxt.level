"""Approval Gate — high-impact agent actions must wait for review.

  • request_approval → pending record exists
  • approve → executes the underlying tool via the supplied executor
  • reject → status flips to rejected
  • past `due_at` in create_task is auto-shifted to now+24h
  • requires_approval map agrees with the manifests
"""

import asyncio
from datetime import datetime, timedelta, timezone

from agents import manifests as m
from core import approval_gate as ag
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------- manifest
def test_requires_approval_matches_manifest():
    # Hermes — autonomous — never requires approval
    assert m.requires_approval("hermes", "create_task") is False
    # Subordinates — every high-impact action requires approval
    for pid in ("hr_mentor", "client_manager", "bookkeeper", "marketer",
                "compliance", "project_coord", "analyst"):
        assert m.requires_approval(pid, "create_task") is True, pid
        assert m.requires_approval(pid, "update_task") is True, pid
        assert m.requires_approval(pid, "mempalace_store") is True, pid
    # Low-impact actions never require approval
    for action in ("search_memory", "web_search", "evaluate_action_roi"):
        assert m.requires_approval("hr_mentor", action) is False, action


# ---------------------------------------------------------------- flow
def test_request_approve_execute_flow():
    async def _go():
        rec = await ag.request_approval(
            agent_id="client_manager",
            action="create_task",
            args={"title": "AG_TEST_FLOW", "priority": "high"},
            company_id="ag_test_co",
            user_id="ag_tester",
        )
        assert rec["ok"] is True and rec["pending"] is True
        pid = rec["approval_id"]

        items = await ag.list_pending(company_id="ag_test_co")
        assert any(i["id"] == pid for i in items)

        executed = []

        async def fake_executor(action, args):
            executed.append((action, args))
            return {"ok": True, "task_id": "fake_id_42", "title": args["title"]}

        r = await ag.approve(pid, decided_by="hermes_test", executor=fake_executor)
        assert r["ok"] is True
        assert r["status"] == ag.STATUS_EXECUTED
        assert r["result"]["task_id"] == "fake_id_42"
        assert executed == [("create_task", {"title": "AG_TEST_FLOW", "priority": "high"})]

        await get_db().pending_approvals.delete_one({"id": pid})

    _run(_go())


def test_reject_flow():
    async def _go():
        rec = await ag.request_approval(
            agent_id="bookkeeper",
            action="update_task",
            args={"task_id": "abc", "status": "done"},
            company_id="ag_test_co",
        )
        pid = rec["approval_id"]
        r = await ag.reject(pid, decided_by="hermes_test", reason="not now")
        assert r["ok"] is True and r["status"] == ag.STATUS_REJECTED

        # second reject should fail (status already non-pending)
        r2 = await ag.reject(pid)
        assert r2["ok"] is False

        await get_db().pending_approvals.delete_one({"id": pid})

    _run(_go())


# ---------------------------------------------------------------- due_at
def test_create_task_sanitizes_past_due_at():
    async def _go():
        from agents.hermes import _t_create_task
        past = "2024-01-01T00:00:00Z"
        res = await _t_create_task({
            "title": "AG_TEST_PAST_DATE",
            "company_id": "ag_test_co",
            "due_at": past,
        })
        assert res["ok"] is True
        doc = await get_db().tasks.find_one({"id": res["task_id"]}, {"_id": 0})
        assert doc is not None
        saved_due = datetime.fromisoformat(doc["due_at"].replace("Z", "+00:00"))
        assert saved_due > datetime.now(timezone.utc), "past date was not bumped"
        await get_db().tasks.delete_one({"id": res["task_id"]})

    _run(_go())


def test_create_task_future_due_at_untouched():
    async def _go():
        from agents.hermes import _t_create_task
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        res = await _t_create_task({
            "title": "AG_TEST_FUTURE_DATE",
            "company_id": "ag_test_co",
            "due_at": future,
        })
        assert res["ok"] is True
        doc = await get_db().tasks.find_one({"id": res["task_id"]}, {"_id": 0})
        assert doc["due_at"] == future
        await get_db().tasks.delete_one({"id": res["task_id"]})

    _run(_go())
