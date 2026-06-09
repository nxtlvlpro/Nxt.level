"""Tests for the Telegram channel bridge.

External HTTP to api.telegram.org is mocked via `_tg_call`. We still
exercise the full webhook handler end-to-end: token mint → /start
<token> → bind → free text → Hermes → reply.

Pattern matches the existing approval_gate tests (sync wrapper around
`asyncio.get_event_loop().run_until_complete`) so we share the
session-scoped event loop fixture from conftest.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import patch

from core import telegram_bot as tg


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _SentBus:
    """Captures every outbound Telegram call into a list for assertions."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, method: str, **payload: Any) -> Dict[str, Any]:
        self.calls.append({"method": method, **payload})
        if method == "getMe":
            return {
                "ok": True,
                "result": {"id": 42, "username": "nxt8_test_bot", "first_name": "NXT8"},
            }
        if method == "setWebhook":
            return {"ok": True, "result": True}
        return {"ok": True, "result": {"message_id": 1, "chat": {"id": payload.get("chat_id")}}}


def _new_bus(monkeypatch_target=tg):
    bus = _SentBus()
    # We're not using pytest's monkeypatch (it's function-scoped and
    # conflicts with sync wrappers). Stash original to restore.
    orig = monkeypatch_target._tg_call
    monkeypatch_target._tg_call = bus
    bus._restore = lambda: setattr(monkeypatch_target, "_tg_call", orig)
    return bus


def _setup_env() -> None:
    import os
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-fixed")
    os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret-fixed")


# ---------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------


def test_approval_card_text_handles_long_args() -> None:
    huge = "x" * 500
    txt = tg._approval_card_text({
        "action": "create_task",
        "agent_id": "client_manager",
        "rationale": "client requested",
        "args": {"title": huge, "priority": "high"},
    })
    assert "create_task" in txt
    assert "client_manager" in txt
    assert "client requested" in txt
    assert "..." in txt  # truncated
    assert huge not in txt


def test_approval_keyboard_has_two_buttons() -> None:
    kb = tg._approval_keyboard("abc-123")
    rows = kb["inline_keyboard"]
    assert len(rows) == 1 and len(rows[0]) == 2
    actions = {b["callback_data"] for b in rows[0]}
    assert actions == {"approve:abc-123", "reject:abc-123"}


# ---------------------------------------------------------------------
# Bind / unbind lifecycle
# ---------------------------------------------------------------------


def test_mint_token_and_bind_via_start() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "tg_test_client_mint"

        mint = _run(tg.mint_link_token(client_id))
        assert mint["ok"] and mint["token"]
        assert "?start=" in mint["deep_link"]

        _run(tg.handle_update({
            "message": {
                "chat": {"id": 555001},
                "from": {"id": 555001, "username": "alice", "first_name": "Alice"},
                "text": f"/start {mint['token']}",
            }
        }))

        bound = _run(tg.get_chat_for_client(client_id))
        assert bound is not None
        assert bound["chat_id"] == 555001
        assert bound["username"] == "alice"

        welcomes = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert any("Telegram подключен" in (c.get("text") or "") for c in welcomes)
    finally:
        bus._restore()
        _run(tg.unbind("tg_test_client_mint"))


def test_invalid_start_token_does_not_bind() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 555002},
                "from": {"id": 555002},
                "text": "/start totally-bogus-token-zzz",
            }
        }))
        err_msgs = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert any("недействительна" in (c.get("text") or "") for c in err_msgs)
    finally:
        bus._restore()


def test_unbind_removes_binding() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "tg_test_client_unbind"
        mint = _run(tg.mint_link_token(client_id))
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 555003},
                "from": {"id": 555003, "username": "bob"},
                "text": f"/start {mint['token']}",
            }
        }))
        assert _run(tg.get_chat_for_client(client_id)) is not None

        res = _run(tg.unbind(client_id))
        assert res["ok"] and res["removed"] >= 1
        assert _run(tg.get_chat_for_client(client_id)) is None
    finally:
        bus._restore()


# ---------------------------------------------------------------------
# Free-form messages -> Hermes
# ---------------------------------------------------------------------


def test_free_text_forwards_to_hermes() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "tg_test_client_hermes"
        mint = _run(tg.mint_link_token(client_id))
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 555004},
                "from": {"id": 555004},
                "text": f"/start {mint['token']}",
            }
        }))

        async def _fake_hermes(**kwargs: Any) -> Dict[str, Any]:
            return {"content": "pong from hermes", "tokens_total": 1, "confidence": 0.9}

        with patch("agents.hermes.hermes_chat", _fake_hermes):
            bus.calls.clear()
            _run(tg.handle_update({
                "message": {
                    "chat": {"id": 555004},
                    "from": {"id": 555004},
                    "text": "what is my next task?",
                }
            }))

        replies = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert any("pong from hermes" in (c.get("text") or "") for c in replies)
    finally:
        bus._restore()
        _run(tg.unbind("tg_test_client_hermes"))


def test_unbound_chat_gets_locked_hint() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        bus.calls.clear()
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 999998},
                "from": {"id": 999998},
                "text": "hello there",
            }
        }))
        msgs = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert any("не привязан" in (c.get("text") or "") for c in msgs)
    finally:
        bus._restore()


# ---------------------------------------------------------------------
# Inline-button callbacks
# ---------------------------------------------------------------------


def test_callback_approve_invokes_approval_gate() -> None:
    _setup_env()
    bus = _new_bus()
    seen: Dict[str, Any] = {}

    async def _fake_approve(approval_id: str, **kw: Any) -> Dict[str, Any]:
        seen["id"] = approval_id
        seen["kw"] = kw
        return {"ok": True, "status": "executed", "approval_id": approval_id}

    try:
        with patch("core.approval_gate.approve", _fake_approve):
            _run(tg.handle_update({
                "callback_query": {
                    "id": "cb_1",
                    "data": "approve:appr-xyz",
                    "from": {"id": 1, "username": "tester"},
                    "message": {"chat": {"id": 700001}, "message_id": 9},
                }
            }))

        assert seen["id"] == "appr-xyz"
        assert seen["kw"]["decided_by"].startswith("tg:")
        assert any(c["method"] == "answerCallbackQuery" for c in bus.calls)
        assert any(
            c["method"] == "sendMessage" and "Approved" in (c.get("text") or "")
            for c in bus.calls
        )
    finally:
        bus._restore()


def test_callback_reject_invokes_approval_gate() -> None:
    _setup_env()
    bus = _new_bus()

    async def _fake_reject(approval_id: str, **kw: Any) -> Dict[str, Any]:
        return {"ok": True, "status": "rejected", "approval_id": approval_id}

    try:
        with patch("core.approval_gate.reject", _fake_reject):
            _run(tg.handle_update({
                "callback_query": {
                    "id": "cb_2",
                    "data": "reject:appr-zzz",
                    "from": {"id": 2},
                    "message": {"chat": {"id": 700002}, "message_id": 9},
                }
            }))

        assert any(
            c["method"] == "sendMessage" and "Rejected" in (c.get("text") or "")
            for c in bus.calls
        )
    finally:
        bus._restore()


# ---------------------------------------------------------------------
# Push notifications
# ---------------------------------------------------------------------


def test_notify_pending_approval_sends_card() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "tg_owner_push"
        mint = _run(tg.mint_link_token(client_id))
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 800001},
                "from": {"id": 800001},
                "text": f"/start {mint['token']}",
            }
        }))
        bus.calls.clear()

        approval = {
            "id": "p-1",
            "user_id": client_id,
            "agent_id": "client_manager",
            "action": "create_task",
            "args": {"title": "Follow up with lead", "priority": "high"},
            "rationale": "client requested",
        }
        _run(tg.notify_pending_approval(approval))

        pushed = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert pushed, "expected a sendMessage push"
        card = pushed[0]
        assert "create_task" in card.get("text", "")
        kb = card.get("reply_markup", {}).get("inline_keyboard")
        assert kb and kb[0][0]["callback_data"] == "approve:p-1"
    finally:
        bus._restore()
        _run(tg.unbind("tg_owner_push"))


def test_notify_without_binding_is_noop() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        bus.calls.clear()
        _run(tg.notify_pending_approval({
            "id": "p-2",
            "user_id": "ghost_user_no_bind",
            "agent_id": "a",
            "action": "x",
            "args": {},
        }))
        assert not [c for c in bus.calls if c["method"] == "sendMessage"]
    finally:
        bus._restore()


def test_notify_improvement_sends_to_first_connected_chat() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "tg_owner_improvement"
        mint = _run(tg.mint_link_token(client_id))
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 800101},
                "from": {"id": 800101, "username": "owner"},
                "text": f"/start {mint['token']}",
            }
        }))
        bus.calls.clear()

        ok = _run(tg.notify_improvement({
            "area": "process",
            "description": "Escalation rate is rising",
            "expected_benefit": "Lower CEO load",
            "priority": "P1",
        }))

        assert ok is True
        pushed = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert pushed, "expected a sendMessage push"
        assert "Hermes Self-Audit Alert" in pushed[0].get("text", "")
        assert "Escalation rate is rising" in pushed[0].get("text", "")
    finally:
        bus._restore()
        _run(tg.unbind("tg_owner_improvement"))


def test_notify_policy_sends_to_first_connected_chat() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "tg_owner_policy"
        mint = _run(tg.mint_link_token(client_id))
        _run(tg.handle_update({
            "message": {
                "chat": {"id": 800102},
                "from": {"id": 800102, "username": "owner2"},
                "text": f"/start {mint['token']}",
            }
        }))
        bus.calls.clear()

        ok = _run(tg.notify_policy({
            "title": "Refund SLA",
            "scope": "sla",
            "proposed_rule": "Refund tickets must be acknowledged within 4 hours",
        }))

        assert ok is True
        pushed = [c for c in bus.calls if c["method"] == "sendMessage"]
        assert pushed, "expected a sendMessage push"
        assert "Hermes Policy Proposal" in pushed[0].get("text", "")
        assert "Refund SLA" in pushed[0].get("text", "")
    finally:
        bus._restore()
        _run(tg.unbind("tg_owner_policy"))
