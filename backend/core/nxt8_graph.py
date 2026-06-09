import os
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, END

from core.deepseek import get_deepseek


class AgentState(TypedDict, total=False):
    messages: List[Dict[str, Any]]
    skill_id: str
    company_id: str
    user_id: str
    session_id: str
    tokens_total: int
    confidence: float


SKILLS_DIR = Path(__file__).parent.parent / "skills"


def load_skill_prompt(skill_id: str) -> str:
    """Динамически собирает системный промпт: Base Charter + Specific Skill."""
    base_path = SKILLS_DIR / "_base.md"
    skill_path = SKILLS_DIR / f"{skill_id}.md"

    base_content = base_path.read_text(encoding="utf-8") if base_path.exists() else ""
    skill_content = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""

    return f"{base_content}\n\n---\n\n{skill_content}"


async def execute_node(state: AgentState) -> Dict[str, Any]:
    """Единственный узел на данном этапе: собирает промпт и делает 1 вызов LLM."""
    skill_id = state.get("skill_id", "general")
    system_prompt = load_skill_prompt(skill_id)

    messages = [{"role": "system", "content": system_prompt}] + state.get("messages", [])

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
