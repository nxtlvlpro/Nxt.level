"""
NXT8 JOKER — isolated sandbox sub-agent (v1.0).

Purpose
-------
JOKER absorbs **non-business** traffic that would otherwise pollute
the operational core (jokes, memes, fantasy match-ups, trolling, idle
small-talk).  It is a defensive perimeter, NOT an entertainment feature.

Design principles
-----------------
1. **Zero trust.** JOKER does *not* import:
   - `agents.memory`     (TF-IDF long-term memory)
   - `agents.mempalace_bridge` (ChromaDB)
   - `agents.documents`  (compliance corpus)
   - `core.db`           (tasks / requests / roi)  — except for its own audit ledger
   - any persona, reliability, mentor or orchestrator surface.
   The only outbound calls are: DeepSeek chat + own audit ledger writes.

2. **Cheap.** Uses the cheapest available DeepSeek (`:free` on OpenRouter),
   tiny `max_tokens` (120 default, 40 when rate-limited), keeps only the
   last 4 turns of history.  Target: ≤10 % of Hermes cost per turn.

3. **Stateless to the business core.** Writes never reach MemPalace,
   tasks, requests, or roi_history.  The only thing persisted is a
   one-row `db.joker_audit` entry per turn (request_id, session_id,
   tokens, ts) — purely for rate-limiting and dashboard counts.

4. **Auto-return.** Re-routing is decided on EVERY user turn by the
   classifier (`agents.classifier`).  JOKER never holds the conversation
   hostage — the moment the user mentions sales/clients/projects/etc.,
   the next turn lands back in Hermes automatically.

5. **Rate limited.** If a session_id exceeds `RATE_LIMIT_MAX` turns
   inside `RATE_LIMIT_WINDOW_MIN`, JOKER downgrades to a tiny model
   budget (max_tokens=40, history=1) for the rest of the window.

Public API:
    respond(message, session_id, history=None, lang="en") -> dict
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.joker")

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
MAX_HISTORY_TURNS = 4
DEFAULT_MAX_TOKENS = 150
DOWNGRADED_MAX_TOKENS = 40
DOWNGRADED_HISTORY = 1

RATE_LIMIT_WINDOW_MIN = 30
RATE_LIMIT_MAX = 20  # turns inside the window before downgrade

_SYSTEM_PROMPTS = {
    "en": (
        "You are JOKER — a sandbox sub-agent of the NXT8 corporate AI OS.\n"
        "Your role is a witty, slightly sarcastic cyber-jester that handles "
        "off-topic, playful, or nonsense queries so they never touch the "
        "operational core.\n\n"
        "Rules — non-negotiable:\n"
        "• You have ZERO access to company data, CRM, documents, analytics, "
        "or memory. Do not pretend you do.\n"
        "• Stay short and punchy: 1–3 sentences, max.\n"
        "• If the user's message is actually business (sales, clients, "
        "projects, documents, KPIs, finance, HR, strategy, analytics), "
        "reply ONE short sentence like \"That's real work — handing you "
        "back to Hermes\" and stop. Do NOT attempt the task yourself.\n"
        "• Never invent facts about the company. Never quote 'data'. "
        "Never claim to have run a tool.\n"
        "• Light humour is welcome; insults, slurs, NSFW, or hostility are not."
    ),
    "ru": (
        "Ты — JOKER, изолированный sandbox-субагент корпоративной AI OS NXT8.\n"
        "Твоя роль — остроумный, чуть саркастичный кибер-шут, который "
        "принимает на себя несерьёзные, провокационные и бессмысленные "
        "запросы, чтобы они не попадали в операционное ядро.\n\n"
        "Правила — без исключений:\n"
        "• У тебя НЕТ доступа к данным компании, CRM, документам, аналитике "
        "или памяти. Не делай вид, что есть.\n"
        "• Отвечай коротко и хлёстко: 1–3 предложения, не больше.\n"
        "• Если запрос на самом деле рабочий (продажи, клиенты, проекты, "
        "документы, KPI, финансы, HR, стратегия, аналитика) — ответь одной "
        "фразой типа «Это уже работа — передаю Гермесу» и остановись. "
        "Не пытайся выполнить задачу сам.\n"
        "• Не выдумывай факты о компании. Не цитируй «данные». "
        "Не утверждай, что вызвал какой-то инструмент.\n"
        "• Лёгкий юмор приветствуется; оскорбления, NSFW и враждебность — нет."
    ),
}

# ---------------------------------------------------------------------
# Rate limiting via own audit ledger
# ---------------------------------------------------------------------


async def _recent_turn_count(session_id: str) -> int:
    if not session_id:
        return 0
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(minutes=RATE_LIMIT_WINDOW_MIN)
    try:
        return await db.joker_audit.count_documents({
            "session_id": session_id,
            "ts": {"$gte": since.isoformat()},
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("joker_audit count failed: %s", e)
        return 0


async def _audit(
    session_id: str,
    user_id: Optional[str],
    message: str,
    reply: str,
    tokens_total: int,
    downgraded: bool,
    request_id: str,
    lang: str,
) -> None:
    db = get_db()
    doc = {
        "id": request_id,
        "session_id": session_id or "",
        "user_id": user_id or "",
        "lang": lang,
        "message": (message or "")[:500],
        "reply": (reply or "")[:500],
        "tokens_total": int(tokens_total or 0),
        "downgraded": bool(downgraded),
        "channel": "joker",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.joker_audit.insert_one(doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("joker_audit insert failed: %s", e)


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------


def _trim_history(history: Optional[List[Dict[str, Any]]], keep: int) -> List[Dict[str, str]]:
    if not history:
        return []
    trimmed: List[Dict[str, str]] = []
    for m in history[-keep:]:
        role = m.get("role", "user")
        content = m.get("content")
        if not isinstance(content, str):
            content = ""
        if role not in ("user", "assistant"):
            role = "user"
        trimmed.append({"role": role, "content": content[:600]})
    return trimmed


async def respond(
    message: str,
    session_id: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[str] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Generate a sandboxed reply.

    Returns:
        {
            "content":      str,         # the reply text
            "routed_to":    "joker",
            "downgraded":   bool,
            "tokens_total": int,
            "mock":         bool,
            "request_id":   str,
            "session_id":   str,
        }
    """
    sid = (session_id or str(uuid.uuid4())).strip()
    request_id = str(uuid.uuid4())
    lang_key = "ru" if (lang or "").lower().startswith("ru") else "en"
    system_prompt = _SYSTEM_PROMPTS[lang_key]

    # Apply rate-limit downgrade if needed.
    prior_count = await _recent_turn_count(sid)
    downgraded = prior_count >= RATE_LIMIT_MAX
    max_tokens = DOWNGRADED_MAX_TOKENS if downgraded else DEFAULT_MAX_TOKENS
    keep_history = DOWNGRADED_HISTORY if downgraded else MAX_HISTORY_TURNS

    msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    msgs.extend(_trim_history(history, keep_history))
    msgs.append({"role": "user", "content": (message or "").strip()[:1000]})

    tokens_total = 0
    mock = False
    content = ""
    try:
        deepseek = get_deepseek()
        resp = await deepseek.chat(
            messages=msgs,
            temperature=0.8,   # slightly higher → more playful
            max_tokens=max_tokens,
            request_logprobs=False,
        )
        content = (resp.get("content") or "").strip()
        tokens_total = int(resp.get("tokens_total") or 0)
        mock = bool(resp.get("mock"))
    except Exception:  # noqa: BLE001
        logger.exception("joker LLM call failed")
        content = (
            "🎭 Системная пауза. Попробуй ещё раз через секунду."
            if lang_key == "ru"
            else "🎭 Sandbox hiccup — give me a sec and try again."
        )
        mock = True

    # Hard ceiling on length so JOKER can never produce a wall of text.
    if len(content) > 800:
        content = content[:800].rstrip() + "…"

    await _audit(
        session_id=sid,
        user_id=user_id,
        message=message,
        reply=content,
        tokens_total=tokens_total,
        downgraded=downgraded,
        request_id=request_id,
        lang=lang_key,
    )

    return {
        "content": content,
        "routed_to": "joker",
        "downgraded": downgraded,
        "tokens_total": tokens_total,
        "mock": mock,
        "request_id": request_id,
        "session_id": sid,
    }


# Convenience: stats endpoint helper.
async def stats(window_minutes: int = 60) -> Dict[str, Any]:
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    pipeline = [
        {"$match": {"ts": {"$gte": since.isoformat()}}},
        {"$group": {
            "_id": None,
            "turns": {"$sum": 1},
            "tokens": {"$sum": "$tokens_total"},
            "downgraded": {"$sum": {"$cond": ["$downgraded", 1, 0]}},
        }},
    ]
    try:
        cur = db.joker_audit.aggregate(pipeline)
        rows = [r async for r in cur]
        if not rows:
            return {"turns": 0, "tokens": 0, "downgraded": 0, "window_minutes": window_minutes}
        r = rows[0]
        return {
            "turns": int(r.get("turns") or 0),
            "tokens": int(r.get("tokens") or 0),
            "downgraded": int(r.get("downgraded") or 0),
            "window_minutes": window_minutes,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("joker stats failed: %s", e)
        return {"turns": 0, "tokens": 0, "downgraded": 0, "window_minutes": window_minutes, "error": str(e)}
