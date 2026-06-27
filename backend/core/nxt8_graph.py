import json
import logging
import re
import uuid
from pathlib import Path
from typing import TypedDict, List, Dict, Any

import yaml

from langgraph.graph import StateGraph, END

from agents.hermes import HERMES_TOOLS
from agents.prompt_policy_registry import SKILL_PROMPT_FRAGMENT_REGISTRY
from core.access_guard import check_access
from core.complexity_router import pick_model
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
    iterations: int
    tool_counts: Dict[str, int]
    mock: bool


SKILLS_DIR = Path(__file__).parent.parent / "skills"
_TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\"tool\".*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)
MAX_ITERATIONS = 3


def _extract_tool_calls(content: str, allowed_tools: List[str]) -> List[Dict[str, Any]]:
    if not content:
        return []
    calls: List[Dict[str, Any]] = []
    for match in _TOOL_JSON_RE.findall(content):
        try:
            obj = json.loads(match)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("tool") in allowed_tools:
            calls.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "name": obj["tool"],
                    "args": obj.get("args") or {},
                }
            )
    return calls


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
            skill_fragments = "".join(SKILL_PROMPT_FRAGMENT_REGISTRY.get(skill_id, ()))
            final_prompt = f"{base_text}\n\n---\n\n{prompt_text}{skill_fragments}"
            return final_prompt, metadata

    return content, {}


async def execute_node(state: AgentState) -> Dict[str, Any]:
    skill_id = state.get("skill_id", "general")
    prompt_text, metadata = load_skill(skill_id)
    allowed_tools = list(metadata.get("allowed_tools") or [])
    iteration = state.get("iterations", 0) + 1

    logger.info(
        "Skill '%s' loaded. Prompt length: %d chars (~%d tokens). Allowed tools: %s. iteration=%d",
        skill_id,
        len(prompt_text),
        len(prompt_text) // 4,
        allowed_tools,
        iteration,
    )

    tool_instruction = ""
    if allowed_tools:
        tool_instruction = (
            "## TOOL CONTRACT\n"
            f"Разрешённые инструменты: {', '.join(allowed_tools)}\n"
            "Если для ответа нужен инструмент, СНАЧАЛА вызови его и НЕ притворяйся, что действие уже выполнено. "
            "Выводи вызов строго одним fenced JSON блоком:\n"
            "```json\n"
            '{"tool":"имя_инструмента","args":{...}}\n'
            "```\n"
            "Для HR Mentor: если пользователь просит начислить очки/подтвердить прогресс, обязательно используй `award_skill_points` перед финальным ответом.\n"
            "Для `award_skill_points` всегда передавай полный JSON: "
            '{"tool":"award_skill_points","args":{"pattern":"role_task_format","points":10,"reason":"..."}}\n'
            "После получения результата инструмента дай короткий финальный ответ обычным текстом."
        )

    messages = [{"role": "system", "content": prompt_text}]
    if tool_instruction:
        messages.append({"role": "system", "content": tool_instruction})
    messages += state.get("messages", [])

    ds = get_deepseek()
    model_to_use = pick_model(messages=messages, intent=state.get("skill_id", "general"))
    response = await ds.chat(
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        model_override=model_to_use,
        request_logprobs=True,
    )

    return {
        "messages": state.get("messages", [])
        + [{"role": "assistant", "content": response.get("content", "")}],
        "skill_id": skill_id,
        "tokens_total": state.get("tokens_total", 0) + int(response.get("tokens_total", 0)),
        "confidence": response.get("confidence", 0.7),
        "allowed_tools": allowed_tools,
        "iterations": iteration,
        "mock": bool(response.get("mock", False)),
    }


async def tools_node(state: AgentState) -> Dict[str, Any]:
    last_msg = state["messages"][-1]
    content = last_msg.get("content", "")
    skill_id = state.get("skill_id", "general")
    allowed_tools = state.get("allowed_tools", [])
    company_id = state.get("company_id", "default")
    user_id = state.get("user_id", "anonymous")
    session_id = state.get("session_id", "")
    counts = dict(state.get("tool_counts", {}))

    tool_calls = _extract_tool_calls(content, allowed_tools)
    if not tool_calls:
        return {"messages": state.get("messages", []), "tool_counts": counts}

    tool_messages = []
    for tc in tool_calls:
        name = tc["name"]
        counts[name] = counts.get(name, 0) + 1
        args = dict(tc.get("args") or {})
        args.setdefault("company_id", company_id)
        args.setdefault("user_id", user_id)
        args.setdefault("session_id", session_id)

        allowed, reason = check_access(skill_id, name)
        if not allowed:
            result = {"ok": False, "error": reason}
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
            continue

        # Guard: Prevent runaway loops on search_memory
        if name == "search_memory" and counts[name] > 1:
            result = {"ok": True, "skipped": True, "reason": "search_memory limit reached. Use existing context."}
        else:
            fn = HERMES_TOOLS.get(name)
            if not fn:
                result = {"ok": False, "error": f"unknown tool: {name}"}
            else:
                try:
                    logger.info("tool %s executing with args=%s", name, args)
                    result = await fn(args)
                    logger.info("tool %s completed ok=%s", name, result.get("ok"))
                except Exception as e:  # noqa: BLE001
                    logger.exception("tool %s failed", name)
                    result = {"ok": False, "error": str(e)}

        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )

    return {
        "messages": state.get("messages", []) + tool_messages,
        "iterations": state.get("iterations", 0),
        "allowed_tools": allowed_tools,
        "tool_counts": counts,
    }


def route_after_execute(state: AgentState):
    iterations = state.get("iterations", 0)
    if iterations >= MAX_ITERATIONS:
        return "end"

    last_msg = state["messages"][-1]
    content = last_msg.get("content", "")
    allowed_tools = state.get("allowed_tools", [])

    if _extract_tool_calls(content, allowed_tools):
        return "tools"
    return "end"


workflow = StateGraph(AgentState)
workflow.add_node("execute", execute_node)
workflow.add_node("tools", tools_node)

workflow.set_entry_point("execute")
workflow.add_conditional_edges("execute", route_after_execute, {"tools": "tools", "end": END})
workflow.add_edge("tools", "execute")

# Убираем MemorySaver — работаем в stateless режиме.
# История сессий контролируется явно через db.sessions + mempalace.
nxt8_graph = workflow.compile()
