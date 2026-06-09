from __future__ import annotations

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional, TypeVar

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.db import get_db

logger = logging.getLogger("nxt8.scheduler_lock")

_OWNER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

T = TypeVar("T")


def get_owner_id() -> str:
    return _OWNER_ID


async def try_acquire(job_id: str, owner_id: str, lease_seconds: int) -> bool:
    if not job_id:
        raise ValueError("job_id is required")
    if not owner_id:
        raise ValueError("owner_id is required")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be > 0")

    now = datetime.now(timezone.utc)
    locked_until = now + timedelta(seconds=lease_seconds)
    query = {
        "_id": job_id,
        "$or": [
            {"locked_until": {"$lte": now}},
            {"owner_id": owner_id},
        ],
    }
    update = {
        "$set": {
            "owner_id": owner_id,
            "locked_until": locked_until,
            "updated_at": now,
        },
        "$setOnInsert": {
            "acquired_at": now,
        },
    }
    try:
        doc = await get_db().scheduler_locks.find_one_and_update(
            query,
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        return False
    return bool(doc is not None and doc.get("owner_id") == owner_id)


async def release(job_id: str, owner_id: str) -> None:
    if not job_id or not owner_id:
        return
    await get_db().scheduler_locks.delete_one({"_id": job_id, "owner_id": owner_id})


async def run_exclusive(
    job_id: str,
    lease_seconds: int,
    runner: Callable[[], Awaitable[T]],
    *,
    owner_id: Optional[str] = None,
) -> Optional[T]:
    owner = owner_id or _OWNER_ID
    acquired = await try_acquire(job_id, owner, lease_seconds)
    if not acquired:
        logger.info("scheduler lock busy: job=%s owner=%s", job_id, owner)
        return None

    logger.info("scheduler lock acquired: job=%s owner=%s", job_id, owner)
    try:
        return await runner()
    finally:
        await release(job_id, owner)
        logger.info("scheduler lock released: job=%s owner=%s", job_id, owner)