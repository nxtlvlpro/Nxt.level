"""
NXT8 — Daily Digest builder & delivery.

Triggered by `core.scheduler` once a day (DIGEST_HOUR in tenant tz).
For each tenant:
  1. Build KPI snapshot for the last 24h (reuses `agents.pulse.compute_kpi`).
  2. Ask Hermes (DeepSeek) for 3 concrete proposals tailored to the data.
  3. Deliver to the owner's Telegram (preferred) or WhatsApp.
  4. Persist into `db.digests` with inline-button callback hooks.

Skip if: no real activity, LLM unavailable, or owner has no channel bound.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.db import get_db
from agents import pulse as _pulse

logger = logging.getLogger("nxt8.digest")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


async def _find_owner(company_id: str) -> Optional[Dict[str, Any]]:
    """Pick the admin user of the tenant (falls back to oldest user)."""
    db = get_db()
    user = await db.users.find_one(
        {"company_id": company_id, "is_admin": True}, {"_id": 0}
    )
    if user:
        return user
    return await db.users.find_one({"company_id": company_id}, {"_id": 0})


async def _already_sent_today(company_id: str) -> bool:
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    return await get_db().digests.count_documents({
        "company_id": company_id,
        "sent_at": {"$gte": _iso(today_start)},
    }) > 0


def _has_activity(kpi: Dict[str, Any]) -> bool:
    return bool(
        kpi.get("interactions_24h", 0)
        or kpi.get("deals_24h", 0)
        or kpi.get("pending_count", 0)
    )


# ---------------------------------------------------------------------
# LLM proposals
# ---------------------------------------------------------------------


_PROMPT = """Ты — Hermes, CEO-ассистент в утреннем дайджесте для владельца компании.
Тебе даны KPI компании за последние 24 часа. Сгенерируй краткий персонализированный
утренний обзор на русском языке.

Формат ответа — СТРОГО валидный JSON, без markdown:
{{
  "greeting": "одно тёплое короткое приветствие, 1 строка",
  "summary": ["bullet1", "bullet2", "bullet3"],
  "proposals": ["конкретное действие 1", "конкретное действие 2", "конкретное действие 3"]
}}

Каждое proposal — конкретное, исполнимое сегодня. Не общие слова.
Учитывай данные ниже.

Данные компании ({company_id}) за последние 24ч:
- Взаимодействий: {interactions_24h}
- Закрытых сделок: {deals_24h}
- Сумма сделок: ${roi_usd_24h:.0f}
- Активных pending-approvals: {pending_count}
- Зависших (>2ч) approvals: {stale_pending}
- Новых сделок за последний час: {new_deals_last_hour}

Имя владельца: {owner_name}.
"""


def _parse_llm_reply(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    raw = raw.strip()
    # Strip code-fence wrappers if present.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Hermes may add prose around the JSON — find the outermost {...}.
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    proposals = data.get("proposals") or []
    if not isinstance(proposals, list) or len(proposals) < 1:
        return None
    return {
        "greeting": str(data.get("greeting") or "Доброе утро!"),
        "summary": [str(s) for s in (data.get("summary") or []) if s][:4],
        "proposals": [str(p) for p in proposals if p][:3],
    }


async def _llm_proposals(
    company_id: str, kpi: Dict[str, Any], owner_name: str
) -> Optional[Dict[str, Any]]:
    """Return digest body or None if LLM unavailable / parse failed."""
    from core import deepseek as _ds
    prompt = _PROMPT.format(company_id=company_id, owner_name=owner_name or "владелец", **kpi)
    try:
        resp = await _ds.get_deepseek().chat(
            messages=[
                {"role": "system", "content": "You are Hermes, NXT8 CEO assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=600,
            request_logprobs=False,
        )
    except _ds.LLMUnavailable as e:
        logger.warning("digest skip — LLM unavailable: %s", e)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("digest LLM call failed: %s", e)
        return None
    body = _parse_llm_reply((resp or {}).get("content") or "")
    if not body:
        logger.warning("digest LLM returned unparseable body for %s", company_id)
        return None
    return body


# ---------------------------------------------------------------------
# Render + deliver
# ---------------------------------------------------------------------


def _render_text(body: Dict[str, Any], kpi: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(body.get("greeting") or "Доброе утро 👋")
    lines.append("")
    lines.append("За последние 24 часа:")
    if not body.get("summary"):
        # Fallback summary built from raw KPI.
        lines.append(f"— {kpi['interactions_24h']} новых обращений")
        lines.append(f"— {kpi['deals_24h']} закрытых сделок · ${kpi['roi_usd_24h']:.0f}")
        lines.append(f"— {kpi['pending_count']} задач ждут вашего решения")
    else:
        for s in body["summary"]:
            lines.append(f"— {s}")
    lines.append("")
    lines.append("Я предлагаю сегодня:")
    for i, p in enumerate(body.get("proposals") or [], start=1):
        lines.append(f"{i}. {p}")
    return "\n".join(lines)


async def _deliver(company_id: str, digest_id: str, text: str) -> Optional[str]:
    """Try Telegram first, then WhatsApp. Returns the channel actually used."""
    owner = await _find_owner(company_id)
    if not owner:
        return None
    owner_id = owner["user_id"]

    # Telegram
    try:
        from core import telegram_bot as _tg
        if _tg.is_enabled():
            chat = await _tg.get_chat_for_client(owner_id)
            if chat:
                keyboard = {"inline_keyboard": [[
                    {"text": "✅ Подтвердить план", "callback_data": f"digest_approve:{digest_id}"},
                    {"text": "✏ Изменить", "callback_data": f"digest_edit:{digest_id}"},
                ]]}
                res = await _tg.send_message(int(chat["chat_id"]), text, reply_markup=keyboard)
                if res.get("ok"):
                    return "telegram"
    except Exception as e:  # noqa: BLE001
        logger.warning("digest telegram delivery failed: %s", e)

    # WhatsApp fallback
    try:
        from core import whatsapp_bot as _wa
        if _wa.is_enabled():
            chat = await _wa.get_chat_for_client(owner_id)
            if chat:
                text_wa = (
                    text
                    + "\n\nОтветьте:\n  1 — Подтвердить план\n  2 — Изменить приоритеты"
                )
                res = await _wa.send_message(chat["wa_id"], text_wa)
                if res.get("ok"):
                    return "whatsapp"
    except Exception as e:  # noqa: BLE001
        logger.warning("digest whatsapp delivery failed: %s", e)

    return None


# ---------------------------------------------------------------------
# Public — build & send
# ---------------------------------------------------------------------


async def build_and_send(company_id: str) -> Dict[str, Any]:
    """Returns `{sent: bool, reason?: str, digest_id?: str, channel?: str}`."""
    if await _already_sent_today(company_id):
        return {"sent": False, "reason": "already_sent_today"}

    kpi = await _pulse.compute_kpi(company_id)
    if not _has_activity(kpi):
        return {"sent": False, "reason": "no_activity"}

    owner = await _find_owner(company_id)
    if not owner:
        return {"sent": False, "reason": "no_owner"}

    body = await _llm_proposals(company_id, kpi, owner.get("name") or "")
    if not body:
        return {"sent": False, "reason": "llm_unavailable_or_parse_failed"}

    text = _render_text(body, kpi)
    digest_id = f"digest_{uuid.uuid4().hex[:16]}"

    channel = await _deliver(company_id, digest_id, text)
    if not channel:
        return {"sent": False, "reason": "no_channel_bound"}

    await get_db().digests.insert_one({
        "digest_id": digest_id,
        "company_id": company_id,
        "owner_user_id": owner["user_id"],
        "sent_at": _iso(_now()),
        "channel": channel,
        "kpi": kpi,
        "body": body,
        "rendered": text,
        "status": "delivered",
    })

    return {"sent": True, "digest_id": digest_id, "channel": channel, "kpi": kpi}


async def build_preview(company_id: str) -> Dict[str, Any]:
    """Same as build_and_send but does NOT deliver — for manual smoke tests."""
    kpi = await _pulse.compute_kpi(company_id)
    activity = _has_activity(kpi)
    owner = await _find_owner(company_id)
    owner_name = (owner or {}).get("name") or ""
    if not activity:
        return {"would_send": False, "reason": "no_activity", "kpi": kpi}
    body = await _llm_proposals(company_id, kpi, owner_name)
    if not body:
        return {"would_send": False, "reason": "llm_unavailable_or_parse_failed", "kpi": kpi}
    return {
        "would_send": True,
        "channel_candidate": "telegram_or_whatsapp",
        "kpi": kpi,
        "body": body,
        "rendered": _render_text(body, kpi),
    }
