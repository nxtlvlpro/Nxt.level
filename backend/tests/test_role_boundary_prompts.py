from agents.personas import PERSONAS
from agents.persona_prompts import get_prompt


def test_client_manager_runtime_prompt_excludes_internal_coordination():
    text = PERSONAS["client_manager"]["system_prompt"]
    assert "взаимодействие с клиентами" in text
    assert "upsell" in text
    assert "Не занимайся внутренними проектами" in text
    assert "project_coord" in text


def test_project_coord_runtime_prompt_excludes_client_comms():
    text = PERSONAS["project_coord"]["system_prompt"]
    assert "внутренние задачи" in text
    assert "мосты между отделами" in text
    assert "Не пиши клиентам напрямую" in text
    assert "client_manager" in text


def test_deep_prompts_reflect_same_role_boundary():
    client_text = get_prompt("client_manager")
    project_text = get_prompt("project_coord")
    assert "Не занимайся внутренними проектами" in client_text
    assert "project_coord" in client_text
    assert "Не пиши клиентам напрямую" in project_text
    assert "client_manager" in project_text