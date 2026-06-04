"""
NXT8 Inter-Agent Communication Layer.

Three real tools that turn the team into a connected organism:

    delegate_to_agent  — Hermes (CEO) hands a concrete task to a subordinate
                         persona, gets their answer back synchronously,
                         and can use it in his own reply.

    escalate_to_hermes — any subordinate flags a situation that requires
                         the CEO. Creates a db.escalations record AND
                         immediately asks Hermes for a verdict on the
                         issue (so the response surfaces back to the
                         original caller).

    ask_colleague      — peer-to-peer Q&A between two subordinates.
                         Example: Bookkeeper asks Marketer for pricing
                         context before recommending an ROI move. Both
                         sides logged to db.agent_dialogues.

All three persist a trace in `db.agent_dialogues` so the UI can show the
real graph of who called whom and why. This is what makes the AI company
behave as a company instead of 7 isolated chat windows.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.inter_agent")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log_dialogue(
    *,
    kind: str,                 # delegate | escalate | ask
    from_agent: str,
    to_agent: str,
    topic: str,
    request: str,
    response: str,
    company_id: Optional[str],
    user_id: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    doc_id = str(uuid.uuid4())
    doc = {
        "id":         doc_id,
        "kind":       kind,
        "from_agent": from_agent,
        "to_agent":   to_agent,
        "topic":      topic[:200],
        "request":    request[:4000],
        "response":   response[:6000],
        "company_id": company_id,
        "user_id":    user_id,
        "created_at": _now(),
        **(extra or {}),
    }
    try:
        await get_db().agent_dialogues.insert_one(doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("agent_dialogues insert failed: %s", e)
    return doc_id


# =====================================================================
# delegate_to_agent  (Hermes → subordinate)
# =====================================================================

async def delegate_to_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    """Hermes (CEO) delegates a concrete task to one of his subordinates.

    args:
        agent_id   — required, one of: hr_mentor / client_manager /
                     project_coord / analyst / bookkeeper / marketer /
                     compliance
        task       — required, concrete instruction in plain language
        context    — optional extra context block
        company_id — propagated from caller
        user_id    — propagated from caller
        from_agent — who delegates (defaults to hermes)
    """
    agent_id = (args.get("agent_id") or "").strip().lower()
    task = (args.get("task") or args.get("instruction") or "").strip()
    if not agent_id or not task:
        return {"ok": False, "error": "agent_id and task are required"}

    # Only Hermes can delegate (chain-of-command).
    from_agent = (args.get("from_agent") or "hermes").strip().lower()
    if from_agent != "hermes":
        return {
            "ok": False,
            "error": "delegate_to_agent is reserved for Hermes (CEO). "
                     "Use escalate_to_hermes or ask_colleague instead.",
        }

    # Lazy import to avoid circular deps with agents.personas.
    from agents.personas import run_persona, PERSONAS

    if agent_id not in PERSONAS or agent_id == "hermes":
        return {"ok": False,
                "error": f"unknown subordinate: {agent_id}",
                "available": [k for k in PERSONAS if k != "hermes"]}

    context_block = (args.get("context") or "").strip()
    user_message = task if not context_block else f"{task}\n\n## Контекст от Hermes (CEO)\n{context_block}"

    company_id = args.get("company_id") or "default"
    user_id = args.get("user_id") or "hermes-delegation"

    try:
        result = await run_persona(
            persona_id=agent_id,
            message=user_message,
            company_id=company_id,
            user_id=user_id,
            plan_id="enterprise",   # Hermes always sees the full team
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("delegate_to_agent run_persona failed")
        return {"ok": False, "error": f"delegation_failed: {e}"}

    content = (result.get("content") or "").strip()
    dialog_id = await _log_dialogue(
        kind="delegate",
        from_agent=from_agent,
        to_agent=agent_id,
        topic=task[:200],
        request=user_message,
        response=content,
        company_id=company_id,
        user_id=user_id,
        extra={
            "confidence": result.get("confidence"),
            "tokens_total": result.get("tokens_total"),
            "tool_traces_count": len(result.get("tool_traces") or []),
        },
    )

    return {
        "ok": True,
        "dialog_id": dialog_id,
        "agent_id": agent_id,
        "agent_name": PERSONAS[agent_id]["name"],
        "task": task,
        "response": content,
        "confidence": result.get("confidence"),
        "tokens_total": result.get("tokens_total"),
    }


# =====================================================================
# escalate_to_hermes  (subordinate → CEO)
# =====================================================================

async def escalate_to_hermes(args: Dict[str, Any]) -> Dict[str, Any]:
    """A subordinate flags an issue that requires the CEO.

    args:
        reason     — required, why escalation is needed (1-2 sentences)
        evidence   — optional, supporting facts/numbers
        urgency    — low | medium | high | critical (default: medium)
        from_agent — id of escalating agent (required)
        question   — optional explicit question for Hermes
        company_id, user_id — propagated
    """
    reason = (args.get("reason") or "").strip()
    from_agent = (args.get("from_agent") or "").strip().lower()
    if not reason or not from_agent:
        return {"ok": False, "error": "reason and from_agent are required"}

    if from_agent == "hermes":
        return {"ok": False, "error": "hermes cannot escalate to himself"}

    urgency = (args.get("urgency") or "medium").lower()
    if urgency not in ("low", "medium", "high", "critical"):
        urgency = "medium"

    evidence = (args.get("evidence") or "").strip()
    question = (args.get("question") or "").strip()
    company_id = args.get("company_id") or "default"
    user_id = args.get("user_id") or "agent-escalation"

    db = get_db()
    escalation_id = str(uuid.uuid4())
    record = {
        "id":         escalation_id,
        "from_agent": from_agent,
        "reason":     reason[:2000],
        "evidence":   evidence[:4000],
        "urgency":    urgency,
        "status":     "open",
        "company_id": company_id,
        "user_id":    user_id,
        "created_at": _now(),
    }
    try:
        await db.escalations.insert_one(record)
    except Exception as e:  # noqa: BLE001
        logger.warning("escalations insert failed: %s", e)

    # Synchronously ask Hermes for a verdict.
    from agents.hermes import hermes_chat
    hermes_prompt_parts = [
        f"## ЭСКАЛАЦИЯ от `{from_agent}`",
        f"- Срочность: **{urgency.upper()}**",
        f"- Причина: {reason}",
    ]
    if evidence:
        hermes_prompt_parts.append(f"- Доказательства/факты:\n{evidence}")
    if question:
        hermes_prompt_parts.append(f"- Вопрос к тебе: {question}")
    hermes_prompt_parts.append(
        "\nКак CEO компании, вынеси короткий verdict: что делать дальше, "
        "кто owner, какой deadline. Если нужно — делегируй другому агенту "
        "через `delegate_to_agent`. Если ситуация требует человека — "
        "честно так и скажи."
    )
    hermes_msg = "\n".join(hermes_prompt_parts)

    try:
        verdict = await hermes_chat(
            messages=[{"role": "user", "content": hermes_msg}],
            company_id=company_id,
            user_id=user_id,
            mode="operational",
            autonomy_level="assistant",
        )
        verdict_text = (verdict.get("content") or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.exception("hermes verdict on escalation failed")
        verdict_text = f"(Hermes недоступен прямо сейчас: {e})"
        verdict = {}

    # Update escalation with verdict
    try:
        await db.escalations.update_one(
            {"id": escalation_id},
            {"$set": {
                "hermes_verdict": verdict_text,
                "verdict_at": _now(),
                "status": "answered",
            }},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("escalations update failed: %s", e)

    dialog_id = await _log_dialogue(
        kind="escalate",
        from_agent=from_agent,
        to_agent="hermes",
        topic=reason[:200],
        request=hermes_msg,
        response=verdict_text,
        company_id=company_id,
        user_id=user_id,
        extra={
            "escalation_id": escalation_id,
            "urgency": urgency,
            "confidence": verdict.get("confidence"),
        },
    )

    return {
        "ok": True,
        "escalation_id": escalation_id,
        "dialog_id": dialog_id,
        "from_agent": from_agent,
        "to_agent": "hermes",
        "urgency": urgency,
        "hermes_verdict": verdict_text,
        "confidence": verdict.get("confidence"),
    }


# =====================================================================
# ask_colleague  (subordinate ↔ subordinate)
# =====================================================================

async def ask_colleague(args: Dict[str, Any]) -> Dict[str, Any]:
    """Peer-to-peer question between subordinates (no Hermes in the loop).

    args:
        from_agent — required, id of asker
        agent_id   — required, id of colleague to ask
        question   — required, concrete question
        context    — optional context
    """
    from_agent = (args.get("from_agent") or "").strip().lower()
    agent_id = (args.get("agent_id") or args.get("to_agent") or "").strip().lower()
    question = (args.get("question") or "").strip()
    if not from_agent or not agent_id or not question:
        return {"ok": False, "error": "from_agent, agent_id, question are required"}

    if from_agent == agent_id:
        return {"ok": False, "error": "cannot ask yourself"}

    from agents.personas import run_persona, PERSONAS
    if from_agent == "hermes":
        return {
            "ok": False,
            "error": "Hermes uses delegate_to_agent, not ask_colleague",
        }
    if agent_id not in PERSONAS or agent_id == "hermes":
        return {
            "ok": False,
            "error": f"unknown colleague: {agent_id}. "
                     f"Hermes is reached via escalate_to_hermes.",
        }

    context_block = (args.get("context") or "").strip()
    framed = (
        f"К тебе обратился коллега-агент `{from_agent}` с peer-to-peer вопросом. "
        f"Ответь как эксперт в своей зоне, коротко и по делу — без избыточных шапок.\n\n"
        f"## Вопрос\n{question}"
    )
    if context_block:
        framed += f"\n\n## Контекст от `{from_agent}`\n{context_block}"

    company_id = args.get("company_id") or "default"
    user_id = args.get("user_id") or f"peer-{from_agent}"

    try:
        result = await run_persona(
            persona_id=agent_id,
            message=framed,
            company_id=company_id,
            user_id=user_id,
            plan_id="enterprise",
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("ask_colleague run_persona failed")
        return {"ok": False, "error": f"ask_failed: {e}"}

    content = (result.get("content") or "").strip()
    dialog_id = await _log_dialogue(
        kind="ask",
        from_agent=from_agent,
        to_agent=agent_id,
        topic=question[:200],
        request=framed,
        response=content,
        company_id=company_id,
        user_id=user_id,
        extra={
            "confidence": result.get("confidence"),
            "tokens_total": result.get("tokens_total"),
        },
    )

    return {
        "ok": True,
        "dialog_id": dialog_id,
        "from_agent": from_agent,
        "to_agent": agent_id,
        "agent_name": PERSONAS[agent_id]["name"],
        "question": question,
        "response": content,
        "confidence": result.get("confidence"),
        "tokens_total": result.get("tokens_total"),
    }


# =====================================================================
# Read-side helpers
# =====================================================================

async def list_dialogues(limit: int = 50, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if agent_id:
        q = {"$or": [{"from_agent": agent_id}, {"to_agent": agent_id}]}
    cursor = db.agent_dialogues.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    return await cursor.to_list(length=int(limit))


async def list_escalations(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    cursor = db.escalations.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    return await cursor.to_list(length=int(limit))
