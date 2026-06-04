"""
Company Context — single source of truth about WHERE and IN WHAT the company operates.

Stored as a singleton-ish document in `db.company_settings` keyed by `company_id`
(default = "default"). Every persona reads this before answering so:

- Compliance Officer cites the **correct regional regulations** (GDPR vs 152-ФЗ
  vs CCPA vs PIPL vs LGPD vs PDPA…).
- Marketer references **regional market trends, currencies and channels**
  that are actually relevant.
- Bookkeeper uses the company's primary currency in calculations.
- HR-Mentor respects regional labour-law norms (notice periods, PTO, etc.).

This module is intentionally **pure data layer** — agents render their own
view of the context through `render_company_block()`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.company_context")

# Region → primary regulations the company is subject to.
# Compliance Officer reads this map to know which laws to cite.
REGIONAL_REGULATIONS: Dict[str, List[str]] = {
    "RU":  ["152-ФЗ (О персональных данных)", "ТК РФ (трудовой кодекс)",
            "ГК РФ (гражданский кодекс)", "Налоговый кодекс РФ",
            "Закон о рекламе", "ФЗ-54 (онлайн-кассы)"],
    "EU":  ["GDPR", "AI Act (2024)", "ePrivacy Directive",
            "Digital Services Act (DSA)", "Digital Markets Act (DMA)",
            "NIS2 Directive"],
    "US":  ["CCPA (California)", "HIPAA (healthcare)",
            "SOX (public companies)", "FTC Act § 5",
            "GLBA (financial)", "COPPA (children)"],
    "UK":  ["UK GDPR", "Data Protection Act 2018",
            "Equality Act 2010", "Bribery Act 2010"],
    "CN":  ["PIPL (Personal Information Protection Law)",
            "Data Security Law", "Cybersecurity Law"],
    "BR":  ["LGPD (Lei Geral de Proteção de Dados)", "Marco Civil da Internet"],
    "IN":  ["DPDP Act 2023", "IT Act 2000", "Consumer Protection Act 2019"],
    "AE":  ["UAE Personal Data Protection Law (Federal Decree-Law 45/2021)",
            "DIFC Data Protection Law"],
    "SG":  ["PDPA (Singapore)", "Cybersecurity Act"],
    "GLOBAL": ["ISO 27001", "SOC 2", "ISO 9001"],
}

# Region → typical sales/marketing channels and currencies
REGIONAL_MARKET_CONTEXT: Dict[str, Dict[str, Any]] = {
    "RU":  {"currency": "RUB", "primary_channels": ["Telegram", "VK", "Yandex.Direct", "WhatsApp", "Email"]},
    "EU":  {"currency": "EUR", "primary_channels": ["LinkedIn", "Google Ads", "Meta Ads", "Email", "WhatsApp"]},
    "US":  {"currency": "USD", "primary_channels": ["LinkedIn", "Google Ads", "Meta Ads", "Email", "X (Twitter)", "SMS"]},
    "UK":  {"currency": "GBP", "primary_channels": ["LinkedIn", "Google Ads", "Meta Ads", "Email"]},
    "CN":  {"currency": "CNY", "primary_channels": ["WeChat", "Douyin", "Weibo", "Baidu", "Xiaohongshu"]},
    "BR":  {"currency": "BRL", "primary_channels": ["WhatsApp", "Instagram", "Meta Ads", "Google Ads"]},
    "IN":  {"currency": "INR", "primary_channels": ["WhatsApp", "Instagram", "Google Ads", "LinkedIn"]},
    "AE":  {"currency": "AED", "primary_channels": ["LinkedIn", "Instagram", "WhatsApp", "Google Ads"]},
    "SG":  {"currency": "SGD", "primary_channels": ["LinkedIn", "Google Ads", "Telegram", "Email"]},
    "GLOBAL": {"currency": "USD", "primary_channels": ["LinkedIn", "Google Ads", "Email"]},
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "company_id":   "default",
    "company_name": "NXT8 Demo Co.",
    "region":       "RU",                  # ISO-2 or "EU"/"GLOBAL"
    "country":      "Russia",
    "industry":     "ecommerce",
    "team_size":    "1-10",
    "currency":     "RUB",
    "primary_language": "ru",
    "secondary_languages": ["en"],
    "primary_channels": ["Telegram", "WhatsApp", "Email"],
    "fiscal_year_start": "01-01",
    "data_residency": "RU",
    "updated_at":   None,
}


async def get_settings(company_id: str = "default") -> Dict[str, Any]:
    """Load company settings or return defaults. Never raises."""
    try:
        db = get_db()
        doc = await db.company_settings.find_one({"company_id": company_id}, {"_id": 0})
        if doc:
            # Merge defaults so missing fields are filled in.
            return {**DEFAULT_SETTINGS, **doc}
    except Exception as e:  # noqa: BLE001
        logger.warning("get_settings failed: %s — returning defaults", e)
    return dict(DEFAULT_SETTINGS)


async def update_settings(company_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert company settings. Auto-derives currency/channels from region if not given."""
    db = get_db()
    patch = {k: v for k, v in (patch or {}).items() if v is not None}
    region = (patch.get("region") or "").upper() or None
    if region:
        market = REGIONAL_MARKET_CONTEXT.get(region) or REGIONAL_MARKET_CONTEXT["GLOBAL"]
        patch.setdefault("currency", market["currency"])
        patch.setdefault("primary_channels", market["primary_channels"])
    patch["company_id"] = company_id
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.company_settings.update_one(
        {"company_id": company_id},
        {"$set": patch, "$setOnInsert": {"created_at": patch["updated_at"]}},
        upsert=True,
    )
    return await get_settings(company_id)


def render_company_block(settings: Dict[str, Any]) -> str:
    """Prompt-ready block describing the company so any agent can read its
    operating context (region, regulations, currency, channels, etc.) BEFORE
    answering.
    """
    region = (settings.get("region") or "GLOBAL").upper()
    regs = REGIONAL_REGULATIONS.get(region) or REGIONAL_REGULATIONS["GLOBAL"]
    market = REGIONAL_MARKET_CONTEXT.get(region) or REGIONAL_MARKET_CONTEXT["GLOBAL"]

    lines: List[str] = ["## КОНТЕКСТ КОМПАНИИ"]
    lines.append(f"- Название: {settings.get('company_name', '—')}")
    lines.append(f"- Регион: {region} ({settings.get('country', '—')})")
    lines.append(f"- Индустрия: {settings.get('industry', '—')}")
    lines.append(f"- Размер команды: {settings.get('team_size', '—')}")
    lines.append(f"- Валюта: {settings.get('currency', market['currency'])}")
    lines.append(f"- Основной язык: {settings.get('primary_language', 'ru')}")
    lines.append(f"- Каналы: {', '.join(settings.get('primary_channels') or market['primary_channels'])}")
    lines.append(f"- Юрисдикция данных: {settings.get('data_residency', region)}")
    lines.append("\n### Применимые регуляции и фреймворки (для Compliance)")
    for r in regs:
        lines.append(f"  - {r}")
    lines.append(
        "\nЕсли твой ответ зависит от закона / тренда / валюты — "
        "ОБЯЗАТЕЛЬНО используй данные выше. Не предлагай решения, "
        "не релевантные региону компании."
    )
    return "\n".join(lines)
