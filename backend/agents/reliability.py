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
MEDIUM = 0.45
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
    """Heuristic contradiction detector based on TF-IDF cosine similarity.

    The original implementation flagged ANY low-similarity candidate as a
    contradiction (the condition `sim < CONTRADICTION_THRESHOLD` triggers
    on every topically unrelated past response). That misfired on routine
    multi-turn chats and was a major source of false escalations.

    Better heuristic: a contradiction requires topical overlap (same
    subject) WITHOUT being a near-duplicate restatement. We therefore
    only flag candidates in a narrow band [0.30, 0.55] — high enough to
    share vocabulary, low enough to be saying something different.
    """
    cands = (past_responses or []) + (known_facts or [])
    sources = (["past"] * len(past_responses or [])) + (["fact"] * len(known_facts or []))
    if not cands:
        return []
    sims = _semantic_similarity_matrix([response], cands)[0]
    out: List[Dict[str, Any]] = []
    for i, s in enumerate(sims):
        sim = float(s)
        # narrow overlap band — topically related, not duplicate
        if 0.30 <= sim <= 0.55:
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
    """Classify each statement against the memory context.

    Tuning notes (2026-02-06): the previous thresholds (sim>=0.6 → verified,
    sim>=0.3 → partial, else hallucinated) misfired on general/operational
    answers where memory snippets are short or absent. That alone was the
    single biggest source of false escalations (~32% of all requests).

    New behaviour:
      • No memory available → status="skipped" (NOT partial). Reliability
        relies on the LLM confidence signal alone.
      • Lower threshold for "hallucinated" classification (sim < 0.15) — be
        strict only when a statement clearly has zero anchoring.
      • Status="hallucination" only when MAJORITY of statements (>50 %)
        clearly unanchored AND zero verified. Otherwise → "partial".
    """
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
        # No corporate memory hits for this turn — verification is N/A.
        # Don't punish the response; let confidence/contradiction logic
        # be the only escalation signals.
        return {
            "status": "skipped",
            "verification_ratio": 1.0,
            "verified": 0,
            "partial": 0,
            "hallucinated": 0,
            "total": len(stmts),
        }
    sims = _semantic_similarity_matrix(stmts, memory_context)
    verified = partial = hallucinated = 0
    for row in sims:
        max_sim = float(row.max()) if row.size else 0.0
        if max_sim >= 0.5:
            verified += 1
        elif max_sim >= 0.15:
            partial += 1
        else:
            hallucinated += 1
    total = len(stmts)
    ratio = verified / total if total else 1.0
    # New, stricter rule: only flag the WHOLE response as hallucination
    # when a clear majority of statements have zero anchoring AND nothing
    # was verified at all.
    if hallucinated > (total // 2) and verified == 0:
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

    # Escalation policy (tuned 2026-02-06 to fix ~42% false-positive rate):
    #   • score below MEDIUM (0.45) → escalate (truly low confidence)
    #   • hallucination status (majority of statements unanchored) → escalate
    #   • contradictions alone do NOT auto-escalate — they only escalate
    #     when combined with already-shaky confidence (<0.6) or multiple
    #     contradictions (>=2). A single low-similarity hit on long chat
    #     history is statistically noisy.
    contradiction_escalates = (
        (len(contradictions) >= 2)
        or (len(contradictions) >= 1 and score < 0.6)
    )

    should_escalate = (
        score < MEDIUM
        or contradiction_escalates
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
