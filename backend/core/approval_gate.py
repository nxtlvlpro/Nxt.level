"""
NXT8 Approval Gate — каждое high-impact решение агентов проходит проверку
перед внедрением.

Когда подчинённый агент (HR-Mentor, Client Manager, Bookkeeper, и т.д.)
пытается выполнить действие из HIGH_IMPACT_ACTIONS (create_task, update_task,
delegate_to, create_cross_department_bridge, mempalace_store), это действие
НЕ выполняется напрямую — вместо этого создаётся запись в
`db.pending_approvals` со статусом "pending". Hermes (или человек-владелец
NXT8) затем явно approve/reject через UI или endpoint.

Approval — это контракт между агентами и владельцем компании: ничто
с реальным побочным эффектом не уходит в продакшн без явного "ОК".

Архитектура:
  agent → request_approval(agent_id, action, args, rationale?) → pending_id
                                              ↓
  Hermes/Human                                ↓
        approve(pending_id) → execute_pending(pending_id) → действие применяется
                       или
        reject(pending_id, reason)            → действие отменяется навсегда

Hermes и нодные роли Constitutional Graph имеют authority=AUTONOMOUS и
обходят этот gate (их решения и так от лица CEO).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.db import TenantAwareCRUD, get_db

logger = logging.getLogger("nxt8.approval_gate")

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_EXECUTED = "executed"
STATUS_FAILED = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def request_approval(
    *,
    agent_id: str,
    action: str,
    args: Dict[str, Any],
    company_id: str = "default",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    rationale: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a pending approval record. Returns the chip-friendly summary."""
    pid = str(uuid.uuid4())
    safe_args = {k: v for k, v in (args or {}).items() if k != "company_id"}
    doc = {
        "id": pid,
        "agent_id": agent_id,
        "action": action,
        "args": safe_args,
        "company_id": company_id,
        "user_id": user_id,
        "session_id": session_id,
        "rationale": rationale or "",
        "status": STATUS_PENDING,
        "created_at": _now(),
        "decided_at": None,
        "decided_by": None,
        "decision_reason": None,
        "result": None,
    }
    try:
        await TenantAwareCRUD(get_db().pending_approvals, company_id=company_id).insert_one(doc)
        logger.info(
            "approval requested: agent=%s action=%s id=%s", agent_id, action, pid
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("approval persist failed: %s", e)
        return {
            "ok": False,
            "error": f"approval persistence failed: {e}",
        }

    # Best-effort push to the owner's Telegram, if bound. Never block.
    try:
        from core import telegram_bot as _tg
        if _tg.is_enabled():
            import asyncio as _asyncio
            _asyncio.create_task(_tg.notify_pending_approval(doc))
    except Exception as e:  # noqa: BLE001
        logger.warning("telegram approval push failed: %s", e)

    # Same for WhatsApp.
    try:
        from core import whatsapp_bot as _wa
        if _wa.is_enabled():
            import asyncio as _asyncio
            _asyncio.create_task(_wa.notify_pending_approval(doc))
    except Exception as e:  # noqa: BLE001
        logger.warning("whatsapp approval push failed: %s", e)
    return {
        "ok": True,
        "pending": True,
        "approval_id": pid,
        "agent_id": agent_id,
        "action": action,
        "status": STATUS_PENDING,
        "message": (
            f"⏸ Действие '{action}' ожидает одобрения Hermes/владельца. "
            f"approval_id={pid}"
        ),
    }


async def list_pending(
    *,
    company_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    status: str = STATUS_PENDING,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if company_id:
        q["company_id"] = company_id
    if agent_id:
        q["agent_id"] = agent_id
    cursor = TenantAwareCRUD(
        get_db().pending_approvals,
        company_id=company_id,
        force_admin=company_id is None,
    ).find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    return await cursor.to_list(length=int(limit))


async def get_pending(pending_id: str, company_id: Optional[str] = None, *, force_admin: bool = False) -> Optional[Dict[str, Any]]:
    return await TenantAwareCRUD(get_db().pending_approvals, company_id=company_id, force_admin=force_admin).find_one(
        {"id": pending_id}, {"_id": 0}
    )


async def approve(
    pending_id: str,
    *,
    decided_by: str = "hermes",
    reason: Optional[str] = None,
    executor=None,
) -> Dict[str, Any]:
    """Mark as approved and run `executor(action, args)` if provided.

    `executor` is an async callable: `executor(action: str, args: dict) -> dict`.
    """
    rec = await get_pending(pending_id, force_admin=True)
    if not rec:
        return {"ok": False, "error": "pending not found"}
    if rec.get("status") != STATUS_PENDING:
        return {
            "ok": False,
            "error": f"approval already in status '{rec.get('status')}'",
            "current_status": rec.get("status"),
        }

    await TenantAwareCRUD(get_db().pending_approvals, company_id=rec.get("company_id")).update_one(
        {"id": pending_id},
        {
            "$set": {
                "status": STATUS_APPROVED,
                "decided_at": _now(),
                "decided_by": decided_by,
                "decision_reason": reason or "",
            }
        },
    )

    if executor is None:
        return {
            "ok": True,
            "approval_id": pending_id,
            "status": STATUS_APPROVED,
            "executed": False,
        }

    try:
        exec_result = await executor(rec["action"], dict(rec.get("args") or {}))
        await TenantAwareCRUD(get_db().pending_approvals, company_id=rec.get("company_id")).update_one(
            {"id": pending_id},
            {
                "$set": {
                    "status": STATUS_EXECUTED,
                    "result": exec_result,
                    "executed_at": _now(),
                }
            },
        )
        return {
            "ok": True,
            "approval_id": pending_id,
            "status": STATUS_EXECUTED,
            "executed": True,
            "result": exec_result,
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("approval execute failed: %s", e)
        await TenantAwareCRUD(get_db().pending_approvals, company_id=rec.get("company_id")).update_one(
            {"id": pending_id},
            {
                "$set": {
                    "status": STATUS_FAILED,
                    "result": {"ok": False, "error": str(e)},
                    "executed_at": _now(),
                }
            },
        )
        return {
            "ok": False,
            "approval_id": pending_id,
            "status": STATUS_FAILED,
            "error": str(e),
        }


async def reject(
    pending_id: str,
    *,
    decided_by: str = "hermes",
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    rec = await get_pending(pending_id, force_admin=True)
    if not rec:
        return {"ok": False, "error": "pending not found"}
    if rec.get("status") != STATUS_PENDING:
        return {
            "ok": False,
            "error": f"approval already in status '{rec.get('status')}'",
            "current_status": rec.get("status"),
        }
    await TenantAwareCRUD(get_db().pending_approvals, company_id=rec.get("company_id")).update_one(
        {"id": pending_id},
        {
            "$set": {
                "status": STATUS_REJECTED,
                "decided_at": _now(),
                "decided_by": decided_by,
                "decision_reason": reason or "",
            }
        },
    )
    return {"ok": True, "approval_id": pending_id, "status": STATUS_REJECTED}


async def stats(window_hours: int = 24) -> Dict[str, Any]:
    """Lightweight counters for an Ops dashboard widget."""
    crud = TenantAwareCRUD(get_db().pending_approvals)
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(hours=window_hours)
    ).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff_iso}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    by_status: Dict[str, int] = {}
    async for row in crud.aggregate(pipeline):
        by_status[row["_id"]] = int(row["count"])
    return {
        "ok": True,
        "window_hours": window_hours,
        "by_status": by_status,
        "total": sum(by_status.values()),
    }
