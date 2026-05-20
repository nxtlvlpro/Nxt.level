"""
MemPalace Bridge for NXT8 — native Python integration (no HTTP).

Wraps mempalace (ChromaDB-backed) as a long-term corporate memory layer
that lives alongside the short-term Mongo memory in agents/memory.py.

Wings/Rooms schema (NXT8):
- clients/{company_id}      — corporate clients
- employees/{user_id}       — employees / users
- projects/{project_id}     — internal projects
- chats/{session_id}        — long-term chat memories
- internal/general          — knowledge base / company-wide notes

All sync mempalace calls run in a thread pool to keep the asyncio loop
free.
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


def _safe_name(name: str, fallback: str) -> str:
    n = _VALID_NAME.sub("_", (name or "").strip().lower()) or fallback
    return n[:64]


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
        room: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "nxt8",
    ) -> Dict[str, Any]:
        if not content or not content.strip():
            return {"ok": False, "error": "empty content"}
        ok = await self._ensure()
        if not ok:
            return {"ok": False, "error": "mempalace unavailable"}

        wing_s = _safe_name(wing, "internal")
        room_s = _safe_name(room, "general")
        meta = dict(metadata or {})
        meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        meta.setdefault("source", source)

        # mempalace add_drawer wants a synthetic source_file path; use a
        # nxt8:// pseudo-path keyed by uuid so each call is unique.
        source_file = f"nxt8://{wing_s}/{room_s}/{uuid.uuid4().hex}"

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
                        room_s,
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
            "room": room_s,
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
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []
        ok = await self._ensure()
        if not ok:
            return []
        top_k = max(1, min(int(top_k or 5), 50))

        where: Optional[Dict[str, Any]] = None
        if wing and room:
            where = {"$and": [{"wing": _safe_name(wing, "internal")},
                              {"room": _safe_name(room, "general")}]}
        elif wing:
            where = {"wing": _safe_name(wing, "internal")}
        elif room:
            where = {"room": _safe_name(room, "general")}

        try:
            res = await asyncio.to_thread(
                self._coll.query,
                query_texts=[query],
                n_results=top_k,
                where=where,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("mempalace search failed: %s", e)
            return []

        # QueryResult is a NamedTuple-ish object with ids/documents/metadatas/distances
        ids = (res.ids or [[]])[0] if hasattr(res, "ids") else []
        docs = (res.documents or [[]])[0] if hasattr(res, "documents") else []
        metas = (res.metadatas or [[]])[0] if hasattr(res, "metadatas") else []
        dists = (res.distances or [[]])[0] if hasattr(res, "distances") else []

        items: List[Dict[str, Any]] = []
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            # ChromaDB cosine distance -> similarity (1 - dist), clamp 0..1
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
        return items

    # -------- listing --------

    async def list_wings(self) -> List[Dict[str, Any]]:
        ok = await self._ensure()
        if not ok:
            return []
        try:
            res = await asyncio.to_thread(self._coll.get, None, None, None, None, ["metadatas"])
        except Exception:
            # different chroma versions — try without positional args
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

        counts: Dict[str, Dict[str, int]] = {}
        for m in metas:
            if not isinstance(m, dict):
                continue
            wing = m.get("wing") or "internal"
            room = m.get("room") or "general"
            counts.setdefault(wing, {})
            counts[wing][room] = counts[wing].get(room, 0) + 1

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
