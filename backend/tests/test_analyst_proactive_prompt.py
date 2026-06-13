from agents.personas import PERSONAS
from agents.persona_prompts import get_prompt


def test_analyst_system_prompt_has_proactive_block():
    text = PERSONAS["analyst"]["system_prompt"]
    assert "❗ ТЫ — ПРОАКТИВНЫЙ АНАЛИТИК" in text
    assert "Каждые 6 часов" in text
    assert "escalate_to_hermes" in text
    assert "evaluate_action_roi" in text


def test_analyst_deep_prompt_has_night_analyst_block():
    text = get_prompt("analyst")
    assert "ПРОАКТИВНЫЙ НОЧНОЙ АНАЛИТИК" in text
    assert "avg_confidence < 0.7" in text
    assert "mock_rate" in text
    assert "Предлагаю создать задачу на улучшение промпта [агент]" in text