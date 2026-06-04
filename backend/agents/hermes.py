"""
Hermes — unified COO Agent (v1.6.0 unification).

This module is the SINGLE source of truth for Hermes COO behaviour. It
replaces the two legacy modules that diverged historically:

  * agents/hermes_coo.py            (6 tools, OpenAI tool-calling format,
                                     required external gateway @ :8642)
  * agents/hermes_max_tools_and_coo.py
                                    (10 tools, fenced-JSON format,
                                     used by LangGraph Ultra orchestrator)

Per user choice (2026-05-20) the unified module standardises on the
**fenced-JSON tool-calling convention** because it works directly with
DeepSeek (no external gateway required) and is what the LangGraph
orchestrator already parses.

Unified collection: tasks + followups are now stored in a single MongoDB
collection `db.tasks` distinguished by the `kind` field
(`"task"` | `"followup"`). Legacy `db.followups` is still queried on read
for backward compatibility — new writes go to `db.tasks` only.

Public surface (back-compat re-exports live in
`agents/hermes_coo.py` and `agents/hermes_max_tools_and_coo.py`):

  HERMES_TOOLS        — dict[name -> async tool callable]
  hermes_chat()       — DeepSeek call with fenced-JSON tool loop
  enhanced_chat()     — alias for hermes_chat() (legacy name)
  hermes_coo_chat()   — alias for hermes_chat() (legacy name, simpler signature)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.hermes")

DEFAULT_COMPANY = "default"
MAX_TOOL_ITERATIONS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Tool implementations
# =====================================================================


async def _t_search_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import memory as memory_agent
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "empty query", "results": []}
    top_k = int(args.get("top_k") or 5)
    mem = memory_agent.get_memory()
    results = await mem.search(query=query, top_k=top_k)
    return {"ok": True, "count": len(results), "results": results,
            "company_id": args.get("company_id", DEFAULT_COMPANY)}


async def _t_create_task(args: Dict[str, Any]) -> Dict[str, Any]:
    title = (args.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "title is required"}
    doc = {
        "id": str(uuid.uuid4()),
        "kind": args.get("kind", "task"),  # "task" | "followup"
        "company_id": args.get("company_id", DEFAULT_COMPANY),
        "title": title,
        "description": args.get("description", ""),
        "assignee": args.get("assignee"),
        "department": args.get("department"),
        "priority": args.get("priority", "medium"),
        "status": "open",
        "due_at": args.get("due_at"),
        "created_at": _now(),
        "source": "hermes",
        "related_contact": args.get("contact_id"),
        "related_deal": args.get("deal_id"),
    }
    await get_db().tasks.insert_one(doc)
    logger.info("Hermes created %s: %s", doc["kind"], title)
    return {"ok": True, "task_id": doc["id"], "kind": doc["kind"], "title": title}


async def _t_update_task(args: Dict[str, Any]) -> Dict[str, Any]:
    task_id = args.get("task_id")
    if not task_id:
        return {"ok": False, "error": "task_id required"}
    update = {k: v for k, v in args.items() if k not in ("task_id", "company_id")}
    if not update:
        return {"ok": False, "error": "no fields to update"}
    update["updated_at"] = _now()
    result = await get_db().tasks.update_one({"id": task_id}, {"$set": update})
    return {
        "ok": result.modified_count > 0,
        "task_id": task_id,
        "matched": result.matched_count,
        "modified": result.modified_count,
    }


async def _t_create_followup(args: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compat alias: creates a `kind=followup` task in db.tasks."""
    title = (args.get("title") or "").strip()
    message = (args.get("message") or "").strip()
    recipients = args.get("recipients") or []
    if not title or not message or not recipients:
        return {"ok": False, "error": "title, message, recipients are required"}
    priority = args.get("priority") or "medium"
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    due_days = int(args.get("due_in_days") or 3)
    due_at = (datetime.now(timezone.utc) + timedelta(days=due_days)).isoformat()
    payload = {
        "kind": "followup",
        "company_id": args.get("company_id", DEFAULT_COMPANY),
        "title": title,
        "description": message,
        "department": None,
        "priority": priority,
        "due_at": due_at,
        "assignee": recipients[0] if recipients else None,
    }
    res = await _t_create_task(payload)
    if res.get("ok"):
        res["followup_id"] = res.pop("task_id")
        res["due_at"] = due_at
        res["recipients"] = list(recipients)
    return res


async def _t_monitor_sla_violations(args: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    company_id = args.get("company_id", DEFAULT_COMPANY)
    cursor = get_db().tasks.find(
        {"company_id": company_id, "status": "open",
         "due_at": {"$ne": None, "$lt": now}},
        {"_id": 0, "id": 1, "title": 1, "priority": 1, "due_at": 1, "kind": 1},
    )
    items = await cursor.to_list(length=50)
    critical = [t for t in items if t.get("priority") == "high"]
    return {"ok": True, "violations": len(items), "critical": critical,
            "sample": items[:10]}


async def _t_detect_bottlenecks(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import diagnostics as diagnostics_agent
    department = (args.get("department") or "all").lower()
    diag = await diagnostics_agent.summary(window=200)
    contradictions = await diagnostics_agent.list_contradictions(limit=10)
    company_id = args.get("company_id", DEFAULT_COMPANY)
    db = get_db()
    # Read from unified tasks + legacy followups (back-compat)
    pending_new = await db.tasks.find(
        {"company_id": company_id, "kind": "followup", "status": "open"},
        {"_id": 0},
    ).sort("due_at", 1).to_list(length=20)
    pending_legacy = await db.followups.find(
        {"company_id": company_id, "status": "open"},
        {"_id": 0},
    ).sort("due_at", 1).to_list(length=20)
    pending = pending_new + pending_legacy
    return {"ok": True, "company_id": company_id, "department": department,
            "health": diag, "recent_contradictions": contradictions,
            "open_followups_count": len(pending),
            "open_followups_sample": pending[:5]}


async def _t_generate_daily_digest(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import diagnostics as diagnostics_agent
    recipient = args.get("recipient_user_id") or "unknown"
    period = args.get("period") or "daily"
    company_id = args.get("company_id", DEFAULT_COMPANY)
    hours = 24 if period == "daily" else 24 * 7
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    db = get_db()
    requests = await db.requests.find(
        {"created_at": {"$gte": cutoff}},
        {"_id": 0, "intent": 1, "confidence": 1, "should_escalate": 1, "message": 1},
    ).sort("created_at", -1).limit(200).to_list(length=200)
    escalations = [r for r in requests if r.get("should_escalate")]
    low_conf = [r for r in requests if (r.get("confidence") or 0) < 0.5]
    open_followups = await db.tasks.find(
        {"company_id": company_id, "kind": "followup", "status": "open"},
        {"_id": 0},
    ).sort("priority", 1).to_list(length=20)
    open_followups += await db.followups.find(
        {"company_id": company_id, "status": "open"}, {"_id": 0},
    ).sort("priority", 1).to_list(length=20)
    diag = await diagnostics_agent.summary(window=200)
    return {"ok": True, "period": period, "company_id": company_id,
            "recipient_user_id": recipient,
            "totals": {"requests": len(requests),
                       "escalations": len(escalations),
                       "low_confidence": len(low_conf),
                       "open_followups": len(open_followups)},
            "health": diag, "open_followups_top": open_followups[:5],
            "generated_at": _now()}


async def _t_create_cross_department_bridge(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_args = {
        **args,
        "title": f"Bridge: {args.get('from_dept', '?')} → {args.get('to_dept', '?')}",
        "department": args.get("to_dept"),
        "description": args.get("description")
        or f"Кросс-функциональная координация {args.get('from_dept')} → {args.get('to_dept')}",
        "kind": "task",
    }
    return await _t_create_task(bridge_args)


async def _t_mempalace_search(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import mempalace_bridge as mempalace_agent
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "empty query", "results": []}
    top_k = int(args.get("top_k") or 5)
    bridge = mempalace_agent.get_mempalace()
    results = await bridge.search(query=query, wing=args.get("wing"),
                                  room=args.get("room"), top_k=top_k)
    return {"ok": True, "count": len(results), "results": results}


async def _t_mempalace_store(args: Dict[str, Any]) -> Dict[str, Any]:
    from agents import mempalace_bridge as mempalace_agent
    content = (args.get("content") or "").strip()
    if not content:
        return {"ok": False, "error": "empty content"}
    bridge = mempalace_agent.get_mempalace()
    return await bridge.store(
        content=content,
        wing=args.get("wing") or "internal",
        room=args.get("room") or "general",
        metadata={"company_id": args.get("company_id"), "via": "hermes_tool"},
        source="hermes",
    )


# ---- previously-stub tools, now real LLM-backed implementations ---


_JSON_FENCED_RE = re.compile(
    r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE
)


def _parse_fenced_json(content: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a single JSON object from an LLM reply."""
    if not content:
        return None
    m = _JSON_FENCED_RE.search(content)
    raw = m.group(1) if m else content.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    return data if isinstance(data, dict) else None


async def _t_generate_communication_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    """Summarise a thread of messages / emails / CRM notes with DeepSeek."""
    text = (args.get("text") or "").strip()
    messages_in = args.get("messages") or []
    if not text and isinstance(messages_in, list) and messages_in:
        parts: List[str] = []
        for m in messages_in:
            if isinstance(m, dict):
                who = m.get("from") or m.get("role") or "—"
                body = m.get("text") or m.get("content") or ""
                parts.append(f"[{who}] {body}")
            elif isinstance(m, str):
                parts.append(m)
        text = "\n".join(parts)
    if not text:
        return {"ok": False, "error": "text or messages required"}

    system = (
        "Ты — операционный аналитик NXT8. Дай краткую сводку переписки. "
        "Ответ строго в fenced-JSON:\n"
        "```json\n"
        '{"summary":"2-4 предложения","sentiment":"positive|neutral|negative",'
        '"key_topics":["..."],"open_questions":["..."],'
        '"suggested_next_action":"одно конкретное действие"}\n'
        "```"
    )
    snippet = text[:8000]
    deepseek = get_deepseek()
    resp = await deepseek.chat(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": f"Переписка:\n\n{snippet}"}],
        temperature=0.2, max_tokens=900,
    )
    parsed = _parse_fenced_json(resp.get("content") or "") or {}
    return {
        "ok": True,
        "summary": parsed.get("summary") or (resp.get("content") or "").strip()[:400],
        "sentiment": parsed.get("sentiment", "neutral"),
        "key_topics": parsed.get("key_topics", []),
        "open_questions": parsed.get("open_questions", []),
        "suggested_next_action": parsed.get("suggested_next_action"),
        "tokens_total": int(resp.get("tokens_total") or 0),
        "mock": bool(resp.get("mock")),
        "provider": resp.get("provider"),
    }


async def _t_suggest_next_best_action(args: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-driven Next Best Action recommender."""
    context = (args.get("context") or args.get("situation") or "").strip()
    goal = (args.get("goal") or "").strip()
    if not context and not goal:
        return {"ok": False, "error": "context or goal required"}

    system = (
        "Ты — Hermes COO. Предложи ОДНО следующее лучшее действие (NBA) "
        "под цели операционной системы. Ответ строго fenced-JSON:\n"
        "```json\n"
        '{"action":"глагол + объект","owner":"роль/отдел",'
        '"urgency":"low|medium|high|critical","horizon_hours":24,'
        '"rationale":"1-2 предложения почему","expected_impact":"измеримый эффект"}\n'
        "```"
    )
    user = f"Контекст:\n{context or '—'}\n\nЦель: {goal or '—'}"
    deepseek = get_deepseek()
    resp = await deepseek.chat(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.3, max_tokens=600,
    )
    parsed = _parse_fenced_json(resp.get("content") or "") or {}
    return {
        "ok": True,
        "action": parsed.get("action") or "Уточнить детали с владельцем процесса",
        "owner": parsed.get("owner"),
        "urgency": parsed.get("urgency", "medium"),
        "horizon_hours": int(parsed.get("horizon_hours") or 24),
        "rationale": parsed.get("rationale"),
        "expected_impact": parsed.get("expected_impact"),
        "confidence": float(resp.get("confidence") or 0.7),
        "tokens_total": int(resp.get("tokens_total") or 0),
        "mock": bool(resp.get("mock")),
        "provider": resp.get("provider"),
    }


async def _t_find_opportunities_in_contact(args: Dict[str, Any]) -> Dict[str, Any]:
    """Surface upsell / cross-sell / retention signals for a contact.

    Pulls prior interactions from MemPalace (best-effort) and asks DeepSeek
    to enumerate concrete monetary opportunities.
    """
    contact_id = (args.get("contact_id") or "").strip()
    contact_context = (args.get("context") or args.get("notes") or "").strip()
    if not contact_id and not contact_context:
        return {"ok": False, "error": "contact_id or context required"}

    # Best-effort context retrieval from MemPalace
    mem_snippets: List[str] = []
    if contact_id:
        try:
            from agents import mempalace_bridge as mempalace_agent
            bridge = mempalace_agent.get_mempalace()
            results = await bridge.search(
                query=f"contact {contact_id}", top_k=5,
            )
            for r in results or []:
                snippet = r.get("content") or r.get("text") or ""
                if snippet:
                    mem_snippets.append(snippet[:400])
        except Exception as e:  # noqa: BLE001
            logger.warning("mempalace lookup for contact failed: %s", e)

    system = (
        "Ты — Hermes COO + revenue strategist NXT8. Найди реальные monetisation "
        "opportunities (upsell, cross-sell, renewal, retention). "
        "Ответ строго fenced-JSON:\n"
        "```json\n"
        '{"opportunities":['
        '{"type":"upsell|cross-sell|renewal|retention|new-product",'
        '"description":"что предложить","value_usd_min":0,"value_usd_max":0,'
        '"confidence":0.0,"why_now":"триггер","next_step":"конкретное действие"}'
        "]}\n"
        "```\n"
        "Если данных мало — верни 0-2 гипотезы с честно низким confidence."
    )
    parts = [f"contact_id: {contact_id or '—'}"]
    if contact_context:
        parts.append(f"Контекст:\n{contact_context}")
    if mem_snippets:
        parts.append("Память (последние взаимодействия):\n- " +
                     "\n- ".join(mem_snippets))
    deepseek = get_deepseek()
    resp = await deepseek.chat(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": "\n\n".join(parts)}],
        temperature=0.4, max_tokens=900,
    )
    parsed = _parse_fenced_json(resp.get("content") or "") or {}
    opps = parsed.get("opportunities")
    if not isinstance(opps, list):
        opps = []
    return {
        "ok": True,
        "contact_id": contact_id or None,
        "opportunities": opps,
        "memory_snippets_used": len(mem_snippets),
        "tokens_total": int(resp.get("tokens_total") or 0),
        "mock": bool(resp.get("mock")),
        "provider": resp.get("provider"),
    }


async def _t_suggest_reply_template(args: Dict[str, Any]) -> Dict[str, Any]:
    """Draft a contextual reply (not just canned tone strings)."""
    last_message = (args.get("last_message") or args.get("incoming") or "").strip()
    intent = (args.get("intent") or args.get("goal") or "").strip()
    tone = (args.get("tone") or "professional").lower()
    language = (args.get("language") or "ru").lower()

    if not last_message and not intent:
        # graceful fallback: pure tone template
        canned = {
            "professional": "Здравствуйте! Спасибо за обращение — подготовим ответ в течение 24 часов.",
            "friendly": "Привет! Спасибо, что написали — скоро вернёмся с деталями.",
            "concise": "Принято. Ответим в течение 24ч.",
        }
        return {"ok": True, "template": canned.get(tone, canned["professional"]),
                "tone": tone, "context_used": False, "mock": False}

    system = (
        "Ты — Hermes communications assistant. Напиши ответ на входящее сообщение. "
        "Учти tone, language и intent. Ответ строго fenced-JSON:\n"
        "```json\n"
        '{"subject":"кратко (если письмо)","body":"полный текст ответа",'
        '"call_to_action":"одно конкретное действие","tone":"...","language":"ru|en"}\n'
        "```"
    )
    user = (
        f"Tone: {tone}\nLanguage: {language}\nIntent: {intent or '—'}\n\n"
        f"Входящее сообщение:\n{last_message or '—'}"
    )
    deepseek = get_deepseek()
    resp = await deepseek.chat(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.4, max_tokens=700,
    )
    parsed = _parse_fenced_json(resp.get("content") or "") or {}
    body = parsed.get("body") or (resp.get("content") or "").strip()
    return {
        "ok": True,
        "subject": parsed.get("subject"),
        "template": body,
        "body": body,
        "call_to_action": parsed.get("call_to_action"),
        "tone": parsed.get("tone") or tone,
        "language": parsed.get("language") or language,
        "context_used": True,
        "tokens_total": int(resp.get("tokens_total") or 0),
        "mock": bool(resp.get("mock")),
        "provider": resp.get("provider"),
    }


async def _t_evaluate_action_roi(args: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate ROI of a proposed action using DeepSeek + recent ROI snapshot."""
    action = (args.get("action") or args.get("description") or "").strip()
    if not action:
        return {"ok": False, "error": "action description required"}
    expected_cost = args.get("expected_cost_usd")
    expected_revenue = args.get("expected_revenue_usd")
    horizon_days = int(args.get("horizon_days") or 30)

    # Pull last hour ROI snapshot for context (best-effort, non-blocking)
    roi_snapshot: Dict[str, Any] = {}
    try:
        from agents import roi as roi_agent
        snap = await get_db().roi_history.find_one(
            {}, {"_id": 0}, sort=[("hour_end", -1)],
        )
        if snap:
            roi_snapshot = {
                "hour_roi": snap.get("roi"),
                "total_cost": snap.get("total_cost"),
                "total_revenue": snap.get("total_revenue"),
            }
        _ = roi_agent  # imported for side-effect / future hook
    except Exception as e:  # noqa: BLE001
        logger.warning("roi snapshot lookup failed: %s", e)

    system = (
        "Ты — Profit Intelligence (ROI engine) NXT8. Оцени ROI предложенного "
        "действия. Ответ строго fenced-JSON:\n"
        "```json\n"
        '{"estimated_roi":"low|medium|high|negative",'
        '"value_usd_low":0,"value_usd_high":0,'
        '"horizon_days":30,"cost_estimate_usd":0,'
        '"confidence":0.0,"rationale":"1-3 предложения",'
        '"risks":["..."]}\n'
        "```\n"
        "Если входные данные о cost/revenue указаны — используй их как ориентир."
    )
    context_parts = [f"Action: {action}", f"Horizon: {horizon_days} days"]
    if expected_cost is not None:
        context_parts.append(f"Expected cost (USD): {expected_cost}")
    if expected_revenue is not None:
        context_parts.append(f"Expected revenue (USD): {expected_revenue}")
    if roi_snapshot:
        context_parts.append(
            f"Текущий часовой ROI компании: {roi_snapshot}"
        )
    deepseek = get_deepseek()
    resp = await deepseek.chat(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": "\n".join(context_parts)}],
        temperature=0.3, max_tokens=700,
    )
    parsed = _parse_fenced_json(resp.get("content") or "") or {}
    return {
        "ok": True,
        "estimated_roi": parsed.get("estimated_roi", "medium"),
        "value_usd_low": parsed.get("value_usd_low"),
        "value_usd_high": parsed.get("value_usd_high"),
        "cost_estimate_usd": parsed.get("cost_estimate_usd", expected_cost),
        "horizon_days": int(parsed.get("horizon_days") or horizon_days),
        "confidence": float(parsed.get("confidence") or resp.get("confidence") or 0.6),
        "rationale": parsed.get("rationale"),
        "risks": parsed.get("risks", []),
        "company_roi_context": roi_snapshot or None,
        "tokens_total": int(resp.get("tokens_total") or 0),
        "mock": bool(resp.get("mock")),
        "provider": resp.get("provider"),
    }


# ---------------------------------------------------------------------
# web_search — free DuckDuckGo lookup (no API key needed)
# ---------------------------------------------------------------------
# Lets Hermes pull live external context (news, market info, definitions,
# anything not in MemPalace). Uses `ddgs` lib which scrapes DDG HTML.
# Always rate-limited inside the lib; we cap max_results to keep replies tight.

WEB_SEARCH_MAX_RESULTS = 8


async def _t_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    max_results = int(args.get("max_results") or 5)
    max_results = max(1, min(WEB_SEARCH_MAX_RESULTS, max_results))
    region = (args.get("region") or "wt-wt").strip() or "wt-wt"
    if not query:
        return {"ok": False, "error": "query is required"}

    import asyncio

    def _do_search() -> List[Dict[str, Any]]:
        from ddgs import DDGS

        with DDGS() as ddgs:
            hits = list(
                ddgs.text(
                    query,
                    region=region,
                    safesearch="moderate",
                    max_results=max_results,
                )
            )
        # Normalize keys so the LLM sees a consistent shape.
        out: List[Dict[str, Any]] = []
        for h in hits:
            out.append({
                "title": (h.get("title") or "").strip(),
                "url": h.get("href") or h.get("url") or "",
                "snippet": (h.get("body") or "").strip(),
            })
        return out

    try:
        results = await asyncio.to_thread(_do_search)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"web_search_failed: {e}"}

    return {
        "ok": True,
        "query": query,
        "region": region,
        "count": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------
# fetch_url — read the main readable content of a web page
# ---------------------------------------------------------------------
# Lets Hermes open the URLs surfaced by web_search (or supplied by the user)
# and read the actual article text — not just the snippet. Uses trafilatura
# which strips navigation, ads, footer, and returns the article body.

FETCH_URL_MAX_CHARS = 8000  # hard cap so we don't flood the LLM context
FETCH_URL_DEFAULT_CHARS = 4000


async def _t_fetch_url(args: Dict[str, Any]) -> Dict[str, Any]:
    url = (args.get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "url is required"}
    if not url.lower().startswith(("http://", "https://")):
        return {"ok": False, "error": "url must start with http:// or https://"}

    max_chars = int(args.get("max_chars") or FETCH_URL_DEFAULT_CHARS)
    max_chars = max(500, min(FETCH_URL_MAX_CHARS, max_chars))

    import asyncio

    def _do_fetch() -> Dict[str, Any]:
        import trafilatura

        html = trafilatura.fetch_url(url)
        if not html:
            return {"ok": False, "error": "fetch_failed_or_empty"}
        meta = trafilatura.extract_metadata(html)
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        ) or ""
        original_len = len(text)
        truncated = False
        if original_len > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "…"
            truncated = True
        out = {
            "ok": True,
            "url": url,
            "title": (getattr(meta, "title", None) if meta else None) or "",
            "author": (getattr(meta, "author", None) if meta else None) or "",
            "date": (getattr(meta, "date", None) if meta else None) or "",
            "sitename": (getattr(meta, "sitename", None) if meta else None) or "",
            "chars": len(text),
            "original_chars": original_len,
            "truncated": truncated,
            "content": text,
        }
        return out

    try:
        result = await asyncio.to_thread(_do_fetch)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"fetch_url_failed: {e}"}

    return result


# ---------------------------------------------------------------------
# Hermes Evolution Engine wrappers (Directive §4-§11)
# ---------------------------------------------------------------------
# Thin pass-throughs so the unified tool registry can dispatch to the
# evolution module while keeping its implementation isolated.

from agents.hermes_evolution import (   # noqa: E402
    propose_improvement as _ev_propose_improvement,
    list_evolution_roadmap as _ev_list_evolution_roadmap,
    approve_proposal as _ev_approve_proposal,
    propose_policy as _ev_propose_policy,
    list_policy_proposals as _ev_list_policy_proposals,
    detect_automation_candidates as _ev_detect_automation_candidates,
    hermes_self_assessment as _ev_hermes_self_assessment,
)


async def _t_propose_improvement(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_propose_improvement(args)


async def _t_list_evolution_roadmap(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_list_evolution_roadmap(args)


async def _t_approve_proposal(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_approve_proposal(args)


async def _t_propose_policy(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_propose_policy(args)


async def _t_list_policy_proposals(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_list_policy_proposals(args)


async def _t_detect_automation_candidates(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_detect_automation_candidates(args)


async def _t_hermes_self_assessment(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ev_hermes_self_assessment(args)


# ---------------------------------------------------------------------
# Inter-agent communication (CEO → subordinate, subordinate → CEO, peer↔peer)
# ---------------------------------------------------------------------

from agents.inter_agent import (  # noqa: E402
    delegate_to_agent as _ia_delegate_to_agent,
    escalate_to_hermes as _ia_escalate_to_hermes,
    ask_colleague as _ia_ask_colleague,
)


async def _t_delegate_to_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    # Hermes is the only legitimate caller — pin from_agent explicitly.
    args = {**args, "from_agent": "hermes"}
    return await _ia_delegate_to_agent(args)


async def _t_escalate_to_hermes(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ia_escalate_to_hermes(args)


async def _t_ask_colleague(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _ia_ask_colleague(args)


# =====================================================================
# Unified tool registry
# =====================================================================


HERMES_TOOLS: Dict[str, Any] = {
    # Core real-side-effect tools
    "search_memory": _t_search_memory,
    "create_task": _t_create_task,
    "update_task": _t_update_task,
    "create_followup": _t_create_followup,
    "create_cross_department_bridge": _t_create_cross_department_bridge,
    "monitor_sla_violations": _t_monitor_sla_violations,
    "detect_bottlenecks": _t_detect_bottlenecks,
    "generate_daily_digest": _t_generate_daily_digest,
    "mempalace_search": _t_mempalace_search,
    "mempalace_store": _t_mempalace_store,
    # Communications & opportunity tools — real LLM-backed (DeepSeek)
    "generate_communication_summary": _t_generate_communication_summary,
    "suggest_next_best_action": _t_suggest_next_best_action,
    "find_opportunities_in_contact": _t_find_opportunities_in_contact,
    "suggest_reply_template": _t_suggest_reply_template,
    "evaluate_action_roi": _t_evaluate_action_roi,
    # External world — free DuckDuckGo web search
    "web_search": _t_web_search,
    "fetch_url": _t_fetch_url,
    # Hermes Evolution Engine (Directive §4-§11)
    "propose_improvement":           _t_propose_improvement,
    "list_evolution_roadmap":        _t_list_evolution_roadmap,
    "approve_proposal":              _t_approve_proposal,
    "propose_policy":                _t_propose_policy,
    "list_policy_proposals":         _t_list_policy_proposals,
    "detect_automation_candidates":  _t_detect_automation_candidates,
    "hermes_self_assessment":        _t_hermes_self_assessment,
    # Inter-agent communication
    "delegate_to_agent":             _t_delegate_to_agent,
    "escalate_to_hermes":            _t_escalate_to_hermes,
    "ask_colleague":                 _t_ask_colleague,
}


_TOOLS_DOC = (
    "Доступные инструменты (вызывать строго fenced-JSON):\n"
    "- `search_memory(query, top_k?)` — поиск по корп. памяти\n"
    "- `create_task(title, description?, department?, priority?, due_at?, kind?)` — задача\n"
    "- `update_task(task_id, status?, priority?, ...)` — обновить\n"
    "- `create_followup(title, message, recipients, priority?, due_in_days?)` — follow-up задача\n"
    "- `create_cross_department_bridge(from_dept, to_dept, description?)` — мост между отделами\n"
    "- `monitor_sla_violations()` — просроченные задачи\n"
    "- `detect_bottlenecks(department?)` — здоровье процессов\n"
    "- `generate_daily_digest(recipient_user_id, period?)` — оперативный дайджест\n"
    "- `mempalace_search(query, wing?, room?, top_k?)` — долговременная память\n"
    "- `mempalace_store(content, wing?, room?)` — записать факт\n"
    "- `suggest_reply_template(last_message, intent?, tone?, language?)` — драфт ответа\n"
    "- `suggest_next_best_action(context, goal?)` — NBA с обоснованием\n"
    "- `find_opportunities_in_contact(contact_id?, context?)` — upsell/cross-sell\n"
    "- `evaluate_action_roi(action, expected_cost_usd?, expected_revenue_usd?, horizon_days?)` — оценка ROI\n"
    "- `generate_communication_summary(text|messages)` — резюме переписки\n"
    "- `web_search(query, max_results?, region?)` — поиск в интернете (DuckDuckGo) — используй когда нужны свежие новости, "
    "определения, цены, имена компаний, факты которых нет во внутренней памяти. region по умолчанию `wt-wt` (мир), для рунета используй `ru-ru`.\n"
    "- `fetch_url(url, max_chars?)` — открыть страницу по URL и прочитать её основной текст (без меню/рекламы). "
    "Используй ПОСЛЕ web_search, когда нужны подробности из конкретной статьи. max_chars по умолчанию 4000, максимум 8000.\n"
    "- `propose_improvement(area, description, expected_benefit?, business_impact?, priority?)` — "
    "записать предложение по развитию NXT8 в Evolution Journal. area: capability/agent/integration/architecture/product/process/policy. priority: P0..P3.\n"
    "- `list_evolution_roadmap(area?, status?, limit?)` — прочитать journal (что уже предложено).\n"
    "- `approve_proposal(id, status)` — перевести предложение в approved/rejected/done.\n"
    "- `propose_policy(title, scope, proposed_rule, justification?, severity?)` — предложить новый регламент компании.\n"
    "- `list_policy_proposals(status?, limit?)` — прочитать список предложенных правил.\n"
    "- `detect_automation_candidates(window?, min_count?)` — найти повторяющиеся ручные intent'ы для автоматизации.\n"
    "- `hermes_self_assessment(window?)` — посмотреть свои метрики (confidence/escalation/mock_rate + журнал).\n"
    "- `delegate_to_agent(agent_id, task, context?)` — как CEO передать конкретную задачу подчинённому "
    "(hr_mentor/client_manager/project_coord/analyst/bookkeeper/marketer/compliance) и получить его ответ. "
    "ИСПОЛЬЗУЙ когда вопрос узкоспециализированный — не тяни одеяло на себя.\n"
    "- `escalate_to_hermes(reason, evidence?, urgency?, from_agent, question?)` — путь СНИЗУ ВВЕРХ "
    "(для подчинённых, не для тебя). Когда подчинённый эскалирует тебе — ты увидишь это в db.escalations.\n"
    "- `ask_colleague(from_agent, agent_id, question, context?)` — peer-to-peer между подчинёнными "
    "(не для тебя, используется в делегированных задачах)."
)


# =====================================================================
# Tool-call extraction (fenced-JSON convention)
# =====================================================================

_TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\"tool\".*?\})\s*```", re.DOTALL | re.IGNORECASE
)


def extract_tool_calls(content: str) -> List[Dict[str, Any]]:
    if not content:
        return []
    calls: List[Dict[str, Any]] = []
    for match in _TOOL_JSON_RE.findall(content):
        try:
            obj = json.loads(match)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("tool") in HERMES_TOOLS:
            calls.append({"id": str(uuid.uuid4())[:8],
                          "name": obj["tool"], "args": obj.get("args") or {}})
    return calls


# =====================================================================
# Chat function (single unified entry point)
# =====================================================================


def _system_prompt(mode: str = "operational", autonomy: str = "assistant") -> str:
    from agents.agent_charter import CHARTER
    from agents.manifests import render_manifest_for_prompt, render_team_for_prompt
    from agents.hermes_directive import DIRECTIVE
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"{CHARTER}\n\n"
        f"{DIRECTIVE}\n\n"
        f"{render_manifest_for_prompt('hermes')}\n\n"
        f"{render_team_for_prompt('hermes', include_self=False)}\n\n"
        "Ты — Hermes, Chief Operating Officer Agent NXT8.PRO. Сердце операционной "
        "системы компании.\n\n"
        f"Режим: {mode}; Автономность: {autonomy.upper()}; Дата: {today}\n\n"
        "Твои обязанности:\n"
        "- Выявлять bottleneck'и и блоки между отделами\n"
        "- Делать follow-up по задачам, сделкам и коммуникациям\n"
        "- Предлагать Next Best Action в реальном времени\n"
        "- Кросс-департаментная координация и SLA-мониторинг\n"
        "- Генерировать operational digests для руководителей\n\n"
        "Длина и формат ответа выбираются под запрос — не под шаблон:\n"
        "• Операционная задача (что делать / приоритеты / план) — структурно: "
        "Summary → Что важно → Действия → Ожидаемый эффект.\n"
        "• Информационный или общий вопрос (что это, расскажи, объясни, как устроено, "
        "о проекте, о компании) — отвечай развёрнуто, человеческим языком, без "
        "обязательных секций. Не сжимай, если тема требует контекста.\n"
        "• Короткий уточняющий вопрос или small-talk — отвечай коротко и по делу.\n"
        "Никогда не обрывай ответ на полуслове ради краткости. Лимит ответа большой "
        "(до ~8000 токенов) — используй его, если тема требует, но без воды.\n\n"
        "## ВЕДЕНИЕ ДИАЛОГА (важно)\n"
        "Ты — CEO, который разговаривает с клиентом, а не справочный бот. "
        "В КОНЦЕ КАЖДОГО содержательного ответа (кроме чистого small-talk) "
        "задавай 1-2 короткие встречные вопроса, которые:\n"
        "  • уточняют контекст бизнеса клиента (сфера, размер команды, цели);\n"
        "  • открывают следующий полезный шаг (что попробуем дальше, какой "
        "тариф ближе, нужен ли пилот);\n"
        "  • либо приглашают копнуть глубже в обсуждаемую тему.\n"
        "Оформляй их в блоке «🤔 Чтобы помочь точнее:» или просто естественно "
        "в финальной фразе («Расскажешь, как у тебя сейчас устроено …?»). "
        "Не задавай шаблонных «Чем ещё могу помочь?» — это ленивый ход. "
        "Спрашивай только то, что реально нужно для следующего полезного "
        "действия.\n\n"
        "Если нужен инструмент — вызови его строго в формате fenced-JSON:\n"
        "```json\n"
        '{"tool":"<name>","args":{...}}\n'
        "```\n"
        "Можно несколько блоков подряд. После выполнения тебе вернут результат, "
        "и ты сделаешь финальный структурированный ответ.\n"
        "Не выполняй критические действия (create_*, update_*, *_bridge) без "
        "подтверждения, если autonomy != controlled_automation.\n\n"
        "ВНЕШНИЙ МИР: если пользователь спросил про что-то, чего нет во внутренних "
        "данных (свежие новости, цены, факты о компаниях, определения, события, погоду, "
        "людей, спорт, политику и т.п.) — обязательно вызови `web_search` перед ответом. "
        "Не выдумывай факты — найди или скажи что не нашёл.\n\n"
        f"{_TOOLS_DOC}"
    )


async def hermes_chat(
    messages: List[Dict[str, Any]],
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "operational",
    autonomy_level: str = "assistant",
    temperature: float = 0.3,
    model: Optional[str] = None,  # accepted for back-compat, ignored
) -> Dict[str, Any]:
    """Unified Hermes chat: DeepSeek + fenced-JSON tool loop.

    Replaces legacy `hermes_coo.enhanced_chat` and `hermes_max...hermes_coo_chat`.

    Pre-step: every incoming turn is first classified by `agents.classifier`.
    Non-business traffic (jokes, memes, trolling, fantasy match-ups, idle
    small-talk) is delegated to the isolated JOKER sandbox so it never
    touches MemPalace, tasks, or the operational core. The classifier runs
    on EVERY turn — so when a user goes back to a business topic, control
    automatically returns to Hermes on the very next message.
    """
    company = (company_id or DEFAULT_COMPANY).strip() or DEFAULT_COMPANY

    # ---- JOKER sandbox routing -------------------------------------
    # Look at the LAST user message only; that is what the user just sent.
    last_user_msg = ""
    history_for_joker: List[Dict[str, Any]] = []
    for m in (messages or []):
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content") if isinstance(m.get("content"), str) else ""
        if role == "user":
            last_user_msg = content
            history_for_joker.append({"role": "user", "content": content})
        elif role == "assistant":
            history_for_joker.append({"role": "assistant", "content": content})

    if last_user_msg.strip():
        # Feature-flag: JOKER is benched until further notice. Keep the
        # classifier + sandbox code intact so we can re-enable later by
        # flipping JOKER_ENABLED=true in backend/.env. While disabled,
        # every turn — including jokes and small-talk — goes through the
        # normal Hermes path.
        import os as _os
        joker_enabled = (_os.environ.get("JOKER_ENABLED") or "false").strip().lower() in ("1", "true", "yes", "on")
        if joker_enabled:
            try:
                from agents import classifier as _classifier
                from agents import joker as _joker
                verdict = await _classifier.classify(
                    last_user_msg,
                    history=history_for_joker[:-1],  # everything except the current turn
                )
                if verdict.get("route") == "joker":
                    jr = await _joker.respond(
                        message=last_user_msg,
                        session_id=user_id or "anon",
                        history=history_for_joker[:-1],
                        user_id=user_id,
                        lang=("ru" if any(ord(c) > 1000 for c in last_user_msg) else "en"),
                    )
                    # Return payload in the SAME shape Hermes normally returns
                    # so all downstream consumers (server.py / voice / chat panels)
                    # work without changes. Tool traces are empty by definition.
                    return {
                        "content": jr.get("content", ""),
                        "tool_calls": [],
                        "iterations": 0,
                        "company_id": company,
                        "confidence": 0.5,
                        "mock": jr.get("mock", False),
                        "tokens_total": jr.get("tokens_total", 0),
                        "provider": "joker_sandbox",
                        "autonomy_level": autonomy_level,
                        "routed_to": "joker",
                        "routing_reason": verdict.get("reason"),
                        "routing_stage": verdict.get("stage"),
                        "downgraded": jr.get("downgraded", False),
                    }
            except Exception as e:  # noqa: BLE001
                # Classifier or JOKER failure must NEVER block a business request.
                # Fall through to normal Hermes path.
                logger.warning("joker pre-route failed (%s) — falling back to Hermes", e)

    full_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(mode, autonomy_level)},
        {"role": "system", "content": (
            f"Контекст вызова: company_id={company}, user_id={user_id or 'unknown'}, "
            f"mode={mode}, autonomy={autonomy_level}.")},
    ]

    # Auto-inject the client's company manifest (from the onboarding survey)
    # so every Hermes turn — and every tool he triggers — answers WITH the
    # client's industry, team_size, channels, pain_points in mind. This is
    # how the onboarding becomes permanent context, not a one-shot.
    if user_id:
        try:
            from agents.onboarding import get_company_manifest, render_company_manifest_block
            cm = await get_company_manifest(user_id)
            if cm:
                lang = "ru" if cm.get("lang", "").startswith("ru") else "en"
                full_messages.insert(
                    2,
                    {"role": "system",
                     "content": render_company_manifest_block(cm, lang=lang)},
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("company manifest injection failed: %s", e)

    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or "user"
        content = m.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False) if content else ""
        if role not in ("system", "user", "assistant"):
            role = "user"
        full_messages.append({"role": role, "content": content})

    deepseek = get_deepseek()
    tool_traces: List[Dict[str, Any]] = []
    last_content = ""
    iterations = 0
    confidence = 0.7
    mock = False
    tokens_total = 0
    provider = None

    # Pick the right DeepSeek model per request — reasoner for planning /
    # math / debug / long context, cheap chat for everything else.
    from core.complexity_router import pick_model as _pick_model
    chosen_model = _pick_model(full_messages, intent="hermes_chat", role=mode)

    for iteration in range(MAX_TOOL_ITERATIONS + 1):
        iterations = iteration + 1
        resp = await deepseek.chat(messages=full_messages,
                                   temperature=temperature, max_tokens=8000,
                                   model_override=chosen_model)
        last_content = (resp.get("content") or "").strip()
        confidence = float(resp.get("confidence") or 0.7)
        mock = mock or bool(resp.get("mock"))
        tokens_total += int(resp.get("tokens_total") or 0)
        provider = resp.get("provider") or provider

        if iteration >= MAX_TOOL_ITERATIONS:
            break

        tool_calls = extract_tool_calls(last_content)
        if not tool_calls:
            break

        full_messages.append({"role": "assistant", "content": last_content})
        for tc in tool_calls:
            name = tc["name"]
            args = dict(tc.get("args") or {})
            args.setdefault("company_id", company)
            fn = HERMES_TOOLS.get(name)
            try:
                result = await fn(args) if fn else {"ok": False, "error": f"unknown tool: {name}"}
            except Exception as e:  # noqa: BLE001
                logger.exception("hermes tool %s failed", name)
                result = {"ok": False, "error": str(e)}
            tool_traces.append({"name": name, "args": args, "result": result})
            full_messages.append({
                "role": "system",
                "content": f"## Результат `{name}`\n```json\n{json.dumps(result, ensure_ascii=False)[:1500]}\n```",
            })

    return {
        "content": last_content,
        "tool_calls": tool_traces,
        "iterations": iterations,
        "company_id": company,
        "confidence": confidence,
        "mock": mock,
        "tokens_total": tokens_total,
        "provider": provider,
        "autonomy_level": autonomy_level,
    }


# =====================================================================
# Back-compat aliases (do NOT use in new code)
# =====================================================================


async def enhanced_chat(
    messages: List[Dict[str, Any]],
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "operational",
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Legacy alias for `hermes_chat` (formerly in agents/hermes_coo.py)."""
    return await hermes_chat(
        messages=messages, company_id=company_id, user_id=user_id,
        mode=mode, temperature=temperature, model=model,
    )


async def hermes_coo_chat(
    messages: List[Dict[str, Any]],
    company_id: str = DEFAULT_COMPANY,
    autonomy_level: str = "assistant",
) -> Dict[str, Any]:
    """Legacy alias for `hermes_chat` (formerly in agents/hermes_max_tools_and_coo.py).

    Returns the same shape the LangGraph orchestrator expects:
        content, autonomy_level, confidence, mock, tokens_total
    """
    res = await hermes_chat(
        messages=messages, company_id=company_id, mode="operational",
        autonomy_level=autonomy_level, temperature=0.3,
    )
    return {
        "content": res["content"],
        "autonomy_level": autonomy_level,
        "confidence": res["confidence"],
        "mock": res["mock"],
        "tokens_total": res["tokens_total"],
        "tool_calls": res.get("tool_calls", []),
    }
