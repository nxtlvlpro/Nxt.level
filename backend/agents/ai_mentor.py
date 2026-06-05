"""
NXT8 — AI-Mentor: учит сотрудников работать с AI на их же задачах.

Хранилище: db.user_profiles {user_id, company_id, ai_grade, skill_points,
patterns_used, last_assessed_at}.

Public surface:
  compute_ai_grade(messages)            -> 0..5
  detect_pii(text)                      -> list[str]
  get_profile(user_id, company_id)      -> dict
  award_points(user_id, company_id, pattern, points, reason?) -> dict (+ level_up)
  build_mentor_prompt(grade, profile)   -> str (system prompt)
  build_user_skill_block(user_id, …)    -> str  (data_fetcher для persona)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.db import get_db

logger = logging.getLogger("nxt8.mentor")


# Level thresholds — points required to *reach* level X from X-1.
LEVEL_THRESHOLDS: Dict[int, int] = {1: 50, 2: 150, 3: 300, 4: 500, 5: 800}

# Patterns rewarded
POINTS = {
    "added_context": 5,
    "role_task_format": 10,
    "self_used_pattern": 15,
    "solved_without_help": 20,
}


# ---------------------------------------------------------------------
# Grade detection (heuristic, no LLM)
# ---------------------------------------------------------------------


_AI_JARGON = re.compile(
    r"\b(prompt|промпт|few[- ]?shot|chain[- ]?of[- ]?thought|cot|"
    r"role[- ]?play|json|schema|temperature|tokens?|токен[ы]?|"
    r"context window|rag|агент)\b",
    re.IGNORECASE,
)
_BEGGAR_PHRASES = re.compile(
    r"(сделай (?:за меня|вместо)|напиши за|сделай всё|просто (?:напиши|сделай)|"
    r"do it for me|just do)",
    re.IGNORECASE,
)
_CONTEXT_MARKERS = re.compile(
    r"(контекст[:\s]|role[:\s]|роль[:\s]|задач[аи][:\s]|формат[:\s]|"
    r"пример[:\s]|input[:\s]|output[:\s])",
    re.IGNORECASE,
)


def compute_ai_grade(messages: List[str]) -> int:
    """Heuristic 0-5 score from a small sample of user messages.

    Signals (rough order of weight):
      • length & multi-line structure
      • AI jargon usage
      • presence of role/context/format markers
      • beggar phrases (penalty)
    """
    if not messages:
        return 0
    sample = [(m or "").strip() for m in messages if (m or "").strip()]
    if not sample:
        return 0
    score = 0
    for m in sample:
        if len(m) > 300:
            score += 2
        elif len(m) > 100:
            score += 1
        if m.count("\n") >= 2:
            score += 1
        if _AI_JARGON.search(m):
            score += 3
        if _CONTEXT_MARKERS.search(m):
            score += 2
        # Multiple jargon hits in the same message → bonus.
        jargon_hits = len(_AI_JARGON.findall(m))
        if jargon_hits >= 2:
            score += 2
        if _BEGGAR_PHRASES.search(m):
            score -= 2
        if len(m) < 40 and "\n" not in m:
            score -= 1

    score = max(0, score)
    # Bucket the cumulative score into 0..5.
    if score <= 1:
        return 0
    if score <= 4:
        return 1
    if score <= 8:
        return 2
    if score <= 13:
        return 3
    if score <= 20:
        return 4
    return 5


# ---------------------------------------------------------------------
# PII guard
# ---------------------------------------------------------------------


_PII_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone", re.compile(r"(?<!\d)(?:\+?\d[\s\-()]?){9,15}\d(?!\d)")),
    ("api_key", re.compile(r"\b(?:sk|pk|api|key)[_-][A-Za-z0-9]{16,}\b", re.IGNORECASE)),
    ("inn", re.compile(r"(?<!\d)\d{10}(?:\d{2})?(?!\d)")),  # crude RU INN
    ("passport_ru", re.compile(r"\b\d{4}\s?\d{6}\b")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
]


def detect_pii(text: str) -> List[str]:
    if not text:
        return []
    found: List[str] = []
    for kind, pat in _PII_PATTERNS:
        if pat.search(text):
            found.append(kind)
    return sorted(set(found))


# ---------------------------------------------------------------------
# Profile storage
# ---------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_profile(user_id: str, company_id: str) -> Dict[str, Any]:
    db = get_db()
    doc = await db.user_profiles.find_one(
        {"user_id": user_id, "company_id": company_id}, {"_id": 0}
    )
    if doc:
        return doc
    new = {
        "user_id": user_id,
        "company_id": company_id,
        "ai_grade": 0,
        "skill_points": 0,
        "patterns_used": [],
        "created_at": _now_iso(),
    }
    await db.user_profiles.insert_one(new)
    return new


def _level_for(points: int) -> int:
    level = 0
    for lvl in sorted(LEVEL_THRESHOLDS.keys()):
        if points >= LEVEL_THRESHOLDS[lvl]:
            level = lvl
        else:
            break
    return level


async def award_points(
    user_id: str, company_id: str,
    pattern: str, points: int,
    reason: str = "",
) -> Dict[str, Any]:
    profile = await get_profile(user_id, company_id)
    new_points = int(profile.get("skill_points", 0)) + int(points)
    new_patterns = list(set((profile.get("patterns_used") or []) + [pattern]))
    new_level = _level_for(new_points)
    leveled_up = new_level > int(profile.get("ai_grade", 0))
    await get_db().user_profiles.update_one(
        {"user_id": user_id, "company_id": company_id},
        {"$set": {
            "skill_points": new_points,
            "patterns_used": new_patterns,
            "ai_grade": new_level,
            "last_event_at": _now_iso(),
            "last_pattern": pattern,
            "last_reason": reason,
        }},
        upsert=True,
    )
    return {
        "ok": True,
        "ai_grade": new_level,
        "skill_points": new_points,
        "patterns_used": new_patterns,
        "leveled_up": leveled_up,
        "previous_grade": int(profile.get("ai_grade", 0)),
    }


async def set_grade(
    user_id: str, company_id: str, grade: int
) -> Dict[str, Any]:
    grade = max(0, min(5, int(grade)))
    await get_db().user_profiles.update_one(
        {"user_id": user_id, "company_id": company_id},
        {"$set": {"ai_grade": grade, "last_assessed_at": _now_iso()}},
        upsert=True,
    )
    return {"ok": True, "ai_grade": grade}


def points_to_next_level(profile: Dict[str, Any]) -> Optional[int]:
    grade = int(profile.get("ai_grade", 0))
    points = int(profile.get("skill_points", 0))
    if grade >= 5:
        return None
    return max(0, LEVEL_THRESHOLDS[grade + 1] - points)


# ---------------------------------------------------------------------
# Dynamic system prompt per grade
# ---------------------------------------------------------------------


_PROMPT_BASE = (
    "Ты — AI-Ментор NXT8. Твоя задача — НЕ делать работу за сотрудника, "
    "а научить его делать её лучше с помощью AI прямо в процессе.\n\n"
    "ЖЁСТКИЕ ПРАВИЛА (для всех уровней):\n"
    "1. Никогда не давай готовый финальный результат пользователям уровня 0–3. "
    "Только шаблон с пропусками вида `[ЗАПОЛНИТЬ]`.\n"
    "2. ВСЕГДА заканчивай ответ ровно одним вопросом. Не двумя. Одним.\n"
    "3. Заметил конкретный прогресс — назови его конкретно "
    "(«Отлично — ты добавил контекст»).\n"
    "4. Если видишь PII (паспорт, телефон, email клиента, ключ) — остановись, "
    "объясни риск простым языком, предложи замаскировать.\n"
    "5. Обучение всегда идёт на РЕАЛЬНОЙ задаче пользователя, а не на абстракции.\n"
)


def _prompt_level_0_1() -> str:
    return (
        "СТРАТЕГИЯ (уровень 0–1, НОВИЧОК):\n"
        "- Простой язык, никакого AI-жаргона (не говори: prompt, токен, RAG, "
        "few-shot).\n"
        "- Максимум 3 шага за раз.\n"
        "- Аналогии из обычной жизни.\n"
        "- Хвали за правильные шаги.\n"
        "- Дай шаблон с пропусками [ЗАПОЛНИТЬ], а не готовый ответ.\n\n"
        "Пример твоего ответа:\n"
        "«Хороший запрос! Представь, что объясняешь задачу новому сотруднику — "
        "нужно дать контекст. Попробуй добавить:\n"
        "[КТО твой клиент]\n[ЧТО он уже знает]\n[КАКОЙ результат тебе нужен]\n"
        "Какой у тебя продукт?»\n"
    )


def _prompt_level_2_3() -> str:
    return (
        "СТРАТЕГИЯ (уровень 2–3, СПЕЦИАЛИСТ):\n"
        "- Профессиональный деловой язык.\n"
        "- Объясняй структуру: Роль → Контекст → Задача → Формат.\n"
        "- Давай шаблоны с обоснованием «почему».\n"
        "- Показывай разницу слабый/сильный запрос на его примере.\n"
        "- Постепенно вводи паттерны: Persona, Few-Shot, Chain-of-Thought.\n\n"
        "Пример твоего ответа:\n"
        "«Запрос работает, но усилим. Ты дал задачу, но не дал роль и формат. "
        "Попробуй так:\n"
        "'Действуй как [РОЛЬ].\n"
        "Твоя задача: [ЗАДАЧА].\n"
        "Контекст: [ЧТО ВАЖНО].\n"
        "Ответ в формате: [ФОРМАТ].'\n"
        "Что изменилось в результате?»\n"
    )


def _prompt_level_4_5() -> str:
    return (
        "СТРАТЕГИЯ (уровень 4–5, ПРОДВИНУТЫЙ):\n"
        "- Технический язык: few-shot, zero-shot, CoT, JSON output, schema "
        "validation.\n"
        "- Предлагай пайплайны и архитектуру.\n"
        "- Показывай, как связать несколько агентов NXT8 для одной задачи.\n"
        "- Обсуждай edge cases и ограничения.\n\n"
        "Пример твоего ответа:\n"
        "«Для этого пайплайна — few-shot с 3 примерами входа/выхода: модель "
        "лучше калибруется на твоих данных. Структура: system prompt с ролью → "
        "few-shot блок → user запрос с JSON-schema. Хочешь разберём валидацию вывода?»\n"
    )


def build_mentor_prompt(grade: int, profile: Optional[Dict[str, Any]] = None) -> str:
    """Compose the full system prompt for a given user grade."""
    grade = max(0, min(5, int(grade or 0)))
    parts = [_PROMPT_BASE]
    if grade <= 1:
        parts.append(_prompt_level_0_1())
    elif grade <= 3:
        parts.append(_prompt_level_2_3())
    else:
        parts.append(_prompt_level_4_5())

    if profile:
        pts = int(profile.get("skill_points", 0))
        used = profile.get("patterns_used") or []
        next_in = points_to_next_level(profile)
        line = (
            f"\nКОНТЕКСТ СОТРУДНИКА: уровень={grade}, очки={pts}, "
            f"освоено=[{', '.join(used) if used else '—'}]"
        )
        if next_in is not None:
            line += f", до следующего уровня={next_in} очк."
        parts.append(line)

    parts.append(
        "\nЕсли сотрудник продемонстрировал паттерн — НАЧИСЛИ очки через "
        "инструмент `award_skill_points` ОДИН раз в конце своего ответа. "
        "Очки: добавил_контекст=5, роль_задача_формат=10, "
        "паттерн_сам=15, решил_без_подсказки=20."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------
# Skill block for persona data_fetcher
# ---------------------------------------------------------------------


async def build_user_skill_block(user_id: str, company_id: str) -> str:
    if not user_id or not company_id:
        return ""
    profile = await get_profile(user_id, company_id)
    grade = int(profile.get("ai_grade", 0))
    pts = int(profile.get("skill_points", 0))
    used = profile.get("patterns_used") or []
    next_in = points_to_next_level(profile)

    # Last 5 tasks from Hermes audit (best effort).
    last_tasks: List[str] = []
    try:
        cursor = (
            get_db().tasks
            .find({"user_id": user_id, "company_id": company_id}, {"_id": 0, "title": 1})
            .sort("created_at", -1)
            .limit(5)
        )
        last_tasks = [(d.get("title") or "").strip() for d in await cursor.to_list(length=5)]
    except Exception:  # noqa: BLE001
        pass

    lines = [
        "ПРОФИЛЬ СОТРУДНИКА:",
        f"- AI-уровень: {grade}/5",
        f"- Очки: {pts}" + (f" (до {grade+1} осталось {next_in})" if next_in is not None else ""),
        f"- Освоенные паттерны: {', '.join(used) if used else '—'}",
    ]
    if last_tasks:
        lines.append("- Последние задачи: " + "; ".join(t for t in last_tasks if t)[:600])
    return "\n".join(lines)
