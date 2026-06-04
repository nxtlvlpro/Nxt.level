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
    # --- New pain mappings introduced by the 9-question onboarding ---
    "owner_overloaded": {
        "title_ru": "Заместитель",
        "title_en": "Deputy",
        "desc_ru": "снимает с вас текущие решения, чтобы вы занимались стратегией",
        "desc_en": "takes the day-to-day decisions off your plate so you can lead",
        "icon": "user-check",
    },
    "no_visibility": {
        "title_ru": "Координатор по команде",
        "title_en": "People coordinator",
        "desc_ru": "видит кто чем занят и где задачи стоят без движения",
        "desc_en": "sees who's doing what and where work has stalled",
        "icon": "users",
    },
    "manual_work": {
        "title_ru": "Автоматизатор",
        "title_en": "Automation lead",
        "desc_ru": "превращает повторяющиеся действия в фоновые процессы",
        "desc_en": "turns repetitive steps into background processes",
        "icon": "zap",
    },
    "no_numbers": {
        "title_ru": "Аналитик",
        "title_en": "Analyst",
        "desc_ru": "собирает цифры бизнеса в один понятный экран без таблиц",
        "desc_en": "puts your business numbers on one clear screen — no spreadsheets",
        "icon": "trending-up",
    },
    "cant_scale": {
        "title_ru": "Стратег роста",
        "title_en": "Growth strategist",
        "desc_ru": "находит узкие места, которые мешают расти, и убирает их",
        "desc_en": "spots the bottlenecks blocking growth and clears them",
        "icon": "rocket",
    },
    "weak_finance_control": {
        "title_ru": "Финансовый контролёр",
        "title_en": "Finance controller",
        "desc_ru": "держит руку на пульсе денег: остатки, оплаты, кассовые разрывы",
        "desc_en": "keeps a hand on the cash: balances, payments, gap forecasts",
        "icon": "wallet",
    },
    "documents_overhead": {
        "title_ru": "Юрист-делопроизводитель",
        "title_en": "Document specialist",
        "desc_ru": "оформляет договоры и документы за минуты, а не за часы",
        "desc_en": "drafts contracts and docs in minutes, not hours",
        "icon": "file-text",
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
    "hot":  {"label_ru": "Начать работу с Hermes",
             "label_en": "Start working with Hermes",
             "action": "contact_now"},
    "warm": {"label_ru": "Получить персональное демо",
             "label_en": "Get a personalised demo",
             "action": "book_demo"},
    "cold": {"label_ru": "Следить за развитием NXT8",
             "label_en": "Follow NXT8's progress",
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
    "management_structure": {
        "owner_only": {"ru": "Когда всё держится на одном человеке, рост упирается в его сутки. Это первое, что мы разгружаем.",
                       "en": "When everything rests on one person, growth hits the limit of their day. That's the first thing we unload."},
        "few_leads":  {"ru": "Несколько руководителей — хорошая база. Hermes выступит координатором между ними.",
                       "en": "A few team leads is a healthy base. Hermes plays the coordinator between them."},
        "full_team":  {"ru": "Полноценная управленческая команда — редкость. С ней Hermes сразу даёт прозрачность по отделам.",
                       "en": "A real management team is rare. With it, Hermes immediately adds cross-department visibility."},
    },
    "communication_channels": {
        "whatsapp":  {"ru": "WhatsApp — главный канал утечки заявок. Здесь автоматизация даёт результат на первой неделе.",
                      "en": "WhatsApp is the #1 channel where leads vanish. Automation pays off in the first week."},
        "telegram":  {"ru": "Telegram удобен для команды и клиентов одновременно. Один из самых быстрых каналов для подключения.",
                      "en": "Telegram works for both team and customers. One of the fastest channels to connect."},
        "instagram": {"ru": "Instagram-сообщения часто теряются в личке. Их можно собрать в общий поток.",
                      "en": "Instagram DMs often disappear into someone's personal inbox. We can route them centrally."},
        "facebook":  {"ru": "Facebook-сообщения подтянем в единую ленту вместе с остальными.",
                      "en": "Facebook messages will join the same unified inbox as the rest."},
        "email":     {"ru": "Email — самый структурированный канал. Здесь хорошо строится автоматизация follow-up.",
                      "en": "Email is the most structured channel. Great for follow-up automation."},
        "phone":     {"ru": "Звонки — самая дорогая коммуникация. Их частично можно перевести в чаты без потери качества.",
                      "en": "Phone calls are the most expensive channel. Some can shift to chat without losing quality."},
        "crm":       {"ru": "Уже есть CRM — отлично. Hermes подключится к ней как координирующий слой над ней.",
                      "en": "You already use a CRM — perfect. Hermes will sit on top of it as the coordinating layer."},
        "other":     {"ru": "Если канал нестандартный — расскажете на следующем шаге, и мы подберём решение.",
                      "en": "If it's a non-standard channel, tell us at the next step and we'll find a fit."},
    },
    "process_system": {
        "head":   {"ru": "Когда процессы «в голове» — это работает до первого пика нагрузки. Hermes выгрузит их аккуратно.",
                   "en": "Processes 'in your head' work until the first big spike. Hermes will get them out gently."},
        "chats":  {"ru": "Задачи в чатах — самая частая причина потери информации. Это лечится единым пространством.",
                   "en": "Tasks in chats are the most common cause of lost information. A single workspace fixes it."},
        "sheets": {"ru": "Таблицы — гибко, но без напоминаний и без статусов. Мы переведём в структуру и добавим контроль.",
                   "en": "Spreadsheets are flexible but lack reminders and statuses. We'll structure them and add control."},
        "notion": {"ru": "Notion — хорошая база. Hermes подключится как операционный слой поверх ваших страниц.",
                   "en": "Notion is a good base. Hermes plugs in as an operations layer on top of your pages."},
        "trello": {"ru": "Trello — простой и понятный. Расширим контроль и автоматику без перехода на другой инструмент.",
                   "en": "Trello is simple and clear. We'll extend control and automation without switching tools."},
        "asana":  {"ru": "Asana — крепкая основа. С ней Hermes сразу даёт сводки и предсказуемость по срокам.",
                   "en": "Asana is solid ground. With it, Hermes adds summaries and predictable deadlines on day one."},
        "crm":    {"ru": "Процессы в CRM — это про продажи. Мы поможем отделить процессы команды от воронки клиентов.",
                   "en": "Processes inside CRM means it's tied to sales. We'll separate internal workflows from the customer funnel."},
        "other":  {"ru": "Свой инструмент — это нормально. Большинство интеграций мы умеем подключать за день.",
                   "en": "Custom tool? Fine — most integrations land in a day."},
    },
    "knowledge_storage": {
        "employees": {"ru": "Знания у сотрудников — самое уязвимое место бизнеса. Это первое, что Hermes выносит в общую базу.",
                      "en": "Knowledge in people's heads is the most fragile asset. Hermes moves it to a shared base first."},
        "gdrive":    {"ru": "Google Drive — отличная база. Hermes подключится для поиска по документам и автоматических подсказок.",
                      "en": "Google Drive is a great base. Hermes will connect for doc search and auto-suggestions."},
        "notion":    {"ru": "Notion для знаний — удобно. Соберём навигацию и поиск через AI без миграции.",
                      "en": "Notion for knowledge — comfortable. We'll add AI navigation and search without migrating."},
        "dropbox":   {"ru": "Dropbox — надёжно. Hermes подключится для индексации и быстрого доступа к контенту.",
                      "en": "Dropbox is dependable. Hermes will index it for quick content access."},
        "local":     {"ru": "Локальные файлы — это риск. Один пожар или потерянный ноутбук — и часть бизнеса исчезает.",
                      "en": "Local files are a risk. One fire or one lost laptop and a piece of the business is gone."},
        "other":     {"ru": "Куда бы вы их ни хранили — мы умеем подключаться к большинству хранилищ.",
                      "en": "Wherever you keep them — we can connect to most storage systems."},
    },
    "pain_points": {
        "leads_lost":            {"ru": "Заявки уходят в тишину — самая дорогая боль. Чинится первой неделей.",
                                  "en": "Leads disappearing into silence — the costliest pain. First-week fix."},
        "low_sales":             {"ru": "Маркетолог + продавец вместе обычно дают +20-40% за квартал.",
                                  "en": "Marketer + sales rep together typically deliver +20-40% within a quarter."},
        "chaos":                 {"ru": "Хаос — самая частая причина обращения. Утренний brief и недельный план — старт.",
                                  "en": "Chaos is the most common reason people call us. Morning brief and weekly plan — that's the start."},
        "owner_overloaded":      {"ru": "Перегрузка руководителя — потолок роста. Это первое, что мы снимаем.",
                                  "en": "Owner overload is the growth ceiling. That's the first thing we relieve."},
        "no_visibility":         {"ru": "Без прозрачности по сотрудникам бизнес слепнет. Hermes сделает картину видимой.",
                                  "en": "Without team visibility a business goes blind. Hermes restores the picture."},
        "manual_work":           {"ru": "Ручная работа — самый быстрый ROI. Сэкономленные часы идут в развитие.",
                                  "en": "Manual work is the fastest ROI. The hours you save go straight into growth."},
        "no_numbers":            {"ru": "Не видеть цифры — это управлять вслепую. Дашборд закроем за неделю.",
                                  "en": "Not seeing the numbers means flying blind. Dashboard ready in a week."},
        "cant_scale":            {"ru": "Часто причина в координации, а не в людях. Найдём узкое место и уберём его.",
                                  "en": "Often the cause is coordination, not headcount. We find the bottleneck and clear it."},
        "weak_finance_control":  {"ru": "Финансовый контроль — это предсказуемость. Бухгалтер закроет риски в первый месяц.",
                                  "en": "Finance control is about predictability. Bookkeeper closes the risks in month one."},
        "documents_overhead":    {"ru": "Договоры за минуты, а не часы — реально. Юрист и автоматизация сделают это.",
                                  "en": "Contracts in minutes, not hours — that's real. Legal + automation do it."},
    },
    "goal_90days": {
        "grow_sales":         {"ru": "+продажи за 90 дней — самая измеримая цель. Подберём связку маркетолог + продавец.",
                               "en": "Sales in 90 days — most measurable goal. We pair a marketer with a sales rep."},
        "order_in_company":   {"ru": "Порядок в компании — это спокойствие. Hermes как операционный директор.",
                               "en": "Order in the company is about calm. Hermes as your operations director."},
        "automate_processes": {"ru": "Автоматизация = вернуть себе 10-15 часов в неделю. Реальная цифра.",
                               "en": "Automation = reclaim 10-15 hours per week. Real number."},
        "scale_business":     {"ru": "Масштабирование — наш любимый сценарий. Кросс-отдельная координация с дня один.",
                               "en": "Scaling — our favorite scenario. Cross-department coordination from day one."},
        "team_control":       {"ru": "Контроль команды — это не про надзор, а про предсказуемость работы.",
                               "en": "Team control is not about surveillance — it's about predictable execution."},
        "financial_clarity":  {"ru": "Прозрачность денег начинается с дашборда. Соберём его на ваших цифрах.",
                               "en": "Financial clarity starts with a dashboard. We'll build it on your numbers."},
        "free_my_time":       {"ru": "Освободить своё время — самая частая цель основателей. Это абсолютно достижимо.",
                               "en": "Freeing up your own time is the most common founder goal. Absolutely achievable."},
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


REQUIRED_FIELDS = ("industry", "team_size", "goal_90days", "urgency", "name")


async def save_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in REQUIRED_FIELDS if not str(payload.get(f) or "").strip()]
    if missing:
        return {"ok": False, "error": f"missing fields: {', '.join(missing)}"}
    profile_id = payload.get("id") or str(uuid.uuid4())

    # The new 9-question onboarding sends `pain_points` (list, up to 3).
    # We keep backward-compat with the old `pain_primary` / `pain_secondary`
    # fields so older clients still work.
    pain_points = list(payload.get("pain_points") or [])
    pain_primary = str(payload.get("pain_primary") or (pain_points[0] if pain_points else ""))
    pain_secondary = str(payload.get("pain_secondary") or (pain_points[1] if len(pain_points) > 1 else ""))
    pain_tertiary = str(pain_points[2] if len(pain_points) > 2 else "")

    # Communication channels: new field. Falls back to legacy `tools_current`
    # so the OLD frontend doesn't break.
    communication_channels = list(payload.get("communication_channels")
                                  or payload.get("tools_current") or [])

    doc = {
        "id":                       profile_id,
        "industry":                 str(payload.get("industry", "other")),
        "industry_template":        INDUSTRY_TEMPLATES.get(payload.get("industry", "other"), {}),
        "team_size":                str(payload.get("team_size", "")),
        "management_structure":     str(payload.get("management_structure") or ""),
        "communication_channels":   communication_channels,
        "process_system":           str(payload.get("process_system") or ""),
        "knowledge_storage":        str(payload.get("knowledge_storage") or ""),
        "pain_points":              pain_points,
        # legacy mirrors
        "has_sales_team":           bool(payload.get("has_sales_team")),
        "has_marketer":             bool(payload.get("has_marketer")),
        "pain_primary":             pain_primary,
        "pain_secondary":           pain_secondary,
        "pain_tertiary":            pain_tertiary,
        "tools_current":            communication_channels,
        "crm_name":                 str(payload.get("crm_name") or ""),
        "goal_90days":              str(payload.get("goal_90days", "")),
        "urgency":                  str(payload.get("urgency", "warm")),
        "name":                     str(payload.get("name") or "Friend"),
        "phone":                    str(payload.get("phone") or ""),
        "telegram":                 str(payload.get("telegram") or ""),
        "email":                    str(payload.get("email") or ""),
        "timezone":                 str(payload.get("timezone") or ""),
        "lang":                     str(payload.get("lang") or "en"),
        "selected_plan":            str(payload.get("selected_plan") or ""),
        "access_code":              str(payload.get("access_code") or ""),
        "test_access":              bool(payload.get("test_access")),
        "status":                   "submitted",
        "created_at":               _now(),
        "updated_at":               _now(),
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
    # New 9-Q flow: pain_points is the canonical list (up to 3).
    # Legacy 7-Q flow: build it from pain_primary + pain_secondary.
    pain_list = list(profile.get("pain_points") or [])
    if not pain_list:
        for p in (profile.get("pain_primary", ""), profile.get("pain_secondary", "")):
            if p:
                pain_list.append(p)
    tools = list(profile.get("communication_channels")
                 or profile.get("tools_current") or [])
    urgency = profile.get("urgency", "warm")
    lang = "ru" if str(profile.get("lang", "en")).startswith("ru") else "en"

    # Professions list (preserves order from pain_points; dedup).
    prof_keys: List[str] = []
    for p in pain_list:
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
  "block4_potential": "string — one paragraph (2-3 sentences) about the growth potential you see, written as if you've already looked at their setup",
  "block5_cta": "string — one short sentence preceding the button"
}
""".strip()


def _system_prompt_for_reply(lang: str) -> str:
    if lang == "ru":
        return (
            "Ты — Гермес, опытный операционный директор. Ты говоришь с предпринимателем "
            "по-человечески, без жаргона, без эмодзи, без воды.\n"
            "Твоя задача — на основе анкеты собрать персональный ответ из 5 блоков. "
            "Клиент должен почувствовать «меня поняли». Никаких общих фраз. "
            "Только конкретика под его нишу и боль.\n"
            "Никогда не выдумывай статистику. Никогда не упоминай таблицы или API.\n"
            + REPLY_SCHEMA_HINT
        )
    return (
        "You are Hermes, a senior operations director talking with a business owner.\n"
        "Speak like a human — no jargon, no emoji, no fluff.\n"
        "Your job: turn the onboarding survey into a personal 5-block reply. "
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
            "intro": f"{name}, я изучил информацию о вашей компании.",
            "block1_understood": (
                "Сейчас значительная часть управления зависит от ручного контроля. "
                "По мере роста это обычно приводит к потере информации, перегрузке руководителя "
                "и замедлению принятия решений."
            ),
            "block2_team": [{"title": p["title"], "desc": p["desc"]} for p in brief["professions"]],
            "block3_in_30_days": [
                "Организую единое пространство для работы компании.",
                "Подключу текущие инструменты и коммуникации.",
                "Настрою контроль задач и подготовлю базу для автоматизации.",
            ],
            "block4_potential": (
                "На основе ваших ответов я вижу значительный потенциал для автоматизации "
                "и систематизации работы компании без смены привычных инструментов. "
                "Часть операционной нагрузки можно постепенно перевести на цифровых специалистов NXT8."
            ),
            "block5_cta": "Один шаг — и я приступаю к работе:",
        }
    return {
        "intro": f"{name}, I've reviewed the information about your company.",
        "block1_understood": (
            "Right now a large part of running the business depends on hands-on control. "
            "As the company grows, this usually leads to information loss, owner overload, "
            "and slower decisions."
        ),
        "block2_team": [{"title": p["title"], "desc": p["desc"]} for p in brief["professions"]],
        "block3_in_30_days": [
            "I'll set up a single workspace for the company.",
            "I'll connect your existing tools and communication channels.",
            "I'll put task control in place and prepare the ground for automation.",
        ],
        "block4_potential": (
            "Based on your answers I see significant potential to automate and systematise "
            "the company's work without changing the tools you already use. Part of the operational "
            "load can be gradually handed off to the NXT8 digital specialists."
        ),
        "block5_cta": "One step and I'm on it:",
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
        "management_structure":   profile.get("management_structure"),
        "communication_channels": profile.get("communication_channels"),
        "process_system":         profile.get("process_system"),
        "knowledge_storage":      profile.get("knowledge_storage"),
        "pain_points":  profile.get("pain_points") or [
            x for x in (profile.get("pain_primary"), profile.get("pain_secondary")) if x
        ],
        "goal_90days": profile.get("goal_90days"),
        "urgency":     profile.get("urgency"),
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
            max_tokens=900,
            request_logprobs=False,
        )
        raw = (resp.get("content") or "").strip()
        # Strip accidental code fences.
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        data = json.loads(raw)
        # Validate shape — fall back if anything is missing.
        if not all(k in data for k in (
            "intro", "block1_understood", "block2_team",
            "block3_in_30_days", "block4_potential", "block5_cta"
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
