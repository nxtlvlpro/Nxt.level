"""
Diagnostics Agent for NXT8.

Scans recent /api/chat audit records for:
- Contradictions: same intent, similar prompt, but cosine-divergent responses
- Low-confidence clusters: same topic repeatedly under threshold
- Repeated escalations: same intent escalating more than N times in window

Exposes:
- scan_contradictions(window=200, sim_threshold=0.45, divergence_threshold=0.3)
- summary() — high-level health: ratios, top noisy intents
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.db import get_db

logger = logging.getLogger("nxt8.diagnostics")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_vectorize(texts: List[str]):
    try:
        vec = TfidfVectorizer(max_features=2048, ngram_range=(1, 2))
        mat = vec.fit_transform(texts)
        return vec, mat
    except ValueError:
        return None, None


async def scan_contradictions(
    window: int = 200,
    sim_threshold: float = 0.45,
    divergence_threshold: float = 0.3,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Find pairs of recent requests with similar prompts but divergent responses.

    Returns {'count': N, 'contradictions': [{a, b, message_similarity, response_divergence, intent}]}.
    Persists each new contradiction to db.contradictions.
    """
    db = get_db()
    query: Dict[str, Any] = {}
    if company_id:
        query["company_id"] = company_id
    docs = await db.requests.find(
        query, {"_id": 0, "id": 1, "intent": 1, "message": 1, "response": 1,
             "confidence": 1, "session_id": 1, "created_at": 1}
    ).sort("created_at", -1).limit(window).to_list(length=window)

    if len(docs) < 2:
        return {"count": 0, "contradictions": [], "scanned": len(docs)}

    msgs = [d.get("message") or "" for d in docs]
    resps = [d.get("response") or "" for d in docs]

    m_vec, m_mat = _safe_vectorize(msgs)
    r_vec, r_mat = _safe_vectorize(resps)
    if m_mat is None or r_mat is None:
        return {"count": 0, "contradictions": [], "scanned": len(docs)}

    msg_sim = cosine_similarity(m_mat)
    rsp_sim = cosine_similarity(r_mat)

    findings: List[Dict[str, Any]] = []
    n = len(docs)
    for i in range(n):
        for j in range(i + 1, n):
            # only compare same intent
            if docs[i].get("intent") != docs[j].get("intent"):
                continue
            m_s = float(msg_sim[i, j])
            r_s = float(rsp_sim[i, j])
            if m_s >= sim_threshold and (m_s - r_s) >= divergence_threshold:
                findings.append({
                    "a_id": docs[i].get("id"),
                    "b_id": docs[j].get("id"),
                    "a_message": docs[i].get("message", "")[:160],
                    "b_message": docs[j].get("message", "")[:160],
                    "a_response": docs[i].get("response", "")[:240],
                    "b_response": docs[j].get("response", "")[:240],
                    "intent": docs[i].get("intent"),
                    "message_similarity": round(m_s, 3),
                    "response_similarity": round(r_s, 3),
                    "divergence": round(m_s - r_s, 3),
                    "a_created_at": docs[i].get("created_at"),
                    "b_created_at": docs[j].get("created_at"),
                })

    findings.sort(key=lambda x: x["divergence"], reverse=True)
    top = findings[:30]

    # persist new contradictions (idempotent on pair ids; use joined string to avoid multikey)
    for f in top:
        a = f["a_id"] or ""
        b = f["b_id"] or ""
        pair_key = "|".join(sorted([a, b]))
        await db.contradictions.update_one(
            {"pair_key": pair_key, "company_id": company_id},
            {"$set": {**f, "pair_key": pair_key, "company_id": company_id,
                      "detected_at": _now(), "id": str(uuid.uuid4())}},
            upsert=True,
        )

    return {"count": len(top), "contradictions": top, "scanned": len(docs)}


async def list_contradictions(
    limit: int = 30,
    company_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db = get_db()
    query: Dict[str, Any] = {}
    if company_id:
        query["company_id"] = company_id
    return await db.contradictions.find(
        query, {"_id": 0, "pair_key": 0}
    ).sort("detected_at", -1).to_list(length=limit)


async def summary(
    window: int = 200,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    db = get_db()
    query: Dict[str, Any] = {}
    if company_id:
        query["company_id"] = company_id
    docs = await db.requests.find(
        query, {"_id": 0, "intent": 1, "confidence": 1, "should_escalate": 1, "mock": 1}
    ).sort("created_at", -1).limit(window).to_list(length=window)

    if not docs:
        return {
            "scanned": 0,
            "avg_confidence": 0.0,
            "escalation_rate": 0.0,
            "mock_rate": 0.0,
            "noisy_intents": [],
        }

    n = len(docs)
    confs = [float(d.get("confidence") or 0) for d in docs]
    escalated = sum(1 for d in docs if d.get("should_escalate"))
    mocks = sum(1 for d in docs if d.get("mock"))

    by_intent: Dict[str, List[float]] = {}
    by_intent_escalation: Dict[str, int] = {}
    for d in docs:
        intent = d.get("intent") or "general"
        by_intent.setdefault(intent, []).append(float(d.get("confidence") or 0))
        if d.get("should_escalate"):
            by_intent_escalation[intent] = by_intent_escalation.get(intent, 0) + 1

    noisy = []
    for intent, vals in by_intent.items():
        if len(vals) < 2:
            continue
        avg = sum(vals) / len(vals)
        noisy.append({
            "intent": intent,
            "count": len(vals),
            "avg_confidence": round(avg, 3),
            "escalations": by_intent_escalation.get(intent, 0),
            "score": round((1 - avg) * 0.6 + (by_intent_escalation.get(intent, 0) / len(vals)) * 0.4, 3),
        })
    noisy.sort(key=lambda x: x["score"], reverse=True)

    return {
        "scanned": n,
        "avg_confidence": round(sum(confs) / n, 3),
        "escalation_rate": round(escalated / n, 3),
        "mock_rate": round(mocks / n, 3),
        "noisy_intents": noisy[:5],
        "generated_at": _now(),
    }
