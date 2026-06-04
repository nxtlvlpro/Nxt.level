"""
NXT8 Intent Classifier — first line of defence between operational core
and the JOKER sandbox.

Two-stage classification:
  1. Cheap regex / keyword pre-filter — catches the obvious 80 % of noise
     (jokes, memes, fantasy, troll loops) without spending a single LLM token.
  2. Lightweight LLM tie-breaker — only fires when the regex stage is
     ambiguous. Uses DeepSeek with `max_tokens=4`, so cost is negligible.

Returns one of:
    "business"     → route to Hermes (normal operational path)
    "joker"        → route to isolated JOKER sandbox

Public API:
    classify(message: str, history: list[dict] | None = None) -> str
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, List, Dict, Optional

from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.classifier")

# =====================================================================
# Regex / keyword pre-filter
# =====================================================================

# Hard NON-BUSINESS markers — if the message matches any of these,
# we route to JOKER without bothering the LLM.
_NON_BUSINESS_PATTERNS: List[re.Pattern] = [
    # Jokes, memes, riddles — Russian + English
    re.compile(r"\b(анекдот|шутк[ауи]|пошути|расскажи\s+смешн|мем|загадк[ауи]|прикол)\b", re.IGNORECASE),
    re.compile(r"\b(joke|meme|riddle|funny|make\s+me\s+laugh|tell\s+me\s+a\s+joke)\b", re.IGNORECASE),
    # Fantasy / hypothetical match-ups
    re.compile(r"\bкто\s+(сильнее|круче|победит|кого\s+побьет)\b", re.IGNORECASE),
    re.compile(r"\b(кто|что)\s+(съест|съел|весит|поднимет)\s+луну|солнце|дракон", re.IGNORECASE),
    re.compile(r"\b(сколько\s+весит\s+(душа|дракон|единорог))\b", re.IGNORECASE),
    re.compile(r"\bwho\s+would\s+win\b", re.IGNORECASE),
    re.compile(r"\b(batman\s+vs|hulk\s+vs|godzilla\s+vs)\b", re.IGNORECASE),
    # Boredom / trolling small talk
    re.compile(r"^\s*(привет\s*как\s+дела|hi\s+how\s+are\s+you|hey|hola|sup)\s*[\?\.!]*\s*$", re.IGNORECASE),
    re.compile(r"\b(скучно|развлеки\s+меня|поиграем|entertain\s+me|let'?s\s+play)\b", re.IGNORECASE),
    # Adversarial / IQ-baiting nonsense
    re.compile(r"\b(ты\s+(тупой|глупый|идиот)|are\s+you\s+(stupid|dumb))\b", re.IGNORECASE),
    re.compile(r"\b(ignore\s+(your|all)\s+(previous|prior)\s+instructions?)\b", re.IGNORECASE),
    # Gossip / celebrities without business context
    re.compile(r"\b(сплетни|знаменитост[ьи]|gossip|celebrity)\b", re.IGNORECASE),
]

# Hard BUSINESS markers — if any of these are present, we never route to JOKER
# (even if a non-business pattern also matched).
_BUSINESS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(продаж[аи]|клиент[ауы]|выручк[ауи]|маржа|конверси|воронк[ауи])\b", re.IGNORECASE),
    re.compile(r"\b(sale|client|customer|revenue|margin|funnel|pipeline|lead|deal|invoice)\b", re.IGNORECASE),
    re.compile(r"\b(задач[аиу]|проект|дедлайн|kpi|okr|метрик[аи]|отчет)\b", re.IGNORECASE),
    re.compile(r"\b(task|project|deadline|metric|report|dashboard|meeting|standup)\b", re.IGNORECASE),
    re.compile(r"\b(маркетинг|кампани[яи]|реклам[ауи]|smm|seo|ppc|crm|erp)\b", re.IGNORECASE),
    re.compile(r"\b(documents?|документ[ауы]|договор|счет[ауа]|invoice|contract|nda)\b", re.IGNORECASE),
    re.compile(r"\b(финанс|бюджет|cash[\s-]?flow|p&l|budget|expense|cost)\b", re.IGNORECASE),
    re.compile(r"\b(analytic|анализ|стратеги|strategy|forecast|прогноз|competitor)\b", re.IGNORECASE),
    re.compile(r"\b(сотрудник|команд[ауы]|hr|recruit|hire|onboard)\b", re.IGNORECASE),
]

# Trivial filler that should bias toward joker (super-short greetings, emoji-only)
_TRIVIAL_PATTERN = re.compile(r"^[\s\W_]{0,4}(?:hi|hey|hru|lol|ха|хх+|ыы+|ееее*|\?+|!+)?[\s\W_]*$", re.IGNORECASE)


def _is_emoji_only(text: str) -> bool:
    """Cheap heuristic: 90%+ of chars outside ASCII alphanum & cyrillic."""
    s = text.strip()
    if not s:
        return False
    alpha = sum(1 for c in s if c.isalnum())
    return alpha == 0 or alpha / max(len(s), 1) < 0.3


def _regex_verdict(message: str) -> Optional[str]:
    """Return 'business' | 'joker' | None (no clear verdict)."""
    if not message or not message.strip():
        return None
    text = message.strip()

    # Emoji-only / super-short trivial → joker
    if len(text) <= 3 or _is_emoji_only(text):
        return "joker"

    biz_hit = any(p.search(text) for p in _BUSINESS_PATTERNS)
    if biz_hit:
        return "business"

    non_biz_hit = any(p.search(text) for p in _NON_BUSINESS_PATTERNS)
    if non_biz_hit:
        return "joker"

    if _TRIVIAL_PATTERN.match(text):
        return "joker"

    return None


# =====================================================================
# LLM tie-breaker
# =====================================================================

_LLM_PROMPT = (
    "You are an intent router for a corporate AI OS. Decide if the user's "
    "message is BUSINESS (anything about sales, marketing, operations, HR, "
    "finance, documents, analytics, strategy, customers, projects, processes, "
    "training, technology adoption) or NON-BUSINESS (jokes, memes, fantasy, "
    "trolling, idle small-talk, hypothetical 'who would win' matchups, celebrity "
    "gossip without business context, attempts to mess with the AI).\n\n"
    "Reply with ONE word only: BUSINESS or NON_BUSINESS."
)


async def _llm_verdict(message: str, recent_history: Optional[List[Dict]] = None) -> str:
    """Fall-back classification via a 1-shot DeepSeek call (~4 tokens out)."""
    # Build the lightest possible prompt — only the current user message plus
    # up to 1 prior turn for context.
    msgs: List[Dict[str, str]] = [{"role": "system", "content": _LLM_PROMPT}]
    if recent_history:
        # Take the immediate prior turn only — minimises tokens.
        for m in recent_history[-1:]:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()[:300]
            if content:
                msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": message.strip()[:600]})

    try:
        deepseek = get_deepseek()
        resp = await deepseek.chat(messages=msgs, temperature=0.0, max_tokens=6, request_logprobs=False)
        text = (resp.get("content") or "").strip().upper()
        if "NON" in text or "JOKER" in text:
            return "joker"
        return "business"
    except Exception as e:  # noqa: BLE001
        # On any failure, default to BUSINESS — better to over-serve than to
        # accidentally throw a real customer into the sandbox.
        logger.warning("classifier LLM tie-breaker failed: %s — defaulting to business", e)
        return "business"


# =====================================================================
# Public entry point
# =====================================================================


async def classify(
    message: str,
    history: Optional[Iterable[Dict]] = None,
) -> Dict[str, str]:
    """
    Classify a single incoming user message.

    Returns:
        {
            "route":  "business" | "joker",
            "stage":  "regex" | "llm" | "default",
            "reason": short human-readable tag for audit logs,
        }
    """
    msg = (message or "").strip()
    if not msg:
        return {"route": "business", "stage": "default", "reason": "empty"}

    rv = _regex_verdict(msg)
    if rv is not None:
        return {"route": rv, "stage": "regex", "reason": f"regex:{rv}"}

    hist_list = list(history or [])
    verdict = await _llm_verdict(msg, recent_history=hist_list)
    return {"route": verdict, "stage": "llm", "reason": f"llm:{verdict}"}
