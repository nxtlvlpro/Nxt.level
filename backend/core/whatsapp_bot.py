"""
NXT8 WhatsApp channel bridge (Twilio).

Mirrors `core/telegram_bot.py`: a single shared Twilio WhatsApp sender
(configured via TWILIO_*) lets clients control NXT8 from WhatsApp in
~one click.

Flow
----
1. Client clicks "Подключить WhatsApp" in the web UI.
2. Backend mints a one-time link token (`whatsapp_link_tokens`).
   UI opens `wa.me/<from-number>?text=NXT8 <token>`.
3. User taps "Send" in WhatsApp → Twilio delivers an inbound message
   to our webhook (form-encoded POST).
4. We extract the token from the message body, write
   `whatsapp_chats` binding `wa_id ↔ client_id`, and reply with a
   welcome.
5. Every subsequent message in that conversation is forwarded to
   Hermes; the reply is sent back via Twilio. Pending approvals are
   pushed as text + Quick-Reply commands (`A` / `R`) because WhatsApp
   inline buttons require approved templates.

External docs
-------------
- POST     /2010-04-01/Accounts/{SID}/Messages.json   (send)
- Inbound webhook: configurable per number in Twilio console
- Signature: header `X-Twilio-Signature` (HMAC-SHA1, base64) over
  the request URL + sorted form parameters.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from core.db import get_db

logger = logging.getLogger("nxt8.whatsapp")

LINK_TOKEN_TTL_MINUTES = 30
TOKEN_PREFIX = "NXT8 "  # what the user sends as first-time text
SESSION_PREFIX = "wa"


# ---------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------


def _sid() -> str:
    return (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()


def _token() -> str:
    return (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()


def _from() -> str:
    """The Twilio-side WhatsApp address (e.g. 'whatsapp:+13253263849')."""
    return (os.environ.get("TWILIO_WHATSAPP_FROM") or "").strip()


def _sandbox_code() -> str:
    """Optional 'join <two-words>' code shown to first-time sandbox users."""
    return (os.environ.get("TWILIO_WHATSAPP_SANDBOX_CODE") or "").strip()


def is_enabled() -> bool:
    return all([_sid(), _token(), _from()])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _phone_from_wa(wa: str) -> str:
    """'whatsapp:+13253...' → '+13253...' (for wa.me deep-links)."""
    if not wa:
        return ""
    return wa.replace("whatsapp:", "", 1).strip()


# ---------------------------------------------------------------------
# Twilio REST
# ---------------------------------------------------------------------


async def _twilio_post(path: str, **form: Any) -> Dict[str, Any]:
    if not is_enabled():
        return {"ok": False, "error": "whatsapp disabled (missing TWILIO_*)"}
    url = f"https://api.twilio.com/2010-04-01/Accounts/{_sid()}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                url,
                data={k: v for k, v in form.items() if v is not None},
                auth=(_sid(), _token()),
            )
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            data = {"raw": r.text}
        if r.status_code >= 400:
            logger.warning("twilio %s failed: %s %s", path, r.status_code, data)
            return {"ok": False, "status": r.status_code, **data}
        return {"ok": True, **data}
    except Exception as e:  # noqa: BLE001
        logger.exception("twilio %s error: %s", path, e)
        return {"ok": False, "error": str(e)}


async def send_message(to_wa: str, text: str) -> Dict[str, Any]:
    """Send a plain text WhatsApp message. `to_wa` is 'whatsapp:+...' form."""
    if not to_wa.startswith("whatsapp:"):
        to_wa = f"whatsapp:{to_wa}"
    return await _twilio_post(
        "/Messages.json",
        From=_from(),
        To=to_wa,
        Body=text[:1500],
    )


# ---------------------------------------------------------------------
# Twilio webhook signature (best-effort, optional)
# ---------------------------------------------------------------------


def verify_twilio_signature(
    url: str, params: Dict[str, str], header_sig: str
) -> bool:
    """Validate `X-Twilio-Signature`. Returns False if signature missing
    or token unset — caller decides whether to enforce."""
    tok = _token()
    if not tok or not header_sig:
        return False
    # Twilio rule: concatenate URL with sorted parameter pairs.
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    mac = hmac.new(tok.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(mac).decode("ascii")
    return hmac.compare_digest(expected, header_sig)


# ---------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------


async def ensure_indexes() -> None:
    if not is_enabled():
        return
    db = get_db()
    try:
        await db.whatsapp_chats.create_index("client_id", unique=True)
        await db.whatsapp_chats.create_index("wa_id", unique=True)
        await db.whatsapp_link_tokens.create_index("token", unique=True)
        await db.whatsapp_link_tokens.create_index(
            "expires_at", expireAfterSeconds=0
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("whatsapp ensure_indexes failed: %s", e)


# ---------------------------------------------------------------------
# Link tokens & bindings
# ---------------------------------------------------------------------


async def mint_link_token(client_id: str) -> Dict[str, Any]:
    """Create a one-time deep-link token. The deep-link asks WhatsApp to
    pre-fill a message; the user just taps Send."""
    if not is_enabled():
        return {"ok": False, "error": "whatsapp disabled"}
    token = secrets.token_urlsafe(12)
    expires_at = _now() + timedelta(minutes=LINK_TOKEN_TTL_MINUTES)
    await get_db().whatsapp_link_tokens.insert_one({
        "token": token,
        "client_id": client_id,
        "expires_at": expires_at,
        "created_at": _now_iso(),
        "used": False,
    })

    from_phone = _phone_from_wa(_from())  # +13253263849
    # If the account is still in Twilio Sandbox the user must first send
    # `join <code>` once, then our `NXT8 <token>` line. We pre-fill BOTH
    # commands; WhatsApp will deliver them as two separate messages.
    code = _sandbox_code()
    body = (f"join {code}\n" if code else "") + f"{TOKEN_PREFIX}{token}"
    encoded = urllib.parse.quote(body)
    # wa.me strips the leading '+' from numbers.
    wa_target = from_phone.lstrip("+")
    deep_link = f"https://wa.me/{wa_target}?text={encoded}"
    return {
        "ok": True,
        "token": token,
        "from": from_phone,
        "deep_link": deep_link,
        "needs_sandbox_code": bool(code),
        "expires_in_minutes": LINK_TOKEN_TTL_MINUTES,
    }


async def _resolve_link_token(token: str) -> Optional[Dict[str, Any]]:
    rec = await get_db().whatsapp_link_tokens.find_one(
        {"token": token, "used": False}, {"_id": 0}
    )
    if not rec:
        return None
    expires_at = rec.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < _now():
            return None
    return rec


async def _consume_link_token(token: str) -> None:
    await get_db().whatsapp_link_tokens.update_one(
        {"token": token}, {"$set": {"used": True, "used_at": _now_iso()}}
    )


async def _bind_chat(
    client_id: str,
    wa_id: str,
    profile_name: Optional[str],
) -> None:
    db = get_db()
    await db.whatsapp_chats.delete_many({"client_id": client_id})
    await db.whatsapp_chats.delete_many({"wa_id": wa_id})
    await db.whatsapp_chats.insert_one({
        "client_id": client_id,
        "wa_id": wa_id,                   # 'whatsapp:+12345...'
        "profile_name": profile_name,
        "bound_at": _now_iso(),
        "session_id": f"{SESSION_PREFIX}:{client_id}",
    })


async def get_chat_for_client(client_id: str) -> Optional[Dict[str, Any]]:
    return await get_db().whatsapp_chats.find_one(
        {"client_id": client_id}, {"_id": 0}
    )


async def _get_client_for_wa(wa_id: str) -> Optional[Dict[str, Any]]:
    return await get_db().whatsapp_chats.find_one(
        {"wa_id": wa_id}, {"_id": 0}
    )


async def unbind(client_id: str) -> Dict[str, Any]:
    res = await get_db().whatsapp_chats.delete_many({"client_id": client_id})
    return {"ok": True, "removed": int(res.deleted_count or 0)}


# ---------------------------------------------------------------------
# Approval cards (no inline buttons in WhatsApp → use Quick-Reply codes)
# ---------------------------------------------------------------------


def _approval_card_text(approval: Dict[str, Any]) -> str:
    action = approval.get("action") or "unknown_action"
    agent = approval.get("agent_id") or "agent"
    rationale = approval.get("rationale") or ""
    args = approval.get("args") or {}
    aid = approval.get("id") or approval.get("approval_id") or "?"
    args_lines: List[str] = []
    for k, v in args.items():
        sv = str(v)
        if len(sv) > 120:
            sv = sv[:117] + "..."
        args_lines.append(f"• {k}: {sv}")
    args_block = "\n".join(args_lines) if args_lines else "—"
    rat_block = f"\n\n🧠 {rationale}" if rationale else ""
    return (
        f"⏸ Требуется одобрение\n\n"
        f"Агент: {agent}\n"
        f"Действие: {action}\n"
        f"ID: {aid}\n\n"
        f"Параметры:\n{args_block}"
        f"{rat_block}\n\n"
        f"Ответьте:\n"
        f"  A {aid}  — Approve\n"
        f"  R {aid}  — Reject"
    )


async def send_approval_card(to_wa: str, approval: Dict[str, Any]) -> Dict[str, Any]:
    return await send_message(to_wa, _approval_card_text(approval))


async def notify_pending_approval(approval: Dict[str, Any]) -> None:
    if not is_enabled():
        return
    client_id = approval.get("user_id") or approval.get("client_id") or "default"
    chat = await get_chat_for_client(client_id)
    if not chat:
        return
    try:
        await send_approval_card(chat["wa_id"], approval)
    except Exception as e:  # noqa: BLE001
        logger.warning("whatsapp notify_pending_approval failed: %s", e)


# ---------------------------------------------------------------------
# Inbound handlers
# ---------------------------------------------------------------------


async def _handle_text_to_hermes(wa_id: str, client_id: str, text: str) -> None:
    if not text.strip():
        return
    try:
        from agents import hermes as _h
        res = await _h.hermes_chat(
            messages=[{"role": "user", "content": text}],
            company_id="default",
            user_id=client_id,
            mode="operational",
            autonomy_level="assistant",
            temperature=0.3,
        )
        reply = (res.get("content") or "").strip() or "…"
    except Exception as e:  # noqa: BLE001
        logger.exception("whatsapp->hermes failed: %s", e)
        reply = f"⚠ Ошибка Hermes: {e}"
    await send_message(wa_id, reply)


async def _handle_help(wa_id: str) -> None:
    await send_message(
        wa_id,
        "🤖 Я — Hermes из NXT8.\n\n"
        "• Пишите задачу, вопрос или команду — отвечу.\n"
        "• approvals — посмотреть pending-запросы.\n"
        "• A <id> — одобрить, R <id> — отклонить.\n"
        "• disconnect — отвязать этот чат.",
    )


async def _handle_disconnect(wa_id: str) -> None:
    db = get_db()
    chat = await _get_client_for_wa(wa_id)
    if not chat:
        await send_message(wa_id, "Чат не привязан.")
        return
    await db.whatsapp_chats.delete_many({"wa_id": wa_id})
    await send_message(wa_id, "🔌 Чат отвязан. Сгенерируйте новую ссылку в NXT8, чтобы вернуть.")


async def _handle_approvals_cmd(wa_id: str) -> None:
    from core import approval_gate as _ag
    items = await _ag.list_pending(status="pending", limit=5)
    if not items:
        await send_message(wa_id, "✅ Нет ожидающих одобрения действий.")
        return
    await send_message(wa_id, f"⏸ Ожидают одобрения: {len(items)}")
    for it in items:
        try:
            await send_approval_card(wa_id, it)
        except Exception as e:  # noqa: BLE001
            logger.warning("send_approval_card failed: %s", e)


async def _handle_approve_or_reject(
    wa_id: str, op: str, approval_id: str, actor: str
) -> None:
    from core import approval_gate as _ag
    from agents.hermes import HERMES_TOOLS

    async def _executor(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        fn = HERMES_TOOLS.get(action)
        if not fn:
            return {"ok": False, "error": f"unknown tool: {action}"}
        return await fn(args)

    if op == "approve":
        res = await _ag.approve(approval_id, decided_by=f"wa:{actor}", executor=_executor)
        await send_message(wa_id, f"✅ Approved: {approval_id}\nstatus: {res.get('status', 'unknown')}")
    elif op == "reject":
        res = await _ag.reject(approval_id, decided_by=f"wa:{actor}")
        await send_message(wa_id, f"❌ Rejected: {approval_id} ({res.get('status', 'unknown')})")


def _extract_token(text: str) -> Optional[str]:
    """Return the binding token if the message starts with 'NXT8 <token>'."""
    stripped = text.lstrip()
    if not stripped.upper().startswith(TOKEN_PREFIX):
        return None
    return stripped[len(TOKEN_PREFIX):].split()[0].strip() or None


def _parse_approve_reject(text: str) -> Optional[tuple[str, str]]:
    """Detect 'A <id>' / 'R <id>' / 'approve <id>' / 'reject <id>'."""
    s = text.strip()
    if not s:
        return None
    low = s.lower()
    parts = s.split()
    if len(parts) >= 2 and parts[0].lower() in {"a", "approve", "approved"}:
        return ("approve", parts[1])
    if len(parts) >= 2 and parts[0].lower() in {"r", "reject", "rejected"}:
        return ("reject", parts[1])
    if low in {"approvals", "/approvals", "pending"}:
        return ("approvals", "")
    return None


async def handle_inbound(form: Dict[str, str]) -> Dict[str, Any]:
    """Process a Twilio inbound webhook form payload."""
    try:
        wa_id = form.get("From") or ""        # 'whatsapp:+...'
        body = (form.get("Body") or "").strip()
        profile = form.get("ProfileName")
        if not wa_id:
            return {"ok": True}

        # First-time binding: message contains 'NXT8 <token>'.
        tok = _extract_token(body)
        if tok:
            rec = await _resolve_link_token(tok)
            if not rec:
                await send_message(
                    wa_id,
                    "🚫 Ссылка недействительна или истекла. Сгенерируйте новую в NXT8.",
                )
                return {"ok": True}
            client_id = rec["client_id"]
            await _bind_chat(client_id, wa_id, profile)
            await _consume_link_token(tok)
            await send_message(
                wa_id,
                "✅ WhatsApp подключен.\n\n"
                "Теперь пишите сюда — я отвечу как Hermes.\n"
                "Команды:\n"
                "  help — что я умею\n"
                "  approvals — pending-запросы\n"
                "  A <id> / R <id> — одобрить / отклонить\n"
                "  disconnect — отвязать чат",
            )
            return {"ok": True}

        binding = await _get_client_for_wa(wa_id)
        if not binding:
            await send_message(
                wa_id,
                "🔒 Этот чат не привязан к NXT8. Откройте приложение и нажмите "
                "«Подключить WhatsApp», чтобы получить персональную ссылку.",
            )
            return {"ok": True}
        client_id = binding["client_id"]

        if body.lower() in {"help", "/help"}:
            await _handle_help(wa_id)
            return {"ok": True}

        if body.lower() in {"disconnect", "/disconnect", "unbind"}:
            await _handle_disconnect(wa_id)
            return {"ok": True}

        parsed = _parse_approve_reject(body)
        if parsed:
            op, arg = parsed
            if op == "approvals":
                await _handle_approvals_cmd(wa_id)
            else:
                await _handle_approve_or_reject(
                    wa_id, op, arg, actor=profile or wa_id
                )
            return {"ok": True}

        await _handle_text_to_hermes(wa_id, client_id, body)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        logger.exception("whatsapp handle_inbound failed: %s", e)
        return {"ok": True, "error": str(e)}
