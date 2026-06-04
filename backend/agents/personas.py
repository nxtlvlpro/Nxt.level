"""
NXT8 Personas Layer — маркетинговые 8 агентов поверх инфраструктуры.

Каждая персона = (system_prompt + allowed_tools + контекстные fetcher'ы).
Тонкий слой над `HERMES_TOOLS` + базовыми агентами (mentor, roi, diagnostics,
market_radar). Не дублирует логику — переиспользует уже работающие модули.

Архитектура run_persona():
  1. Pre-context fetch: персона забирает data из своих agents (ROI snapshot,
     mentor patterns, diagnostics summary и т.д.)
  2. Persona-specific system prompt
  3. DeepSeek (через единый core/deepseek.py)
  4. Парсим fenced-JSON tool_calls
  5. Выполняем только tools из allowed_tools (allow-list)
  6. Если были tool_calls — второй проход с tool-results для финального ответа
     (тот же паттерн, что в LangGraph Ultra после фикса router-bug).

Тарифные ворота: PLANS отдельная карта plan_id → list[persona_id].
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents import diagnostics as diagnostics_agent
from agents import market_radar as market_agent
from agents import memory as memory_agent
from agents import mentor as mentor_agent
from agents import roi as roi_agent
from agents.hermes_max_tools_and_coo import HERMES_TOOLS
from agents.manifests import render_manifest_for_prompt
from agents.persona_prompts import get_prompt as get_deep_prompt
from agents.agent_charter import CHARTER
from core.company_context import get_settings as get_company_settings, render_company_block
from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.personas")

MAX_ITER = 3  # iterations of LLM → tools → LLM (must allow tools + final summary)

# =====================================================================
# Persona definitions
# =====================================================================


def _tools_doc(allowed: List[str]) -> str:
    """Render list of allowed tool signatures for the system prompt."""
    descriptions = {
        "search_memory": 'search_memory(query, top_k?) — поиск в корп. памяти',
        "create_task": 'create_task(title, description?, assignee?, department?, priority?, due_at?) — создать задачу',
        "update_task": 'update_task(task_id, status?, priority?, ...) — обновить задачу',
        "generate_communication_summary": 'generate_communication_summary(summary, suggested_next_action?) — резюме переписки',
        "suggest_next_best_action": 'suggest_next_best_action(action?, context?) — предложить NBA',
        "find_opportunities_in_contact": 'find_opportunities_in_contact(contact_id) — найти upsell',
        "create_cross_department_bridge": 'create_cross_department_bridge(from_dept, to_dept, description?) — мост между отделами',
        "monitor_sla_violations": 'monitor_sla_violations() — посмотреть просроченные задачи',
        "suggest_reply_template": 'suggest_reply_template(tone) — шаблон ответа',
        "evaluate_action_roi": 'evaluate_action_roi(action) — оценить ROI действия',
        "mempalace_search": 'mempalace_search(query, wing?, room?, top_k?) — поиск в долговременной памяти (wing=documents для договоров)',
        "mempalace_store": 'mempalace_store(content, wing?, room?) — записать факт в долгосрочную память',
        "web_search": 'web_search(query, max_results?, region?) — поиск свежей информации в интернете (DuckDuckGo). ИСПОЛЬЗУЙ когда не уверен в факте — лучше поиск, чем выдумывание',
        "fetch_url": 'fetch_url(url, max_chars?) — открыть страницу из web_search и прочитать основной текст',
        "delegate_to_agent": 'delegate_to_agent(agent_id, task, context?) — [ТОЛЬКО ДЛЯ HERMES] передать задачу подчинённому и получить его ответ',
        "escalate_to_hermes": 'escalate_to_hermes(reason, evidence?, urgency?, from_agent, question?) — поднять ситуацию CEO. Используй когда вопрос вне твоей зоны / нужно его решение / видишь риск.',
        "ask_colleague": 'ask_colleague(from_agent, agent_id, question, context?) — peer-to-peer спросить коллегу-агента до того, как ответить пользователю (не идёт через Hermes)',
    }
    return "\n".join(f"- `{name}` — {descriptions.get(name, '')}" for name in allowed)


PERSONAS: Dict[str, Dict[str, Any]] = {
    "hermes": {
        "id": "hermes",
        "name": "Hermes",
        "role": "CEO компании",
        "description": "CEO и владелец финрезультата AI-компании. Принимает финальные решения, делегирует подчинённым через delegate_to_agent, собирает их ответы в единый бизнес-вердикт. Профит-инстинкт включён в каждый разговор.",
        "icon": "Crown",
        "color": "turquoise",
        "allowed_tools": list(HERMES_TOOLS.keys()),
        "system_prompt": (
            "Ты — Hermes, CEO компании NXT8 и владелец её финансового результата.\n\n"
            "Ты управляешь командой из 7 специалистов (hr_mentor, client_manager, "
            "project_coord, analyst, bookkeeper, marketer, compliance). Они подчиняются тебе.\n\n"
            "Когда вопрос узкий — делегируй через `delegate_to_agent(agent_id, task)`. "
            "Сильный CEO умеет поручать. Затем соедини ответы подчинённых в "
            "единый CEO-вердикт от своего имени и подсвети, чей вклад был.\n\n"
            "Формат: 1) Резюме; 2) Что важно; 3) Действия (приоритет); 4) Эффект; "
            "5) 💡 Где здесь деньги."
        ),
        "data_fetchers": [],
    },
    "hr_mentor": {
        "id": "hr_mentor",
        "name": "HR-Ментор",
        "role": "Развитие сотрудников",
        "description": "Оценивает сотрудников, находит слабые места, даёт рекомендации по обучению и менторингу. Видит 5 уровней (junior→strategist) и сравнивает с уровневой нормой.",
        "icon": "GraduationCap",
        "color": "violet",
        "allowed_tools": ["search_memory", "web_search", "fetch_url"],
        "system_prompt": (
            "Ты — HR-Ментор NXT8. Твой фокус: люди.\n\n"
            "Ты анализируешь performance, выявляешь weak patterns (low_accuracy, "
            "high_escalation, repeating_errors), даёшь конкретные рекомендации:\n"
            "  - training session\n  - pair-mentoring с senior\n"
            "  - чек-листы для повторяющихся ошибок.\n\n"
            "У тебя в контексте — реальные данные по сотрудникам. Опирайся ТОЛЬКО на них, "
            "не выдумывай. Если данных мало — попроси внести через `/api/mentor/performance`."
        ),
        "data_fetchers": ["mentor_overview"],
    },
    "client_manager": {
        "id": "client_manager",
        "name": "Менеджер по клиентам",
        "role": "Клиентский успех и follow-up",
        "description": "Следит, чтобы запросы не терялись, SLA не нарушался, follow-up уходил вовремя. Помнит историю взаимодействий.",
        "icon": "HeartHandshake",
        "color": "rose",
        "allowed_tools": [
            "search_memory",
            "create_task",
            "monitor_sla_violations",
            "find_opportunities_in_contact",
            "suggest_reply_template",
            "web_search",
            "fetch_url",
        ],
        "system_prompt": (
            "Ты — Менеджер по клиентам NXT8. Ни один запрос не должен потеряться.\n\n"
            "Твои обязанности:\n"
            "- Фиксировать договорённости как задачи (`create_task` с `kind=followup`)\n"
            "- Мониторить SLA (`monitor_sla_violations`)\n"
            "- Предлагать шаблоны вежливых/быстрых ответов (`suggest_reply_template`)\n"
            "- Искать возможности апсейла (`find_opportunities_in_contact`)\n"
            "- Поднимать историю клиента из памяти (`search_memory`)\n\n"
            "Будь конкретен, давай готовые формулировки."
        ),
        "data_fetchers": [],
    },
    "project_coord": {
        "id": "project_coord",
        "name": "Координатор проектов",
        "role": "Кросс-функциональная координация",
        "description": "Синхронизирует команды между отделами. Создаёт мосты, держит сроки, не даёт задачам зависать на стыке ответственности.",
        "icon": "Network",
        "color": "amber",
        "allowed_tools": [
            "search_memory",
            "create_task",
            "update_task",
            "create_cross_department_bridge",
            "monitor_sla_violations",
            "web_search",
            "fetch_url",
        ],
        "system_prompt": (
            "Ты — Координатор проектов NXT8. Фокус: не дать задаче зависнуть между отделами.\n\n"
            "Когда запрос затрагивает 2+ отдела — создавай bridging-задачу через "
            "`create_cross_department_bridge`. Следи за просрочками через "
            "`monitor_sla_violations`. Структурируй ответ как мини-проектный план: "
            "владелец → срок → результат."
        ),
        "data_fetchers": [],
    },
    "analyst": {
        "id": "analyst",
        "name": "Аналитик",
        "role": "Здоровье AI-операций",
        "description": "Показывает KPI, замечает проблемные зоны, видит противоречия и просадки confidence. Аналитика самой AI-системы и её влияния на бизнес.",
        "icon": "TrendingUp",
        "color": "cyan",
        "allowed_tools": ["search_memory", "evaluate_action_roi"],
        "system_prompt": (
            "Ты — Аналитик NXT8. Твоя зона: данные о работе системы и бизнеса.\n\n"
            "Ты видишь:\n"
            "- avg confidence по интентам\n"
            "- escalation_rate (% запросов с эскалацией)\n"
            "- противоречия (когда AI отвечает по-разному на похожие запросы)\n"
            "- noisy intents (топ интентов с низкой уверенностью)\n\n"
            "Делай выводы и предлагай действия. Не описывай данные — интерпретируй их."
        ),
        "data_fetchers": ["diagnostics_summary", "roi_current"],
    },
    "bookkeeper": {
        "id": "bookkeeper",
        "name": "Бухгалтер",
        "role": "Финансовая телеметрия AI",
        "description": "Считает costs/revenue/ROI каждый час. Видит структуру расходов (API/compute/escalations) и доходов по агентам. Готовит цифры — не заменяет бухгалтерию компании.",
        "icon": "Calculator",
        "color": "emerald",
        "allowed_tools": ["search_memory", "web_search", "fetch_url"],
        "system_prompt": (
            "Ты — Бухгалтер NXT8. Считаешь unit-economics AI-операций компании.\n\n"
            "В контексте у тебя — реальные cifры за последний час и тренд:\n"
            "- total_cost / total_revenue / hourly ROI\n"
            "- разбивка cost по типам (deepseek_api, compute, human_escalation)\n"
            "- разбивка cost и revenue по агентам\n\n"
            "Отвечай точно. Если ROI отрицательный — назови причину и предложи 1-2 действия.\n"
            "Помни: ты ведёшь финансы AI-операций, не корпоративную бухгалтерию. "
            "При запросе про P&L всей компании — честно скажи, что для этого нужна "
            "интеграция с учётной системой."
        ),
        "data_fetchers": ["roi_dashboard"],
    },
    "marketer": {
        "id": "marketer",
        "name": "Маркетолог",
        "role": "Рынок и конкуренты",
        "description": "Следит за сигналами рынка: конкуренты, цены, регуляции, технологии. Даёт еженедельный дайджест и идеи для команды.",
        "icon": "Radar",
        "color": "orange",
        "allowed_tools": ["search_memory", "suggest_next_best_action", "web_search", "fetch_url"],
        "system_prompt": (
            "Ты — Маркетолог NXT8. Твой объект — внешний рынок.\n\n"
            "В контексте — свежие сигналы (competitor, pricing, regulation, tech, "
            "macro, customer) и последние дайджесты.\n\n"
            "Что делать:\n"
            "- топ-3 события за период\n"
            "- общий тренд\n"
            "- 2-3 рекомендации для sales/product\n\n"
            "Если данных мало — предложи источники для регулярного ingestion."
        ),
        "data_fetchers": ["market_intel"],
    },
    "compliance": {
        "id": "compliance",
        "name": "Юрист / Compliance",
        "role": "Политики, документы, риски, audit",
        "description": "Хранит политики и SLA. Анализирует загруженные документы (PDF/DOCX/TXT), подсвечивает риски и категории (ответственность, оплата, расторжение, данные, регуляции). Мониторит противоречия и regulatory сигналы.",
        "icon": "Shield",
        "color": "slate",
        "allowed_tools": ["search_memory", "mempalace_search", "web_search", "fetch_url"],
        "system_prompt": (
            "Ты — Compliance Officer NXT8.\n\n"
            "Твоя зона:\n"
            "- политики компании (priority=critical в памяти)\n"
            "- audit log (`db.requests`) — что AI отвечал и кому\n"
            "- противоречия в ответах AI (TF-IDF diagnostics)\n"
            "- regulatory сигналы из market radar (например AI Act)\n"
            "- загруженные документы (договоры, NDA, оферты) в MemPalace "
            "wing=`documents` — ищи через `mempalace_search` с wing='documents'.\n\n"
            "Если пользователь спрашивает про конкретный договор / документ — "
            "сначала вызови `mempalace_search` с wing='documents' и room=<document_id> "
            "(если id известен), либо без room — чтобы поднять контекст. "
            "Затем подсвети риски со ссылкой на цитату.\n\n"
            "Подсвечивай риски, ссылайся на конкретные политики и пункты документов, "
            "предлагай action items ДО того, как проблема стала инцидентом."
        ),
        "data_fetchers": ["compliance_context"],
    },
}


# All 7 subordinates can escalate up to Hermes AND ask peers. Inject the
# two inter-agent tools into every persona's allowed_tools (except hermes,
# who already has `*` via HERMES_TOOLS.keys()).
_INTER_AGENT_TOOLS_FOR_SUBORDINATES = ["escalate_to_hermes", "ask_colleague"]
for _pid, _cfg in PERSONAS.items():
    if _pid == "hermes":
        continue
    _allowed = _cfg.get("allowed_tools") or []
    for _t in _INTER_AGENT_TOOLS_FOR_SUBORDINATES:
        if _t not in _allowed:
            _allowed.append(_t)
    _cfg["allowed_tools"] = _allowed


# =====================================================================
# Tariff plans
# =====================================================================

PLANS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "name": "Basic",
        "price_usd": 9,
        "personas": ["hermes"],
    },
    "simple": {
        "name": "Simple",
        "price_usd": 14,
        "personas": ["hermes", "hr_mentor", "client_manager"],
    },
    "pro": {
        "name": "Pro",
        "price_usd": 19,
        "personas": ["hermes", "hr_mentor", "client_manager", "bookkeeper", "marketer", "compliance"],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_usd": 24,
        "personas": list(PERSONAS.keys()),  # all 8
    },
}


def get_plan(plan_id: Optional[str]) -> Dict[str, Any]:
    pid = (plan_id or "enterprise").lower()
    if pid not in PLANS:
        pid = "enterprise"
    return {"id": pid, **PLANS[pid]}


# =====================================================================
# Context fetchers (pull live data into LLM context)
# =====================================================================


async def _fetch_mentor_overview() -> str:
    try:
        emps = await mentor_agent.list_employees()
        patterns = await mentor_agent.list_open_patterns(limit=20)
    except Exception as e:
        logger.warning("mentor_overview fetch failed: %s", e)
        return "(данные по сотрудникам недоступны)"
    if not emps:
        return "В системе пока нет сотрудников. Добавьте через `POST /api/mentor/employees`."
    lines = [f"## Сотрудники ({len(emps)})"]
    for e in emps[:20]:
        lines.append(
            f"- {e.get('name', '?')} ({e.get('department', '?')}, {e.get('level', '?')}, "
            f"{e.get('experience_months', 0)} мес опыта)"
        )
    if patterns:
        lines.append(f"\n## Открытые weak patterns ({len(patterns)})")
        for p in patterns[:10]:
            lines.append(
                f"- {p.get('employee_id', '?')}: {p.get('pattern', '?')} — {p.get('details', '')[:120]}"
            )
    else:
        lines.append("\n## Открытых weak patterns: 0 (всё спокойно)")
    return "\n".join(lines)


async def _fetch_diagnostics_summary() -> str:
    try:
        s = await diagnostics_agent.summary(window=200)
    except Exception as e:
        return f"(diagnostics unavailable: {e})"
    if not s.get("scanned"):
        return "Аудит-лог пустой. Начните работу с системой через CMD/CHAT."
    lines = [
        f"Просканировано: {s['scanned']} запросов",
        f"Avg confidence: {s.get('avg_confidence', 0):.2f}",
        f"Escalation rate: {s.get('escalation_rate', 0):.1%}",
        f"Mock rate: {s.get('mock_rate', 0):.1%}",
    ]
    if s.get("noisy_intents"):
        lines.append("\nТоп шумных интентов:")
        for it in s["noisy_intents"][:5]:
            lines.append(
                f"  - {it['intent']}: avg={it['avg_confidence']:.2f}, "
                f"esc={it['escalations']}/{it['count']}"
            )
    return "\n".join(lines)


async def _fetch_roi_current() -> str:
    try:
        snap = await roi_agent.calculate_hourly_roi()
    except Exception as e:
        return f"(roi unavailable: {e})"
    lines = [
        f"Текущий час ROI: {snap.get('roi')}",
        f"Cost (1h): ${snap.get('total_cost', 0):.2f}",
        f"Revenue (1h): ${snap.get('total_revenue', 0):.2f}",
    ]
    if snap.get("by_type_cost"):
        lines.append("\nCost по типам:")
        for k, v in snap["by_type_cost"].items():
            lines.append(f"  - {k}: ${v:.2f}")
    if snap.get("alert"):
        lines.append(f"\n⚠ {snap['alert']}")
    return "\n".join(lines)


async def _fetch_roi_dashboard() -> str:
    try:
        d = await roi_agent.dashboard_summary()
    except Exception as e:
        return f"(roi unavailable: {e})"
    cur = d.get("current_hour", {})
    trend = d.get("trend_24h", [])
    lines = [
        "## Текущий час",
        f"ROI: {cur.get('roi')}, cost ${cur.get('total_cost', 0):.2f}, rev ${cur.get('total_revenue', 0):.2f}",
    ]
    if cur.get("by_agent_cost"):
        lines.append("\n## Cost по агентам")
        for k, v in list(cur["by_agent_cost"].items())[:10]:
            rev = cur.get("by_agent_revenue", {}).get(k, 0)
            lines.append(f"- {k}: cost ${v:.2f}, rev ${rev:.2f}")
    if trend:
        rois = [t.get("roi") for t in trend if t.get("roi") is not None]
        if rois:
            avg = sum(rois) / len(rois)
            lines.append(f"\n## Тренд 24ч: {len(trend)} снэпшотов, avg ROI {avg:.2%}")
    return "\n".join(lines)


async def _fetch_market_intel() -> str:
    try:
        digests = await market_agent.list_digests(limit=2)
        signals = await market_agent.list_signals(limit=15)
    except Exception as e:
        return f"(market unavailable: {e})"
    lines = []
    if digests:
        lines.append("## Последние дайджесты")
        for d in digests:
            lines.append(
                f"- [{d.get('created_at', '')[:16]}] "
                f"{d.get('signals_count', 0)} сигналов, "
                f"{(d.get('digest', '')[:200])}…"
            )
    if signals:
        lines.append(f"\n## Свежие сигналы ({len(signals)})")
        for s in signals[:15]:
            lines.append(
                f"- [{s.get('category', '?')}] {s.get('headline', '')[:100]} "
                f"(score {s.get('score', 0)})"
            )
    if not lines:
        lines.append("Сигналов пока нет. Добавьте вручную через `POST /api/market/signals`.")
    return "\n".join(lines)


async def _fetch_compliance_context() -> str:
    try:
        contras = await diagnostics_agent.list_contradictions(limit=10)
        critical_mem = await memory_agent.get_memory().search(query="политика SLA", top_k=5)
        db = get_db()
        alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=10)
        recent_docs = await db.documents.find(
            {}, {"_id": 0, "id": 1, "title": 1, "filename": 1, "severity": 1,
                 "summary": 1, "created_at": 1, "findings": 1},
        ).sort("created_at", -1).to_list(length=10)
    except Exception as e:
        return f"(compliance ctx unavailable: {e})"
    lines = []
    if critical_mem:
        lines.append("## Ключевые политики в памяти")
        for m in critical_mem[:5]:
            meta = m.get("metadata") or {}
            lines.append(
                f"- [priority={meta.get('priority', '?')}, dept={meta.get('department', '?')}] "
                f"{m.get('content', '')[:160]}"
            )
    if recent_docs:
        lines.append(f"\n## Недавно загруженные документы ({len(recent_docs)})")
        for d in recent_docs[:5]:
            findings_n = len(d.get("findings") or [])
            lines.append(
                f"- [{d.get('severity', '?')}] {d.get('title') or d.get('filename')} "
                f"(id={d.get('id', '?')[:8]}, рисков {findings_n}): "
                f"{(d.get('summary') or '')[:140]}"
            )
    if contras:
        lines.append(f"\n## Противоречия в ответах AI ({len(contras)})")
        for c in contras[:5]:
            lines.append(
                f"- intent={c.get('intent', '?')}, divergence={c.get('divergence', 0):.2f}: "
                f"{(c.get('a_message') or '')[:80]} vs {(c.get('b_message') or '')[:80]}"
            )
    if alerts:
        lines.append(f"\n## Последние алерты ({len(alerts)})")
        for a in alerts[:5]:
            lines.append(
                f"- [{a.get('severity', '?')}] {a.get('source', '?')}: {a.get('message', '')[:120]}"
            )
    return "\n".join(lines) or "(данные compliance пусты)"


_FETCHER_DISPATCH = {
    "mentor_overview": _fetch_mentor_overview,
    "diagnostics_summary": _fetch_diagnostics_summary,
    "roi_current": _fetch_roi_current,
    "roi_dashboard": _fetch_roi_dashboard,
    "market_intel": _fetch_market_intel,
    "compliance_context": _fetch_compliance_context,
}


# =====================================================================
# Tool-call extraction (same convention as nxt8_langgraph_ultra)
# =====================================================================

_TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\"tool\".*?\})\s*```", re.DOTALL | re.IGNORECASE
)


def _extract_tool_calls(content: str) -> List[Dict[str, Any]]:
    if not content:
        return []
    calls: List[Dict[str, Any]] = []
    for match in _TOOL_JSON_RE.findall(content):
        try:
            obj = json.loads(match)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("tool"):
            calls.append(
                {"id": str(uuid.uuid4())[:8], "name": obj["tool"], "args": obj.get("args") or {}}
            )
    return calls


# =====================================================================
# Main runner
# =====================================================================


def list_personas(plan_id: Optional[str] = None) -> List[Dict[str, Any]]:
    plan = get_plan(plan_id)
    allowed = set(plan["personas"])
    items: List[Dict[str, Any]] = []
    for pid, cfg in PERSONAS.items():
        items.append(
            {
                "id": pid,
                "name": cfg["name"],
                "role": cfg["role"],
                "description": cfg["description"],
                "icon": cfg.get("icon"),
                "color": cfg.get("color"),
                "tools_count": len(cfg["allowed_tools"]),
                "available_on_plan": pid in allowed,
                "min_plan": _min_plan_for(pid),
            }
        )
    return items


def _min_plan_for(persona_id: str) -> str:
    """Cheapest plan that includes the persona."""
    order = ["basic", "simple", "pro", "enterprise"]
    for p in order:
        if persona_id in PLANS[p]["personas"]:
            return p
    return "enterprise"


async def run_persona(
    persona_id: str,
    message: str,
    company_id: str = "default",
    user_id: str = "anonymous",
    session_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> Dict[str, Any]:
    if persona_id not in PERSONAS:
        return {"success": False, "error": f"unknown persona: {persona_id}"}
    plan = get_plan(plan_id)
    if persona_id not in plan["personas"]:
        return {
            "success": False,
            "error": f"persona '{persona_id}' недоступна на тарифе '{plan['id']}'",
            "current_plan": plan["id"],
            "required_plan": _min_plan_for(persona_id),
        }
    cfg = PERSONAS[persona_id]
    sid = session_id or f"persona_{persona_id}_{uuid.uuid4().hex[:10]}"

    # 1. Pre-context
    ctx_blocks: List[str] = []
    for fetcher in cfg.get("data_fetchers") or []:
        fn = _FETCHER_DISPATCH.get(fetcher)
        if fn:
            try:
                ctx_blocks.append(await fn())
            except Exception as e:  # noqa: BLE001
                logger.warning("fetcher %s failed: %s", fetcher, e)

    # 2. System prompt — manifest injection makes the agent literally
    #    self-aware of its specialty, data access, chain of command and
    #    decision authority. This is the "constitutional" layer.
    #    Deep v2.0 prompt overrides the legacy short prompt if available.
    deep_prompt = get_deep_prompt(persona_id) or cfg["system_prompt"]
    manifest_block = render_manifest_for_prompt(persona_id)

    # 2b. Company context — region/industry/regulations/channels so agents
    #     adapt their answers to WHERE the company operates.
    try:
        company_settings = await get_company_settings(company_id)
        company_block = render_company_block(company_settings)
    except Exception as e:  # noqa: BLE001
        logger.warning("company context fetch failed: %s", e)
        company_block = ""

    sys_prompt = (
        f"{CHARTER}\n\n"
        f"{deep_prompt}\n\n"
        f"{manifest_block}\n\n"
        f"{company_block}\n\n"
        f"## Доступные инструменты\n{_tools_doc(cfg['allowed_tools'])}\n\n"
        "Если нужен инструмент — вызови его строго в формате fenced-JSON:\n"
        "```json\n"
        '{"tool":"<name>","args":{...}}\n'
        "```\n"
        "Можно несколько блоков подряд. После выполнения тебе вернут результат "
        "и ты сделаешь финальный структурированный ответ.\n\n"
        "## APPROVAL GATE (важно)\n"
        "Если результат инструмента вернул `pending=true` и `approval_id` — это "
        "означает что действие НЕ выполнено, оно ждёт одобрения Hermes/владельца. "
        "В финальном ответе пользователю ЯВНО скажи: «⏸ Предложение отправлено "
        "на одобрение Hermes (approval_id=...)». Не делай вид что задача создана. "
        "Объясни пользователю почему действие требует одобрения (high-impact)."
    )

    messages: List[Dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
    if ctx_blocks:
        messages.append(
            {"role": "system", "content": "## Текущий контекст\n\n" + "\n\n".join(ctx_blocks)}
        )
    messages.append({"role": "user", "content": message})

    # 3. Up to MAX_ITER cycles of LLM → tools → LLM
    deepseek = get_deepseek()
    tool_traces: List[Dict[str, Any]] = []
    confidence = 0.7
    provider = None
    last_content = ""
    iterations = 0
    mock = False
    tokens_total = 0

    for iteration in range(MAX_ITER + 1):
        iterations = iteration + 1
        resp = await deepseek.chat(messages=messages, temperature=0.3, max_tokens=2048)
        last_content = (resp.get("content") or "").strip()
        confidence = float(resp.get("confidence") or 0.7)
        provider = resp.get("provider") or provider
        mock = mock or bool(resp.get("mock"))
        tokens_total += int(resp.get("tokens_total") or 0)

        if iteration >= MAX_ITER:
            break

        tool_calls = _extract_tool_calls(last_content)
        if not tool_calls:
            break

        # add assistant turn
        messages.append({"role": "assistant", "content": last_content})

        # execute allowed tools only
        from agents.manifests import requires_approval
        from core import approval_gate
        for tc in tool_calls:
            name = tc["name"]
            args = dict(tc.get("args") or {})
            args.setdefault("company_id", company_id)
            if name not in cfg["allowed_tools"]:
                result = {
                    "ok": False,
                    "error": (
                        f"Инструмент '{name}' недоступен для персоны '{cfg['name']}'. "
                        f"Доступные: {', '.join(cfg['allowed_tools'])}"
                    ),
                }
            elif requires_approval(persona_id, name):
                # Approval Gate — high-impact actions don't execute directly.
                # They land in db.pending_approvals for Hermes/human review.
                result = await approval_gate.request_approval(
                    agent_id=persona_id,
                    action=name,
                    args=args,
                    company_id=company_id,
                    user_id=user_id,
                    session_id=sid,
                    rationale=f"persona {persona_id} proposed during turn",
                )
            else:
                fn = HERMES_TOOLS.get(name)
                if not fn:
                    result = {"ok": False, "error": f"unknown tool: {name}"}
                else:
                    try:
                        result = await fn(args)
                    except Exception as e:  # noqa: BLE001
                        logger.exception("persona %s tool %s failed", persona_id, name)
                        result = {"ok": False, "error": str(e)}
            tool_traces.append({"name": name, "args": args, "result": result})
            messages.append(
                {
                    "role": "system",
                    "content": f"## Результат `{name}`\n```json\n{json.dumps(result, ensure_ascii=False)[:1500]}\n```",
                }
            )

    # 4. Persist a thin audit record
    try:
        db = get_db()
        await db.persona_requests.insert_one(
            {
                "id": str(uuid.uuid4()),
                "persona_id": persona_id,
                "company_id": company_id,
                "user_id": user_id,
                "session_id": sid,
                "plan_id": plan["id"],
                "message": message,
                "response": last_content,
                "tool_traces": tool_traces,
                "iterations": iterations,
                "confidence": confidence,
                "provider": provider,
                "mock": mock,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("persona audit insert failed: %s", e)

    return {
        "success": True,
        "persona_id": persona_id,
        "persona_name": cfg["name"],
        "session_id": sid,
        "content": last_content,
        "tool_traces": tool_traces,
        "iterations": iterations,
        "confidence": round(confidence, 4),
        "provider": provider,
        "mock": mock,
        "plan_id": plan["id"],
        "tokens_total": tokens_total,
    }
