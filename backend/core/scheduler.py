"""
NXT8 background scheduler — Pulse + Daily Digest.

Lifespan-managed singleton. Jobs:
  • `pulse_tick`     — every PULSE_INTERVAL_MINUTES.  For every active
                       tenant: snapshot KPI → compare with prev → emit
                       nudge through `core.approval_gate` if rules fire.
  • `daily_digest`   — every day at DIGEST_HOUR in each tenant's tz.
                       Builds an AI-generated morning digest and pushes
                       to the owner's Telegram or WhatsApp chat.
  • `discover_tenants` — every 5m. Caches the active-tenant list so the
                       hot path doesn't query Mongo each tick.

Tenancy: a tenant is "active" if any user with that `company_id` has
logged in within the last TENANT_INACTIVE_DAYS days.

All cron behaviour is gated by env flags: PULSE_ENABLED / DIGEST_ENABLED.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.db import get_db
from core.scheduler_lock import run_exclusive

logger = logging.getLogger("nxt8.scheduler")


def _flag(name: str, default: str = "true") -> bool:
    return (os.environ.get(name) or default).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default


PULSE_ENABLED = _flag("PULSE_ENABLED", "true")
DIGEST_ENABLED = _flag("DIGEST_ENABLED", "true")
SESSION_CLEANUP_ENABLED = _flag("SESSION_CLEANUP_ENABLED", "true")
ANALYST_SELF_SCAN_ENABLED = _flag("ANALYST_SELF_SCAN_ENABLED", "true")
PULSE_INTERVAL_MINUTES = _int("PULSE_INTERVAL_MINUTES", 60)
DIGEST_HOUR = _int("DIGEST_HOUR", 9)
SESSION_CLEANUP_HOUR = _int("SESSION_CLEANUP_HOUR", 3)
ANALYST_SELF_SCAN_INTERVAL_HOURS = _int("ANALYST_SELF_SCAN_INTERVAL_HOURS", 6)
TENANT_INACTIVE_DAYS = _int("TENANT_INACTIVE_DAYS", 7)
DEFAULT_TZ = (os.environ.get("DIGEST_DEFAULT_TIMEZONE") or "Europe/Moscow").strip()
PULSE_LOCK_LEASE_SECONDS = 30 * 60
DIGEST_LOCK_LEASE_SECONDS = 2 * 60 * 60
SESSION_CLEANUP_LOCK_LEASE_SECONDS = 30 * 60
ANALYST_SELF_SCAN_LOCK_LEASE_SECONDS = 30 * 60


_scheduler: Optional[AsyncIOScheduler] = None
_active_tenants_cache: List[str] = []
_cache_refreshed_at: Optional[datetime] = None


# ---------------------------------------------------------------------
# Tenant discovery
# ---------------------------------------------------------------------


async def list_active_tenants(*, force: bool = False) -> List[str]:
    """Distinct `company_id`s whose users were active in the last N days."""
    global _active_tenants_cache, _cache_refreshed_at
    now = datetime.now(timezone.utc)
    if (
        not force
        and _cache_refreshed_at
        and (now - _cache_refreshed_at).total_seconds() < 300
    ):
        return list(_active_tenants_cache)

    cutoff = (now - timedelta(days=TENANT_INACTIVE_DAYS)).isoformat()
    try:
        ids = await get_db().users.distinct(
            "company_id",
            {"company_id": {"$exists": True, "$ne": ""}, "last_login_at": {"$gte": cutoff}},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("active tenants query failed: %s", e)
        ids = []
    _active_tenants_cache = [t for t in ids if t]
    _cache_refreshed_at = now
    return list(_active_tenants_cache)


# ---------------------------------------------------------------------
# Job runners
# ---------------------------------------------------------------------


async def _run_pulse_for_all() -> None:
    if not PULSE_ENABLED:
        return
    tenants = await list_active_tenants()
    if not tenants:
        logger.info("pulse_tick: 0 active tenants")
        return
    from agents import pulse as _pulse
    started_at = datetime.now(timezone.utc).isoformat()
    results = await asyncio.gather(
        *[_pulse.pulse_tick(t) for t in tenants], return_exceptions=True
    )
    nudges = sum((r or {}).get("nudges", 0) for r in results if isinstance(r, dict))
    errs = [str(r) for r in results if isinstance(r, Exception)]
    try:
        await get_db().scheduler_jobs.insert_one({
            "job": "pulse_tick",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "tenants": len(tenants),
            "nudges": int(nudges),
            "ok": not errs,
            "errors": errs[:5],
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("Suppressed error during pulse_tick cron logging: %s", type(e).__name__)
    logger.info("pulse_tick done: tenants=%d nudges=%d errors=%d", len(tenants), nudges, len(errs))


async def _run_digest_for_all() -> None:
    if not DIGEST_ENABLED:
        return
    tenants = await list_active_tenants()
    from agents import digest as _digest
    started_at = datetime.now(timezone.utc).isoformat()
    sent = 0
    skipped = 0
    for t in tenants:
        try:
            res = await _digest.build_and_send(t)
            if res.get("sent"):
                sent += 1
            else:
                skipped += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("digest for %s failed: %s", t, e)
    try:
        await get_db().scheduler_jobs.insert_one({
            "job": "daily_digest",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "tenants": len(tenants),
            "sent": sent,
            "skipped": skipped,
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("Suppressed error during daily_digest cron logging: %s", type(e).__name__)
    logger.info("daily_digest done: tenants=%d sent=%d skipped=%d", len(tenants), sent, skipped)


async def _refresh_tenants_cache() -> None:
    await list_active_tenants(force=True)


async def _run_session_cleanup() -> None:
    """M3 — daily 03:00 sweep of anonymous-session short-term memory.

    The 90-day TTL index on `sessions.expires_at` is the absolute backstop;
    this job runs the 24h-stale anon-only purge for a tighter retention.
    Known users (with stable user_id) are explicitly skipped inside
    `MemoryEngine.cleanup_expired_sessions`.
    """
    if not SESSION_CLEANUP_ENABLED:
        return
    started_at = datetime.now(timezone.utc).isoformat()
    deleted = 0
    err: Optional[str] = None
    try:
        from agents import memory as _mem
        deleted = await _mem.get_memory().cleanup_expired_sessions()
    except Exception as e:  # noqa: BLE001
        err = str(e)
        logger.warning("session cleanup failed: %s", e)
    try:
        await get_db().scheduler_jobs.insert_one({
            "job": "session_cleanup",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "deleted": int(deleted),
            "ok": err is None,
            "error": err,
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("Suppressed error during session_cleanup cron logging: %s", type(e).__name__)
    logger.info("session_cleanup done: deleted=%d", deleted)


async def _run_analyst_scan_for_all() -> None:
    """Run periodic analyst self-scan across active tenants."""
    if not ANALYST_SELF_SCAN_ENABLED:
        return
    tenants = await list_active_tenants()
    if not tenants:
        logger.info("analyst_self_scan: 0 active tenants")
        return
    from agents.personas import run_persona

    for tenant in tenants:
        try:
            await run_persona(
                persona_id="analyst",
                message=(
                    "Проведи self-scan системы: проверь avg_confidence, "
                    "escalation_rate, mock_rate, contradictions за последние 6 часов."
                ),
                company_id=tenant,
                user_id="system_analyst_scan",
                session_id=f"analyst_self_scan_{tenant}",
                plan_id="headquarters",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Analyst self-scan failed for %s: %s", tenant, e)


async def _run_pulse_for_all_locked() -> None:
    await run_exclusive("pulse_tick", PULSE_LOCK_LEASE_SECONDS, _run_pulse_for_all)


async def _run_digest_for_all_locked() -> None:
    await run_exclusive("daily_digest", DIGEST_LOCK_LEASE_SECONDS, _run_digest_for_all)


async def _run_session_cleanup_locked() -> None:
    await run_exclusive(
        "session_cleanup",
        SESSION_CLEANUP_LOCK_LEASE_SECONDS,
        _run_session_cleanup,
    )


async def _run_analyst_scan_locked() -> None:
    await run_exclusive(
        "analyst_self_scan",
        ANALYST_SELF_SCAN_LOCK_LEASE_SECONDS,
        _run_analyst_scan_for_all,
    )


# ---------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------


def start() -> None:
    """Idempotent — safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        return
    if not (PULSE_ENABLED or DIGEST_ENABLED or SESSION_CLEANUP_ENABLED or ANALYST_SELF_SCAN_ENABLED):
        logger.info("scheduler disabled (PULSE, DIGEST, SESSION_CLEANUP and ANALYST_SELF_SCAN all off)")
        return

    sch = AsyncIOScheduler(timezone="UTC")

    sch.add_job(
        _refresh_tenants_cache,
        IntervalTrigger(minutes=5),
        id="discover_tenants",
        name="Refresh active-tenant cache",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    if PULSE_ENABLED:
        sch.add_job(
            _run_pulse_for_all_locked,
            IntervalTrigger(minutes=max(1, PULSE_INTERVAL_MINUTES)),
            id="pulse_tick",
            name=f"Pulse every {PULSE_INTERVAL_MINUTES}m",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    if DIGEST_ENABLED:
        sch.add_job(
            _run_digest_for_all_locked,
            CronTrigger(hour=DIGEST_HOUR, minute=0, timezone=DEFAULT_TZ),
            id="daily_digest",
            name=f"Daily digest @ {DIGEST_HOUR}:00 {DEFAULT_TZ}",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    if SESSION_CLEANUP_ENABLED:
        sch.add_job(
            _run_session_cleanup_locked,
            CronTrigger(hour=SESSION_CLEANUP_HOUR, minute=0, timezone=DEFAULT_TZ),
            id="session_cleanup",
            name=f"Session cleanup @ {SESSION_CLEANUP_HOUR}:00 {DEFAULT_TZ}",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    if ANALYST_SELF_SCAN_ENABLED:
        sch.add_job(
            _run_analyst_scan_locked,
            IntervalTrigger(hours=max(1, ANALYST_SELF_SCAN_INTERVAL_HOURS)),
            id="analyst_self_scan",
            name=f"Analyst self-scan every {ANALYST_SELF_SCAN_INTERVAL_HOURS}h",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    sch.start()
    _scheduler = sch
    logger.info(
        "scheduler started · pulse_every=%dm digest_at=%02d:00 session_cleanup_at=%02d:00 analyst_scan_every=%dh %s",
        PULSE_INTERVAL_MINUTES, DIGEST_HOUR, SESSION_CLEANUP_HOUR, ANALYST_SELF_SCAN_INTERVAL_HOURS, DEFAULT_TZ,
    )


async def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception as e:  # noqa: BLE001
            logger.warning("Suppressed error during scheduler shutdown: %s", type(e).__name__)
        _scheduler = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler
