"""
NXT8 LLM complexity router — picks `deepseek-chat` vs `deepseek-reasoner`
per-request via a free heuristic (no extra LLM call).

`deepseek-reasoner` (R1) is ~2× more expensive per token than
`deepseek-chat` (V3). We only route to it when the request actually
benefits from chain-of-thought reasoning. Everything else stays on the
cheaper, faster chat model.

The function is **stateless and synchronous** — safe to call from inside
any hot path (Hermes, Graph v2 planner, etc.) with zero latency overhead.

Telemetry: every routing decision is counted in an in-memory dict
exposed via `stats()` so we can ship a small `/api/llm/router-stats`
endpoint and watch the distribution.
"""

from __future__ import annotations

import logging
import re
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nxt8.complexity_router")

MODEL_CHEAP = "deepseek-chat"
MODEL_REASONER = "deepseek-reasoner"
ANALYTICAL_INTENTS = {"analyst", "bookkeeper"}
HARD_REASONER_INTENTS = {"analyst", "bookkeeper"}
INTENT_REASONER_HINTS = {"planner", "deep_reasoning", "validation", "analyst"}

# ---------------------------------------------------------------------
# Heuristic signals
# ---------------------------------------------------------------------

# Strong tokens that *almost always* indicate a reasoning task.
_REASONING_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(посчитай|вычисли|реши|докажи|оптимизируй|спланируй|проанализируй)\b", re.I),
    re.compile(r"\b(calculate|compute|solve|prove|optimi[sz]e|plan|analyze|analyse)\b", re.I),
    re.compile(r"\b(why\b|объясни\s+почему|step.by.step|пошагово|reasoning|chain.of.thought)\b", re.I),
    re.compile(r"\b(если.+то|если.+иначе|when.+then|trade.off|compare|сравни)\b", re.I),
    re.compile(r"\b(strategy|strategie|стратеги|архитектур|architecture|forecast|прогноз)\b", re.I),
    # Math / data signals
    re.compile(r"\b(\d{2,}\s*(?:%|процент|euro|usd|руб|rub))\b", re.I),
    re.compile(r"\b(sum|integral|equation|formula|регресси|корреляц)\b", re.I),
    # Code / debug signals — reasoner often produces cleaner code
    re.compile(r"\b(debug|trace|root\s+cause|почему\s+падает|stack\s*trace|exception|traceback)\b", re.I),
    re.compile(r"\b(algorithm|алгоритм|complexity|complexity|O\(\w+\))\b", re.I),
]

_ANALYST_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(mrr|arr|cac|ltv|arpu|aov|gmv|nps|roi|romi|roas)\b", re.I),
    re.compile(r"\b(churn|retention|cohort|funnel|conversion|payback|margin|burn|runway)\b", re.I),
    re.compile(r"\b(unit\s+economics|contribution\s+margin|take\s*rate|pricing|forecast|sensitivity)\b", re.I),
    re.compile(r"\b(a/?b\s*test|stat(istical)?\s+sig(nificance)?|p-?value|north\s*star)\b", re.I),
    re.compile(r"\b(sql|python|schema|query|debug|traceback|stack\s*trace|root\s*cause|refactor|architecture)\b", re.I),
    re.compile(r"\b(юнит-экономик|когорт|ретеншн|конверс|отток|маржин|выручк|прогноз|чувствительност)\b", re.I),
    re.compile(r"\b(ценообразован|a/b|статзначим|p-value|корнева(я|я причина)|sql|python|схем[аы])\b", re.I),
]

_NUMERIC_FRAGMENT_RE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?\b|[%$€₽]|\b(?:usd|eur|rub|руб|mr[r]?|arr|cac|ltv|roi)\b)",
    re.I,
)

# Tokens that signal a CHEAP task — fast chat, no reasoning needed.
_CHEAP_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*(привет|hi|hey|hello|спасибо|thanks|thank\s+you)\b", re.I),
    re.compile(r"\b(перефразируй|rephrase|переведи|translate|summari[sz]e|короче)\b", re.I),
    re.compile(r"\b(joke|анекдот|поздрав|congrat|приветств|greeting)\b", re.I),
]

# Heavy-context threshold — long combined message body usually means
# the task needs more thought.
HEAVY_CONTEXT_CHARS = 1500


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------

_STATS: Dict[str, int] = {
    MODEL_CHEAP: 0,
    MODEL_REASONER: 0,
    "force_cheap": 0,
    "force_reasoner": 0,
}
_STATS_LOCK = Lock()


def _bump(key: str) -> None:
    with _STATS_LOCK:
        _STATS[key] = _STATS.get(key, 0) + 1


def stats() -> Dict[str, Any]:
    with _STATS_LOCK:
        snapshot = dict(_STATS)
    total = (snapshot.get(MODEL_CHEAP, 0) + snapshot.get(MODEL_REASONER, 0)) or 1
    snapshot["reasoner_share_pct"] = round(
        100 * snapshot.get(MODEL_REASONER, 0) / total, 1
    )
    return snapshot


def reset_stats() -> None:
    with _STATS_LOCK:
        for k in _STATS:
            _STATS[k] = 0


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def pick_model(
    messages: List[Dict[str, Any]],
    *,
    force: Optional[str] = None,
    intent: str = "",
    role: str = "",
) -> str:
    """
    Decide which DeepSeek model should serve the current call.

    Args:
        messages:  the chat messages array about to be sent.
        force:     "cheap" | "reasoner" — bypass heuristic, lock the choice.
        intent:    optional one-word intent hint ("classifier", "planner", ...).
        role:      optional role of the caller for stats segmentation.

    Returns:
        Model identifier ready to drop into `deepseek.chat(model_override=...)`.
    """
    if force == "cheap":
        _bump("force_cheap")
        _bump(MODEL_CHEAP)
        return MODEL_CHEAP
    if force == "reasoner":
        _bump("force_reasoner")
        _bump(MODEL_REASONER)
        return MODEL_REASONER

    # Aggregate user content for inspection — ONLY user messages.
    # System prompts can be many KB with words like "анализ"/"план" that
    # would otherwise inflate the score for every Hermes call.
    blob = " ".join(
        (m.get("content") or "")[:3000]
        for m in (messages or [])
        if isinstance(m, dict) and m.get("role") == "user"
    ).strip()
    body_len = len(blob)
    intent_norm = (intent or "").strip().lower()
    # Hard override: Analytical roles ALWAYS need reasoning power.
    if intent_norm in HARD_REASONER_INTENTS:
        _bump(MODEL_REASONER)
        return MODEL_REASONER
    role_norm = (role or "").strip().lower()

    # Cheap-bias signals.
    if any(p.search(blob) for p in _CHEAP_PATTERNS):
        _bump(MODEL_CHEAP)
        return MODEL_CHEAP

    # Reasoner-bias signals.
    reasoner_hits = sum(1 for p in _REASONING_PATTERNS if p.search(blob))
    analyst_hits = sum(1 for p in _ANALYST_PATTERNS if p.search(blob))
    numeric_hits = len(_NUMERIC_FRAGMENT_RE.findall(blob))
    is_analytical_intent = intent_norm in ANALYTICAL_INTENTS or role_norm in ANALYTICAL_INTENTS

    score = reasoner_hits
    if analyst_hits:
        score += min(2, analyst_hits)
    if numeric_hits >= 3:
        score += 1
    if body_len >= HEAVY_CONTEXT_CHARS:
        score += 1
    if is_analytical_intent and (analyst_hits >= 1 or numeric_hits >= 2 or reasoner_hits >= 1):
        score += 1

    if is_analytical_intent and score >= 2:
        _bump(MODEL_REASONER)
        return MODEL_REASONER

    # Long body alone is *not* enough — needs at least 1 reasoning signal.
    if score >= 3 or (score >= 2 and body_len >= HEAVY_CONTEXT_CHARS):
        _bump(MODEL_REASONER)
        return MODEL_REASONER

    # Intent hints from callers.
    if intent_norm in INTENT_REASONER_HINTS and score >= 1:
        _bump(MODEL_REASONER)
        return MODEL_REASONER

    _bump(MODEL_CHEAP)
    return MODEL_CHEAP
