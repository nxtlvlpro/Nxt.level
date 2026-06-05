"""Tests for the AI-Mentor module (Iteration 2)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agents import ai_mentor as aim
from core.db import get_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------
# Grade detection
# ---------------------------------------------------------------------


def test_grade_novice_short_beggar() -> None:
    msgs = ["сделай за меня описание", "пиши", "ну давай"]
    assert aim.compute_ai_grade(msgs) <= 1


def test_grade_specialist_with_context_markers() -> None:
    msgs = [
        "Роль: маркетолог B2B SaaS. Задача: написать email-серию для тёплых лидов.\n"
        "Контекст: продукт CRM, клиенты — малый бизнес.\n"
        "Формат: 3 письма с CTA.",
        "Что нужно улучшить в моём запросе? Я указал роль и формат, но не уверен в контексте.",
    ]
    g = aim.compute_ai_grade(msgs)
    assert 2 <= g <= 4


def test_grade_advanced_jargon_heavy() -> None:
    msgs = [
        "Хочу сделать few-shot pipeline с 3 примерами входа/выхода. JSON schema: "
        "{type:string, fields:[...]}. Output должен валидироваться pydantic-моделью.",
        "Подскажи как организовать chain-of-thought reasoning для классификации "
        "обращений с использованием role-play в system prompt.",
        "Какая temperature оптимальна для structured JSON output и можно ли "
        "использовать context window полнее через RAG поверх MemPalace?",
    ]
    assert aim.compute_ai_grade(msgs) >= 4


def test_grade_empty_messages() -> None:
    assert aim.compute_ai_grade([]) == 0
    assert aim.compute_ai_grade(["", "  ", None]) == 0


# ---------------------------------------------------------------------
# PII guard
# ---------------------------------------------------------------------


def test_detect_pii_email() -> None:
    assert "email" in aim.detect_pii("Свяжись с client@acme.com")


def test_detect_pii_phone() -> None:
    assert "phone" in aim.detect_pii("Телефон клиента: +7 925 123 45 67")


def test_detect_pii_api_key() -> None:
    assert "api_key" in aim.detect_pii("ключ sk-abcdefghijklmnopqrstuvwx")


def test_detect_pii_clean_text() -> None:
    assert aim.detect_pii("Расскажи про маркетинг для SaaS") == []


# ---------------------------------------------------------------------
# Profile storage / point awarding / level-up
# ---------------------------------------------------------------------


def _mk_ids() -> tuple[str, str]:
    return f"user_test_{uuid.uuid4().hex[:8]}", f"tenant_test_{uuid.uuid4().hex[:8]}"


def test_get_profile_creates_default() -> None:
    uid, cid = _mk_ids()
    try:
        p = _run(aim.get_profile(uid, cid))
        assert p["ai_grade"] == 0
        assert p["skill_points"] == 0
        assert p["patterns_used"] == []
    finally:
        _run(get_db().user_profiles.delete_many({"user_id": uid}))


def test_award_points_increments_and_records_pattern() -> None:
    uid, cid = _mk_ids()
    try:
        r1 = _run(aim.award_points(uid, cid, "added_context", 5))
        assert r1["skill_points"] == 5
        assert "added_context" in r1["patterns_used"]
        assert r1["leveled_up"] is False

        r2 = _run(aim.award_points(uid, cid, "role_task_format", 10))
        assert r2["skill_points"] == 15
        assert set(r2["patterns_used"]) >= {"added_context", "role_task_format"}
    finally:
        _run(get_db().user_profiles.delete_many({"user_id": uid}))


def test_level_up_at_50_points() -> None:
    uid, cid = _mk_ids()
    try:
        r1 = _run(aim.award_points(uid, cid, "added_context", 45))
        assert r1["ai_grade"] == 0
        r2 = _run(aim.award_points(uid, cid, "added_context", 10))
        assert r2["ai_grade"] == 1
        assert r2["leveled_up"] is True
    finally:
        _run(get_db().user_profiles.delete_many({"user_id": uid}))


def test_level_thresholds_cumulative() -> None:
    uid, cid = _mk_ids()
    try:
        # Jump straight to 800 = level 5
        r = _run(aim.award_points(uid, cid, "self_used_pattern", 800))
        assert r["ai_grade"] == 5
        assert r["leveled_up"] is True
        # Can't go above 5
        r2 = _run(aim.award_points(uid, cid, "self_used_pattern", 100))
        assert r2["ai_grade"] == 5
    finally:
        _run(get_db().user_profiles.delete_many({"user_id": uid}))


# ---------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------


def test_prompt_level_0_uses_simple_language() -> None:
    p = aim.build_mentor_prompt(0)
    assert "шаблон" in p.lower() or "[ЗАПОЛНИТЬ]" in p
    assert "один" in p.lower() and "вопрос" in p.lower()
    # No advanced jargon in level-0 prompt body
    assert "few-shot" not in p.lower() or "не говори" in p.lower()


def test_prompt_level_4_uses_technical_terms() -> None:
    p = aim.build_mentor_prompt(4)
    assert "few-shot" in p.lower()
    assert "json" in p.lower() or "schema" in p.lower()


def test_prompt_includes_profile_summary_when_given() -> None:
    profile = {
        "ai_grade": 2, "skill_points": 200,
        "patterns_used": ["added_context", "role_task_format"],
    }
    p = aim.build_mentor_prompt(2, profile=profile)
    assert "уровень=2" in p
    assert "200" in p
    assert "added_context" in p


# ---------------------------------------------------------------------
# Skill block fetcher
# ---------------------------------------------------------------------


def test_build_user_skill_block_returns_human_text() -> None:
    uid, cid = _mk_ids()
    try:
        _run(aim.award_points(uid, cid, "added_context", 25))
        block = _run(aim.build_user_skill_block(uid, cid))
        assert "AI-уровень" in block
        assert "Очки" in block
    finally:
        _run(get_db().user_profiles.delete_many({"user_id": uid}))


def test_points_to_next_level() -> None:
    assert aim.points_to_next_level({"ai_grade": 0, "skill_points": 10}) == 40
    assert aim.points_to_next_level({"ai_grade": 1, "skill_points": 60}) == 90
    assert aim.points_to_next_level({"ai_grade": 5, "skill_points": 999}) is None
