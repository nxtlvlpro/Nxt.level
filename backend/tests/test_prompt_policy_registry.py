from agents.persona_prompts import get_prompt
from agents.personas import PERSONAS
from agents.prompt_fragments import HERMES_ANTI_HALLUCINATION_FRAGMENT, RESPONSE_SAFETY_RULES_FRAGMENT
from agents.prompt_policy_registry import (
    PERSONA_PROMPT_FRAGMENT_REGISTRY,
    PERSONA_RESPONSE_SAFETY_TARGETS,
    SKILL_PROMPT_FRAGMENT_REGISTRY,
)
from core.nxt8_graph import load_skill


def test_persona_registry_covers_client_manager_and_hermes():
    assert "client_manager" in PERSONA_RESPONSE_SAFETY_TARGETS
    assert "hermes" in PERSONA_RESPONSE_SAFETY_TARGETS
    assert PERSONA_PROMPT_FRAGMENT_REGISTRY["client_manager"] == (RESPONSE_SAFETY_RULES_FRAGMENT,)
    assert PERSONA_PROMPT_FRAGMENT_REGISTRY["hermes"] == (RESPONSE_SAFETY_RULES_FRAGMENT,)


def test_persona_registry_fragments_applied_runtime():
    for pid in PERSONA_RESPONSE_SAFETY_TARGETS:
        assert RESPONSE_SAFETY_RULES_FRAGMENT in PERSONAS[pid]["system_prompt"]
        assert RESPONSE_SAFETY_RULES_FRAGMENT in get_prompt(pid)


def test_skill_registry_applies_hermes_fragment():
    assert SKILL_PROMPT_FRAGMENT_REGISTRY["hermes"] == (HERMES_ANTI_HALLUCINATION_FRAGMENT,)
    prompt_text, _ = load_skill("hermes")
    assert HERMES_ANTI_HALLUCINATION_FRAGMENT in prompt_text