"""Backfill `company_id` on legacy db.sessions docs.

Memory Sprint · M1 migration.

For every session doc with a known `user_id` but no `company_id`, look up
the user's company_id and write it. Sessions without a known user are left
untagged (`company_id` absent) — they remain visible only to admins or the
"global" pool.

Memories are NOT backfilled: legacy un-tagged memories stay in the global
pool by design (option `a` per spec).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.db import get_db

logger = logging.getLogger("nxt8.migrations.m_tag_memory")


async def run() -> Dict[str, Any]:
    db = get_db()
    summary: Dict[str, Any] = {
        "sessions_scanned": 0,
        "sessions_tagged": 0,
        "sessions_no_user": 0,
        "sessions_no_company": 0,
    }
    cursor = db.sessions.find(
        {"company_id": {"$exists": False}, "user_id": {"$exists": True, "$ne": ""}},
        {"_id": 0, "session_id": 1, "user_id": 1},
    )
    async for sess in cursor:
        summary["sessions_scanned"] += 1
        uid = sess.get("user_id")
        if not uid:
            summary["sessions_no_user"] += 1
            continue
        user = await db.users.find_one({"user_id": uid}, {"_id": 0, "company_id": 1})
        if not user or not user.get("company_id"):
            summary["sessions_no_company"] += 1
            continue
        await db.sessions.update_one(
            {"session_id": sess["session_id"]},
            {"$set": {"company_id": user["company_id"]}},
        )
        summary["sessions_tagged"] += 1

    logger.info("memory backfill: %s", summary)
    return summary
