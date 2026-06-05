"""
NXT8 Telegram channel bridge.

A single shared bot (configured via TELEGRAM_BOT_TOKEN) lets clients
control NXT8 from Telegram in one click.

Flow
----
1. Client clicks "Подключить Telegram" in the web UI.
2. Backend mints a one-time link token, stored in
   `telegram_link_tokens`. UI opens `t.me/<bot>?start=<token>`.
3. User presses "Start" in Telegram → bot receives `/start <token>`
   via webhook.
4. We resolve the token, write a `telegram_chats` document binding
   `chat_id ↔ client_id`, and send a welcome message.
5. From then on, every message in that chat is forwarded to Hermes
   and the reply is delivered back to Telegram. Pending approvals
   are pushed as inline-button cards so the owner can Approve/Reject
   without leaving Telegram.

Public surface
--------------
    is_enabled()
    ensure_indexes()
    get_bot_info()
    install_webhook(base_url)
    delete_webhook()
    mint_link_token(client_id)
    get_chat_for_client(client_id)
    unbind(client_id)
    handle_update(payload)          # webhook entry
    send_message(chat_id, text, ...)
    send_approval_card(chat_id, approval)
    notify_pending_approval(approval)
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from core.db import get_db

logger = logging.getLogger("nxt8.telegram")

TG_API_BASE = "https://api.telegram.org"
LINK_TOKEN_TTL_MINUTES = 30
DEFAULT_SESSION_PREFIX = "tg"


# ---------------------------------------------------------------------
# Config / helpers
# ---------------------------------------------------------------------


def _token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _webhook_secret() -> str:
    return (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip()


def is_enabled() -> bool:
    return bool(_token())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


_BOT_INFO_CACHE: Dict[str, Any] = {}


# ---------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------


async def ensure_indexes() -> None:
    if not is_enabled():
        return
    db = get_db()
    try:
        await db.telegram_chats.create_index("client_id", unique=True)
        await db.telegram_chats.create_index("chat_id", unique=True)
        await db.telegram_link_tokens.create_index("token", unique=True)
        await db.telegram_link_tokens.create_index(
            "expires_at", expireAfterSeconds=0
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("telegram ensure_indexes failed: %s", e)


# ---------------------------------------------------------------------
# Telegram API (httpx)
# ---------------------------------------------------------------------


async def _tg_call(method: str, **payload: Any) -> Dict[str, Any]:
    if not is_enabled():
        return {"ok": False, "error": "telegram disabled (no token)"}
    url = f"{TG_API_BASE}/bot{_token()}/{method}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(url, json=payload)
        data = r.json()
        if not data.get("ok"):
            logger.warning("tg %s failed: %s", method, data)
        return data
    except Exception as e:  # noqa: BLE001
        logger.exception("tg %s error: %s", method, e)
        return {"ok": False, "error": str(e)}


async def get_bot_info(force: bool = False) -> Dict[str, Any]:
    """Fetch (and cache) the bot username/profile."""
    if not force and _BOT_INFO_CACHE.get("username"):
        return _BOT_INFO_CACHE
    res = await _tg_call("getMe")
    if res.get("ok"):
        u = res.get("result") or {}
        _BOT_INFO_CACHE.update({
            "id": u.get("id"),
            "username": u.get("username"),
            "first_name": u.get("first_name"),
            "can_join_groups": u.get("can_join_groups"),
        })
    return _BOT_INFO_CACHE


async def install_webhook(base_url: str) -> Dict[str, Any]:
    """Register the webhook URL with Telegram. Idempotent."""
    if not is_enabled():
        return {"ok": False, "error": "telegram disabled"}
    secret = _webhook_secret() or "nxt8"
    webhook_url = f"{base_url.rstrip('/')}/api/telegram/webhook/{secret}"
    res = await _tg_call(
        "setWebhook",
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )
    return {"ok": bool(res.get("ok")), "url": webhook_url, "raw": res}


async def delete_webhook() -> Dict[str, Any]:
    return await _tg_call("deleteWebhook", drop_pending_updates=False)


async def send_message(
    chat_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await _tg_call("sendMessage", **payload)


async def _answer_callback(callback_id: str, text: str = "") -> None:
    await _tg_call("answerCallbackQuery", callback_query_id=callback_id, text=text[:180])


async def _send_chat_action(chat_id: int, action: str = "typing") -> None:
    await _tg_call("sendChatAction", chat_id=chat_id, action=action)


# ---------------------------------------------------------------------
# Link tokens & bindings
# ---------------------------------------------------------------------


async def mint_link_token(client_id: str) -> Dict[str, Any]:
    """Create a one-time deep-link token that ties a Telegram /start to client_id."""
    if not is_enabled():
        return {"ok": False, "error": "telegram disabled"}
    token = secrets.token_urlsafe(18)  # ~24 chars, deep-link safe
    expires_at = _now() + timedelta(minutes=LINK_TOKEN_TTL_MINUTES)
    await get_db().telegram_link_tokens.insert_one({
        "token": token,
        "client_id": client_id,
        "expires_at": expires_at,
        "created_at": _now_iso(),
        "used": False,
    })
    info = await get_bot_info()
    username = info.get("username") or "nxt8_bot"
    return {
        "ok": True,
        "token": token,
        "bot_username": username,
        "deep_link": f"https://t.me/{username}?start={token}",
        "expires_in_minutes": LINK_TOKEN_TTL_MINUTES,
    }


async def _resolve_link_token(token: str) -> Optional[Dict[str, Any]]:
    rec = await get_db().telegram_link_tokens.find_one(
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
    await get_db().telegram_link_tokens.update_one(
        {"token": token}, {"$set": {"used": True, "used_at": _now_iso()}}
    )


async def _bind_chat(
    client_id: str,
    chat_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> None:
    db = get_db()
    # Allow only one chat per client_id and one client_id per chat_id.
    await db.telegram_chats.delete_many({"client_id": client_id})
    await db.telegram_chats.delete_many({"chat_id": chat_id})
    await db.telegram_chats.insert_one({
        "client_id": client_id,
        "chat_id": chat_id,
        "username": username,
        "first_name": first_name,
        "bound_at": _now_iso(),
        "session_id": f"{DEFAULT_SESSION_PREFIX}:{client_id}",
    })


async def get_chat_for_client(client_id: str) -> Optional[Dict[str, Any]]:
    return await get_db().telegram_chats.find_one(
        {"client_id": client_id}, {"_id": 0}
    )


async def _get_client_for_chat(chat_id: int) -> Optional[Dict[str, Any]]:
    return await get_db().telegram_chats.find_one(
        {"chat_id": chat_id}, {"_id": 0}
    )


async def unbind(client_id: str) -> Dict[str, Any]:
    res = await get_db().telegram_chats.delete_many({"client_id": client_id})
    return {"ok": True, "removed": int(res.deleted_count or 0)}


# ---------------------------------------------------------------------
# Approval cards
# ---------------------------------------------------------------------


def _approval_card_text(approval: Dict[str, Any]) -> str:
    action = approval.get("action") or "unknown_action"
    agent = approval.get("agent_id") or "agent"
    rationale = approval.get("rationale") or ""
    args = approval.get("args") or {}
    args_lines: List[str] = []
    for k, v in args.items():
        sv = str(v)
        if len(sv) > 140:
            sv = sv[:137] + "..."
        args_lines.append(f"• {k}: {sv}")
    args_block = "\n".join(args_lines) if args_lines else "—"
    rat_block = f"\n\n🧠 {rationale}" if rationale else ""
    return (
        f"⏸ Требуется одобрение\n\n"
        f"Агент: {agent}\n"
        f"Действие: {action}\n\n"
        f"Параметры:\n{args_block}"
        f"{rat_block}"
    )


def _approval_keyboard(approval_id: str) -> Dict[str, Any]:
    return {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{approval_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{approval_id}"},
        ]]
    }


async def send_approval_card(chat_id: int, approval: Dict[str, Any]) -> Dict[str, Any]:
    return await send_message(
        chat_id,
        _approval_card_text(approval),
        reply_markup=_approval_keyboard(approval.get("id") or approval.get("approval_id") or ""),
    )


async def notify_pending_approval(approval: Dict[str, Any]) -> None:
    """Best-effort push of a pending approval to the owner's Telegram, if bound."""
    if not is_enabled():
        return
    client_id = approval.get("user_id") or approval.get("client_id") or "default"
    chat = await get_chat_for_client(client_id) or await get_chat_for_client("default")
    if not chat:
        return
    try:
        await send_approval_card(int(chat["chat_id"]), approval)
    except Exception as e:  # noqa: BLE001
        logger.warning("telegram notify_pending_approval failed: %s", e)


# ---------------------------------------------------------------------
# Incoming updates
# ---------------------------------------------------------------------


async def _handle_start(chat_id: int, payload: str, username: Optional[str], first_name: Optional[str]) -> None:
    payload = (payload or "").strip()
    if not payload:
        await send_message(
            chat_id,
            "👋 Привет! Это NXT8.\n\n"
            "Чтобы привязать этот чат к вашему аккаунту, откройте в NXT8 раздел "
            "«Подключить Telegram» и нажмите кнопку. Я открою этот же чат с уникальной ссылкой.",
        )
        return

    rec = await _resolve_link_token(payload)
    if not rec:
        await send_message(
            chat_id,
            "🚫 Ссылка недействительна или истекла. Сгенерируйте новую в NXT8.",
        )
        return

    client_id = rec["client_id"]
    await _bind_chat(client_id, chat_id, username, first_name)
    await _consume_link_token(payload)

    await send_message(
        chat_id,
        "✅ Telegram подключен.\n\n"
        "Теперь пишите сюда — я отвечу как Hermes. Команды:\n"
        "/help — что я умею\n"
        "/approvals — открытые запросы на одобрение\n"
        "/disconnect — отвязать чат",
    )


async def _handle_help(chat_id: int) -> None:
    await send_message(
        chat_id,
        "🤖 Я — Hermes из NXT8.\n\n"
        "• Пишите задачу, вопрос или команду — отвечу.\n"
        "• /approvals — посмотреть pending-запросы и одобрить/отклонить.\n"
        "• /disconnect — отвязать этот чат от аккаунта.",
    )


async def _handle_disconnect(chat_id: int) -> None:
    db = get_db()
    chat = await _get_client_for_chat(chat_id)
    if not chat:
        await send_message(chat_id, "Чат не привязан.")
        return
    await db.telegram_chats.delete_many({"chat_id": chat_id})
    await send_message(chat_id, "🔌 Чат отвязан. Чтобы вернуть — сгенерируйте новую ссылку в NXT8.")


async def _handle_approvals_cmd(chat_id: int, client_id: str) -> None:
    from core import approval_gate as _ag
    items = await _ag.list_pending(status="pending", limit=5)
    if not items:
        await send_message(chat_id, "✅ Нет ожидающих одобрения действий.")
        return
    await send_message(chat_id, f"⏸ Ожидают одобрения: {len(items)}")
    for it in items:
        try:
            await send_approval_card(chat_id, it)
        except Exception as e:  # noqa: BLE001
            logger.warning("send_approval_card failed: %s", e)


async def _handle_text_to_hermes(chat_id: int, client_id: str, text: str) -> None:
    """Forward arbitrary text to Hermes and reply with his answer."""
    if not text.strip():
        return
    await _send_chat_action(chat_id, "typing")
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
        logger.exception("telegram->hermes failed: %s", e)
        reply = f"⚠ Ошибка Hermes: {e}"
    await send_message(chat_id, reply)


async def _handle_callback(update_cb: Dict[str, Any]) -> None:
    cb_id = update_cb.get("id")
    data = (update_cb.get("data") or "").strip()
    msg = update_cb.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    from_user = update_cb.get("from") or {}
    actor = from_user.get("username") or str(from_user.get("id") or "telegram")

    if not data or ":" not in data or chat_id is None:
        if cb_id:
            await _answer_callback(cb_id, "invalid")
        return

    op, approval_id = data.split(":", 1)
    # Daily digest inline buttons — handled separately from approvals.
    if op in {"digest_approve", "digest_edit"}:
        digest_id = approval_id
        try:
            from core.db import get_db as _gdb
            await _gdb().digests.update_one(
                {"digest_id": digest_id},
                {"$set": {"status": "approved" if op == "digest_approve" else "edit_requested"}},
            )
        except Exception:  # noqa: BLE001
            pass
        if cb_id:
            await _answer_callback(cb_id, "OK")
        if op == "digest_approve":
            await send_message(chat_id, "✅ План на день подтверждён. Запускаю.")
        else:
            await send_message(
                chat_id,
                "✏ Хорошо — напишите, что хотите изменить, и я перестрою план.",
            )
        return

    from core import approval_gate as _ag
    from agents.hermes import HERMES_TOOLS

    async def _executor(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        fn = HERMES_TOOLS.get(action)
        if not fn:
            return {"ok": False, "error": f"unknown tool: {action}"}
        return await fn(args)

    if op == "approve":
        res = await _ag.approve(approval_id, decided_by=f"tg:{actor}", executor=_executor)
        ok = bool(res.get("ok"))
        if cb_id:
            await _answer_callback(cb_id, "Approved" if ok else "Failed")
        await send_message(
            chat_id,
            f"✅ Approved: {approval_id}\nstatus: {res.get('status', 'unknown')}",
        )
    elif op == "reject":
        res = await _ag.reject(approval_id, decided_by=f"tg:{actor}")
        ok = bool(res.get("ok"))
        if cb_id:
            await _answer_callback(cb_id, "Rejected" if ok else "Failed")
        await send_message(chat_id, f"❌ Rejected: {approval_id}")
    else:
        if cb_id:
            await _answer_callback(cb_id, "unknown op")


async def handle_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main webhook entry point. Returns a tiny ack — Telegram only cares
    that we return 2xx quickly."""
    try:
        if "callback_query" in payload:
            await _handle_callback(payload["callback_query"])
            return {"ok": True}

        msg = payload.get("message") or payload.get("edited_message") or {}
        if not msg:
            return {"ok": True}

        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        from_user = msg.get("from") or {}
        username = from_user.get("username")
        first_name = from_user.get("first_name")
        text = (msg.get("text") or "").strip()

        if chat_id is None:
            return {"ok": True}

        # /start <token>
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""
            await _handle_start(chat_id, arg, username, first_name)
            return {"ok": True}

        # Other commands need a binding.
        binding = await _get_client_for_chat(chat_id)
        if not binding:
            await send_message(
                chat_id,
                "🔒 Этот чат не привязан к NXT8. Откройте приложение и нажмите "
                "«Подключить Telegram», чтобы получить персональную ссылку.",
            )
            return {"ok": True}

        client_id = binding["client_id"]

        if text in ("/help", "help"):
            await _handle_help(chat_id)
            return {"ok": True}

        if text == "/disconnect":
            await _handle_disconnect(chat_id)
            return {"ok": True}

        if text in ("/approvals", "/pending"):
            await _handle_approvals_cmd(chat_id, client_id)
            return {"ok": True}

        # Default → forward to Hermes
        await _handle_text_to_hermes(chat_id, client_id, text)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        logger.exception("telegram handle_update failed: %s", e)
        return {"ok": True, "error": str(e)}
