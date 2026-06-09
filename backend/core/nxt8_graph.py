import logging
from pathlib import Path
from typing import TypedDict, List, Dict, Any

import yaml

from langgraph.graph import StateGraph, END

from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.graph")


class AgentState(TypedDict, total=False):
    messages: List[Dict[str, Any]]
    skill_id: str
    company_id: str
    user_id: str
    session_id: str
    tokens_total: int
    confidence: float
    allowed_tools: List[str]


SKILLS_DIR = Path(__file__).parent.parent / "skills"


def load_skill(skill_id: str) -> tuple[str, dict]:
    """Загружает скилл, парсит YAML-шапку и возвращает (prompt_text, metadata)."""
    skill_path = SKILLS_DIR / f"{skill_id}.md"

    if not skill_path.exists():
        base_path = SKILLS_DIR / "_base.md"
        return base_path.read_text(encoding="utf-8") if base_path.exists() else "", {}

    content = skill_path.read_text(encoding="utf-8")

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_text = parts[1].strip()
            prompt_text = parts[2].strip()

            try:
                metadata = yaml.safe_load(yaml_text) or {}
            except yaml.YAMLError:
                metadata = {}

            base_path = SKILLS_DIR / "_base.md"
            base_text = base_path.read_text(encoding="utf-8") if base_path.exists() else ""
            final_prompt = f"{base_text}\n\n---\n\n{prompt_text}"
            return final_prompt, metadata

    return content, {}


async def execute_node(state: AgentState) -> Dict[str, Any]:
    skill_id = state.get("skill_id", "general")
    prompt_text, metadata = load_skill(skill_id)
    allowed_tools = metadata.get("allowed_tools", [])

    logger.info(
        "Skill '%s' loaded. Prompt length: %d chars (~%d tokens). Allowed tools: %s",
        skill_id,
        len(prompt_text),
        len(prompt_text) // 4,
        allowed_tools,
    )

    messages = [{"role": "system", "content": prompt_text}] + state.get("messages", [])

    ds = get_deepseek()
    response = await ds.chat(
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        request_logprobs=True,
    )

    return {
        "messages": [{"role": "assistant", "content": response.get("content", "")}],
        "tokens_total": response.get("tokens_total", 0),
        "confidence": response.get("confidence", 0.7),
        "allowed_tools": allowed_tools,
    }


workflow = StateGraph(AgentState)
workflow.add_node("execute", execute_node)
workflow.set_entry_point("execute")
workflow.add_edge("execute", END)

try:
    from langgraph.checkpoint.memory import MemorySaver

    memory = MemorySaver()
    nxt8_graph = workflow.compile(checkpointer=memory)
except ImportError:
    nxt8_graph = workflow.compile()
