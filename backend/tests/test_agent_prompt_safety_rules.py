from agents.personas import PERSONAS
from agents.persona_prompts import get_prompt
from agents.prompt_policy_registry import PERSONA_RESPONSE_SAFETY_TARGETS


TARGETS = list(PERSONA_RESPONSE_SAFETY_TARGETS)


def _assert_rules(text: str):
    assert "ПРАВИЛА ОТВЕТА" in text
    assert "Нет данных для этого расчёта" in text
    assert "web_search" in text
    assert "Approval Gate" in text
    assert "Предлагаю эскалировать это решение Гермесу — согласен?" in text


def test_target_system_prompts_have_safety_rules():
    for pid in TARGETS:
        _assert_rules(PERSONAS[pid]["system_prompt"])


def test_target_deep_prompts_have_safety_rules():
    for pid in TARGETS:
        _assert_rules(get_prompt(pid))
