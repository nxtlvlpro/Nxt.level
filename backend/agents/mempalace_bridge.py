"""
MemPalace Bridge for NXT8 — native Python integration (no HTTP).

Wraps mempalace (ChromaDB-backed) as a long-term corporate memory layer
that lives alongside the short-term Mongo memory in agents/memory.py.

Tenant isolation (Memory Sprint · M2)
-------------------------------------
mempalace 3.3.5 does NOT propagate arbitrary metadata through
`miner.add_drawer` — it only persists `wing` and `room`. We therefore
use the **room** field as the tenant namespace:

    room == company_id   (or "__global__" for legacy / admin / NULL pool)

The original semantic room (session_id, doc_id, contact name…) is
preserved inside `source_file` as a path segment:

    source_file = "nxt8://{wing}/{company_id}/{logical_room}/{uuid}"

Callers express their original intent through the new `logical_room`
argument. Searches filter by exact `room=company_id` first (cheap
ChromaDB metadata match), then post-filter results by the
`logical_room` path segment when requested.

Pre-M2 drawers (173 of them at audit time) used arbitrary rooms
(`acme_corp`, `mp_full_…`, document uuids). They are NOT visible to
new tenant-scoped queries — they live in the `__global__` pool and can
only be reached by admin/global searches. Backfill is intentionally
out of scope for M2.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nxt8.mempalace")

PALACE_PATH = os.environ.get("MEMPALACE_PATH", "/app/data/mempalace")
ENABLED = os.environ.get("MEMPALACE_ENABLED", "true").lower() in ("1", "true", "yes")

_VALID_NAME = re.compile(r"[^A-Za-z0-9_\-]+")
_GLOBAL_TENANT_ROOM = "__global__"


def _safe_name(name: str, fallback: str) -> str:
    n = _VALID_NAME.sub("_", (name or "").strip().lower()) or fallback
    return n[:64]


def _tenant_room(company_id: Optional[str]) -> str:
    """Map a `company_id` to the ChromaDB `room` field. `None` → global pool."""
    if not company_id:
        return _GLOBAL_TENANT_ROOM
    return _safe_name(company_id, _GLOBAL_TENANT_ROOM)


class MemPalaceBridge:
    """Async-friendly wrapper around mempalace's ChromaDB store."""

    def __init__(self, palace_path: str = PALACE_PATH) -> None:
        self.palace_path = palace_path
        self._coll = None
        self._stack = None
        self._init_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._available = False

    # -------- init / health --------

    async def _ensure(self) -> bool:
        if not ENABLED:
            return False
        if self._coll is not None and self._stack is not None:
            return True
        async with self._init_lock:
            if self._coll is not None and self._stack is not None:
                return True
            try:
                os.makedirs(self.palace_path, exist_ok=True)
                self._coll, self._stack = await asyncio.to_thread(self._init_sync)
                self._available = True
                logger.info("MemPalace initialised at %s", self.palace_path)
                return True
            except Exception as e:  # noqa: BLE001
                logger.warning("MemPalace init failed: %s", e)
                self._available = False
                return False

    def _init_sync(self):
        from mempalace import miner
        from mempalace.layers import MemoryStack

        coll = miner.get_collection(self.palace_path, create=True)
        stack = MemoryStack(palace_path=self.palace_path)
        return coll, stack

    async def health(self) -> Dict[str, Any]:
        ok = await self._ensure()
        if not ok:
            return {"ok": False, "enabled": ENABLED, "palace_path": self.palace_path}
        try:
            count = await asyncio.to_thread(self._coll.count)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "enabled": ENABLED, "error": str(e)}
        return {
            "ok": True,
            "enabled": True,
            "palace_path": self.palace_path,
            "drawer_count": int(count),
        }

    # -------- write --------

    async def store(
        self,
        content: str,
        wing: str = "internal",
        room: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "nxt8",
        *,
        company_id: Optional[str] = None,
        logical_room: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a drawer.

        - `company_id` → ChromaDB `room` (tenant namespace).
        - `logical_room` → preserved in `source_file` path for post-filter.
        - Legacy positional `room` kwarg is accepted as `logical_room`
          when `logical_room` is not provided (back-compat for callers
          that still use the pre-M2 signature).
        """
        if not content or not content.strip():
            return {"ok": False, "error": "empty content"}
        ok = await self._ensure()
        if not ok:
            return {"ok": False, "error": "mempalace unavailable"}

        # Back-compat: old callers pass `room=<session_id>` etc.
        if logical_room is None and room and room != "general":
            logical_room = room

        wing_s = _safe_name(wing, "internal")
        tenant_room = _tenant_room(company_id)
        logical_s = _safe_name(logical_room or "main", "main")

        meta = dict(metadata or {})
        meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        meta.setdefault("source", source)
        # NB: mempalace 3.3.5 ignores arbitrary metadata when writing, but
        # we still surface it in the API response so the caller has a
        # complete audit record.

        source_file = (
            f"nxt8://{wing_s}/{tenant_room}/{logical_s}/{uuid.uuid4().hex}"
        )

        # mempalace 3.3.5 takes an exclusive process-level palace lock per
        # add_drawer call — concurrent writes from the same uvicorn PID would
        # fail with "palace ... is held by PID ...". Serialise locally and
        # retry transient lock errors a few times before giving up.
        from mempalace import miner

        last_err: Optional[Exception] = None
        async with self._write_lock:
            for attempt in range(4):
                try:
                    await asyncio.to_thread(
                        miner.add_drawer,
                        self._coll,
                        wing_s,
                        tenant_room,
                        content,
                        source_file,
                        0,
                        "nxt8",
                    )
                    last_err = None
                    break
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    msg = str(e).lower()
                    if "is held by pid" in msg or "lock" in msg:
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    logger.exception("mempalace store failed")
                    return {"ok": False, "error": str(e)}
        if last_err is not None:
            logger.warning("mempalace store gave up after retries: %s", last_err)
            return {"ok": False, "error": str(last_err)}

        return {
            "ok": True,
            "wing": wing_s,
            "room": tenant_room,           # tenant namespace
            "logical_room": logical_s,     # original semantic room
            "company_id": company_id,
            "source_file": source_file,
            "metadata": meta,
        }

    # -------- search --------

    async def search(
        self,
        query: str,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        top_k: int = 5,
        *,
        company_id: Optional[str] = None,
        logical_room: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Tenant-scoped semantic search.

        `company_id=None` ⇒ search the legacy/admin `__global__` pool only;
        it NEVER falls through to other tenants.

        `logical_room` filters by the original semantic room (e.g. doc_id)
        via a `source_file` substring check after ChromaDB returns
        candidates — needed because mempalace 3.3.5 does not expose
        arbitrary metadata for `where` filtering.
        """
        if not query or not query.strip():
            return []
        ok = await self._ensure()
        if not ok:
            return []
        top_k = max(1, min(int(top_k or 5), 50))

        # Back-compat: legacy callers pass `room=<doc_id>` instead of
        # `logical_room`. We treat it as logical_room.
        if logical_room is None and room:
            logical_room = room

        tenant_room = _tenant_room(company_id)
        and_clauses: List[Dict[str, Any]] = [{"room": tenant_room}]
        if wing:
            and_clauses.append({"wing": _safe_name(wing, "internal")})
        where: Dict[str, Any] = (
            {"$and": and_clauses} if len(and_clauses) > 1 else and_clauses[0]
        )

        # Over-fetch when post-filtering by logical_room so a single
        # narrowly-named room doesn't return empty after Chroma top-k.
        fetch_k = top_k * 4 if logical_room else top_k

        try:
            res = await asyncio.to_thread(
                self._coll.query,
                query_texts=[query],
                n_results=fetch_k,
                where=where,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("mempalace search failed: %s", e)
            return []

        ids = (res.ids or [[]])[0] if hasattr(res, "ids") else []
        docs = (res.documents or [[]])[0] if hasattr(res, "documents") else []
        metas = (res.metadatas or [[]])[0] if hasattr(res, "metadatas") else []
        dists = (res.distances or [[]])[0] if hasattr(res, "distances") else []

        items: List[Dict[str, Any]] = []
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            sim = None
            if isinstance(dist, (int, float)):
                sim = max(0.0, min(1.0, 1.0 - float(dist)))
            items.append({
                "id": ids[i] if i < len(ids) else None,
                "content": doc,
                "wing": (meta or {}).get("wing"),
                "room": (meta or {}).get("room"),
                "source_file": (meta or {}).get("source_file"),
                "filed_at": (meta or {}).get("filed_at"),
                "metadata": meta or {},
                "distance": dist,
                "similarity": sim,
            })

        if logical_room:
            marker = f"/{_safe_name(logical_room, 'main')}/"
            items = [it for it in items if marker in (it.get("source_file") or "")]

        return items[:top_k]

    # -------- listing --------

    async def list_wings(
        self, *, company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List wings/rooms. When `company_id` is given, only that tenant's
        drawers contribute to the counts; otherwise the global pool only."""
        ok = await self._ensure()
        if not ok:
            return []
        try:
            res = await asyncio.to_thread(self._coll.get, None, None, None, None, ["metadatas"])
        except Exception:
            try:
                res = await asyncio.to_thread(self._coll.get)
            except Exception as e:  # noqa: BLE001
                logger.warning("mempalace list failed: %s", e)
                return []
        metas = []
        if isinstance(res, dict):
            metas = res.get("metadatas") or []
        elif hasattr(res, "metadatas"):
            metas = res.metadatas or []

        tenant_room = _tenant_room(company_id)
        counts: Dict[str, Dict[str, int]] = {}
        for m in metas:
            if not isinstance(m, dict):
                continue
            if (m.get("room") or "") != tenant_room:
                continue
            wing = m.get("wing") or "internal"
            # Surface the logical_room (extracted from source_file) instead
            # of the tenant namespace, which would otherwise be the same
            # value for every drawer of one tenant.
            sf = m.get("source_file") or ""
            logical = "main"
            parts = sf.split("/")
            # nxt8://{wing}/{tenant}/{logical}/{uuid}
            if len(parts) >= 5:
                logical = parts[4] or "main"
            counts.setdefault(wing, {})
            counts[wing][logical] = counts[wing].get(logical, 0) + 1

        return [
            {
                "wing": w,
                "drawer_count": sum(rooms.values()),
                "rooms": [{"room": r, "drawer_count": c} for r, c in sorted(rooms.items())],
            }
            for w, rooms in sorted(counts.items())
        ]


# singleton
_bridge: Optional[MemPalaceBridge] = None


def get_mempalace() -> MemPalaceBridge:
    global _bridge
    if _bridge is None:
        _bridge = MemPalaceBridge()
    return _bridge
