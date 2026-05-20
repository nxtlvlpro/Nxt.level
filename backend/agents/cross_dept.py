"""
Cross-Department Coordinator Agent for NXT8.

When a request spans multiple departments (e.g. "что у нас по продажам и
поддержке?"), this agent:
1. detects mentioned departments
2. fans out memory.search restricted to each dept
3. dispatches a single DeepSeek synthesis pass with department-tagged context
4. persists the coordination task for audit
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents import memory as memory_agent
from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.cross_dept")

# canonical department vocabulary + RU/EN synonyms
DEPT_KEYWORDS = {
    "sales":       ["sales", "продаж", "сделк", "клиент", "выручк", "revenue", "deal"],
    "support":     ["support", "поддерж", "тикет", "ticket", "sla", "клиентск"],
    "engineering": ["engineering", "инжен", "разработ", "код", "deploy", "архитектур"],
    "hr":          ["hr", "найм", "сотрудник", "обучен", "human resources"],
    "finance":     ["finance", "финанс", "бюджет", "cost", "стоимост", "arr", "ebitda"],
    "product":     ["product", "продукт", "feature", "roadmap", "релиз"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_departments(query: str) -> List[str]:
    """Return list of departments mentioned in the query (lowercased, deduped, order-preserved)."""
    q = (query or "").lower()
    found: List[str] = []
    for dept, kws in DEPT_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k)}", q) for k in kws):
            found.append(dept)
    return found


async def coordinate(
    query: str,
    user_id: str = "anonymous",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Multi-department coordination pipeline. Returns synthesis + per-dept findings."""
    deepseek = get_deepseek()
    mem = memory_agent.get_memory()

    departments = detect_departments(query)
    multi = len(departments) >= 2

    # 1. fan-out search per department
    findings: List[Dict[str, Any]] = []
    if departments:
        for dept in departments:
            results = await mem.search(query=query, top_k=4)
            # filter by metadata.department when present
            scoped = [r for r in results if (r.get("metadata") or {}).get("department") == dept]
            # fall back to top-k if no exact dept match
            if not scoped:
                scoped = results[:2]
            findings.append({
                "department": dept,
                "items": [
                    {
                        "content": r["content"],
                        "rank": r["rank"],
                        "metadata": r.get("metadata", {}),
                    }
                    for r in scoped
                ],
            })
    else:
        # single-dept: fall back to general search
        results = await mem.search(query=query, top_k=5)
        findings.append({"department": "general", "items": [
            {"content": r["content"], "rank": r["rank"], "metadata": r.get("metadata", {})}
            for r in results
        ]})

    # 2. build dept-tagged context for synthesis
    blocks: List[str] = []
    for f in findings:
        if not f["items"]:
            continue
        dept = f["department"]
        bullets = "\n".join(f"- {it['content']}" for it in f["items"])
        blocks.append(f"### {dept.upper()}\n{bullets}")
    context_str = "\n\n".join(blocks) or "(no department knowledge available)"

    # 3. DeepSeek synthesis
    sys_prompt = (
        "Ты NXT8 cross-department coordinator. Тебе дали запрос, затрагивающий "
        "несколько отделов. Каждое подразделение прислало свой контекст. "
        "Синтезируй короткий, структурированный ответ: 1) по каждому отделу — "
        "ключевая выжимка; 2) общий вывод / конфликты / следующий шаг. "
        "Не выдумывай факты вне контекста."
    )
    answer = await deepseek.chat(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": f"## Departments involved: {', '.join(departments) or 'general'}\n\n{context_str}"},
            {"role": "user", "content": query},
        ],
        temperature=0.4,
        max_tokens=900,
    )

    # 4. persist coordination task
    task_id = str(uuid.uuid4())
    db = get_db()
    await db.cross_dept_tasks.insert_one({
        "id": task_id,
        "query": query,
        "user_id": user_id,
        "session_id": session_id,
        "departments": departments,
        "multi_department": multi,
        "findings_count": sum(len(f["items"]) for f in findings),
        "synthesis": answer.get("content", ""),
        "confidence": answer.get("confidence", 0.7),
        "tokens_total": answer.get("tokens_total", 0),
        "provider": answer.get("provider"),
        "created_at": _now(),
    })

    return {
        "task_id": task_id,
        "query": query,
        "departments": departments,
        "multi_department": multi,
        "findings": findings,
        "synthesis": answer.get("content", ""),
        "confidence": answer.get("confidence", 0.7),
        "provider": answer.get("provider"),
        "mock": bool(answer.get("mock")),
        "created_at": _now(),
    }


async def list_tasks(limit: int = 20) -> List[Dict[str, Any]]:
    db = get_db()
    return await db.cross_dept_tasks.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
