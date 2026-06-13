"""Central registry for prompt-policy fragments and coverage."""

from __future__ import annotations

from agents.prompt_fragments import (
    HERMES_ANTI_HALLUCINATION_FRAGMENT,
    RESPONSE_SAFETY_RULES_FRAGMENT,
)

PERSONA_RESPONSE_SAFETY_TARGETS = (
    "bookkeeper",
    "analyst",
    "marketer",
    "project_coord",
    "hr_mentor",
    "compliance",
    "client_manager",
    "hermes",
)

PERSONA_PROMPT_FRAGMENT_REGISTRY = {
    pid: (RESPONSE_SAFETY_RULES_FRAGMENT,)
    for pid in PERSONA_RESPONSE_SAFETY_TARGETS
}

SKILL_PROMPT_FRAGMENT_REGISTRY = {
    "hermes": (HERMES_ANTI_HALLUCINATION_FRAGMENT,),
}