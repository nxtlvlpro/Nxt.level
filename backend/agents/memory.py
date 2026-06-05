"""
Memory Agent for NXT8.

Implements multi-tier memory per ТЗ Module 4:
- short_term: recent session messages (MongoDB, 24h TTL applied via cleanup)
- long_term: corporate / episodic / semantic memories with TF-IDF semantic search
- ranking : recency × frequency × importance

Tenant isolation (Memory Sprint · M1):
- Every `db.sessions` and `db.memories` doc carries a top-level `company_id`.
- `search` / `get_optimal_context` REQUIRE a tenant scope. Calls without
  `company_id` get ONLY documents whose `company_id` is None (legacy/admin
  pool) — they never see another tenant's data.
- TF-IDF cache is keyed per tenant so corpora do not cross-pollinate and
  one tenant's `store_memory` does not invalidate another's cache.

Session size + TTL (Memory Sprint · M3):
- Sessions cap message array at MAX_SESSION_MESSAGES (200) via `$push` +
  `$slice` so a doc never approaches the 16 MB BSON limit.
- Anonymous sessions get a BSON-Date `expires_at` (now + 90 days). A MongoDB
  TTL index on `sessions.expires_at` auto-purges them. Known users
  (stable user_id) have `expires_at` cleared so their history is kept.
- `cleanup_expired_sessions` is also scheduled daily @ 03:00 in
  core.scheduler for fast 24h-TTL pruning on top of the 90d TTL index.

Note: ТЗ specifies Chroma + sentence-transformers. For Emergent single-process
deployment we use TF-IDF (scikit-learn) — same semantic search contract,
no external service. When DeepSeek embeddings API is wired this module
can be swapped without changing call sites.
"""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.db import get_db

logger = logging.getLogger("nxt8.memory")

# M3 — hard cap on session.messages length so a single session doc never
# explodes past the 16MB BSON limit. `$push` + `$slice` keeps the most
# recent N entries on every write.
MAX_SESSION_MESSAGES = 200

# M3 — absolute TTL on anonymous sessions. Backstop for the 24h
# `cleanup_expired_sessions` sweeper. Known users' sessions don't get
# `expires_at` set, so they're never auto-purged by the TTL index.
SESSION_ANON_TTL_DAYS = 90


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_known_user_id(user_id: Optional[str]) -> bool:
    """True if `user_id` is a stable browser/account id (not an anon stub)."""
    if not user_id:
        return False
    return not user_id.lower().startswith(("anon", "home_visitor"))


def _half_life_decay(days_old: float, half_life_days: float = 30.0) -> float:
    if days_old <= 0:
        return 1.0
    return math.exp(-days_old * math.log(2) / half_life_days)


class MemoryEngine:
    """Unified memory: short-term + long-term + ranking."""

    def __init__(self) -> None:
        self.short_term_ttl_hours = 24
        # Per-tenant TF-IDF cache. Key = company_id (str) or None for the
        # legacy/admin pool. Each entry is independent so writes in one
        # tenant never invalidate another tenant's cache.
        self._tfidf_cache: Dict[Optional[str], Dict[str, Any]] = {}
        self._tfidf_lock = asyncio.Lock()

    # ---------- short-term ----------

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        *,
        company_id: Optional[str] = None,
    ) -> None:
        db = get_db()
        msg = {"role": role, "content": content, "ts": _now()}
        set_fields: Dict[str, Any] = {"updated_at": _now()}
        unset_fields: Dict[str, Any] = {}
        is_known = _is_known_user_id(user_id)
        # Bind a stable per-browser user_id to the session so cross-session
        # continuity (M1) and ttl-exemption for known users (M5) work.
        if is_known:
            set_fields["user_id"] = user_id
        # Tenant binding: write `company_id` at the root of every session
        # doc so all reads can filter cheaply by tenant.
        if company_id:
            set_fields["company_id"] = company_id
        # M3 — absolute TTL on anonymous sessions only. BSON-Date so the
        # MongoDB TTL index on `expires_at` can auto-purge. For known users
        # we strip any stale `expires_at` so their history is preserved.
        if is_known:
            unset_fields["expires_at"] = ""
        else:
            set_fields["expires_at"] = datetime.now(timezone.utc) + timedelta(
                days=SESSION_ANON_TTL_DAYS
            )
        update: Dict[str, Any] = {
            # M3 — cap messages[] at MAX_SESSION_MESSAGES on every write.
            "$push": {
                "messages": {
                    "$each": [msg],
                    "$slice": -MAX_SESSION_MESSAGES,
                }
            },
            "$set": set_fields,
            "$setOnInsert": {"created_at": _now()},
        }
        if unset_fields:
            update["$unset"] = unset_fields
        await db.sessions.update_one(
            {"session_id": session_id},
            update,
            upsert=True,
        )

    async def get_session(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        db = get_db()
        doc = await db.sessions.find_one({"session_id": session_id}, {"_id": 0, "messages": 1})
        if not doc:
            return []
        msgs = doc.get("messages") or []
        return msgs[-limit:]

    async def build_short_context(self, session_id: str, max_chars: int = 6000) -> str:
        msgs = await self.get_session(session_id, limit=50)
        parts: List[str] = []
        total = 0
        for m in reversed(msgs):
            chunk = f"[{m.get('role', 'user')}]: {m.get('content', '')}"
            if total + len(chunk) > max_chars:
                break
            parts.append(chunk)
            total += len(chunk)
        parts.reverse()
        return "\n".join(parts)

    # ---------- long-term ----------

    async def store_memory(
        self,
        content: str,
        memory_type: str = "corporate",
        metadata: Optional[Dict[str, Any]] = None,
        *,
        company_id: Optional[str] = None,
    ) -> str:
        db = get_db()
        doc = {
            "id": str(uuid.uuid4()),
            "content": content,
            "type": memory_type,
            "metadata": metadata or {},
            "access_count": 0,
            "company_id": company_id,
            "created_at": _now(),
        }
        await db.memories.insert_one(doc)
        # Only invalidate the cache for THIS tenant — other tenants'
        # corpora are untouched.
        self._tfidf_cache.pop(company_id, None)
        logger.info("Stored %s memory (%d chars) tenant=%s",
                    memory_type, len(content), company_id)
        return doc["id"]

    async def list_memories(
        self, memory_type: Optional[str] = None, limit: int = 100,
        *, company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = get_db()
        q: Dict[str, Any] = {}
        if memory_type:
            q["type"] = memory_type
        if company_id is not None:
            q["company_id"] = company_id
        cursor = db.memories.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def _ensure_tfidf(
        self, company_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        async with self._tfidf_lock:
            cached = self._tfidf_cache.get(company_id)
            if cached is not None:
                return cached
            db = get_db()
            # Strict tenant scope: a tenant query returns ONLY that tenant's
            # docs. The legacy/admin pool (company_id=None) sees only NULL-
            # tagged docs; it never inherits another tenant's data.
            q = {"company_id": company_id}
            docs = await db.memories.find(
                q,
                {"_id": 0, "id": 1, "content": 1, "type": 1,
                 "metadata": 1, "created_at": 1, "access_count": 1,
                 "company_id": 1},
            ).to_list(length=5000)
            if not docs:
                return None
            corpus = [d.get("content", "") for d in docs]
            try:
                vectorizer = TfidfVectorizer(max_features=4096, ngram_range=(1, 2))
                matrix = vectorizer.fit_transform(corpus)
            except ValueError:
                # empty vocab (only stopwords / empty docs)
                return None
            entry = {"docs": docs, "vectorizer": vectorizer, "matrix": matrix}
            self._tfidf_cache[company_id] = entry
            return entry

    async def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        *,
        company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cache = await self._ensure_tfidf(company_id=company_id)
        if not cache:
            return []
        try:
            q_vec = cache["vectorizer"].transform([query])
        except Exception:
            return []
        sims = cosine_similarity(q_vec, cache["matrix"]).ravel()
        docs = cache["docs"]

        results: List[Dict[str, Any]] = []
        for i, sim in enumerate(sims):
            doc = docs[i]
            if memory_type and doc.get("type") != memory_type:
                continue
            if sim <= 0.0:
                continue
            # Composite rank: 0.6 similarity + 0.25 recency + 0.15 importance
            try:
                age_days = (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00"))
                ).total_seconds() / 86400
            except Exception:
                age_days = 0
            recency = _half_life_decay(age_days)
            importance = 0.5
            meta = doc.get("metadata") or {}
            if str(meta.get("priority", "")).lower() in ("critical", "high"):
                importance = 0.9
            elif meta.get("department") in ("executive", "c-suite", "board"):
                importance = 0.85
            rank = 0.6 * float(sim) + 0.25 * recency + 0.15 * importance
            results.append(
                {
                    "id": doc.get("id"),
                    "content": doc.get("content"),
                    "type": doc.get("type"),
                    "metadata": meta,
                    "created_at": doc.get("created_at"),
                    "similarity": float(sim),
                    "recency": float(recency),
                    "importance": float(importance),
                    "rank": float(rank),
                }
            )

        results.sort(key=lambda r: r["rank"], reverse=True)
        top = results[:top_k]

        # increment access counters for ranked memories (tenant-scoped)
        if top:
            db = get_db()
            ids = [r["id"] for r in top if r.get("id")]
            match: Dict[str, Any] = {"id": {"$in": ids}}
            match["company_id"] = company_id
            await db.memories.update_many(match, {"$inc": {"access_count": 1}})

        return top

    async def get_optimal_context(
        self, query: str, session_id: str, max_chars: int = 6000,
        *, company_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Combine short-term + retrieved long-term memories into one context string."""
        short = await self.build_short_context(session_id, max_chars=max_chars // 2)
        retrieved = await self.search(query, top_k=5, company_id=company_id)
        long_parts: List[str] = []
        used = len(short)
        for r in retrieved:
            chunk = f"[{r['type']}] {r['content']}"
            if used + len(chunk) > max_chars:
                break
            long_parts.append(chunk)
            used += len(chunk)
        context = (
            "## Recent dialogue\n" + short + "\n\n## Relevant knowledge\n" + "\n".join(long_parts)
        ).strip()
        return {
            "context": context,
            "short_term_chars": len(short),
            "long_term_items": len(long_parts),
            "retrieved": retrieved,
        }

    async def cleanup_expired_sessions(self) -> int:
        db = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=self.short_term_ttl_hours)).isoformat()
        # M5: only purge anonymous sessions. Known users (with a stable
        # browser user_id) keep their full history forever.
        res = await db.sessions.delete_many({
            "updated_at": {"$lt": cutoff},
            "$or": [
                {"user_id": {"$exists": False}},
                {"user_id": None},
                {"user_id": ""},
            ],
        })
        return res.deleted_count


# singleton
_engine: Optional[MemoryEngine] = None


def get_memory() -> MemoryEngine:
    global _engine
    if _engine is None:
        _engine = MemoryEngine()
    return _engine
