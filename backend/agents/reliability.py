"""
Reliability Engine for NXT8 (Module 5).

Three layers per ТЗ:
1. Confidence scoring  — composite of (deepseek_logprob, source, evidence, consistency)
2. Contradiction detection — TF-IDF cosine vs past responses / known facts
3. Hallucination prevention — per-statement verification vs memory context

Thresholds:
- score >= 0.8  → HIGH
- 0.5 <= score < 0.8 → MEDIUM (flag low_confidence)
- score < 0.5  → LOW (escalate to human)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("nxt8.reliability")

HIGH = 0.8
MEDIUM = 0.5
SIMILARITY_THRESHOLD = 0.85
CONTRADICTION_THRESHOLD = 0.30


SOURCE_TRUST = {
    "deepseek": 0.95,
    "corporate_memory": 0.90,
    "user_input": 0.85,
    "external_api": 0.75,
    "unknown": 0.50,
}


@dataclass
class ReliabilityResult:
    score: float
    level: str
    should_escalate: bool
    has_contradiction: bool
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    verification_status: str = "verified"
    verification_ratio: float = 1.0
    signals: Dict[str, float] = field(default_factory=dict)


def _semantic_similarity_matrix(a: List[str], b: List[str]) -> np.ndarray:
    if not a or not b:
        return np.zeros((len(a), len(b)))
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), max_features=2048)
        all_docs = a + b
        m = vec.fit_transform(all_docs)
        sims = cosine_similarity(m[: len(a)], m[len(a) :])
        return sims
    except ValueError:
        return np.zeros((len(a), len(b)))


def _split_statements(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 10]


def _confidence_signals(
    deepseek_confidence: float,
    source: str,
    evidence_count: int,
    consistency: float,
) -> Dict[str, float]:
    return {
        "deepseek": max(0.0, min(1.0, deepseek_confidence)),
        "source": SOURCE_TRUST.get(source, 0.7),
        "evidence": max(0.0, min(1.0, evidence_count / 3.0)),
        "consistency": max(0.0, min(1.0, consistency)),
    }


def _weighted_score(signals: Dict[str, float]) -> float:
    weights = {"deepseek": 0.5, "source": 0.2, "evidence": 0.2, "consistency": 0.1}
    total = sum(weights.values())
    return sum(signals[k] * weights[k] for k in weights) / total


def _detect_contradictions(
    response: str,
    past_responses: List[str],
    known_facts: List[str],
) -> List[Dict[str, Any]]:
    cands = (past_responses or []) + (known_facts or [])
    sources = (["past"] * len(past_responses or [])) + (["fact"] * len(known_facts or []))
    if not cands:
        return []
    sims = _semantic_similarity_matrix([response], cands)[0]
    out: List[Dict[str, Any]] = []
    for i, s in enumerate(sims):
        sim = float(s)
        if SIMILARITY_THRESHOLD > sim and sim < CONTRADICTION_THRESHOLD:
            out.append(
                {
                    "type": sources[i],
                    "similarity": sim,
                    "snippet": cands[i][:200],
                }
            )
    return out


def _verify_against_memory(
    response: str, memory_context: List[str]
) -> Dict[str, Any]:
    stmts = _split_statements(response)
    if not stmts:
        return {
            "status": "verified",
            "verification_ratio": 1.0,
            "verified": 0,
            "partial": 0,
            "hallucinated": 0,
            "total": 0,
        }
    if not memory_context:
        # Without memory, mark partial — not hallucinated
        return {
            "status": "partial",
            "verification_ratio": 0.5,
            "verified": 0,
            "partial": len(stmts),
            "hallucinated": 0,
            "total": len(stmts),
        }
    sims = _semantic_similarity_matrix(stmts, memory_context)
    verified = partial = hallucinated = 0
    for row in sims:
        max_sim = float(row.max()) if row.size else 0.0
        if max_sim >= 0.6:
            verified += 1
        elif max_sim >= 0.3:
            partial += 1
        else:
            hallucinated += 1
    total = len(stmts)
    ratio = verified / total if total else 1.0
    if hallucinated > verified + partial:
        status = "hallucination"
    elif hallucinated > 0 and verified == 0:
        status = "hallucination"
    elif partial > verified:
        status = "partial"
    else:
        status = "verified"
    return {
        "status": status,
        "verification_ratio": ratio,
        "verified": verified,
        "partial": partial,
        "hallucinated": hallucinated,
        "total": total,
    }


def assess(
    response: str,
    deepseek_confidence: float,
    source: str = "deepseek",
    evidence_count: int = 1,
    past_responses: Optional[List[str]] = None,
    memory_context: Optional[List[str]] = None,
    known_facts: Optional[List[str]] = None,
) -> ReliabilityResult:
    past_responses = past_responses or []
    memory_context = memory_context or []
    known_facts = known_facts or []

    contradictions = _detect_contradictions(response, past_responses, known_facts)
    consistency = 1.0 - min(1.0, len(contradictions) / 5.0)

    signals = _confidence_signals(
        deepseek_confidence=deepseek_confidence,
        source=source,
        evidence_count=evidence_count,
        consistency=consistency,
    )
    score = _weighted_score(signals)

    if score >= HIGH:
        level = "high"
    elif score >= MEDIUM:
        level = "medium"
    else:
        level = "low"

    verification = _verify_against_memory(response, memory_context)

    should_escalate = (
        score < MEDIUM
        or len(contradictions) > 0
        or verification["status"] == "hallucination"
    )

    return ReliabilityResult(
        score=round(score, 4),
        level=level,
        should_escalate=bool(should_escalate),
        has_contradiction=bool(contradictions),
        contradictions=contradictions,
        verification_status=verification["status"],
        verification_ratio=round(verification["verification_ratio"], 4),
        signals={k: round(v, 4) for k, v in signals.items()},
    )
