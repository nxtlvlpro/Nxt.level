"""
Channel binding registry.

A "binding" is the contract between an inbound channel and a target
agent. Each `(channel_id, intent_filter)` pair maps to exactly one
agent. Matching is **most-specific-first**: bindings with a longer
`intent_filter` regex (i.e. more constrained) win over wildcard ones.

Storage hierarchy (in this order):
  1. Built-in defaults  — `backend/data/channels.json`
  2. Runtime overrides  — MongoDB `db.channel_bindings`

Runtime overrides shadow built-ins so an operator can edit bindings
without redeploying. Reads first try Mongo, then fall back to the file.

Public surface:
    list_bindings()
    get_binding(channel_id, message_text=None)
    upsert_binding(binding)
    delete_binding(channel_id, intent_filter)
    invoke_agent_for_binding(binding, event)
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import ChannelBinding, InboundEvent, OutboundReply

logger = logging.getLogger("nxt8.channels.registry")

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "channels.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------
# Loading & persistence
# ---------------------------------------------------------------------


def _load_file_bindings() -> List[ChannelBinding]:
    if not os.path.exists(_DATA_PATH):
        return []
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out: List[ChannelBinding] = []
        for r in raw if isinstance(raw, list) else []:
            try:
                out.append(ChannelBinding(
                    channel_id=str(r["channel_id"]),
                    channel_kind=str(r.get("channel_kind", "webhook")),
                    agent=str(r.get("agent", "hermes")),
                    intent_filter=str(r.get("intent_filter", "")),
                    name=str(r.get("name", "")),
                    signing_secret=str(r.get("signing_secret", "")),
                    active=bool(r.get("active", True)),
                    created_at=str(r.get("created_at") or _now()),
                    updated_at=str(r.get("updated_at") or _now()),
                ))
            except KeyError as e:
                logger.warning("skipping malformed binding (%s): %s", e, r)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("failed to read %s: %s", _DATA_PATH, e)
        return []


async def _load_db_bindings() -> List[ChannelBinding]:
    from core.db import get_db
    db = get_db()
    out: List[ChannelBinding] = []
    try:
        async for r in db.channel_bindings.find({}):
            try:
                out.append(ChannelBinding(
                    channel_id=str(r["channel_id"]),
                    channel_kind=str(r.get("channel_kind", "webhook")),
                    agent=str(r.get("agent", "hermes")),
                    intent_filter=str(r.get("intent_filter", "")),
                    name=str(r.get("name", "")),
                    signing_secret=str(r.get("signing_secret", "")),
                    active=bool(r.get("active", True)),
                    created_at=str(r.get("created_at") or _now()),
                    updated_at=str(r.get("updated_at") or _now()),
                ))
            except Exception as e:  # noqa: BLE001
                logger.warning("skipping malformed db binding: %s", e)
    except Exception as e:  # noqa: BLE001
        logger.warning("channel_bindings read failed: %s", e)
    return out


async def list_bindings(include_inactive: bool = False) -> List[ChannelBinding]:
    """Merge built-in defaults with runtime overrides (DB wins per channel_id+filter)."""
    file_b = _load_file_bindings()
    db_b = await _load_db_bindings()
    by_key: Dict[str, ChannelBinding] = {}
    for b in file_b + db_b:  # db_b later → overrides
        by_key[f"{b.channel_id}|{b.intent_filter}"] = b
    result = list(by_key.values())
    if not include_inactive:
        result = [b for b in result if b.active]
    return result


async def get_binding(
    channel_id: str,
    message_text: Optional[str] = None,
) -> Optional[ChannelBinding]:
    """
    Resolve the most-specific-first binding for an incoming message.

    Tie-break order:
      1. Longer `intent_filter` regex wins (more specific).
      2. If two filters share length, prefer the one whose regex matches.
      3. Empty filter ("") is the wildcard — always last.
    """
    all_b = await list_bindings(include_inactive=False)
    candidates = [b for b in all_b if b.channel_id == channel_id]
    if not candidates:
        return None

    text = (message_text or "").strip()
    matched: List[ChannelBinding] = []
    wildcard: Optional[ChannelBinding] = None
    for b in candidates:
        if not b.intent_filter:
            wildcard = b if wildcard is None else wildcard
            continue
        try:
            if re.search(b.intent_filter, text, re.IGNORECASE):
                matched.append(b)
        except re.error as e:
            logger.warning("invalid regex in binding %s: %s", b.channel_id, e)
    if matched:
        matched.sort(key=lambda b: len(b.intent_filter), reverse=True)
        return matched[0]
    return wildcard


async def upsert_binding(binding: ChannelBinding) -> ChannelBinding:
    from core.db import get_db
    db = get_db()
    binding.updated_at = _now()
    if not binding.created_at:
        binding.created_at = binding.updated_at
    doc = {
        "channel_id": binding.channel_id,
        "channel_kind": binding.channel_kind,
        "agent": binding.agent,
        "intent_filter": binding.intent_filter,
        "name": binding.name,
        "signing_secret": binding.signing_secret,
        "active": binding.active,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }
    await db.channel_bindings.update_one(
        {"channel_id": binding.channel_id, "intent_filter": binding.intent_filter},
        {"$set": doc},
        upsert=True,
    )
    return binding


async def delete_binding(channel_id: str, intent_filter: str = "") -> int:
    from core.db import get_db
    db = get_db()
    res = await db.channel_bindings.delete_one(
        {"channel_id": channel_id, "intent_filter": intent_filter}
    )
    return res.deleted_count or 0


# ---------------------------------------------------------------------
# Agent dispatch
# ---------------------------------------------------------------------


async def invoke_agent_for_binding(
    binding: ChannelBinding,
    event: InboundEvent,
) -> OutboundReply:
    """
    Call the agent referenced by `binding.agent` and return a uniform
    `OutboundReply`. Supported agent targets:

        "hermes"              → unified Hermes COO (auto-routes through JOKER classifier)
        "joker"               → force-route into the JOKER sandbox
        "auto"                → alias of "hermes" (classifier decides)
        "persona:<persona_id>" → marketing persona endpoint
    """
    agent_target = (binding.agent or "hermes").strip()
    text = event.text or ""

    if agent_target == "joker":
        from agents import joker as _joker
        jr = await _joker.respond(
            message=text,
            session_id=event.session_id,
            user_id=event.external_user_id,
            lang=event.lang or "en",
        )
        return OutboundReply(
            text=jr.get("content", ""),
            agent="joker",
            routed_to="joker",
            tokens_total=jr.get("tokens_total", 0),
            confidence=0.5,
            request_id=jr.get("request_id"),
            extra={"downgraded": jr.get("downgraded", False)},
        )

    if agent_target.startswith("persona:"):
        persona_id = agent_target.split(":", 1)[1] or "hermes"
        try:
            from agents import personas as _p
            res = await _p.run_persona(
                persona_id=persona_id,
                message=text,
                user_id=event.external_user_id,
                company_id="default",
                session_id=event.session_id,
                # Channel webhooks are server-to-server — bypass user tariff gate.
                plan_id="enterprise",
            )
            if not res.get("success", True):
                logger.warning("persona %s rejected: %s", persona_id, res.get("error"))
            else:
                return OutboundReply(
                    text=(res.get("content") or res.get("text") or ""),
                    agent=f"persona:{persona_id}",
                    tokens_total=int(res.get("tokens_total") or 0),
                    confidence=float(res.get("confidence") or 0.7),
                    extra={"persona": persona_id},
                )
        except Exception as e:  # noqa: BLE001
            logger.exception("persona %s failed: %s", persona_id, e)
            # Fall through to hermes below.

    # Default: hermes (classifier inside hermes will silently divert
    # off-topic messages to JOKER without us having to do anything).
    from agents import hermes as _hermes
    res = await _hermes.hermes_chat(
        messages=[{"role": "user", "content": text}],
        company_id="default",
        user_id=event.external_user_id,
        mode="operational",
        autonomy_level="assistant",
        temperature=0.3,
    )
    return OutboundReply(
        text=(res.get("content") or ""),
        agent="hermes",
        routed_to=res.get("routed_to"),
        tokens_total=int(res.get("tokens_total") or 0),
        confidence=float(res.get("confidence") or 0.7),
        extra={
            "iterations": res.get("iterations"),
            "tool_calls": len(res.get("tool_calls") or []),
            "provider": res.get("provider"),
        },
    )
