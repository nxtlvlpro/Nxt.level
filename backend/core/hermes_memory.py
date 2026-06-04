"""
NXT8 Hermes 4-layer memory.

Layer 1 — Short-Term Memory (STM)
    In-process LRU + TTL cache. Holds the *working set* of the cycle:
    recent events per user/company, last cycle ids, hot context that
    must survive across the 10 OS nodes without round-tripping Mongo.

Layer 2 — Operational Memory (OPS)
    Thin read-only facade over existing Mongo collections that ALREADY
    contain the business state (client_profiles, tasks, requests,
    deals, interactions, employees, performance, roi_history). The
    Context Assembly node asks OPS by user_id / company_id and gets
    back a normalised bundle.

Layer 3 — Knowledge Graph (KG)
    Read/write façade over `db.knowledge_graph` (created in Phase 1).
    Stores `(source, target, relation)` edges harvested by the Learning
    node. Lookup is by entity value; we walk one hop out.

Layer 4 — Institutional Memory (INST)
    Read/write façade over `db.institutional_memory`. Holds the
    company's accumulated lessons-learned, tagged by scope.

The Context Assembly node calls `assemble_context(...)` which pulls
all 4 layers in parallel and returns a normalised bundle.

Every call is best-effort: Mongo errors are logged and degrade
gracefully — the OS cycle continues even with empty memory.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.hermes_memory")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================
# Layer 1 — Short-Term Memory (in-process)
# =====================================================================


class _LRUCache:
    """Tiny thread-unsafe LRU+TTL cache. Process-local by design — the
    OS cycle is short-lived and we want zero network hops here."""

    def __init__(self, max_items: int = 512, ttl_seconds: int = 3600):
        self._max = max_items
        self._ttl = ttl_seconds
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()

    def get(self, key: str) -> Any:
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or self._ttl
        self._data[key] = (time.time() + ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def keys(self, prefix: Optional[str] = None) -> List[str]:
        if prefix is None:
            return list(self._data.keys())
        return [k for k in self._data.keys() if k.startswith(prefix)]

    def stats(self) -> Dict[str, int]:
        now = time.time()
        live = sum(1 for exp, _ in self._data.values() if exp >= now)
        return {"items": len(self._data), "live": live, "max": self._max,
                "default_ttl_s": self._ttl}


_STM = _LRUCache(max_items=1024, ttl_seconds=3600)


def stm_set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    _STM.set(key, value, ttl=ttl_seconds)


def stm_get(key: str) -> Any:
    return _STM.get(key)


def stm_stats() -> Dict[str, Any]:
    return _STM.stats()


def stm_remember_cycle(
    cycle_id: str, user_id: Optional[str], company_id: Optional[str],
    event_kind: str, summary: str,
) -> None:
    """Push a compact record so the next cycle for the same user/company
    can see what just happened."""
    record = {
        "cycle_id":   cycle_id,
        "event_kind": event_kind,
        "summary":    summary,
        "ts":         _now(),
    }
    if user_id:
        key = f"recent_cycles:user:{user_id}"
        existing = stm_get(key) or []
        existing.insert(0, record)
        stm_set(key, existing[:5])
    if company_id:
        key = f"recent_cycles:company:{company_id}"
        existing = stm_get(key) or []
        existing.insert(0, record)
        stm_set(key, existing[:10])


def stm_recent_cycles(user_id: Optional[str] = None,
                      company_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return the latest cached cycle summaries for this user/company."""
    out: List[Dict[str, Any]] = []
    if user_id:
        out.extend(stm_get(f"recent_cycles:user:{user_id}") or [])
    if company_id:
        out.extend(stm_get(f"recent_cycles:company:{company_id}") or [])
    # Dedup by cycle_id while preserving order.
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for r in out:
        cid = r.get("cycle_id")
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(r)
    return deduped[:5]


# =====================================================================
# Layer 2 — Operational Memory (Mongo facade)
# =====================================================================


async def ops_lookup(
    user_id: Optional[str] = None,
    company_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Pull the working business state for this user/company.

    Reads from collections that already exist in NXT8: client_profiles,
    tasks, requests, deals, interactions, roi_history. Each section
    is independent — a missing collection or a query failure simply
    returns [] for that slice.
    """
    db = get_db()
    limit = max(1, min(int(limit or 5), 25))

    async def _safe(coro, label):
        try:
            return await coro
        except Exception as e:  # noqa: BLE001
            logger.warning("ops_lookup.%s failed: %s", label, e)
            return []

    tasks: Dict[str, asyncio.Task] = {}
    if user_id:
        tasks["clients"] = asyncio.create_task(_safe(
            db.client_profiles.find(
                {"$or": [{"user_id": user_id}, {"telegram": user_id}, {"phone": user_id}]},
                {"_id": 0},
            ).limit(limit).to_list(length=limit),
            "clients",
        ))
    if company_id:
        tasks["open_tasks"] = asyncio.create_task(_safe(
            db.tasks.find(
                {"company_id": company_id, "status": {"$ne": "done"}},
                {"_id": 0},
            ).sort("created_at", -1).limit(limit).to_list(length=limit),
            "open_tasks",
        ))
        tasks["roi_recent"] = asyncio.create_task(_safe(
            db.roi_history.find({"company_id": company_id}, {"_id": 0})
                .sort("hour_end", -1).limit(3).to_list(length=3),
            "roi_recent",
        ))
        # Fallback ROI lookup without company scoping if multi-tenant
        # isn't wired yet — still useful as a "last known" snapshot.
    if session_id:
        tasks["recent_requests"] = asyncio.create_task(_safe(
            db.requests.find({"session_id": session_id}, {"_id": 0, "response_full": 0})
                .sort("created_at", -1).limit(limit).to_list(length=limit),
            "recent_requests",
        ))

    out: Dict[str, Any] = {"clients": [], "open_tasks": [],
                          "roi_recent": [], "recent_requests": []}
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=False)
        for name, res in zip(tasks.keys(), results):
            out[name] = _scrub(res)
    return out


# =====================================================================
# Layer 3 — Knowledge Graph
# =====================================================================


async def kg_neighbors(entities: Iterable[str], *, limit: int = 20) -> List[Dict[str, Any]]:
    """Return edges where any of the given entity values appears as
    source OR target. One-hop walk only."""
    values = [v for v in (entities or []) if v]
    if not values:
        return []
    db = get_db()
    try:
        docs = await db.knowledge_graph.find(
            {"$or": [{"source": {"$in": values}}, {"target": {"$in": values}}]},
            {"_id": 0},
        ).limit(max(1, min(int(limit), 100))).to_list(length=limit)
        return _scrub(docs)
    except Exception as e:  # noqa: BLE001
        logger.warning("kg_neighbors failed: %s", e)
        return []


async def kg_add_edge(source: str, target: str, relation: str,
                     cycle_id: Optional[str] = None) -> Optional[str]:
    """Add a single KG edge. Returns the generated edge id, or None on
    failure. Idempotent (source+target+relation triplet is unique)."""
    if not (source and target):
        return None
    db = get_db()
    edge_id = str(uuid.uuid4())
    doc = {
        "id":         edge_id,
        "cycle_id":   cycle_id,
        "source":     source,
        "target":     target,
        "relation":   relation or "related",
        "created_at": _now(),
    }
    try:
        # Upsert on triple, so repeated cycles don't bloat the graph.
        await db.knowledge_graph.update_one(
            {"source": source, "target": target, "relation": relation or "related"},
            {"$setOnInsert": doc},
            upsert=True,
        )
        return edge_id
    except Exception as e:  # noqa: BLE001
        logger.warning("kg_add_edge failed: %s", e)
        return None


# =====================================================================
# Layer 4 — Institutional Memory
# =====================================================================


async def inst_recall(
    tags: Optional[List[str]] = None,
    scope: Optional[str] = None,
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Pull recent lessons matching any tag and/or scope."""
    db = get_db()
    q: Dict[str, Any] = {}
    if tags:
        q["tags"] = {"$in": list(tags)}
    if scope:
        q["scope"] = scope
    try:
        docs = await db.institutional_memory.find(q, {"_id": 0}) \
            .sort("created_at", -1).limit(max(1, min(int(limit), 50))) \
            .to_list(length=limit)
        return _scrub(docs)
    except Exception as e:  # noqa: BLE001
        logger.warning("inst_recall failed: %s", e)
        return []


async def inst_record(
    text: str,
    *,
    tags: Optional[List[str]] = None,
    scope: str = "process",
    cycle_id: Optional[str] = None,
) -> Optional[str]:
    if not (text or "").strip():
        return None
    db = get_db()
    lid = str(uuid.uuid4())
    doc = {
        "id":         lid,
        "cycle_id":   cycle_id,
        "text":       text.strip(),
        "tags":       list(tags or []),
        "scope":      scope,
        "created_at": _now(),
    }
    try:
        await db.institutional_memory.insert_one(doc)
        return lid
    except Exception as e:  # noqa: BLE001
        logger.warning("inst_record failed: %s", e)
        return None


# =====================================================================
# Composite: full Context Assembly bundle
# =====================================================================


async def assemble_context(
    event: Dict[str, Any],
    observation: Dict[str, Any],
    *,
    ops_limit: int = 5,
    kg_limit: int = 15,
    inst_limit: int = 5,
) -> Dict[str, Any]:
    """Pull all 4 memory layers in parallel and return a normalised
    bundle for the Context Assembly node."""
    user_id    = event.get("user_id")
    company_id = event.get("company_id")
    session_id = (event.get("payload") or {}).get("session_id") or user_id

    entity_values: List[str] = []
    for e in (observation.get("entities") or []):
        v = e.get("value")
        if v:
            entity_values.append(v)
    if user_id:
        entity_values.append(user_id)
    if company_id:
        entity_values.append(company_id)

    # Tag set for institutional lookup: event.kind + any 'tags' in signals
    inst_tags: List[str] = []
    if event.get("kind"):
        inst_tags.append(event["kind"])
    for s in (observation.get("signals") or [])[:5]:
        if isinstance(s, str) and len(s) < 40:
            inst_tags.append(s)

    ops_task  = ops_lookup(user_id=user_id, company_id=company_id,
                           session_id=session_id, limit=ops_limit)
    kg_task   = kg_neighbors(entity_values, limit=kg_limit)
    inst_task = inst_recall(tags=inst_tags or None, limit=inst_limit)

    ops, kg, inst = await asyncio.gather(ops_task, kg_task, inst_task)

    stm = {
        "recent_cycles": stm_recent_cycles(user_id=user_id, company_id=company_id),
    }

    return {
        "short_term":   stm,
        "operational":  ops,
        "knowledge_graph": kg,
        "institutional":   inst,
        "assembled_at": _now(),
        "totals": {
            "stm_cycles":   len(stm["recent_cycles"]),
            "ops_records":  sum(len(v) if isinstance(v, list) else 0 for v in ops.values()),
            "kg_edges":     len(kg),
            "inst_lessons": len(inst),
        },
    }


# =====================================================================
# Internal helpers
# =====================================================================


def _scrub(value: Any) -> Any:
    """Recursively normalise Mongo types for JSON output."""
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        from bson import ObjectId  # type: ignore
        if isinstance(value, ObjectId):
            return str(value)
    except ImportError:
        pass
    return value
