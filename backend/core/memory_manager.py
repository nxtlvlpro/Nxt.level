from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents import mempalace_bridge as mempalace_agent
from agents import memory as memory_agent


class MemoryManager:
    def __init__(self) -> None:
        self._memory = memory_agent.get_memory()
        self._mempalace = mempalace_agent.get_mempalace()

    async def get_context(
        self,
        query: str,
        session_id: str,
        *,
        company_id: Optional[str] = None,
        max_chars: int = 6000,
    ) -> Dict[str, Any]:
        return await self._memory.get_optimal_context(
            query,
            session_id,
            max_chars=max_chars,
            company_id=company_id,
        )

    async def search_memory(
        self,
        query: str,
        *,
        company_id: Optional[str] = None,
        top_k: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._memory.search(
            query,
            top_k=top_k,
            memory_type=memory_type,
            company_id=company_id,
        )

    async def search_mempalace(
        self,
        query: str,
        *,
        company_id: Optional[str] = None,
        wing: Optional[str] = None,
        logical_room: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        return await self._mempalace.search(
            query,
            wing=wing,
            top_k=top_k,
            company_id=company_id,
            logical_room=logical_room,
        )

    async def store_mempalace(
        self,
        content: str,
        *,
        company_id: Optional[str] = None,
        wing: str = "internal",
        logical_room: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "nxt8",
    ) -> Dict[str, Any]:
        return await self._mempalace.store(
            content,
            wing=wing,
            metadata=metadata,
            source=source,
            company_id=company_id,
            logical_room=logical_room,
        )

    async def health(self) -> Dict[str, Any]:
        return {
            "memory_engine": {
                "short_term_ttl_hours": self._memory.short_term_ttl_hours,
            },
            "mempalace": await self._mempalace.health(),
        }


_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
