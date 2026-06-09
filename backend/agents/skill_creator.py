"""
Skill Creator Agent for NXT8.

Watches the request audit log; when the same (intent, keyword-signature) pattern
fires ≥ N times with average confidence ≥ T, it auto-registers a Skill — a
reusable prompt template + recommended memory_type filter. Operators can
manually create / edit / disable skills too.

Stored in db.skills:
  {
    id, name, intent, signature_terms, prompt_template,
    memory_filter, hit_count, last_confidence_avg,
    auto_generated, enabled, created_at, updated_at
  }
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.db import TenantAwareCRUD, get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.skill_creator")

MIN_PATTERN_HITS = 3
MIN_AVG_CONFIDENCE = 0.75
STOP = set("""
а в во и на не но о об по при с со у я мы вы он она это что как где кто или для из от
the a an of and to in is it that this with for on at by from be are was were been have
has had do does did will would can could should какой какая какое какие что-то этом нашем
""".split())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signature(text: str, top: int = 4) -> List[str]:
    tokens = re.findall(r"[\wа-яёА-ЯЁ]{3,}", (text or "").lower())
    tokens = [t for t in tokens if t not in STOP and not t.isdigit()]
    if not tokens:
        return []
    most = Counter(tokens).most_common(top)
    return sorted(t for t, _ in most)


async def scan_and_register() -> Dict[str, Any]:
    """Look at recent requests, find recurring (intent, signature) patterns, register skills."""
    db = get_db()
    requests = TenantAwareCRUD(db.requests)
    skills = TenantAwareCRUD(db.skills)
    docs = await requests.find(
        {}, {"_id": 0, "intent": 1, "message": 1, "confidence": 1, "should_escalate": 1}
    ).sort("created_at", -1).limit(400).to_list(length=400)

    buckets: Dict[tuple, List[Dict[str, Any]]] = {}
    for d in docs:
        sig = tuple(_signature(d.get("message", "")))
        if not sig:
            continue
        key = (d.get("intent") or "general", sig)
        buckets.setdefault(key, []).append(d)

    created: List[Dict[str, Any]] = []
    for (intent, sig), items in buckets.items():
        if len(items) < MIN_PATTERN_HITS:
            continue
        confs = [float(x.get("confidence") or 0) for x in items]
        avg_conf = sum(confs) / len(confs)
        if avg_conf < MIN_AVG_CONFIDENCE:
            continue
        if any(x.get("should_escalate") for x in items):
            continue  # don't crystallise a problematic pattern

        sig_terms = list(sig)
        name = f"{intent}:{'+'.join(sig_terms[:3])}"

        # idempotent: skip if same intent+signature already exists
        existing = await skills.find_one({"intent": intent, "signature_terms": sig_terms},
                                            {"_id": 0})
        if existing:
            await skills.update_one(
                {"id": existing["id"]},
                {"$set": {
                    "hit_count": len(items),
                    "last_confidence_avg": round(avg_conf, 3),
                    "updated_at": _now(),
                }},
            )
            continue

        skill = {
            "id": str(uuid.uuid4()),
            "name": name,
            "intent": intent,
            "signature_terms": sig_terms,
            "prompt_template": (
                f"User is asking about: {', '.join(sig_terms)}. "
                f"Intent: {intent}. "
                "Use corporate memory tagged with relevant department. "
                "Reply concisely with verifiable facts and a confidence note."
            ),
            "memory_filter": {"type": "corporate"},
            "hit_count": len(items),
            "last_confidence_avg": round(avg_conf, 3),
            "auto_generated": True,
            "enabled": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await skills.insert_one(skill)
        # don't leak _id
        skill_clean = {k: v for k, v in skill.items() if k != "_id"}
        created.append(skill_clean)

    return {"created": len(created), "count": len(created), "skills": created}


async def list_skills(only_enabled: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
    q = {"enabled": True} if only_enabled else {}
    return await TenantAwareCRUD(get_db().skills).find(q, {"_id": 0}).sort("updated_at", -1).to_list(length=limit)


async def create_skill(payload: Dict[str, Any]) -> Dict[str, Any]:
    skills = TenantAwareCRUD(get_db().skills)
    skill = {
        "id": str(uuid.uuid4()),
        "name": payload.get("name") or f"manual:{uuid.uuid4().hex[:6]}",
        "intent": payload.get("intent") or "general",
        "signature_terms": payload.get("signature_terms") or [],
        "prompt_template": payload.get("prompt_template") or "Reply concisely.",
        "memory_filter": payload.get("memory_filter") or {},
        "hit_count": 0,
        "last_confidence_avg": 0.0,
        "auto_generated": False,
        "enabled": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await skills.insert_one(skill)
    return {k: v for k, v in skill.items() if k != "_id"}


async def toggle_skill(skill_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    res = await TenantAwareCRUD(get_db().skills).find_one_and_update(
        {"id": skill_id},
        {"$set": {"enabled": enabled, "updated_at": _now()}},
        return_document=True,
        projection={"_id": 0},
    )
    return res
