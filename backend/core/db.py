"""
MongoDB collections for NXT8.

Collections:
- sessions          : short-term memory (per session messages)
- memories          : long-term memory (corporate / episodic / semantic) with metadata
- requests          : every routed request (audit log)
- employees         : employee profiles
- performance       : monthly performance metrics per employee
- weak_patterns     : detected weak patterns
- costs             : cost records (deepseek api, compute, escalations)
- deals             : closed deals
- interactions      : agent-deal interactions
- roi_history      : hourly ROI snapshots
- alerts            : reliability / ROI alerts
"""

from __future__ import annotations

import os
from contextvars import ContextVar, Token
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase


_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None
_request_company_id: ContextVar[Optional[str]] = ContextVar("request_company_id", default=None)
_request_force_admin: ContextVar[bool] = ContextVar("request_force_admin", default=False)


def set_request_company_context(
    company_id: Optional[str], *, force_admin: bool = False
) -> tuple[Token, Token]:
    return (
        _request_company_id.set(company_id),
        _request_force_admin.set(force_admin),
    )


def reset_request_company_context(tokens: tuple[Token, Token]) -> None:
    company_tok, admin_tok = tokens
    _request_company_id.reset(company_tok)
    _request_force_admin.reset(admin_tok)


def get_request_company_id() -> Optional[str]:
    return _request_company_id.get()


def get_request_force_admin() -> bool:
    return _request_force_admin.get()


class TenantAwareCRUD:
    def __init__(
        self,
        collection: Any,
        company_id: Optional[str] = None,
        *,
        force_admin: bool = False,
    ):
        if isinstance(collection, TenantAwareCollection):
            self.collection = collection.raw_collection
        else:
            self.collection = collection
        self.company_id = get_request_company_id() if company_id is None else company_id
        self.force_admin = force_admin or get_request_force_admin()

    def _add_tenant_filter(self, filter_dict: Optional[dict]) -> dict:
        base_filter = filter_dict or {}
        if self.force_admin or self.company_id is None:
            return base_filter
        tenant_filter = {"company_id": self.company_id}
        if not base_filter:
            return tenant_filter
        if all(not str(k).startswith("$") for k in base_filter.keys()):
            merged = dict(base_filter)
            merged["company_id"] = self.company_id
            return merged
        return {"$and": [tenant_filter, base_filter]}

    def _inject_company(self, document: dict) -> dict:
        payload = dict(document or {})
        if not self.force_admin and self.company_id:
            payload["company_id"] = self.company_id
        return payload

    def _inject_company_into_update(self, update: dict) -> dict:
        payload = dict(update or {})
        if self.force_admin or not self.company_id:
            return payload
        if any(k.startswith("$") for k in payload.keys()):
            cleaned = {}
            for op_payload in payload.values():
                pass
            for op, op_payload in payload.items():
                if isinstance(op_payload, dict):
                    nested = dict(op_payload)
                    nested.pop("company_id", None)
                    cleaned[op] = nested
                else:
                    cleaned[op] = op_payload
            set_on_insert = dict(cleaned.get("$setOnInsert") or {})
            set_on_insert.pop("company_id", None)
            set_on_insert["company_id"] = self.company_id
            cleaned["$setOnInsert"] = set_on_insert
            return cleaned
        payload["company_id"] = self.company_id
        return payload

    def _inject_company_into_pipeline(self, pipeline: list[dict]) -> list[dict]:
        if self.force_admin or self.company_id is None:
            return list(pipeline)
        match_stage = {"$match": {"company_id": self.company_id}}
        if not pipeline:
            return [match_stage]
        cloned = [dict(stage) for stage in pipeline]
        first = cloned[0]
        if "$match" in first:
            first["$match"] = self._add_tenant_filter(first.get("$match") or {})
            cloned[0] = first
            return cloned
        return [match_stage, *cloned]

    async def find_one(self, filter: Optional[dict] = None, *args, **kwargs):
        return await self.collection.find_one(self._add_tenant_filter(filter), *args, **kwargs)

    def find(self, filter: Optional[dict] = None, *args, **kwargs):
        return self.collection.find(self._add_tenant_filter(filter), *args, **kwargs)

    async def insert_one(self, document: dict, *args, **kwargs):
        return await self.collection.insert_one(self._inject_company(document), *args, **kwargs)

    async def update_one(self, filter: Optional[dict], update: dict, *args, **kwargs):
        return await self.collection.update_one(
            self._add_tenant_filter(filter),
            self._inject_company_into_update(update),
            *args,
            **kwargs,
        )

    async def update_many(self, filter: Optional[dict], update: dict, *args, **kwargs):
        return await self.collection.update_many(
            self._add_tenant_filter(filter),
            self._inject_company_into_update(update),
            *args,
            **kwargs,
        )

    async def delete_one(self, filter: Optional[dict], *args, **kwargs):
        return await self.collection.delete_one(self._add_tenant_filter(filter), *args, **kwargs)

    async def delete_many(self, filter: Optional[dict], *args, **kwargs):
        return await self.collection.delete_many(self._add_tenant_filter(filter), *args, **kwargs)

    async def count_documents(self, filter: Optional[dict] = None, *args, **kwargs):
        return await self.collection.count_documents(self._add_tenant_filter(filter), *args, **kwargs)

    def aggregate(self, pipeline: Optional[list[dict]] = None, *args, **kwargs):
        return self.collection.aggregate(self._inject_company_into_pipeline(pipeline or []), *args, **kwargs)

    async def find_one_and_update(self, filter: Optional[dict], update: dict, *args, **kwargs):
        return await self.collection.find_one_and_update(
            self._add_tenant_filter(filter),
            self._inject_company_into_update(update),
            *args,
            **kwargs,
        )


class TenantAwareCollection:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.raw_collection = collection

    def _crud(self) -> TenantAwareCRUD:
        return TenantAwareCRUD(self.raw_collection)

    async def find_one(self, filter: Optional[dict] = None, *args, **kwargs):
        return await self._crud().find_one(filter, *args, **kwargs)

    def find(self, filter: Optional[dict] = None, *args, **kwargs):
        return self._crud().find(filter, *args, **kwargs)

    async def insert_one(self, document: dict, *args, **kwargs):
        return await self._crud().insert_one(document, *args, **kwargs)

    async def update_one(self, filter: Optional[dict], update: dict, *args, **kwargs):
        return await self._crud().update_one(filter, update, *args, **kwargs)

    async def update_many(self, filter: Optional[dict], update: dict, *args, **kwargs):
        return await self._crud().update_many(filter, update, *args, **kwargs)

    async def delete_one(self, filter: Optional[dict], *args, **kwargs):
        return await self._crud().delete_one(filter, *args, **kwargs)

    async def delete_many(self, filter: Optional[dict], *args, **kwargs):
        return await self._crud().delete_many(filter, *args, **kwargs)

    async def count_documents(self, filter: Optional[dict] = None, *args, **kwargs):
        return await self._crud().count_documents(filter, *args, **kwargs)

    def aggregate(self, pipeline: Optional[list[dict]] = None, *args, **kwargs):
        return self._crud().aggregate(pipeline, *args, **kwargs)

    async def find_one_and_update(self, filter: Optional[dict], update: dict, *args, **kwargs):
        return await self._crud().find_one_and_update(filter, update, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.raw_collection, name)


class TenantAwareDatabaseProxy:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.raw_db = db

    def __getattr__(self, name: str):
        attr = getattr(self.raw_db, name)
        if isinstance(attr, AsyncIOMotorCollection):
            return TenantAwareCollection(attr)
        return attr


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    assert _db is not None  # for type checkers
    return TenantAwareDatabaseProxy(_db)


async def ensure_indexes() -> None:
    db = get_db()
    await db.sessions.create_index("session_id", unique=True)
    # M3 — TTL on anonymous sessions. `expires_at` is BSON-Date (set only
    # for anonymous sessions in `agents.memory.append_message`); known
    # users have no `expires_at`, so this TTL ignores them.
    await db.sessions.create_index(
        "expires_at", expireAfterSeconds=0, name="sessions_expires_at_ttl"
    )
    # M3 — used by the 24h `cleanup_expired_sessions` sweeper.
    await db.sessions.create_index([("updated_at", 1)])
    await db.sessions.create_index([("company_id", 1), ("updated_at", -1)])
    await db.memories.create_index([("type", 1), ("created_at", -1)])
    await db.memories.create_index("metadata.department")
    await db.requests.create_index([("session_id", 1), ("created_at", -1)])
    await db.employees.create_index("employee_id", unique=True)
    await db.performance.create_index([("employee_id", 1), ("period_end", -1)])
    await db.weak_patterns.create_index([("employee_id", 1), ("detected_at", -1)])
    await db.costs.create_index([("agent", 1), ("created_at", -1)])
    await db.deals.create_index("deal_id", unique=True)
    await db.interactions.create_index([("deal_id", 1), ("agent", 1)])
    await db.roi_history.create_index("hour_end", unique=True)
    await db.alerts.create_index([("created_at", -1)])
    await db.cross_dept_tasks.create_index([("created_at", -1)])
    await db.tasks.create_index([("company_id", 1), ("kind", 1), ("status", 1), ("due_at", 1)])
    await db.tasks.create_index([("created_at", -1)])
    await db.followups.create_index([("company_id", 1), ("status", 1), ("due_at", 1)])  # legacy; kept for back-compat reads
    await db.persona_requests.create_index([("created_at", -1)])
    await db.contradictions.create_index("pair_key", unique=True)
    await db.contradictions.create_index([("detected_at", -1)])
    await db.skills.create_index([("intent", 1), ("updated_at", -1)])
    await db.market_signals.create_index([("ingested_at", -1)])
    await db.market_signals.create_index("category")
    await db.market_digests.create_index([("created_at", -1)])
    # JOKER sandbox audit ledger — used for rate-limit + dashboard counts.
    await db.joker_audit.create_index([("session_id", 1), ("ts", -1)])
    await db.joker_audit.create_index([("ts", -1)])
    # Channel bindings (Wingman-inspired ingress router).
    await db.channel_bindings.create_index(
        [("channel_id", 1), ("intent_filter", 1)], unique=True
    )
    await db.channel_events.create_index([("channel_id", 1), ("ts", -1)])
    await db.channel_events.create_index([("ts", -1)])
    # Onboarding survey + access codes.
    await db.client_profiles.create_index([("created_at", -1)])
    await db.client_profiles.create_index([("urgency", 1), ("created_at", -1)])
    await db.client_profiles.create_index("phone")
    await db.client_profiles.create_index("telegram")
    await db.access_codes.create_index("code", unique=True)
    # Hermes Operating Graph (10-node continuous cycle).
    await db.hermes_os_cycles.create_index("cycle_id", unique=True)
    await db.hermes_os_cycles.create_index([("started_at", -1)])
    await db.hermes_os_cycles.create_index([("event.source", 1), ("started_at", -1)])
    # 4-layer Hermes memory.
    await db.knowledge_graph.create_index([("source", 1), ("target", 1), ("relation", 1)])
    await db.knowledge_graph.create_index([("created_at", -1)])
    await db.institutional_memory.create_index([("scope", 1), ("created_at", -1)])
    await db.institutional_memory.create_index([("tags", 1)])
    # Stripe payment transactions
    await db.payment_transactions.create_index("session_id", unique=True)
    await db.payment_transactions.create_index([("created_at", -1)])
    await db.payment_transactions.create_index([("user_id", 1), ("created_at", -1)])
    # Approval Gate — high-impact agent actions waiting for Hermes/human review.
    await db.pending_approvals.create_index("id", unique=True)
    await db.pending_approvals.create_index([("status", 1), ("created_at", -1)])
    await db.pending_approvals.create_index([("agent_id", 1), ("created_at", -1)])
    await db.pending_approvals.create_index([("company_id", 1), ("status", 1)])
    # Scheduler distributed lease-locks for multi-instance safe cron execution.
    await db.scheduler_locks.create_index([("locked_until", 1)])


def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
