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

    # Cheap-bias signals.
    if any(p.search(blob) for p in _CHEAP_PATTERNS):
        _bump(MODEL_CHEAP)
        return MODEL_CHEAP

    # Reasoner-bias signals.
    reasoner_hits = sum(1 for p in _REASONING_PATTERNS if p.search(blob))

    # Long body alone is *not* enough — needs at least 1 reasoning signal.
    if reasoner_hits >= 2 or (reasoner_hits >= 1 and body_len >= HEAVY_CONTEXT_CHARS):
        _bump(MODEL_REASONER)
        return MODEL_REASONER

    # Intent hints from callers.
    if intent in {"planner", "deep_reasoning", "validation"} and reasoner_hits >= 1:
        _bump(MODEL_REASONER)
        return MODEL_REASONER

    _bump(MODEL_CHEAP)
    return MODEL_CHEAP
