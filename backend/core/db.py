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
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    assert _db is not None  # for type checkers
    return _db


async def ensure_indexes() -> None:
    db = get_db()
    await db.sessions.create_index("session_id", unique=True)
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


def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
