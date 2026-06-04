"""
NXT8 Onboarding agent — 7-question intake → personalised Hermes brief.

Triggered by any "Connect" CTA on a tariff card. The flow has three parts:

  1. **Survey** (frontend) — 7 questions, in-line insight after each answer.
  2. **Brief generation** (this module) — deterministic mapping of pain →
     profession, industry → template, urgency → next-step CTA.
  3. **Hermes reply** (this module + DeepSeek) — 4-block JSON response
     rendered as the closing screen of the flow.

This module is intentionally self-contained: it does not import other
agent surfaces. It does write to its own MongoDB collection
`db.client_profiles` and reads the `db.access_codes` collection seeded
with a single hardcoded pilot code `888`.

Public API:
    save_profile(payload) -> {id, ...}
    get_profile(profile_id) -> dict | None
    get_insight(qid, answer, lang) -> str
    build_brief(profile) -> dict
    generate_hermes_reply(profile, brief, lang) -> dict
    verify_access_code(code) -> {valid, label} | {valid: False}
    seed_default_codes() -> None  # called at startup
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.onboarding")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Static configuration tables
# =====================================================================

# Industry → preset that downstream agents will use as a starting context.
INDUSTRY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "edu":       {"label_ru": "Онлайн-образование", "label_en": "Online education",
                  "focus": ["sales", "marketing"]},
    "services":  {"label_ru": "Услуги (юрист/бухгалтер/консалтинг)",
                  "label_en": "Services (legal/accounting/consulting)",
                  "focus": ["ops", "client_manager"]},
    "ecommerce": {"label_ru": "Торговля / eCommerce", "label_en": "Retail / eCommerce",
                  "focus": ["sales", "bookkeeper"]},
    "manufacturing": {"label_ru": "Производство / поставки",
                  "label_en": "Manufacturing / supply",
                  "focus": ["ops", "compliance"]},
    "wellness":  {"label_ru": "Медицина / wellness",
                  "label_en": "Medical / wellness", "focus": ["client_manager", "compliance"]},
    "realestate": {"label_ru": "Недвижимость", "label_en": "Real estate",
                  "focus": ["sales", "compliance"]},
    "horeca":    {"label_ru": "HoReCa", "label_en": "HoReCa",
                  "focus": ["ops", "marketing"]},
    "saas":      {"label_ru": "IT / SaaS", "label_en": "IT / SaaS",
                  "focus": ["marketing", "ops"]},
    "other":     {"label_ru": "Другое", "label_en": "Other",
                  "focus": ["ops"]},
}

# Pain → primary profession (the "Кто будет работать с вами" Block-2 card).
# Each entry has a profession name (RU+EN) and a one-line human description.
PROFESSIONS: Dict[str, Dict[str, Any]] = {
    "leads_lost": {
        "title_ru": "Продавец",
        "title_en": "Sales rep",
        "desc_ru": "отвечает клиентам в WhatsApp и Telegram пока вы заняты другим",
        "desc_en": "replies to leads on WhatsApp & Telegram while you are busy",
        "icon": "headset",
    },
    "chaos": {
        "title_ru": "Операционный директор",
        "title_en": "Operations director",
        "desc_ru": "ставит задачи команде каждое утро и следит за дедлайнами",
        "desc_en": "assigns morning tasks and tracks deadlines for the team",
        "icon": "compass",
    },
    "low_sales": {
        "title_ru": "Маркетолог",
        "title_en": "Marketer",
        "desc_ru": "подскажет где ищут ваших клиентов и какой канал даёт деньги",
        "desc_en": "tells you where your customers actually live and which channel pays",
        "icon": "megaphone",
    },
    "finance": {
        "title_ru": "Бухгалтер",
        "title_en": "Bookkeeper",
        "desc_ru": "напомнит об оплатах и покажет где утекают деньги",
        "desc_en": "reminds about payments and shows where money quietly leaks",
        "icon": "calculator",
    },
    "legal": {
        "title_ru": "Юрист",
        "title_en": "Legal counsel",
        "desc_ru": "проверяет договоры и предупреждает о рисках до подписания",
        "desc_en": "reviews contracts and flags risks before you sign",
        "icon": "shield",
    },
    "no_clients_source": {
        "title_ru": "Аналитик",
        "title_en": "Analyst",
        "desc_ru": "покажет откуда реально приходят клиенты и сколько они стоят",
        "desc_en": "shows where your customers really come from and what they cost",
        "icon": "bar-chart",
    },
    "routine": {
        "title_ru": "Координатор",
        "title_en": "Coordinator",
        "desc_ru": "забирает повторяющуюся рутину — отчёты, рассылки, напоминания",
        "desc_en": "absorbs repeat busywork — reports, follow-ups, reminders",
        "icon": "repeat",
    },
}

# Tools → integration plan (just labels for now; channels package wires the wires).
TOOL_INTEGRATIONS: Dict[str, Dict[str, str]] = {
    "whatsapp":  {"ru": "WhatsApp Business — авто-ответы и фиксация заявок",
                  "en": "WhatsApp Business — auto-replies and lead capture"},
    "telegram":  {"ru": "Telegram — приём сообщений и команды боту",
                  "en": "Telegram — inbound messages and bot commands"},
    "social":    {"ru": "Соцсети — мониторинг упоминаний и комментариев",
                  "en": "Social — mention tracking and comment triage"},
    "crm":       {"ru": "CRM-коннектор — данные синхронизируются автоматически",
                  "en": "CRM connector — automatic data sync"},
    "sheets":    {"ru": "Google Таблицы — отчёты обновляются сами",
                  "en": "Google Sheets — reports update themselves"},
    "1c":        {"ru": "1С / бухучёт — выгрузка остатков и оплат",
                  "en": "1C / accounting — balances and payments export"},
    "notion":    {"ru": "Notion/Trello/Asana — задачи едут двусторонне",
                  "en": "Notion/Trello/Asana — two-way task sync"},
    "none":      {"ru": "Начнём с базового стека — ничего настраивать не нужно",
                  "en": "We start from a clean stack — no setup required"},
}

# Urgency → ETA + next-step CTA copy.
URGENCY_CTAS: Dict[str, Dict[str, Any]] = {
    "hot":  {"label_ru": "Начать сейчас",   "label_en": "Start now",
             "action": "contact_now"},
    "warm": {"label_ru": "Получить демо",   "label_en": "Get a demo",
             "action": "book_demo"},
    "cold": {"label_ru": "Подписаться на обновления",
             "label_en": "Subscribe to updates",
             "action": "subscribe"},
}

# ---------- Per-question insights (static layer) ----------
# Question id → answer key → {ru, en}.  Hybrid strategy:
# popular combos covered here; missing ones fall back to LLM generation.
INSIGHTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "industry": {
        "edu":         {"ru": "Образование живёт на повторных продажах. Главное — не упустить выпускника после первого курса.",
                        "en": "Education thrives on repeat sales. The trick is not losing students after their first course."},
        "services":    {"ru": "В услугах больше всего теряется на этапе «обещали и забыли». Это лечится одним агентом.",
                        "en": "Service businesses lose the most at the 'we promised and forgot' stage. One agent fixes that."},
        "ecommerce":   {"ru": "В eCommerce каждая минута без ответа = ушедший заказ. Авто-ответ окупится за неделю.",
                        "en": "In eCommerce each silent minute = a lost order. Auto-replies pay back in a week."},
        "manufacturing": {"ru": "Производство тонет в координации между отделами. Это — самый частый запрос на старте.",
                        "en": "Manufacturing drowns in cross-team coordination. That's the most common day-1 request."},
        "wellness":    {"ru": "В медицине ключ — напоминания и follow-up после визита. ROI заметен сразу.",
                        "en": "Healthcare runs on reminders and post-visit follow-ups. ROI shows up immediately."},
        "realestate":  {"ru": "В недвижимости 80% сделок — про скорость ответа. Здесь агент даёт самый быстрый эффект.",
                        "en": "Real estate is 80% about response speed. Agents deliver the fastest measurable win here."},
        "horeca":      {"ru": "HoReCa — это поток: брони, отзывы, заказы. Без автоматизации команда выгорает за месяц.",
                        "en": "HoReCa is a flood: bookings, reviews, orders. Without automation teams burn out in a month."},
        "saas":        {"ru": "IT/SaaS чаще всего просит маркетинг и аналитику. Это то, что мы делаем лучше всего.",
                        "en": "IT/SaaS usually asks for marketing and analytics first. That's exactly our sweet spot."},
        "other":       {"ru": "Нестандартная ниша — это интересно. Соберём конфигурацию под вас.",
                        "en": "A non-standard niche — interesting. We'll build a custom configuration for you."},
    },
    "team_size": {
        "solo":   {"ru": "Соло — это про скорость. Один агент сразу разгружает на 8-12 часов в неделю.",
                   "en": "Solo means speed. One agent frees up 8-12 hours per week immediately."},
        "2-5":    {"ru": "Команда 2-5 — самая отзывчивая на автоматизацию. Эффект виден за пару недель.",
                   "en": "Teams of 2-5 respond fastest to automation. The effect lands within two weeks."},
        "6-20":   {"ru": "В команде 6-20 чаще всего теряются процессы между людьми. Это легко чинится.",
                   "en": "Teams of 6-20 typically leak between people. Easy to fix."},
        "21-50":  {"ru": "21-50 — пора структурировать. Hermes выступит как операционный директор.",
                   "en": "21-50 means it's time to structure. Hermes plays the operations director role."},
        "50+":    {"ru": "Большая команда. Нужен enterprise-сценарий с координацией между отделами.",
                   "en": "A big team — enterprise scenario with cross-department coordination."},
    },
    "pain_primary": {
        "leads_lost": {"ru": "Эта боль решается первой неделей работы. Заявки больше не уйдут в пустоту.",
                       "en": "This pain disappears in the first week. No more leads vanishing into silence."},
        "chaos":      {"ru": "Хаос — самая частая причина обращения. Поставим утренний brief и недельный план.",
                       "en": "Chaos is the most common reason people call us. Morning briefs and weekly plans incoming."},
        "no_clients_source": {"ru": "Аналитика источников — это первое, что мы настраиваем. Цифры будут уже через 7 дней.",
                       "en": "Channel analytics is what we set up first. You'll see numbers within 7 days."},
        "routine":    {"ru": "Рутина — самый быстрый ROI. Сэкономленные часы переходят в развитие.",
                       "en": "Routine work is the fastest ROI. The hours you save go straight into growth."},
        "low_sales":  {"ru": "Маркетолог + продавец вместе обычно дают +20-40% за квартал.",
                       "en": "Marketer + sales rep together typically deliver +20-40% within a quarter."},
        "finance":    {"ru": "Финансы — это про предсказуемость. Бухгалтер закроет кассовые риски в первый месяц.",
                       "en": "Finance is about predictability. Bookkeeper closes cashflow risks in month one."},
        "legal":      {"ru": "Юридические риски — это спокойный сон. Проверим всё что подписано и что собираетесь.",
                       "en": "Legal risk is about peace of mind. We'll vet what you've signed and what you're about to."},
    },
    "goal_90days": {
        "grow_sales":  {"ru": "+продажи за 90 дней — самая измеримая цель. Подберём связку маркетолог + продавец.",
                        "en": "Sales in 90 days — most measurable goal. We pair a marketer with a sales rep."},
        "order_processes": {"ru": "Порядок в процессах — это про спокойствие. Hermes как операционный директор.",
                        "en": "Process clarity is about calm. Hermes as your operations director."},
        "cut_costs":   {"ru": "Сокращение расходов начинается с прозрачности. Бухгалтер покажет где течёт.",
                        "en": "Cost cuts start with transparency. Bookkeeper shows where it leaks."},
        "scale":       {"ru": "Масштабирование — наш любимый сценарий. Закладываем мульти-отдельную координацию.",
                        "en": "Scaling — our favorite scenario. We design cross-department coordination from day one."},
        "automate":    {"ru": "Автоматизация = вернуть себе 10-15 часов в неделю. Реальная цифра, проверено.",
                        "en": "Automation = reclaim 10-15 hours per week. Real number, measured."},
        "legal_safety": {"ru": "Юридическая защита — это про сон без тревоги. Все договоры под надзором юриста.",
                        "en": "Legal safety is about sleeping at night. Every contract reviewed by counsel."},
    },
    "urgency": {
        "hot":  {"ru": "Огонь — запустимся в течение 24 часов после оплаты. Никаких ожиданий.",
                 "en": "On fire — we launch within 24 hours of payment. No queues."},
        "warm": {"ru": "Хороший темп. Демо за 15 минут покажет точно ли мы вам подходим.",
                 "en": "Healthy pace. A 15-minute demo will show if we're the right fit."},
        "cold": {"ru": "Изучайте спокойно. Мы пришлём дайджест раз в неделю — без спама.",
                 "en": "Take your time. We'll send a weekly digest — no spam."},
    },
}


def _industry_focus(industry: str) -> List[str]:
    tpl = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["other"])
    return list(tpl.get("focus") or [])


# =====================================================================
# Access codes (5a — single hardcoded pilot code = 888)
# =====================================================================

DEFAULT_CODES = [
    {"code": "888", "label": "Pilot 2026", "max_uses": 10000, "active": True},
]


async def seed_default_codes() -> None:
    db = get_db()
    for c in DEFAULT_CODES:
        try:
            await db.access_codes.update_one(
                {"code": c["code"]},
                {"$setOnInsert": {**c, "used_count": 0, "created_at": _now()}},
                upsert=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("seed_default_codes failed for %s: %s", c["code"], e)


async def verify_access_code(code: str) -> Dict[str, Any]:
    """Returns {valid, label} or {valid: False, reason}."""
    code = (code or "").strip()
    if not code or not re.fullmatch(r"\d{3}", code):
        return {"valid": False, "reason": "format"}
    db = get_db()
    row = await db.access_codes.find_one({"code": code, "active": True})
    if not row:
        return {"valid": False, "reason": "unknown"}
    used = int(row.get("used_count") or 0)
    cap = int(row.get("max_uses") or 0)
    if cap and used >= cap:
        return {"valid": False, "reason": "exhausted"}
    return {"valid": True, "label": row.get("label", "")}


async def consume_access_code(code: str) -> bool:
    code = (code or "").strip()
    if not code:
        return False
    db = get_db()
    res = await db.access_codes.update_one(
        {"code": code, "active": True},
        {"$inc": {"used_count": 1}, "$set": {"last_used_at": _now()}},
    )
    return res.modified_count > 0


# =====================================================================
# Insight resolution (4c — hybrid: static + LLM fallback)
# =====================================================================


def _static_insight(qid: str, answer: str, lang: str) -> Optional[str]:
    q_map = INSIGHTS.get(qid) or {}
    a_map = q_map.get(answer) or {}
    return a_map.get(lang) or a_map.get("en")


async def get_insight(qid: str, answer: str, lang: str = "en") -> Dict[str, Any]:
    """Return {text, source: 'static'|'llm'}."""
    lang_key = "ru" if (lang or "").lower().startswith("ru") else "en"
    static = _static_insight(qid, str(answer or ""), lang_key)
    if static:
        return {"text": static, "source": "static"}

    # LLM fallback for unmapped combinations.
    sys = (
        "You are a friendly business strategist. Given a single onboarding "
        "answer, write ONE short insight (max 22 words) starting with a strong "
        "noun phrase, no fluff, no emoji, no hedging. Reply in "
        f"{'Russian' if lang_key == 'ru' else 'English'} only."
    )
    user = f"Question: {qid}\nAnswer: {answer}"
    try:
        ds = get_deepseek()
        resp = await ds.chat(
            messages=[{"role": "system", "content": sys},
                      {"role": "user",   "content": user}],
            temperature=0.6,
            max_tokens=80,
            request_logprobs=False,
        )
        text = (resp.get("content") or "").strip()
        # Single-sentence cap.
        text = re.split(r"(?<=[\.\!\?])\s", text, maxsplit=1)[0][:200]
        return {"text": text or "OK", "source": "llm"}
    except Exception as e:  # noqa: BLE001
        logger.warning("insight LLM fallback failed: %s", e)
        return {"text": "OK", "source": "fallback"}


# =====================================================================
# Profile persistence
# =====================================================================


REQUIRED_FIELDS = ("industry", "team_size", "pain_primary", "goal_90days", "urgency", "name")


async def save_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in REQUIRED_FIELDS if not str(payload.get(f) or "").strip()]
    if missing:
        return {"ok": False, "error": f"missing fields: {', '.join(missing)}"}
    profile_id = payload.get("id") or str(uuid.uuid4())
    doc = {
        "id":                  profile_id,
        "industry":            str(payload.get("industry", "other")),
        "industry_template":   INDUSTRY_TEMPLATES.get(payload.get("industry", "other"), {}),
        "team_size":           str(payload.get("team_size", "")),
        "has_sales_team":      bool(payload.get("has_sales_team")),
        "has_marketer":        bool(payload.get("has_marketer")),
        "pain_primary":        str(payload.get("pain_primary", "")),
        "pain_secondary":      str(payload.get("pain_secondary", "")),
        "tools_current":       list(payload.get("tools_current") or []),
        "crm_name":            str(payload.get("crm_name") or ""),
        "goal_90days":         str(payload.get("goal_90days", "")),
        "urgency":             str(payload.get("urgency", "warm")),
        "name":                str(payload.get("name") or "Friend"),
        "phone":               str(payload.get("phone") or ""),
        "telegram":            str(payload.get("telegram") or ""),
        "timezone":            str(payload.get("timezone") or ""),
        "lang":                str(payload.get("lang") or "en"),
        "selected_plan":       str(payload.get("selected_plan") or ""),
        "access_code":         str(payload.get("access_code") or ""),
        "test_access":         bool(payload.get("test_access")),
        "status":              "submitted",
        "created_at":          _now(),
        "updated_at":          _now(),
    }
    db = get_db()
    await db.client_profiles.update_one(
        {"id": profile_id}, {"$set": doc}, upsert=True,
    )
    return {"ok": True, **doc}


async def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await db.client_profiles.find_one({"id": profile_id})
    if doc:
        doc.pop("_id", None)
    return doc


# =====================================================================
# Brief builder (deterministic part)
# =====================================================================


def build_brief(profile: Dict[str, Any]) -> Dict[str, Any]:
    industry = profile.get("industry", "other")
    pain_primary = profile.get("pain_primary", "")
    pain_secondary = profile.get("pain_secondary", "")
    tools = list(profile.get("tools_current") or [])
    urgency = profile.get("urgency", "warm")
    lang = "ru" if str(profile.get("lang", "en")).startswith("ru") else "en"

    # Professions list (primary pain first, then secondary, dedup).
    prof_keys: List[str] = []
    for p in (pain_primary, pain_secondary):
        if p and p in PROFESSIONS and p not in prof_keys:
            prof_keys.append(p)
    # Always add an Ops anchor if not already present (Hermes role).
    if "chaos" not in prof_keys and len(prof_keys) < 3:
        prof_keys.append("chaos")
    # Take at most 3.
    prof_keys = prof_keys[:3]
    professions = []
    for k in prof_keys:
        p = PROFESSIONS[k]
        professions.append({
            "key": k,
            "title": p[f"title_{lang}"],
            "desc":  p[f"desc_{lang}"],
            "icon":  p["icon"],
        })

    # Integration plan from tools.
    integ: List[Dict[str, str]] = []
    seen = set()
    for t in tools:
        if t in seen:
            continue
        seen.add(t)
        i = TOOL_INTEGRATIONS.get(t)
        if i:
            integ.append({"tool": t, "plan": i[lang]})
    if not integ:
        integ.append({"tool": "none", "plan": TOOL_INTEGRATIONS["none"][lang]})

    cta = URGENCY_CTAS.get(urgency, URGENCY_CTAS["warm"])

    return {
        "industry":      industry,
        "industry_focus": _industry_focus(industry),
        "professions":   professions,
        "integrations":  integ,
        "urgency":       urgency,
        "cta": {
            "label":  cta[f"label_{lang}"],
            "action": cta["action"],
        },
        "lang": lang,
    }


# =====================================================================
# Hermes reply (LLM with strict 4-block JSON schema)
# =====================================================================


REPLY_SCHEMA_HINT = """
Return STRICT JSON ONLY (no markdown, no fences) with exactly this shape:
{
  "intro": "string — one line that addresses the user by name",
  "block1_understood": "string — 2 short sentences summarising their situation in their own words",
  "block2_team": [
    {"title": "string", "desc": "string"},
    {"title": "string", "desc": "string"}
  ],
  "block3_in_30_days": ["string", "string", "string"],
  "block4_cta": "string — one short sentence preceding the button"
}
""".strip()


def _system_prompt_for_reply(lang: str) -> str:
    if lang == "ru":
        return (
            "Ты — Гермес, опытный операционный директор. Ты говоришь с предпринимателем "
            "по-человечески, без жаргона, без эмодзи, без воды.\n"
            "Твоя задача — на основе анкеты собрать персональный ответ из 4 блоков. "
            "Клиент должен почувствовать «меня поняли». Никаких общих фраз. "
            "Только конкретика под его нишу и боль.\n"
            "Никогда не выдумывай статистику. Никогда не упоминай таблицы или API.\n"
            + REPLY_SCHEMA_HINT
        )
    return (
        "You are Hermes, a senior operations director talking with a business owner.\n"
        "Speak like a human — no jargon, no emoji, no fluff.\n"
        "Your job: turn the onboarding survey into a personal 4-block reply. "
        "The client must feel 'they understood me'. No generic phrases. "
        "Be specific to their industry and primary pain.\n"
        "Never invent statistics. Never reference tables or APIs.\n"
        + REPLY_SCHEMA_HINT
    )


def _fallback_reply(profile: Dict[str, Any], brief: Dict[str, Any]) -> Dict[str, Any]:
    """Returned when the LLM call fails or output cannot be parsed."""
    name = profile.get("name", "Friend")
    lang = brief.get("lang", "en")
    if lang == "ru":
        return {
            "intro": f"{name}, вот что я вижу по вашей ситуации:",
            "block1_understood": (
                "Вы хотите больше управляемости и меньше хаоса в ежедневной работе. "
                "Ваши ответы показывают конкретные точки, где автоматизация даст эффект "
                "уже в первые недели."
            ),
            "block2_team": [{"title": p["title"], "desc": p["desc"]} for p in brief["professions"]],
            "block3_in_30_days": [
                "Ни одна заявка не останется без ответа.",
                "Команда будет получать чёткий план каждое утро.",
                "Вы увидите, откуда реально приходят деньги.",
            ],
            "block4_cta": "Один шаг — и команда подключается:",
        }
    return {
        "intro": f"{name}, here's what I see in your situation:",
        "block1_understood": (
            "You want more control and less chaos in day-to-day work. "
            "Your answers point to specific spots where automation pays back "
            "within the first weeks."
        ),
        "block2_team": [{"title": p["title"], "desc": p["desc"]} for p in brief["professions"]],
        "block3_in_30_days": [
            "No lead will go unanswered.",
            "Your team gets a crisp morning plan every day.",
            "You'll see where the money actually comes from.",
        ],
        "block4_cta": "One step and the team is on:",
    }


async def generate_hermes_reply(
    profile: Dict[str, Any],
    brief: Dict[str, Any],
    lang: str = "en",
) -> Dict[str, Any]:
    lang_key = "ru" if (lang or "").lower().startswith("ru") else "en"
    sys = _system_prompt_for_reply(lang_key)
    # Compact, structured user message — the LLM doesn't need the full document.
    user_blob = {
        "name":         profile.get("name"),
        "industry":     profile.get("industry"),
        "team_size":    profile.get("team_size"),
        "pain_primary": profile.get("pain_primary"),
        "pain_secondary": profile.get("pain_secondary"),
        "goal_90days": profile.get("goal_90days"),
        "urgency":     profile.get("urgency"),
        "tools":       profile.get("tools_current"),
        "professions_picked": [p["title"] for p in brief["professions"]],
        "integration_plan":   [i["plan"] for i in brief["integrations"]],
    }
    try:
        ds = get_deepseek()
        resp = await ds.chat(
            messages=[
                {"role": "system", "content": sys},
                {"role": "user",   "content": json.dumps(user_blob, ensure_ascii=False)},
            ],
            temperature=0.5,
            max_tokens=700,
            request_logprobs=False,
        )
        raw = (resp.get("content") or "").strip()
        # Strip accidental code fences.
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        data = json.loads(raw)
        # Validate shape — fall back if anything is missing.
        if not all(k in data for k in (
            "intro", "block1_understood", "block2_team",
            "block3_in_30_days", "block4_cta"
        )):
            raise ValueError("missing keys")
        if not isinstance(data["block2_team"], list) or not data["block2_team"]:
            raise ValueError("block2_team empty")
        if not isinstance(data["block3_in_30_days"], list) or len(data["block3_in_30_days"]) < 2:
            raise ValueError("block3 too short")
        return {"ok": True, "source": "llm", **data}
    except Exception as e:  # noqa: BLE001
        logger.warning("hermes reply LLM failed: %s — using fallback", e)
        return {"ok": True, "source": "fallback", **_fallback_reply(profile, brief)}


# =====================================================================
# Funnel stats (Ops dashboard later)
# =====================================================================


async def funnel_stats(days: int = 30) -> Dict[str, Any]:
    db = get_db()
    since = datetime.now(timezone.utc).timestamp() - days * 86400
    since_iso = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
    total = await db.client_profiles.count_documents({"created_at": {"$gte": since_iso}})
    hot = await db.client_profiles.count_documents({"urgency": "hot", "created_at": {"$gte": since_iso}})
    warm = await db.client_profiles.count_documents({"urgency": "warm", "created_at": {"$gte": since_iso}})
    cold = await db.client_profiles.count_documents({"urgency": "cold", "created_at": {"$gte": since_iso}})
    test_access = await db.client_profiles.count_documents({"test_access": True, "created_at": {"$gte": since_iso}})
    return {
        "days": days, "total": total,
        "hot": hot, "warm": warm, "cold": cold,
        "test_access": test_access,
    }
