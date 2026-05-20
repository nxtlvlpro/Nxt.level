"""
Market Radar Agent for NXT8.

Tracks external market signals (competitor moves, pricing changes, news).
Signals can be ingested via POST /api/market/signals, then scan() runs a
DeepSeek summarisation pass to produce daily intelligence digest.

Since no external news API key is configured, signals are sourced from:
1. Manual POST ingestion (operators paste headlines)
2. seed_demo() injects a small synthetic batch so the dashboard isn't empty

db.market_signals: {id, headline, source, category, url?, ingested_at, score?, processed}
db.market_digests: {id, period, signals_count, digest, created_at}
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import get_db
from core.deepseek import get_deepseek

logger = logging.getLogger("nxt8.market_radar")

CATEGORIES = {"competitor", "pricing", "regulation", "tech", "macro", "customer"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ingest_signal(payload: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    cat = (payload.get("category") or "tech").lower()
    if cat not in CATEGORIES:
        cat = "tech"
    sig = {
        "id": str(uuid.uuid4()),
        "headline": (payload.get("headline") or "").strip(),
        "source": payload.get("source") or "manual",
        "category": cat,
        "url": payload.get("url"),
        "score": float(payload.get("score") or 0.5),
        "ingested_at": _now(),
        "processed": False,
    }
    if not sig["headline"]:
        raise ValueError("headline is required")
    await db.market_signals.insert_one(sig)
    return {k: v for k, v in sig.items() if k != "_id"}


async def list_signals(category: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if category:
        q["category"] = category
    return await db.market_signals.find(q, {"_id": 0}).sort("ingested_at", -1).to_list(length=limit)


async def scan(window_hours: int = 24) -> Dict[str, Any]:
    """Summarise recent signals into a market intelligence digest."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    signals = await db.market_signals.find(
        {"ingested_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("ingested_at", -1).to_list(length=200)

    if not signals:
        return {
            "status": "empty",
            "signals_count": 0,
            "digest": "За указанный период новых сигналов не поступало.",
            "window_hours": window_hours,
        }

    bullets = "\n".join(
        f"- [{s.get('category')}] {s.get('headline')} (source: {s.get('source')})"
        for s in signals
    )

    deepseek = get_deepseek()
    answer = await deepseek.chat(
        messages=[
            {"role": "system", "content": (
                "Ты — рыночный аналитик NXT8. Получив список сигналов за период, "
                "сделай краткий дайджест: 1) топ-3 события, 2) общий тренд, 3) "
                "рекомендации для команды (sales/product). Без воды, на русском."
            )},
            {"role": "user", "content": f"## Signals (last {window_hours}h)\n{bullets}"},
        ],
        temperature=0.4,
        max_tokens=700,
    )

    digest = {
        "id": str(uuid.uuid4()),
        "period_hours": window_hours,
        "signals_count": len(signals),
        "digest": answer.get("content", ""),
        "confidence": answer.get("confidence", 0.7),
        "provider": answer.get("provider"),
        "created_at": _now(),
    }
    await db.market_digests.insert_one(digest)

    # mark signals processed (idempotent)
    ids = [s["id"] for s in signals]
    await db.market_signals.update_many({"id": {"$in": ids}}, {"$set": {"processed": True}})

    return {k: v for k, v in digest.items() if k != "_id"}


async def list_digests(limit: int = 10) -> List[Dict[str, Any]]:
    db = get_db()
    return await db.market_digests.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)


async def seed_demo_signals() -> int:
    """Insert a small synthetic batch if signals collection is empty."""
    db = get_db()
    existing = await db.market_signals.count_documents({})
    if existing > 0:
        return 0
    demo = [
        {"headline": "Конкурент X запустил free-tier на 50% больше квот", "category": "competitor", "source": "techcrunch.example", "score": 0.85},
        {"headline": "DeepSeek снизил цены на v3.2 на 22%", "category": "pricing", "source": "deepseek.com", "score": 0.9},
        {"headline": "ЕС принял AI Act phase 2 — требования к explainability", "category": "regulation", "source": "ec.europa.eu", "score": 0.7},
        {"headline": "OpenRouter добавил bulk inference API", "category": "tech", "source": "openrouter.ai", "score": 0.6},
        {"headline": "Enterprise клиент Acme Corp удвоил бюджет на AI-ops", "category": "customer", "source": "linkedin.example", "score": 0.75},
    ]
    n = 0
    for d in demo:
        await ingest_signal(d)
        n += 1
    return n
