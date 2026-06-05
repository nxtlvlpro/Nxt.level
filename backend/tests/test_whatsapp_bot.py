"""Tests for the WhatsApp (Twilio) channel bridge.

External HTTP to api.twilio.com is mocked via `_twilio_post`. We exercise
the full inbound webhook handler end-to-end: token mint → first
'NXT8 <token>' message → bind → free text → Hermes → reply, plus
inline-style 'A <id>' / 'R <id>' approve-reject commands.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List
from unittest.mock import patch

from core import whatsapp_bot as wa


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _SentBus:
    """Captures every outbound Twilio call into a list for assertions."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, path: str, **form: Any) -> Dict[str, Any]:
        self.calls.append({"path": path, **form})
        return {"ok": True, "sid": "SMxxx"}


def _new_bus():
    bus = _SentBus()
    orig = wa._twilio_post
    wa._twilio_post = bus
    bus._restore = lambda: setattr(wa, "_twilio_post", orig)
    return bus


def _setup_env() -> None:
    os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest1234567890abcdef1234567890ab")
    os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_auth_token_32_chars_xxxxxx12")
    os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+13253263849")


# ---------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------


def test_extract_token_recognises_nxt8_prefix() -> None:
    assert wa._extract_token("NXT8 abc123") == "abc123"
    assert wa._extract_token("nxt8 xyz") == "xyz"
    assert wa._extract_token("  NXT8   tokenx  ") == "tokenx"
    assert wa._extract_token("hi there") is None
    assert wa._extract_token("NXT8") is None  # no token after prefix


def test_parse_approve_reject_variants() -> None:
    assert wa._parse_approve_reject("A appr-1") == ("approve", "appr-1")
    assert wa._parse_approve_reject("approve appr-2") == ("approve", "appr-2")
    assert wa._parse_approve_reject("R appr-3") == ("reject", "appr-3")
    assert wa._parse_approve_reject("reject appr-4") == ("reject", "appr-4")
    assert wa._parse_approve_reject("approvals") == ("approvals", "")
    assert wa._parse_approve_reject("hello world") is None


def test_approval_card_truncates_long_values() -> None:
    huge = "y" * 500
    txt = wa._approval_card_text({
        "id": "p-7",
        "action": "create_task",
        "agent_id": "client_manager",
        "rationale": "client asked",
        "args": {"title": huge},
    })
    assert "p-7" in txt
    assert "A p-7" in txt
    assert "R p-7" in txt
    assert "..." in txt
    assert huge not in txt


def test_verify_signature_round_trip() -> None:
    _setup_env()
    import base64, hashlib, hmac
    url = "https://example.com/api/whatsapp/webhook/secret"
    params = {"From": "whatsapp:+15551234", "Body": "hi"}
    tok = os.environ["TWILIO_AUTH_TOKEN"]
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    expected = base64.b64encode(
        hmac.new(tok.encode(), data.encode(), hashlib.sha1).digest()
    ).decode()
    assert wa.verify_twilio_signature(url, params, expected) is True
    assert wa.verify_twilio_signature(url, params, "bogus") is False


# ---------------------------------------------------------------------
# Bind / unbind lifecycle
# ---------------------------------------------------------------------


def test_mint_token_and_bind_via_nxt8_message() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "wa_test_mint"
        mint = _run(wa.mint_link_token(client_id))
        assert mint["ok"] and mint["token"]
        assert mint["deep_link"].startswith("https://wa.me/13253263849?text=")
        assert "NXT8" in mint["deep_link"]

        _run(wa.handle_inbound({
            "From": "whatsapp:+15551112222",
            "Body": f"NXT8 {mint['token']}",
            "ProfileName": "Alice",
        }))

        bound = _run(wa.get_chat_for_client(client_id))
        assert bound is not None
        assert bound["wa_id"] == "whatsapp:+15551112222"
        assert bound["profile_name"] == "Alice"

        welcomes = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert any("WhatsApp подключен" in (c.get("Body") or "") for c in welcomes)
    finally:
        bus._restore()
        _run(wa.unbind("wa_test_mint"))


def test_invalid_nxt8_token_does_not_bind() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        _run(wa.handle_inbound({
            "From": "whatsapp:+15551112223",
            "Body": "NXT8 totally-bogus-zzz",
        }))
        msgs = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert any("недействительна" in (c.get("Body") or "") for c in msgs)
    finally:
        bus._restore()


def test_unbind_removes_binding() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "wa_test_unbind"
        mint = _run(wa.mint_link_token(client_id))
        _run(wa.handle_inbound({
            "From": "whatsapp:+15551112224",
            "Body": f"NXT8 {mint['token']}",
        }))
        assert _run(wa.get_chat_for_client(client_id)) is not None

        res = _run(wa.unbind(client_id))
        assert res["ok"] and res["removed"] >= 1
        assert _run(wa.get_chat_for_client(client_id)) is None
    finally:
        bus._restore()


# ---------------------------------------------------------------------
# Free-form text -> Hermes
# ---------------------------------------------------------------------


def test_free_text_forwards_to_hermes() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "wa_test_hermes"
        mint = _run(wa.mint_link_token(client_id))
        _run(wa.handle_inbound({
            "From": "whatsapp:+15551112225",
            "Body": f"NXT8 {mint['token']}",
        }))

        async def _fake_hermes(**kwargs: Any) -> Dict[str, Any]:
            return {"content": "pong from hermes wa", "tokens_total": 1, "confidence": 0.9}

        with patch("agents.hermes.hermes_chat", _fake_hermes):
            bus.calls.clear()
            _run(wa.handle_inbound({
                "From": "whatsapp:+15551112225",
                "Body": "what's my next task?",
            }))

        replies = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert any("pong from hermes wa" in (c.get("Body") or "") for c in replies)
    finally:
        bus._restore()
        _run(wa.unbind("wa_test_hermes"))


def test_unbound_chat_gets_locked_hint() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        bus.calls.clear()
        _run(wa.handle_inbound({
            "From": "whatsapp:+15559999999",
            "Body": "hello",
        }))
        msgs = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert any("не привязан" in (c.get("Body") or "") for c in msgs)
    finally:
        bus._restore()


# ---------------------------------------------------------------------
# Approve / Reject commands
# ---------------------------------------------------------------------


def test_approve_command_invokes_approval_gate() -> None:
    _setup_env()
    bus = _new_bus()
    seen: Dict[str, Any] = {}

    async def _fake_approve(approval_id: str, **kw: Any) -> Dict[str, Any]:
        seen["id"] = approval_id
        seen["kw"] = kw
        return {"ok": True, "status": "executed", "approval_id": approval_id}

    try:
        client_id = "wa_test_approve"
        mint = _run(wa.mint_link_token(client_id))
        _run(wa.handle_inbound({
            "From": "whatsapp:+15551113333",
            "Body": f"NXT8 {mint['token']}",
            "ProfileName": "Bob",
        }))
        bus.calls.clear()

        with patch("core.approval_gate.approve", _fake_approve):
            _run(wa.handle_inbound({
                "From": "whatsapp:+15551113333",
                "Body": "A appr-xyz",
                "ProfileName": "Bob",
            }))

        assert seen["id"] == "appr-xyz"
        assert seen["kw"]["decided_by"].startswith("wa:")
        replies = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert any("Approved" in (c.get("Body") or "") for c in replies)
    finally:
        bus._restore()
        _run(wa.unbind("wa_test_approve"))


def test_reject_command_invokes_approval_gate() -> None:
    _setup_env()
    bus = _new_bus()

    async def _fake_reject(approval_id: str, **kw: Any) -> Dict[str, Any]:
        return {"ok": True, "status": "rejected", "approval_id": approval_id}

    try:
        client_id = "wa_test_reject"
        mint = _run(wa.mint_link_token(client_id))
        _run(wa.handle_inbound({
            "From": "whatsapp:+15551114444",
            "Body": f"NXT8 {mint['token']}",
        }))
        bus.calls.clear()

        with patch("core.approval_gate.reject", _fake_reject):
            _run(wa.handle_inbound({
                "From": "whatsapp:+15551114444",
                "Body": "R appr-zzz",
            }))

        replies = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert any("Rejected" in (c.get("Body") or "") for c in replies)
    finally:
        bus._restore()
        _run(wa.unbind("wa_test_reject"))


# ---------------------------------------------------------------------
# Push notifications
# ---------------------------------------------------------------------


def test_notify_pending_approval_sends_card() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        client_id = "wa_owner_push"
        mint = _run(wa.mint_link_token(client_id))
        _run(wa.handle_inbound({
            "From": "whatsapp:+15551115555",
            "Body": f"NXT8 {mint['token']}",
        }))
        bus.calls.clear()

        _run(wa.notify_pending_approval({
            "id": "p-1",
            "user_id": client_id,
            "agent_id": "client_manager",
            "action": "create_task",
            "args": {"title": "Follow up"},
            "rationale": "client asked",
        }))

        pushed = [c for c in bus.calls if c["path"] == "/Messages.json"]
        assert pushed
        body = pushed[0].get("Body", "")
        assert "create_task" in body
        assert "A p-1" in body and "R p-1" in body
    finally:
        bus._restore()
        _run(wa.unbind("wa_owner_push"))


def test_notify_without_binding_is_noop() -> None:
    _setup_env()
    bus = _new_bus()
    try:
        bus.calls.clear()
        _run(wa.notify_pending_approval({
            "id": "p-2",
            "user_id": "ghost_user_no_bind_wa",
            "agent_id": "a",
            "action": "x",
            "args": {},
        }))
        assert not [c for c in bus.calls if c["path"] == "/Messages.json"]
    finally:
        bus._restore()
