from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from core.db import ensure_indexes, get_db
from core.scheduler_lock import release, run_exclusive, try_acquire

PREFIX = "test_sched_lock_"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _cleanup() -> None:
    await get_db().scheduler_locks.delete_many({"_id": {"$regex": f"^{PREFIX}"}})


def test_try_acquire_succeeds_for_new_lock() -> None:
    async def _go():
        await ensure_indexes()
        await _cleanup()
        job_id = f"{PREFIX}new"
        try:
            ok = await try_acquire(job_id, "owner-a", 60)
            assert ok is True
            doc = await get_db().scheduler_locks.find_one({"_id": job_id}, {"_id": 0})
            assert doc is not None
            assert doc["owner_id"] == "owner-a"
            assert _as_utc(doc["locked_until"]) > datetime.now(timezone.utc)
        finally:
            await _cleanup()

    _run(_go())


def test_try_acquire_blocks_second_owner_while_lease_active() -> None:
    async def _go():
        await ensure_indexes()
        await _cleanup()
        job_id = f"{PREFIX}busy"
        try:
            assert await try_acquire(job_id, "owner-a", 120) is True
            assert await try_acquire(job_id, "owner-b", 120) is False
            doc = await get_db().scheduler_locks.find_one({"_id": job_id}, {"_id": 0})
            assert doc is not None
            assert doc["owner_id"] == "owner-a"
        finally:
            await _cleanup()

    _run(_go())


def test_try_acquire_allows_takeover_after_expiry() -> None:
    async def _go():
        await ensure_indexes()
        await _cleanup()
        job_id = f"{PREFIX}expired"
        now = datetime.now(timezone.utc)
        try:
            await get_db().scheduler_locks.insert_one({
                "_id": job_id,
                "owner_id": "owner-a",
                "locked_until": now - timedelta(seconds=5),
                "acquired_at": now - timedelta(minutes=5),
                "updated_at": now - timedelta(minutes=5),
            })
            assert await try_acquire(job_id, "owner-b", 60) is True
            doc = await get_db().scheduler_locks.find_one({"_id": job_id}, {"_id": 0})
            assert doc is not None
            assert doc["owner_id"] == "owner-b"
            assert _as_utc(doc["locked_until"]) > datetime.now(timezone.utc)
        finally:
            await _cleanup()

    _run(_go())


def test_release_deletes_only_matching_owner() -> None:
    async def _go():
        await ensure_indexes()
        await _cleanup()
        job_id = f"{PREFIX}release"
        try:
            assert await try_acquire(job_id, "owner-a", 60) is True
            await release(job_id, "owner-b")
            assert await get_db().scheduler_locks.find_one({"_id": job_id}) is not None
            await release(job_id, "owner-a")
            assert await get_db().scheduler_locks.find_one({"_id": job_id}) is None
        finally:
            await _cleanup()

    _run(_go())


def test_run_exclusive_skips_runner_when_lock_is_busy() -> None:
    async def _go():
        await ensure_indexes()
        await _cleanup()
        job_id = f"{PREFIX}skip"
        called = {"count": 0}

        async def _runner():
            called["count"] += 1
            return "ran"

        try:
            assert await try_acquire(job_id, "owner-a", 60) is True
            result = await run_exclusive(job_id, 60, _runner, owner_id="owner-b")
            assert result is None
            assert called["count"] == 0
        finally:
            await _cleanup()

    _run(_go())


def test_run_exclusive_executes_only_once_under_race() -> None:
    async def _go():
        await ensure_indexes()
        await _cleanup()
        job_id = f"{PREFIX}race"
        called = {"count": 0}

        async def _runner():
            called["count"] += 1
            await asyncio.sleep(0.05)
            return "ok"

        try:
            results = await asyncio.gather(
                run_exclusive(job_id, 60, _runner, owner_id="owner-a"),
                run_exclusive(job_id, 60, _runner, owner_id="owner-b"),
            )
            assert called["count"] == 1
            assert results.count("ok") == 1
            assert results.count(None) == 1
            assert await get_db().scheduler_locks.find_one({"_id": job_id}) is None
        finally:
            await _cleanup()

    _run(_go())