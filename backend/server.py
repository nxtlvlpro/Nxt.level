"""
NXT8 backend — single FastAPI process exposing all agents as /api endpoints.

All 10 ТЗ MVP components live in this process:
- orchestrator   — POST /api/chat, GET /api/requests
- memory         — /api/memory/{store,search,session}
- reliability    — embedded inside chat pipeline (POST /api/reliability/assess available)
- mentor         — /api/mentor/{employees,performance,patterns,recommend}
- roi            — /api/roi/{costs,deals,interactions,dashboard}
- alerts         — /api/alerts
- voice          — /api/voice (stub returning 'coming soon')
- system         — /api/health, /api/seed
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from core import auth as _auth_mod  # imported early — referenced by route decorators
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from agents import mentor as mentor_agent  # noqa: E402
from agents import memory as memory_agent  # noqa: E402
from agents import orchestrator as orchestrator_agent  # noqa: E402
from agents import reliability as reliability_agent  # noqa: E402
from agents import roi as roi_agent  # noqa: E402
from agents import voice as voice_agent  # noqa: E402
from agents import cross_dept as cross_dept_agent  # noqa: E402
from agents import diagnostics as diagnostics_agent  # noqa: E402
from agents import skill_creator as skills_agent  # noqa: E402
from agents import market_radar as market_agent  # noqa: E402
from agents import hermes_proxy as hermes_agent  # noqa: E402
from agents import hermes_coo as hermes_coo_agent  # noqa: E402
from agents import mempalace_bridge as mempalace_agent  # noqa: E402
from agents import personas as personas_agent  # noqa: E402
from agents import documents as documents_agent  # noqa: E402
from agents._pipeline_hooks import finalize_llm_turn  # noqa: E402
from nxt8_langgraph_ultra import run_nxt8_ultra  # noqa: E402
from core.db import (  # noqa: E402
    TenantAwareCRUD,
    close_db,
    ensure_indexes,
    get_db,
    reset_request_company_context,
    set_request_company_context,
)
from core.deepseek import get_deepseek  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("nxt8.server")


# ---------- background scheduler ----------


async def _roi_scheduler() -> None:
    """Hourly tick: ROI + session cleanup + diagnostics + skill discovery."""
    while True:
        try:
            await roi_agent.calculate_hourly_roi()
            await memory_agent.get_memory().cleanup_expired_sessions()
            try:
                await diagnostics_agent.scan_contradictions()
            except Exception as e:  # noqa: BLE001
                logger.warning("diagnostics scan failed: %s", e)
            try:
                await skills_agent.scan_and_register()
            except Exception as e:  # noqa: BLE001
                logger.warning("skill discovery failed: %s", e)
        except Exception as e:  # noqa: BLE001
            logger.exception("scheduler tick failed: %s", e)
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    # Tour analytics indexes (best effort — never block startup).
    try:
        from core import tour as _tour
        await _tour.ensure_indexes()
    except Exception as e:  # noqa: BLE001
        logger.warning("tour ensure_indexes failed: %s", e)
    # Share-My-Journey indexes (viral marketing channel).
    try:
        from core import share as _share
        await _share.ensure_indexes()
    except Exception as e:  # noqa: BLE001
        logger.warning("share ensure_indexes failed: %s", e)
    # Auth indexes (users + user_sessions).
    try:
        from core import auth as _auth
        await _auth.ensure_indexes()
    except Exception as e:  # noqa: BLE001
        logger.warning("auth ensure_indexes failed: %s", e)
    # Telegram channel — indexes + auto-install webhook (only if token set).
    try:
        from core import telegram_bot as _tg
        await _tg.ensure_indexes()
        if _tg.is_enabled():
            base_url = (os.environ.get("PUBLIC_BASE_URL") or "").strip()
            if base_url:
                res = await _tg.install_webhook(base_url)
                logger.info("telegram webhook install: %s", res.get("ok"))
            await _tg.get_bot_info(force=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("telegram bootstrap failed: %s", e)
    # WhatsApp channel — indexes only (Twilio inbound URL is configured
    # in the Twilio console, not via API).
    try:
        from core import whatsapp_bot as _wa
        await _wa.ensure_indexes()
        logger.info(
            "whatsapp channel enabled=%s from=%s",
            _wa.is_enabled(),
            _wa._phone_from_wa(_wa._from()) if _wa.is_enabled() else "—",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("whatsapp bootstrap failed: %s", e)
    # Seed default onboarding access code(s) — currently a single pilot code.
    try:
        from agents import onboarding as _onb
        await _onb.seed_default_codes()
    except Exception as e:  # noqa: BLE001
        logger.warning("onboarding seed failed: %s", e)
    # Memory Sprint · M1: backfill company_id on legacy sessions.
    try:
        from core.migrations import m_tag_memory_with_company_id as _m
        res = await _m.run()
        logger.info("memory backfill: %s", res)
    except Exception as e:  # noqa: BLE001
        logger.warning("memory backfill failed: %s", e)
    deepseek = get_deepseek()
    logger.info("DeepSeek mock_mode=%s model=%s", deepseek.mock_mode, deepseek.model)
    task = asyncio.create_task(_roi_scheduler())
    # Pulse + Daily-digest background scheduler.
    try:
        from core import scheduler as _sch
        _sch.start()
    except Exception as e:  # noqa: BLE001
        logger.warning("scheduler start failed: %s", e)
    try:
        yield
    finally:
        try:
            from core import scheduler as _sch
            await _sch.shutdown()
        except Exception:  # noqa: BLE001
            pass
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        close_db()


app = FastAPI(title="NXT8 API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def inject_company_context(request: Request, call_next):
    user = getattr(request.state, "user", None)
    company_id = getattr(request.state, "company_id", None)
    force_admin = bool(getattr(request.state, "force_admin", False))
    if user and getattr(user, "company_id", None):
        company_id = user.company_id
        force_admin = force_admin or bool(getattr(user, "is_admin", False))
    tokens = set_request_company_context(company_id, force_admin=force_admin)
    try:
        return await call_next(request)
    finally:
        reset_request_company_context(tokens)


api = APIRouter(prefix="/api")


# Map LLM-exhaustion exceptions to a clean 503. Triggered when every
# configured LLM provider failed AND `ALLOW_LLM_MOCK=false`. Frontend
# (`lib/api.js`) recognises `detail == "llm_unavailable"` and shows
# the dedicated toast.
from core.deepseek import LLMUnavailable as _LLMUnavailable  # noqa: E402
from fastapi.responses import JSONResponse as _JSONResp  # noqa: E402


@app.exception_handler(_LLMUnavailable)
async def _handle_llm_unavailable(_request: Request, exc: _LLMUnavailable):  # noqa: ARG001
    logger.warning("LLM unavailable: %s", exc)
    return _JSONResp(
        {"detail": "llm_unavailable", "note": getattr(exc, "note", ""), "errors": getattr(exc, "errors", "")},
        status_code=503,
    )


# =====================================================================
# Schemas
# =====================================================================


class ChatRequest(BaseModel):
    user_id: str = "anonymous"
    session_id: Optional[str] = None
    message: str
    channel: str = "web"
    context: Dict[str, Any] = Field(default_factory=dict)


class MemoryStoreRequest(BaseModel):
    content: str
    type: str = "corporate"  # corporate | episodic | semantic
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    type: Optional[str] = None


class EmployeeRequest(BaseModel):
    employee_id: Optional[str] = None
    name: str
    department: str = "general"
    level: str = "junior"
    experience_months: int = 0
    hire_date: Optional[str] = None
    manager_id: Optional[str] = None
    skills: List[str] = Field(default_factory=list)


class PerformanceRequest(BaseModel):
    employee_id: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    accuracy: float = 0.0
    speed: float = 1.0
    escalation_rate: float = 0.0
    error_repeat: int = 0
    tasks_completed: int = 0
    tasks_reviewed: int = 0


class DealRequest(BaseModel):
    deal_id: str
    value_usd: float
    team: str
    closed_at: Optional[str] = None


class InteractionRequest(BaseModel):
    deal_id: str
    agent: str
    interaction_type: str = "touch"


class ReliabilityRequest(BaseModel):
    response: str
    deepseek_confidence: float = 0.7
    source: str = "deepseek"
    evidence_count: int = 1
    past_responses: List[str] = Field(default_factory=list)
    memory_context: List[str] = Field(default_factory=list)


# =====================================================================
# System
# =====================================================================


@api.get("/")
async def root() -> Dict[str, Any]:
    return {
        "service": "NXT8",
        "version": "1.0.0",
        "modules": [
            "orchestrator", "memory", "reliability", "mentor", "roi", "voice",
            "cross_dept", "diagnostics", "skill_creator", "market_radar", "hermes",
        ],
    }


@api.get("/health")
async def health() -> Dict[str, Any]:
    db = get_db()
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    ds = get_deepseek()
    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongo": mongo_ok,
        "deepseek": {
            "mock_mode": ds.mock_mode,
            "model": ds.model,
            "last_error": ds.last_error,
            "live": ds.last_error is None and not ds.mock_mode,
            "active_provider": ds.active_provider,
            "providers": [p.name for p in ds.providers],
        },
        "voice": {
            "enabled": bool(os.environ.get("EMERGENT_LLM_KEY", "").strip()),
            "stt_model": "whisper-1",
            "tts_model": "tts-1",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api.post("/seed")
async def seed_demo(
    _admin: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_admin),
) -> Dict[str, Any]:
    """Insert demo corporate memory + employees + deals — for first WOW screen.

    Admin-only. Either:
      • header `X-Admin-Token: $SEED_ADMIN_TOKEN`, or
      • an authenticated session whose email is in `NXT8_ADMIN_EMAILS`.
    """
    DEMO_COMPANY_ID = "demo"
    mem = memory_agent.get_memory()
    memories = TenantAwareCRUD(get_db().memories, company_id=DEMO_COMPANY_ID, force_admin=True)
    interactions = TenantAwareCRUD(get_db().interactions, company_id=DEMO_COMPANY_ID, force_admin=True)

    # idempotent
    existing = await memories.count_documents({})
    if existing > 5:
        return {"status": "already_seeded", "memories": existing}

    corporate_docs = [
        ("Политика возвратов: возврат возможен в течение 14 дней с момента покупки при наличии чека.",
         {"department": "support", "priority": "high"}),
        ("Скидка для корпоративных клиентов от 100 пользователей — 15%, от 500 — 25%.",
         {"department": "sales", "priority": "high"}),
        ("План найма Q1: 12 инженеров, 4 продакт-менеджера, 2 дизайнера.",
         {"department": "hr", "priority": "medium"}),
        ("Текущий ARR компании: $4.8M. Целевой ARR на конец года: $7.5M.",
         {"department": "finance", "priority": "critical"}),
        ("NXT8 — AI-операционная система. Ядро на DeepSeek, единый интерфейс для всех корпоративных AI задач.",
         {"department": "product", "priority": "high"}),
        ("SLA для enterprise клиентов: 99.9% uptime, ответ в течение 15 минут.",
         {"department": "support", "priority": "high"}),
    ]
    for content, meta in corporate_docs:
        await mem.store_memory(content, memory_type="corporate", metadata=meta,
                               company_id=DEMO_COMPANY_ID)

    employees = [
        {"employee_id": "emp_alex", "name": "Alex Morgan", "department": "sales",
         "level": "senior", "experience_months": 38, "skills": ["enterprise", "negotiation"]},
        {"employee_id": "emp_carla", "name": "Carla Reyes", "department": "support",
         "level": "mid", "experience_months": 14, "skills": ["technical", "deescalation"]},
        {"employee_id": "emp_mike", "name": "Mike Chen", "department": "engineering",
         "level": "lead", "experience_months": 72, "skills": ["python", "architecture"]},
        {"employee_id": "emp_jr", "name": "Junior Lee", "department": "support",
         "level": "junior", "experience_months": 3, "skills": []},
    ]
    for e in employees:
        await mentor_agent.upsert_employee(e, company_id=DEMO_COMPANY_ID)

    # performance for junior — intentionally weak to trigger patterns
    base = datetime.now(timezone.utc)
    for i in range(4):
        await mentor_agent.record_performance({
            "employee_id": "emp_jr",
            "period_start": (base - timedelta(weeks=i + 1)).isoformat(),
            "period_end": (base - timedelta(weeks=i)).isoformat(),
            "accuracy": 0.55 - i * 0.02,
            "speed": 1.7,
            "escalation_rate": 0.42,
            "error_repeat": 2,
            "tasks_completed": 30,
            "tasks_reviewed": 18,
        }, company_id=DEMO_COMPANY_ID)
    # healthy performance for senior
    for i in range(4):
        await mentor_agent.record_performance({
            "employee_id": "emp_alex",
            "period_start": (base - timedelta(weeks=i + 1)).isoformat(),
            "period_end": (base - timedelta(weeks=i)).isoformat(),
            "accuracy": 0.93,
            "speed": 0.8,
            "escalation_rate": 0.04,
            "error_repeat": 0,
            "tasks_completed": 45,
            "tasks_reviewed": 2,
        }, company_id=DEMO_COMPANY_ID)

    # demo deals + interactions
    for i, value in enumerate([2400, 600, 1800, 950]):
        deal_id = f"deal_demo_{i}"
        # interactions BEFORE the deal close (1-4 days before)
        for day, agent in enumerate(["orchestrator", "memory", "orchestrator"]):
            await interactions.insert_one({
                "id": str(uuid.uuid4()),
                "deal_id": deal_id,
                "agent": agent,
                "interaction_type": "touch",
                "interaction_time": (base - timedelta(days=day + 1, hours=i)).isoformat(),
                "attributed_revenue": None,
                "company_id": DEMO_COMPANY_ID,
            })
        await roi_agent.record_deal(
            deal_id=deal_id,
            value_usd=float(value),
            team="sales",
            closed_at=(base - timedelta(hours=i)).isoformat(),
            company_id=DEMO_COMPANY_ID,
        )

    # synthetic costs over last hour to make ROI non-zero
    for _ in range(40):
        await roi_agent.record_api_cost(
            "orchestrator", tokens=15000, company_id=DEMO_COMPANY_ID
        )
    for _ in range(8):
        await roi_agent.record_escalation_cost(
            "support", minutes=5.0, company_id=DEMO_COMPANY_ID
        )

    # detect weak patterns for junior
    await mentor_agent.detect_weak_patterns("emp_jr", company_id=DEMO_COMPANY_ID)

    # generate first roi snapshot
    await roi_agent.calculate_hourly_roi(company_id=DEMO_COMPANY_ID)

    # seed market signals + first digest
    try:
        await market_agent.seed_demo_signals()
    except Exception as e:  # noqa: BLE001
        logger.warning("market seed failed: %s", e)

    return {
        "status": "seeded",
        "memories": len(corporate_docs),
        "employees": len(employees),
        "deals": 4,
    }


# =====================================================================
# Orchestrator / chat
# =====================================================================


@api.post("/chat")
async def chat(req: ChatRequest) -> Dict[str, Any]:
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    return await orchestrator_agent.route(
        user_id=req.user_id,
        session_id=session_id,
        message=req.message,
        channel=req.channel,
        context=req.context,
    )


@api.post("/v2/chat")
async def chat_v2(payload: dict) -> Dict[str, Any]:
    """Новый оптимизированный чат на базе Skills-based LangGraph."""
    from core.nxt8_graph import nxt8_graph
    import time

    message = (payload.get("message") or "").strip()
    if not message:
        return {"error": "message is required"}

    skill_id = payload.get("skill_id", "general")
    session_id = payload.get("session_id") or f"v2_sess_{uuid.uuid4().hex[:10]}"
    company_id = payload.get("company_id", "default")
    user_id = payload.get("user_id", "anonymous")

    t0 = time.time()
    initial_state = {
        "messages": [{"role": "user", "content": message}],
        "skill_id": skill_id,
        "company_id": company_id,
        "user_id": user_id,
        "session_id": session_id,
    }
    config = {"configurable": {"thread_id": session_id}}

    try:
        result = await nxt8_graph.ainvoke(initial_state, config)
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "success": True,
            "content": result["messages"][-1]["content"],
            "skill_id": result.get("skill_id", skill_id),
            "allowed_tools": result.get("allowed_tools", []),
            "tokens_total": result.get("tokens_total", 0),
            "confidence": result.get("confidence", 0.7),
            "session_id": session_id,
            "latency_ms": latency_ms,
            "mock": result.get("mock", False),
        }
    except Exception as e:  # noqa: BLE001
        logging.exception("Chat v2 graph execution failed")
        return {"success": False, "error": str(e)}


@api.get("/requests")
async def list_requests(
    limit: int = 20,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> List[Dict[str, Any]]:
    # Admin sees all tenants; regular users see only their company
    company_filter = None if user.is_admin else user.company_id
    return await orchestrator_agent.list_recent_requests(
        limit=limit, company_id=company_filter,
    )


@api.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    msgs = await memory_agent.get_memory().get_session(
        session_id,
        limit=200,
        company_id=None if user.is_admin else user.company_id,
    )
    return {"session_id": session_id, "messages": msgs}


# =====================================================================
# Memory
# =====================================================================


@api.post("/memory/store")
async def memory_store(
    req: MemoryStoreRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    mid = await memory_agent.get_memory().store_memory(
        content=req.content, memory_type=req.type, metadata=req.metadata,
        company_id=user.company_id,
    )
    return {"id": mid, "status": "stored"}


@api.post("/memory/search")
async def memory_search(
    req: MemorySearchRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    res = await memory_agent.get_memory().search(
        query=req.query, top_k=req.top_k, memory_type=req.type,
        company_id=user.company_id,
    )
    return {"count": len(res), "results": res}


@api.get("/memory/list")
async def memory_list(
    type: Optional[str] = None,
    limit: int = 100,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {"company_id": user.company_id}
    if type:
        q["type"] = type
    items = (
        await get_db()
        .memories.find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )
    return {"count": len(items), "items": items}


# =====================================================================
# MemPalace — long-term corporate memory (Wings → Rooms → Drawers)
# =====================================================================


class MemPalaceStoreRequest(BaseModel):
    content: str
    wing: str = "internal"
    room: str = "general"
    metadata: Optional[Dict[str, Any]] = None
    source: str = "nxt8"


class MemPalaceSearchRequest(BaseModel):
    query: str
    wing: Optional[str] = None
    room: Optional[str] = None
    top_k: int = 5


@api.get("/mempalace/health")
async def mempalace_health() -> Dict[str, Any]:
    return await mempalace_agent.get_mempalace().health()


@api.post("/mempalace/store")
async def mempalace_store(
    req: MemPalaceStoreRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    if not (req.content or "").strip():
        raise HTTPException(status_code=400, detail="content must not be empty")
    return await mempalace_agent.get_mempalace().store(
        content=req.content,
        wing=req.wing,
        logical_room=req.room,
        metadata=req.metadata,
        source=req.source,
        company_id=user.company_id,
    )


@api.post("/mempalace/search")
async def mempalace_search(
    req: MemPalaceSearchRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    items = await mempalace_agent.get_mempalace().search(
        query=req.query,
        wing=req.wing,
        logical_room=req.room,
        top_k=req.top_k,
        company_id=user.company_id,
    )
    return {"count": len(items), "results": items}


@api.get("/mempalace/wings")
async def mempalace_wings(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    wings = await mempalace_agent.get_mempalace().list_wings(
        company_id=user.company_id,
    )
    return {"count": len(wings), "wings": wings}


# =====================================================================
# Reliability (standalone, for external integration)
# =====================================================================


@api.post("/reliability/assess")
async def reliability_assess(req: ReliabilityRequest) -> Dict[str, Any]:
    rel = reliability_agent.assess(
        response=req.response,
        deepseek_confidence=req.deepseek_confidence,
        source=req.source,
        evidence_count=req.evidence_count,
        past_responses=req.past_responses,
        memory_context=req.memory_context,
    )
    return {
        "score": rel.score,
        "level": rel.level,
        "should_escalate": rel.should_escalate,
        "has_contradiction": rel.has_contradiction,
        "contradictions": rel.contradictions,
        "verification_status": rel.verification_status,
        "verification_ratio": rel.verification_ratio,
        "signals": rel.signals,
    }


# =====================================================================
# Mentor
# =====================================================================


@api.post("/mentor/employees")
async def mentor_upsert_employee(
    req: EmployeeRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    return await mentor_agent.upsert_employee(req.model_dump(), company_id=user.company_id)


@api.get("/mentor/employees")
async def mentor_list_employees(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    emps = await mentor_agent.list_employees(company_id=user.company_id)
    return {"count": len(emps), "employees": emps}


@api.get("/mentor/employees/{employee_id}")
async def mentor_employee_summary(
    employee_id: str,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    summary = await mentor_agent.employee_summary(employee_id, company_id=user.company_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail="not_found")
    return summary


@api.post("/mentor/performance")
async def mentor_record_performance(
    req: PerformanceRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    return await mentor_agent.record_performance(req.model_dump(), company_id=user.company_id)


@api.post("/mentor/detect/{employee_id}")
async def mentor_detect_patterns(
    employee_id: str,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    patterns = await mentor_agent.detect_weak_patterns(employee_id, company_id=user.company_id)
    return {"employee_id": employee_id, "patterns": patterns}


@api.get("/mentor/patterns")
async def mentor_list_patterns(
    limit: int = 50,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    items = await mentor_agent.list_open_patterns(company_id=user.company_id, limit=limit)
    return {"count": len(items), "patterns": items}


@api.get("/mentor/recommend/{employee_id}/{pattern}")
async def mentor_recommendation(
    employee_id: str,
    pattern: str,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    return await mentor_agent.generate_recommendation(employee_id, pattern, company_id=user.company_id)


# =====================================================================
# ROI / Profit Intelligence
# =====================================================================


def _roi_company_filter(user: "_auth_mod.AuthedUser") -> Optional[str]:
    """Resolve the tenant filter for ROI reads.

    Admins see global aggregates (`None`). All other users are strictly
    scoped to their own `company_id`.
    """
    return None if user.is_admin else user.company_id


async def _resolve_company_id(
    user_id: Optional[str], explicit: Optional[str] = None
) -> Optional[str]:
    """Best-effort tenant resolver for unauthenticated streaming endpoints.

    Order: explicit value → DB lookup by `user_id` → derive from email →
    `None` (global / untagged).
    """
    if explicit:
        return explicit
    if not user_id or user_id == "anonymous":
        return None
    try:
        u = await TenantAwareCRUD(get_db().users, force_admin=True).find_one({"user_id": user_id}, {"_id": 0})
        if u:
            cid = u.get("company_id")
            if cid:
                return cid
            email = u.get("email") or ""
            if email:
                return _auth_mod.derive_company_id(email)
    except Exception:  # noqa: BLE001
        pass
    return None


def _tenant_for_public_chat(
    authed_user: "Optional[_auth_mod.AuthedUser]", session_id: str
) -> str:
    """Tenant scope for OPEN (anonymous-allowed) chat/voice endpoints.

    NEVER trusts `company_id` from request body or form — that's a
    cross-tenant leak vector. Resolution order:
      1. Logged-in user → `user.company_id` (JWT-derived).
      2. Anonymous → session-isolated pool `anon_<session_id>` so each
         browser session is its own private tenant and cannot read another
         visitor's data even if they guess the session_id.
    """
    if authed_user and authed_user.company_id:
        return authed_user.company_id
    safe_sid = re.sub(r"[^a-zA-Z0-9_\-]", "_", session_id or "")[:64] or "session"
    return f"anon_{safe_sid}"


@api.get("/roi/dashboard")
async def roi_dashboard(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    return await roi_agent.dashboard_summary(company_id=_roi_company_filter(user))


@api.get("/roi/current")
async def roi_current(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    return await roi_agent.calculate_hourly_roi(company_id=_roi_company_filter(user))


@api.get("/roi/trend")
async def roi_trend(
    hours: int = 24,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    items = await roi_agent.roi_trend(
        hours=hours, company_id=_roi_company_filter(user)
    )
    return {"count": len(items), "items": items}


@api.post("/roi/deals")
async def roi_create_deal(
    req: DealRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    return await roi_agent.record_deal(
        deal_id=req.deal_id,
        value_usd=req.value_usd,
        team=req.team,
        closed_at=req.closed_at,
        company_id=user.company_id,
    )


@api.post("/roi/interactions")
async def roi_record_interaction(
    req: InteractionRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    await roi_agent.record_interaction(
        deal_id=req.deal_id,
        agent=req.agent,
        interaction_type=req.interaction_type,
        company_id=user.company_id,
    )
    return {"status": "recorded"}


# =====================================================================
# Alerts
# =====================================================================


@api.get("/alerts")
async def list_alerts(
    limit: int = 20,
    user: Optional["_auth_mod.AuthedUser"] = Depends(_auth_mod.optional_user),
) -> Dict[str, Any]:
    if user and user.is_admin:
        company_id = None
        force_admin = True
    elif user:
        company_id = user.company_id
        force_admin = False
    else:
        company_id = "demo"
        force_admin = False

    items = await TenantAwareCRUD(
        get_db().alerts,
        company_id=company_id,
        force_admin=force_admin,
    ).find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"count": len(items), "alerts": items}


# =====================================================================
# Voice — Whisper STT + OpenAI TTS via Emergent Universal Key
# =====================================================================


class TTSRequest(BaseModel):
    text: str
    voice: str = "onyx"
    speed: float = 1.0
    model: str = "tts-1"


@api.post("/voice/stt")
async def voice_stt(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Transcribe an uploaded audio blob (webm/mp3/wav/m4a/ogg) via Whisper."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio file")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audio exceeds 25 MB limit")
    try:
        result = await voice_agent.transcribe(
            file_bytes=raw,
            filename=file.filename or "audio.webm",
            language=language,
        )
        return result
    except Exception as e:  # noqa: BLE001
        logger.exception("STT failed: %s", e)
        raise HTTPException(status_code=502, detail=f"stt_failed: {e}")


@api.post("/voice/tts")
async def voice_tts(req: TTSRequest) -> Response:
    """Synthesize speech from text — returns audio/mpeg bytes."""
    try:
        audio = await voice_agent.synthesize(
            text=req.text, voice=req.voice, speed=req.speed, model=req.model
        )
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("TTS failed: %s", e)
        raise HTTPException(status_code=502, detail=f"tts_failed: {e}")


@api.post("/voice/tts/stream")
async def voice_tts_stream(req: TTSRequest) -> StreamingResponse:
    """Stream MP3 chunks from Fish Audio for low time-to-first-byte playback.

    On any Fish failure, the response degrades gracefully into a single-chunk
    stream filled with audio from the OpenAI fallback path so the browser
    `<audio>` element can still play.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    async def producer():
        primed = False
        try:
            async for chunk in voice_agent.fish_synthesize_stream(text, lang=None):
                primed = True
                yield chunk
            if primed:
                return
        except Exception as e:  # noqa: BLE001
            logger.warning("voice_tts_stream Fish failed, falling back: %s", e)
        # Fallback: single-shot OpenAI/Emergent path, sent as one chunk.
        try:
            audio = await voice_agent.synthesize(
                text=text, voice=req.voice, speed=req.speed, model=req.model
            )
            yield audio
        except Exception as e:  # noqa: BLE001
            logger.exception("voice_tts_stream fallback failed: %s", e)
            # Nothing else to do — client gets an empty stream, browser will
            # emit a media error which the frontend already handles.

    return StreamingResponse(
        producer(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


VOICE_REPLY_MAX_CHARS = 500
VOICE_REPLY_MAX_SENTENCES = 4
VOICE_SYSTEM_HINT = (
    "ВАЖНО: это голосовой канал. Ответ должен звучать как живая речь — "
    "разговорный тон, без markdown, без нумерованных списков, без JSON и без кода. "
    "Никаких заголовков типа 'Summary' или '1.'. По умолчанию держись в пределах "
    "3-4 предложений, но если вопрос требует развёрнутого пояснения — отвечай "
    "столько, сколько нужно, чтобы быть исчерпывающим, и не обрывай мысль на "
    "полуслове ради краткости."
)


def _trim_for_voice(text: str) -> str:
    """Strip markdown noise and clamp to a TTS-friendly length."""
    import re

    if not text:
        return ""
    t = text.strip()
    # Remove fenced code blocks
    t = re.sub(r"```[\s\S]*?```", " ", t)
    # Remove markdown emphasis/headers/list markers
    t = re.sub(r"^[ \t]*#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^[ \t]*[-*•]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^[ \t]*\d+[\.\)]\s+", "", t, flags=re.MULTILINE)
    t = t.replace("**", "").replace("__", "").replace("`", "")
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    # Keep first N sentences
    parts = re.split(r"(?<=[.!?…])\s+", t)
    if len(parts) > VOICE_REPLY_MAX_SENTENCES:
        t = " ".join(parts[:VOICE_REPLY_MAX_SENTENCES]).strip()
    # Hard cap
    if len(t) > VOICE_REPLY_MAX_CHARS:
        t = t[: VOICE_REPLY_MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:- ") + "…"
    return t


@api.post("/voice/converse")
async def voice_converse(
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    voice: str = Form("onyx"),
    authed: "Optional[_auth_mod.AuthedUser]" = Depends(_auth_mod.optional_user),
) -> Dict[str, Any]:
    """One-shot voice loop: STT → Hermes COO (tools) → trim → TTS (base64 mp3)."""
    import base64
    import time as _time

    t0 = _time.time()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio file")
    try:
        stt = await voice_agent.transcribe(
            file_bytes=raw,
            filename=file.filename or "audio.webm",
            language=language,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("converse STT failed: %s", e)
        raise HTTPException(status_code=502, detail=f"stt_failed: {e}")

    user_text = stt["text"]
    if not user_text:
        raise HTTPException(status_code=422, detail="no speech detected")

    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    # Tenant from JWT or session-isolated for anon — NEVER from request body.
    v_company_id = _tenant_for_public_chat(authed, sid)

    # Build conversation: prior session memory + voice hint + current turn
    history: List[Dict[str, Any]] = []
    try:
        mem = memory_agent.get_memory()
        prev = await mem.get_session(sid, limit=6, company_id=v_company_id)
        for m in prev or []:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})
    except Exception as mem_err:  # noqa: BLE001
        logger.warning("voice memory read failed: %s", mem_err)

    messages = (
        [{"role": "system", "content": VOICE_SYSTEM_HINT}]
        + history
        + [{"role": "user", "content": user_text}]
    )

    try:
        chat_resp = await hermes_coo_agent.enhanced_chat(
            messages=messages,
            company_id=v_company_id,
            user_id=user_id,
            mode="operational",
            temperature=0.3,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("voice hermes chat failed: %s", e)
        raise HTTPException(status_code=502, detail=f"hermes_failed: {e}")

    raw_reply = (chat_resp.get("content") or "").strip()
    reply_text = _trim_for_voice(raw_reply)

    # Persist to short-term memory (best effort)
    try:
        mem = memory_agent.get_memory()
        await mem.append_message(sid, "user", user_text,
                                 user_id=user_id, company_id=v_company_id)
        if reply_text:
            await mem.append_message(sid, "assistant", reply_text,
                                     user_id=user_id, company_id=v_company_id)
    except Exception as mem_err:  # noqa: BLE001
        logger.warning("voice memory append failed: %s", mem_err)

    audio_b64: Optional[str] = None
    tts_error: Optional[str] = None
    if reply_text:
        try:
            audio_bytes = await voice_agent.synthesize(
                text=reply_text,
                voice=voice,
                lang=(stt.get("language") or "en"),
            )
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        except Exception as e:  # noqa: BLE001
            logger.exception("converse TTS failed: %s", e)
            tts_error = str(e)
    else:
        tts_error = "empty_reply_from_hermes"

    # Universal pipeline hook: cost + reliability + unified audit
    latency_ms = int((_time.time() - t0) * 1000)
    hook_res = await finalize_llm_turn(
        channel="voice",
        agent="hermes_coo",
        user_id=user_id,
        session_id=sid,
        message=user_text,
        response_text=reply_text or raw_reply,
        tokens_total=int(chat_resp.get("tokens_total", 0) or 0),
        deepseek_confidence=float(chat_resp.get("confidence", 0.7) or 0.7),
        evidence_count=0,
        past_responses=[m.get("content", "") for m in history if m.get("role") == "assistant"],
        memory_context=[],
        intent="voice",
        agent_chain=["voice_stt", "hermes_coo", "voice_tts"],
        mock=bool(chat_resp.get("mock")),
        latency_ms=latency_ms,
        extra={"language": stt.get("language"), "voice": voice},
    )

    return {
        "session_id": sid,
        "transcript": user_text,
        "language": stt.get("language"),
        "reply": reply_text,
        "reply_raw": raw_reply if raw_reply != reply_text else None,
        "confidence": hook_res.get("confidence", chat_resp.get("confidence")),
        "confidence_level": hook_res.get("confidence_level"),
        "should_escalate": hook_res.get("should_escalate", False),
        "verification_status": hook_res.get("verification_status"),
        "request_id": hook_res.get("request_id"),
        "tools_used": [t.get("name") for t in (chat_resp.get("tool_calls") or []) if isinstance(t, dict)],
        "iterations": chat_resp.get("iterations", 0),
        "provider": chat_resp.get("provider"),
        "fallback": chat_resp.get("fallback"),
        "agent": "hermes_coo",
        "audio_b64": audio_b64,
        "audio_format": "mp3" if audio_b64 else None,
        "tts_error": tts_error,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------
# Streaming voice converse — sentence-chunk TTS over NDJSON
# ---------------------------------------------------------------------
# Lets the frontend start playing the first sentence as soon as it's
# synthesised, instead of waiting for the full reply to be TTS'd.
# Frames:
#   {"type":"meta","session_id":"..."}                         — once at start
#   {"type":"transcript","text":"..."}                         — STT result
#   {"type":"reply_text","text":"<full Hermes reply trimmed>"} — text-only reply
#   {"type":"audio_chunk","idx":0,"text":"<sentence>","audio_b64":"..."}
#   ...                                                        — one per sentence, IN ORDER
#   {"type":"done","latency_ms":1234}                          — final close
#   {"type":"error","message":"..."}                           — on failure


_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|\n+")


def _split_sentences_for_tts(text: str, max_chunks: int = 4) -> List[str]:
    """Split a Hermes voice reply into independently-TTS-able chunks."""
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_RE.split(text) if p.strip()]
    if not parts:
        return [text]
    return parts[:max_chunks]


@api.post("/voice/converse_stream")
async def voice_converse_stream(
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    voice: str = Form("onyx"),
    authed: "Optional[_auth_mod.AuthedUser]" = Depends(_auth_mod.optional_user),
) -> StreamingResponse:
    """Same as /voice/converse but streams sentence-by-sentence audio chunks."""
    import asyncio
    import base64
    import json
    import time as _time

    t0 = _time.time()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio file")
    filename = file.filename or "audio.webm"
    # Session id is needed up-front so we can lock the anonymous tenant
    # scope BEFORE entering the stream generator (where Depends can't run).
    sid_locked = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    vs_company_id = _tenant_for_public_chat(authed, sid_locked)

    async def event_stream():
        try:
            stt = await voice_agent.transcribe(
                file_bytes=raw, filename=filename, language=language
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("converse_stream STT failed: %s", e)
            yield json.dumps({"type": "error", "message": f"stt_failed: {e}"}) + "\n"
            return

        user_text = stt.get("text") or ""
        if not user_text:
            yield json.dumps({"type": "error", "message": "no speech detected"}) + "\n"
            return

        sid = sid_locked
        v_company_id = _tenant_for_public_chat(authed, sid)
        yield json.dumps({"type": "meta", "session_id": sid}) + "\n"
        yield json.dumps({"type": "transcript", "text": user_text}) + "\n"

        # Pull a few prior turns from memory for session context.
        history: List[Dict[str, Any]] = []
        try:
            mem = memory_agent.get_memory()
            prev = await mem.get_session(sid, limit=6, company_id=v_company_id)
            for m in prev or []:
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and content:
                    history.append({"role": role, "content": content})
        except Exception as mem_err:  # noqa: BLE001
            logger.warning("voice_stream memory read failed: %s", mem_err)

        messages = (
            [{"role": "system", "content": VOICE_SYSTEM_HINT}]
            + history
            + [{"role": "user", "content": user_text}]
        )

        try:
            chat_resp = await hermes_coo_agent.enhanced_chat(
                messages=messages,
                company_id=vs_company_id,
                user_id=user_id,
                mode="operational",
                temperature=0.3,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("voice_stream hermes failed: %s", e)
            yield json.dumps({"type": "error", "message": f"hermes_failed: {e}"}) + "\n"
            return

        raw_reply = (chat_resp.get("content") or "").strip()
        reply_text = _trim_for_voice(raw_reply)
        yield json.dumps({"type": "reply_text", "text": reply_text}) + "\n"

        # Persist memory.
        try:
            mem = memory_agent.get_memory()
            await mem.append_message(sid, "user", user_text,
                                     user_id=user_id, company_id=vs_company_id)
            if reply_text:
                await mem.append_message(sid, "assistant", reply_text,
                                         user_id=user_id, company_id=vs_company_id)
        except Exception as mem_err:  # noqa: BLE001
            logger.warning("voice_stream memory append failed: %s", mem_err)

        # Synthesize each sentence in parallel, stream chunks IN ORDER.
        sentences = _split_sentences_for_tts(reply_text)
        if not sentences:
            yield json.dumps({"type": "error", "message": "empty_reply_from_hermes"}) + "\n"
            return

        async def tts_one(idx: int, text: str):
            try:
                audio_bytes = await voice_agent.synthesize(
                    text=text,
                    voice=voice,
                    lang=(stt.get("language") or "en"),
                )
                return idx, text, base64.b64encode(audio_bytes).decode("ascii"), None
            except Exception as e:  # noqa: BLE001
                logger.exception("voice_stream tts chunk %d failed: %s", idx, e)
                return idx, text, None, str(e)

        tasks = [asyncio.create_task(tts_one(i, s)) for i, s in enumerate(sentences)]
        # Strict in-order emission: await tasks sequentially. Because they all
        # started in parallel above, later sentences are often ready by the
        # time we await them — the user perceives near-zero gap.
        for tsk in tasks:
            idx, text, b64, err = await tsk
            frame = {"type": "audio_chunk", "idx": idx, "text": text}
            if b64:
                frame["audio_b64"] = b64
            if err:
                frame["error"] = err
            yield json.dumps(frame) + "\n"

        latency_ms = int((_time.time() - t0) * 1000)
        # Fire-and-forget pipeline hook for cost / audit (don't block stream).
        try:
            await finalize_llm_turn(
                channel="voice",
                agent="hermes_coo",
                user_id=user_id,
                session_id=sid,
                message=user_text,
                response_text=reply_text or raw_reply,
                tokens_total=int(chat_resp.get("tokens_total", 0) or 0),
                deepseek_confidence=float(chat_resp.get("confidence", 0.7) or 0.7),
                evidence_count=0,
                past_responses=[m.get("content", "") for m in history if m.get("role") == "assistant"],
                memory_context=[],
                intent="voice",
                agent_chain=["voice_stt", "hermes_coo", "voice_tts_stream"],
                mock=bool(chat_resp.get("mock")),
                latency_ms=latency_ms,
                extra={"language": stt.get("language"), "voice": voice, "chunks": len(sentences)},
            )
        except Exception as hook_err:  # noqa: BLE001
            logger.warning("voice_stream pipeline hook failed: %s", hook_err)

        yield json.dumps({"type": "done", "latency_ms": latency_ms}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


# =====================================================================
# Streaming chat (SSE)
# =====================================================================


@api.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Server-Sent Events stream of an orchestrator response.

    Frame format:
        event: meta   data: {session_id, intent, ...}
        event: delta  data: {text}
        event: done   data: {confidence, latency_ms, ...}
        event: error  data: {message}
    """
    import json as _json
    import time as _time

    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:12]}"

    async def gen():
        t0 = _time.time()
        deepseek = get_deepseek()
        mem = memory_agent.get_memory()

        try:
            stream_company_id = await _resolve_company_id(req.user_id)
            await mem.append_message(session_id, "user", req.message,
                                     user_id=req.user_id, company_id=stream_company_id)
            ctx = await mem.get_optimal_context(req.message, session_id, max_chars=6000,
                                                company_id=stream_company_id)

            # Quick intent classify via fast model call (small max_tokens)
            intent_resp = await deepseek.chat(
                messages=[
                    {"role": "system", "content":
                        "Classify into ONE of: knowledge, task, mentor, roi, voice, general. "
                        "Respond with ONLY the category name."},
                    {"role": "user", "content": req.message},
                ],
                temperature=0.0,
                max_tokens=10,
                request_logprobs=False,
            )
            intent_raw = (intent_resp.get("content") or "general").strip().lower().split()[0]
            valid = {"knowledge", "task", "mentor", "roi", "voice", "general"}
            intent = intent_raw if intent_raw in valid else "general"

            yield f"event: meta\ndata: {_json.dumps({'session_id': session_id, 'intent': intent})}\n\n"

            messages_for_llm = [
                {"role": "system", "content":
                    "Ты NXT8 — AI-операционная система. Отвечай на русском, по делу, "
                    "используй корпоративный контекст, не выдумывай."},
                {"role": "system", "content": f"## Context\n{ctx['context']}"},
                {"role": "user", "content": req.message},
            ]

            full_chunks: list[str] = []
            stream_usage: Dict[str, int] = {}
            async for delta in deepseek.chat_stream(
                messages=messages_for_llm,
                temperature=0.6,
                max_tokens=1024,
                usage_out=stream_usage,
            ):
                full_chunks.append(delta)
                yield f"event: delta\ndata: {_json.dumps({'text': delta})}\n\n"

            full = "".join(full_chunks)
            await mem.append_message(session_id, "assistant", full,
                                     user_id=req.user_id, company_id=stream_company_id)

            # Long-term memory: store the user/assistant exchange in MemPalace
            # under chats/{session_id}. Fire-and-forget; never blocks streaming.
            try:
                if len(req.message.strip()) >= 12 and len(full.strip()) >= 20:
                    asyncio.create_task(
                        mempalace_agent.get_mempalace().store(
                            content=f"USER: {req.message}\nASSISTANT: {full}",
                            wing="chats",
                            logical_room=session_id,
                            metadata={
                                "user_id": req.user_id,
                                "intent": intent,
                                "channel": "stream",
                            },
                            source="chat_stream",
                            company_id=stream_company_id,
                        )
                    )
            except Exception as _mp_err:  # noqa: BLE001
                logger.debug("mempalace autosave skipped: %s", _mp_err)

            # post-stream reliability + cost + unified audit via hook.
            # Token accounting (Sprint A · Fix 2):
            #   real_stream_tokens — from `stream_options: include_usage`.
            #   intent_tokens      — quick classifier call.
            #   fallback estimate  — (prompt_chars + reply_chars) / 4 when
            #                        provider didn't emit a usage chunk.
            past = [m["content"] for m in (await mem.get_session(session_id, limit=10, company_id=stream_company_id))
                    if m.get("role") == "assistant"]
            mem_ctx_texts = [r.get("content", "") for r in ctx.get("retrieved", [])]
            latency_ms = int((_time.time() - t0) * 1000)
            intent_tokens = int(intent_resp.get("tokens_total", 0) or 0)
            stream_tokens = int(stream_usage.get("total_tokens", 0) or 0)
            if stream_tokens == 0:
                prompt_chars = sum(len(m.get("content", "")) for m in messages_for_llm)
                stream_tokens = max(1, (prompt_chars + len(full)) // 4)
            total_tokens = intent_tokens + stream_tokens
            company_id = await _resolve_company_id(req.user_id)
            hook_res = await finalize_llm_turn(
                channel="stream",
                agent="orchestrator_stream",
                user_id=req.user_id,
                session_id=session_id,
                message=req.message,
                response_text=full,
                tokens_total=total_tokens,
                deepseek_confidence=0.78,  # streamed; no logprobs aggregate
                evidence_count=len(mem_ctx_texts),
                past_responses=past,
                memory_context=mem_ctx_texts,
                intent=intent,
                agent_chain=["orchestrator(stream)"],
                mock=False,
                latency_ms=latency_ms,
                company_id=company_id,
            )

            done_payload = {
                "request_id": hook_res.get("request_id"),
                "session_id": session_id,
                "intent": intent,
                "confidence": hook_res.get("confidence"),
                "confidence_level": hook_res.get("confidence_level"),
                "should_escalate": hook_res.get("should_escalate"),
                "verification_status": hook_res.get("verification_status"),
                "latency_ms": latency_ms,
                "provider": deepseek.active_provider,
            }
            yield f"event: done\ndata: {_json.dumps(done_payload)}\n\n"
        except Exception as e:  # noqa: BLE001
            logger.exception("stream pipeline failed: %s", e)
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# =====================================================================
# Hermes Talk — chained LLM stream → sentence buffer → TTS stream
# =====================================================================
# Frame format (SSE):
#   event: text   data: {"chunk": "<delta>"}              ← raw LLM token
#   event: voice  data: {"i": <sentence_idx>, "audio_b64": "<base64 mp3>"}
#   event: done   data: {"latency_ms": <int>}
#
# The audio of sentence N can start playing while sentence N+1 is still
# being generated by the LLM. This gives ~250-400 ms time-to-first-sound
# instead of waiting for the full reply.


class HermesTalkRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    lang: Optional[str] = None


_SENT_END = (".", "!", "?", "…")


def _flush_sentence(buf: str) -> tuple:
    """If `buf` contains at least one sentence boundary, return (sentence, rest).
    Otherwise return (None, buf)."""
    for i, ch in enumerate(buf):
        if ch in _SENT_END:
            j = i + 1
            while j < len(buf) and buf[j] in ' "\'»)':
                j += 1
            sent = buf[:j].strip()
            if len(sent) >= 12:
                return sent, buf[j:]
    return None, buf


@api.post("/hermes/talk")
async def hermes_talk(
    req: HermesTalkRequest,
    authed: "Optional[_auth_mod.AuthedUser]" = Depends(_auth_mod.optional_user),
) -> StreamingResponse:
    """Real-time talk: streams LLM tokens AND Fish-Audio TTS chunks of each
    completed sentence as they're generated. Designed for live voice/chat UX
    where the first audio plays in ~300 ms."""
    import base64 as _b64
    import json as _json
    import time as _time

    session_id = req.session_id or f"talk_{uuid.uuid4().hex[:10]}"
    # Tenant is derived from JWT for logged-in users, or session-isolated for
    # anonymous visitors. `company_id` is NEVER read from the request body.
    talk_company_id = _tenant_for_public_chat(authed, session_id)

    async def gen():
        t0 = _time.time()
        deepseek = get_deepseek()
        mem = memory_agent.get_memory()

        try:
            await mem.append_message(session_id, "user", req.message,
                                     user_id=req.user_id, company_id=talk_company_id)

            from agents.hermes import _system_prompt as _hermes_sys
            from agents.onboarding import get_company_manifest, render_company_manifest_block

            sys_msgs = [
                {"role": "system", "content": _hermes_sys("operational", "assistant")},
                {"role": "system",
                 "content": "Это голосовой канал. Отвечай разговорно, без markdown, без "
                            "списков, без JSON, законченными предложениями. 3-4 предложения "
                            "по умолчанию, развёрнуто только если вопрос требует."},
            ]
            if req.user_id:
                cm = await get_company_manifest(req.user_id)
                if cm:
                    lang = "ru" if (cm.get("lang") or "ru").startswith("ru") else "en"
                    sys_msgs.append({"role": "system",
                                     "content": render_company_manifest_block(cm, lang)})

            yield f"event: meta\ndata: {_json.dumps({'session_id': session_id})}\n\n"

            full_chunks: List[str] = []
            buf = ""
            sent_idx = 0
            stream_usage: Dict[str, int] = {}

            async def tts_and_emit(sentence: str, idx: int):
                try:
                    audio = await voice_agent.synthesize(text=sentence, lang=req.lang)
                    b64 = _b64.b64encode(audio).decode("ascii")
                    return f"event: voice\ndata: {_json.dumps({'i': idx, 'audio_b64': b64, 'text': sentence})}\n\n"
                except Exception as e:  # noqa: BLE001
                    logger.warning("talk TTS sentence %d failed: %s", idx, e)
                    return f"event: voice_err\ndata: {_json.dumps({'i': idx, 'error': str(e)[:120]})}\n\n"

            async for delta in deepseek.chat_stream(
                messages=sys_msgs + [{"role": "user", "content": req.message}],
                temperature=0.4,
                max_tokens=1200,
                usage_out=stream_usage,
            ):
                full_chunks.append(delta)
                buf += delta
                yield f"event: text\ndata: {_json.dumps({'chunk': delta})}\n\n"

                while True:
                    sentence, buf = _flush_sentence(buf)
                    if not sentence:
                        break
                    frame = await tts_and_emit(sentence, sent_idx)
                    sent_idx += 1
                    yield frame

            tail = buf.strip()
            if len(tail) >= 6:
                yield await tts_and_emit(tail, sent_idx)
                sent_idx += 1

            full = "".join(full_chunks)
            await mem.append_message(session_id, "assistant", full,
                                     user_id=req.user_id, company_id=talk_company_id)

            latency_ms = int((_time.time() - t0) * 1000)

            # Universal pipeline hook (Sprint A · Fix 2):
            # voice/talk was the last LLM channel bypassing audit + ROI.
            # Without this, ~all voice traffic was missing from the ROI
            # dashboard and from /api/requests.
            try:
                prompt_chars = sum(len(m.get("content", "")) for m in sys_msgs) + len(req.message)
                stream_tokens = int(stream_usage.get("total_tokens", 0) or 0)
                if stream_tokens == 0:
                    stream_tokens = max(1, (prompt_chars + len(full)) // 4)
                past = [
                    m["content"] for m in (await mem.get_session(session_id, limit=10, company_id=talk_company_id))
                    if m.get("role") == "assistant"
                ]
                await finalize_llm_turn(
                    channel="talk",
                    agent="hermes_talk",
                    user_id=req.user_id or "anonymous",
                    session_id=session_id,
                    message=req.message,
                    response_text=full,
                    tokens_total=stream_tokens,
                    deepseek_confidence=0.78,
                    evidence_count=0,
                    past_responses=past,
                    memory_context=[],
                    intent="voice",
                    agent_chain=["hermes_talk(stream)", "voice_tts"],
                    mock=False,
                    latency_ms=latency_ms,
                    extra={"sentences": sent_idx, "lang": req.lang},
                    company_id=talk_company_id,
                )
            except Exception as _hook_err:  # noqa: BLE001
                logger.warning("hermes_talk finalize_llm_turn failed: %s", _hook_err)

            yield f"event: done\ndata: {_json.dumps({'latency_ms': latency_ms, 'sentences': sent_idx})}\n\n"

        except Exception as e:  # noqa: BLE001
            logger.exception("hermes_talk stream failed: %s", e)
            yield f"event: error\ndata: {_json.dumps({'message': str(e)[:200]})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )



# =====================================================================
# Cross-Department Coordinator
# =====================================================================


class CrossDeptRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    session_id: Optional[str] = None


@api.post("/cross-dept/coordinate")
async def cross_dept_coordinate(req: CrossDeptRequest) -> Dict[str, Any]:
    return await cross_dept_agent.coordinate(
        query=req.query, user_id=req.user_id, session_id=req.session_id
    )


@api.get("/cross-dept/tasks")
async def cross_dept_tasks(limit: int = 20) -> Dict[str, Any]:
    items = await cross_dept_agent.list_tasks(limit=limit)
    return {"count": len(items), "tasks": items}


@api.get("/cross-dept/detect")
async def cross_dept_detect(query: str) -> Dict[str, Any]:
    depts = cross_dept_agent.detect_departments(query)
    return {"query": query, "departments": depts, "multi_department": len(depts) >= 2}


# =====================================================================
# Diagnostics
# =====================================================================


@api.post("/diagnostics/scan")
async def diagnostics_scan(
    window: int = 200,
    sim_threshold: float = 0.45,
    divergence_threshold: float = 0.3,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    company_filter = None if user.is_admin else user.company_id
    return await diagnostics_agent.scan_contradictions(
        window=window,
        sim_threshold=sim_threshold,
        divergence_threshold=divergence_threshold,
        company_id=company_filter,
    )


@api.get("/diagnostics/contradictions")
async def diagnostics_list(
    limit: int = 30,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    company_filter = None if user.is_admin else user.company_id
    items = await diagnostics_agent.list_contradictions(limit=limit, company_id=company_filter)
    return {"count": len(items), "contradictions": items}


@api.get("/diagnostics/summary")
async def diagnostics_summary(
    window: int = 200,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    company_filter = None if user.is_admin else user.company_id
    return await diagnostics_agent.summary(window=window, company_id=company_filter)


# =====================================================================
# Skill Creator
# =====================================================================


class SkillRequest(BaseModel):
    name: Optional[str] = None
    intent: str = "general"
    signature_terms: List[str] = Field(default_factory=list)
    prompt_template: Optional[str] = None
    memory_filter: Dict[str, Any] = Field(default_factory=dict)


@api.post("/skills/scan")
async def skills_scan() -> Dict[str, Any]:
    return await skills_agent.scan_and_register()


@api.get("/skills")
async def skills_list(enabled: bool = False, limit: int = 100) -> Dict[str, Any]:
    items = await skills_agent.list_skills(only_enabled=enabled, limit=limit)
    return {"count": len(items), "skills": items}


@api.post("/skills")
async def skills_create(req: SkillRequest) -> Dict[str, Any]:
    return await skills_agent.create_skill(req.model_dump())


@api.post("/skills/{skill_id}/toggle")
async def skills_toggle(skill_id: str, enabled: bool = True) -> Dict[str, Any]:
    res = await skills_agent.toggle_skill(skill_id, enabled=enabled)
    if not res:
        raise HTTPException(status_code=404, detail="skill not found")
    return res


# =====================================================================
# Market Radar
# =====================================================================


class MarketSignalRequest(BaseModel):
    headline: str
    source: str = "manual"
    category: str = "tech"
    url: Optional[str] = None
    score: float = 0.5


@api.post("/market/signals")
async def market_ingest(req: MarketSignalRequest) -> Dict[str, Any]:
    try:
        return await market_agent.ingest_signal(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api.get("/market/signals")
async def market_list_signals(category: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    items = await market_agent.list_signals(category=category, limit=limit)
    return {"count": len(items), "signals": items}


@api.post("/market/scan")
async def market_scan(window_hours: int = 24) -> Dict[str, Any]:
    return await market_agent.scan(window_hours=window_hours)


@api.get("/market/digests")
async def market_digests(limit: int = 10) -> Dict[str, Any]:
    items = await market_agent.list_digests(limit=limit)
    return {"count": len(items), "digests": items}


# =====================================================================
# Hermes Agent proxy (module 15, additive)
# =====================================================================


class HermesChatRequest(BaseModel):
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    company_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    mode: str = "operational"
    temperature: float = 0.3
    model: Optional[str] = None
    attachment_ids: List[str] = Field(default_factory=list)


class HermesDigestRequest(BaseModel):
    company_id: Optional[str] = None
    user_id: str
    period: str = "daily"


class HermesJobRequest(BaseModel):
    prompt: str
    schedule: Optional[str] = None  # cron expression
    name: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    deliver: Optional[str] = None  # log | telegram | discord | slack


@api.get("/hermes/health")
async def hermes_health() -> Dict[str, Any]:
    return await hermes_agent.health()


@api.get("/joker/stats")
async def joker_stats(window_minutes: int = 60) -> Dict[str, Any]:
    """JOKER sandbox usage stats — how much off-topic traffic was absorbed.

    Lightweight read against `db.joker_audit` only; never touches the
    business core collections.
    """
    from agents import joker as _joker
    window = max(5, min(int(window_minutes or 60), 24 * 60))
    return await _joker.stats(window_minutes=window)


# =====================================================================
# Onboarding survey (Connect button → 7 questions → Hermes brief)
# =====================================================================


class OnboardingProfileRequest(BaseModel):
    id: Optional[str] = None
    industry: str
    team_size: str
    # ── v2 (9-question) fields ──
    management_structure: str = ""
    communication_channels: List[str] = []
    process_system: str = ""
    knowledge_storage: str = ""
    pain_points: List[str] = []
    email: str = ""
    # ── legacy mirrors kept so older clients keep working ──
    has_sales_team: bool = False
    has_marketer: bool = False
    pain_primary: str = ""
    pain_secondary: str = ""
    tools_current: List[str] = []
    crm_name: str = ""
    goal_90days: str
    urgency: str = "warm"
    name: str
    phone: str = ""
    telegram: str = ""
    timezone: str = ""
    lang: str = "en"
    selected_plan: str = ""
    access_code: str = ""


class OnboardingInsightRequest(BaseModel):
    qid: str
    answer: str
    lang: str = "en"


class AccessCodeRequest(BaseModel):
    code: str


@api.post("/onboarding/insight")
async def onboarding_insight(req: OnboardingInsightRequest) -> Dict[str, Any]:
    """Return the '💡 ДЛЯ ВАС' line for a single question/answer pair."""
    from agents import onboarding as _onb
    return await _onb.get_insight(req.qid, req.answer, req.lang)


@api.post("/onboarding/verify-code")
async def onboarding_verify_code(req: AccessCodeRequest) -> Dict[str, Any]:
    """Check if an access code is valid and not exhausted (read-only)."""
    from agents import onboarding as _onb
    return await _onb.verify_access_code(req.code)


@api.post("/onboarding/profiles")
async def onboarding_save_profile(
    req: OnboardingProfileRequest,
    user: Optional["_auth_mod.AuthedUser"] = Depends(_auth_mod.optional_user),
) -> Dict[str, Any]:
    """Save the completed survey and, if an access code was provided, validate
    and consume it. Returns the profile id plus a `test_access` flag.

    PUBLIC endpoint — anonymous visitors from the landing page must be able to
    complete the onboarding survey without an account. If a session IS present
    we tag the resulting profile with the caller's tenant so admin listings
    stay isolated; anonymous profiles are left untagged until the user signs up.
    """
    from agents import onboarding as _onb
    payload = req.model_dump()
    test_access = False
    code = (payload.get("access_code") or "").strip()
    if code:
        check = await _onb.verify_access_code(code)
        if check.get("valid"):
            consumed = await _onb.consume_access_code(code)
            test_access = bool(consumed)
    payload["test_access"] = test_access
    saved = await _onb.save_profile(payload)
    if not saved.get("ok"):
        raise HTTPException(status_code=400, detail=saved.get("error") or "save_failed")
    # Tag the freshly-saved profile with the caller's tenant when a session
    # exists. Anonymous landing-page submissions stay untagged.
    if user is not None:
        try:
            await TenantAwareCRUD(get_db().client_profiles, company_id=user.company_id).update_one(
                {"id": saved["id"]},
                {"$set": {"company_id": user.company_id, "owner_user_id": user.user_id}},
            )
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "profile_id": saved["id"], "test_access": test_access}


@api.get("/onboarding/profiles/{profile_id}")
async def onboarding_get_profile(
    profile_id: str,
    user: Optional["_auth_mod.AuthedUser"] = Depends(_auth_mod.optional_user),
) -> Dict[str, Any]:
    from agents import onboarding as _onb
    profile = await _onb.get_profile(
        profile_id,
        company_id=None if (user and user.is_admin) else (user.company_id if user else None),
        force_admin=bool(user and user.is_admin),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")
    # Cross-tenant isolation — admins still see everything. Anonymous profiles
    # (no company_id) remain readable by their session-less submitter via
    # profile_id (it acts as a capability token until the user signs up).
    owner_company = profile.get("company_id")
    if owner_company:
        if user is None or (not user.is_admin and owner_company != user.company_id):
            raise HTTPException(status_code=404, detail="profile_not_found")
    return profile


@api.post("/onboarding/brief/{profile_id}")
async def onboarding_brief(profile_id: str) -> Dict[str, Any]:
    """Build the brief and generate Hermes' 4-block personalised reply."""
    from agents import onboarding as _onb
    profile = await _onb.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")
    brief = _onb.build_brief(profile)
    reply = await _onb.generate_hermes_reply(profile, brief, lang=profile.get("lang", "en"))
    # Persist for later retrieval (Ops / admin).
    await TenantAwareCRUD(get_db().client_profiles, company_id=profile.get("company_id")).update_one(
        {"id": profile_id},
        {"$set": {"brief": brief, "hermes_reply": reply, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"profile_id": profile_id, "brief": brief, "hermes_reply": reply}


@api.get("/onboarding/funnel")
async def onboarding_funnel(days: int = 30) -> Dict[str, Any]:
    from agents import onboarding as _onb
    days = max(1, min(int(days or 30), 365))
    return await _onb.funnel_stats(days)


# =====================================================================
# Hermes Constitutional Graph v2 (see agents/hermes_graph_v2.py)
# =====================================================================


class GraphV2RunRequest(BaseModel):
    task: str
    intent: Optional[str] = None
    task_type: str = "execute"
    context: Optional[Dict[str, Any]] = None


@api.post("/graph/v2/run")
async def graph_v2_run(req: GraphV2RunRequest) -> Dict[str, Any]:
    """Run the Constitutional Graph end-to-end.

    Returns the FULL final `GraphState` so callers can inspect the audit
    trail (`status.history`), the plan, every executor step, the
    reviewer/Hermes verdicts, and the packed `final_output`.
    """
    from agents import hermes_graph_v2 as _g
    if not (req.task or "").strip():
        raise HTTPException(status_code=400, detail="task is required")
    state = await _g.run_graph_v2(
        task_description=req.task,
        intent=req.intent or req.task,
        context=req.context,
        task_type=req.task_type,
    )
    return state


@api.get("/llm/router-stats")
async def llm_router_stats() -> Dict[str, Any]:
    """Distribution of deepseek-chat vs deepseek-reasoner since process start."""
    from core.complexity_router import stats as _stats
    return _stats()


# =====================================================================
# Hermes Operating Graph (10-node continuous cycle, see hermes_os_graph.py)
# =====================================================================


class HermesOSCycleRequest(BaseModel):
    source: str = "manual"
    kind: str = "generic"
    payload: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    company_id: Optional[str] = None
    lang: Optional[str] = "ru"
    persist: bool = True


@api.post("/hermes/os/cycle")
async def hermes_os_cycle(req: HermesOSCycleRequest) -> Dict[str, Any]:
    """Run one full Observe→Context→Validate→Reason→Route→Execute→
    Monitor→Learn→Improve→Evolve cycle on the supplied event."""
    from agents import hermes_os_graph as _os
    event = {
        "source":     req.source,
        "kind":       req.kind,
        "payload":    req.payload or {},
        "user_id":    req.user_id,
        "company_id": req.company_id,
        "lang":       req.lang or "ru",
    }
    state = await _os.run_os_cycle(event, persist=req.persist)
    return state


@api.post("/hermes/os/cycle/stream")
async def hermes_os_cycle_stream(req: HermesOSCycleRequest) -> StreamingResponse:
    """Live mode: stream one OS cycle as Server-Sent Events.

    Emits one `event: node` line per completed node containing the
    fresh slice of state, plus a final `event: done` with the full
    cycle. Frontend can render the 10 nodes lighting up in real time.
    """
    from agents import hermes_os_graph as _os
    event = {
        "source":     req.source,
        "kind":       req.kind,
        "payload":    req.payload or {},
        "user_id":    req.user_id,
        "company_id": req.company_id,
        "lang":       req.lang or "ru",
    }

    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    # Per-node payload extractor: send ONLY that node's slice + meta,
    # not the entire 30 KB state, on every tick.
    NODE_SLICE_KEY = {
        "observation":             "observation",
        "context_assembly":        "context",
        "constitution_validation": "validation",
        "reasoning":               "reasoning",
        "agent_routing":           "routing_plan",
        "execution":               "execution",
        "monitoring":              "monitoring",
        "learning":                "learning",
        "improvement":             "improvement",
        "evolution":               "evolution",
    }

    async def on_node(node_name: str, state: Dict[str, Any]) -> None:
        if node_name == "done":
            await queue.put(("done", {
                "cycle_id":    state.get("cycle_id"),
                "stage":       state.get("status", {}).get("stage"),
                "hops":        state.get("hops"),
                "error":       state.get("status", {}).get("error"),
                "finished_at": state.get("finished_at"),
            }))
            await queue.put(SENTINEL)
            return
        payload = {
            "node":     node_name,
            "cycle_id": state.get("cycle_id"),
            "stage":    state.get("status", {}).get("stage"),
            "routing":  state.get("routing"),
            "slice":    state.get(NODE_SLICE_KEY.get(node_name, ""), {}),
        }
        await queue.put((node_name, payload))

    async def runner() -> None:
        try:
            await _os.run_os_cycle(event, persist=req.persist, on_node=on_node)
        except Exception as e:  # noqa: BLE001
            await queue.put(("error", {"reason": str(e)}))
            await queue.put(SENTINEL)

    async def generator():
        task = asyncio.create_task(runner())
        try:
            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                event_name, payload = item
                yield (f"event: {event_name}\n"
                       f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n")
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@api.get("/hermes/os/cycle/{cycle_id}")
async def hermes_os_cycle_get(cycle_id: str, user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user)) -> Dict[str, Any]:
    """Fetch a persisted cycle by id."""
    doc = await TenantAwareCRUD(get_db().hermes_os_cycles, company_id=None if user.is_admin else user.company_id, force_admin=user.is_admin).find_one({"cycle_id": cycle_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="cycle not found")
    return doc


@api.get("/hermes/os/cycles")
async def hermes_os_cycles_list(limit: int = 20, source: Optional[str] = None, user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user)) -> Dict[str, Any]:
    """List recent cycles for the Ops dashboard."""
    limit = max(1, min(int(limit or 20), 200))
    q: Dict[str, Any] = {}
    if source:
        q["event.source"] = source
    cursor = TenantAwareCRUD(get_db().hermes_os_cycles, company_id=None if user.is_admin else user.company_id, force_admin=user.is_admin).find(q, {"_id": 0, "history": 0, "stages": 0}) \
        .sort("started_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"count": len(items), "items": items}


@api.get("/hermes/os/nodes")
async def hermes_os_nodes() -> Dict[str, Any]:
    """Return the canonical 10-node order — used by the UI to render the graph."""
    from agents import hermes_os_graph as _os
    return {"nodes": _os.list_node_order()}


# ---------- Hermes 4-layer memory inspection ----------

@api.get("/hermes/memory/stats")
async def hermes_memory_stats() -> Dict[str, Any]:
    """Lightweight counters across all 4 memory layers."""
    from core import hermes_memory as _hm
    db = get_db()
    try:
        kg_count = await db.knowledge_graph.estimated_document_count()
    except Exception:  # noqa: BLE001
        kg_count = 0
    try:
        inst_count = await db.institutional_memory.estimated_document_count()
    except Exception:  # noqa: BLE001
        inst_count = 0
    try:
        cycles_count = await db.hermes_os_cycles.estimated_document_count()
    except Exception:  # noqa: BLE001
        cycles_count = 0
    return {
        "short_term":      _hm.stm_stats(),
        "operational":     {"cycles_persisted": cycles_count},
        "knowledge_graph": {"edges_total": kg_count},
        "institutional":   {"lessons_total": inst_count},
    }


@api.get("/hermes/memory/short-term")
async def hermes_memory_short_term(user_id: Optional[str] = None,
                                    company_id: Optional[str] = None) -> Dict[str, Any]:
    """Return cached recent cycle summaries for a user/company."""
    from core import hermes_memory as _hm
    return {
        "recent_cycles": _hm.stm_recent_cycles(user_id=user_id, company_id=company_id),
        "stats": _hm.stm_stats(),
    }


@api.get("/hermes/memory/knowledge-graph")
async def hermes_memory_kg(entity: Optional[str] = None,
                            limit: int = 25,
                            user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user)) -> Dict[str, Any]:
    """One-hop walk of the company knowledge graph from a given entity.
    When `entity` is omitted, returns the most recent edges."""
    from core import hermes_memory as _hm
    if entity:
        edges = await _hm.kg_neighbors([entity], limit=limit)
    else:
        try:
            edges = await TenantAwareCRUD(get_db().knowledge_graph, company_id=None if user.is_admin else user.company_id, force_admin=user.is_admin).find({}, {"_id": 0}) \
                .sort("created_at", -1).limit(max(1, min(int(limit), 200))) \
                .to_list(length=limit)
        except Exception:  # noqa: BLE001
            edges = []
    return {"count": len(edges), "edges": edges}


@api.get("/hermes/memory/institutional")
async def hermes_memory_institutional(scope: Optional[str] = None,
                                       tag: Optional[str] = None,
                                       limit: int = 25) -> Dict[str, Any]:
    """List recent institutional lessons, optionally filtered by scope/tag."""
    from core import hermes_memory as _hm
    tags = [tag] if tag else None
    lessons = await _hm.inst_recall(tags=tags, scope=scope, limit=limit)
    return {"count": len(lessons), "lessons": lessons}


# =====================================================================
# Channel adapters (Wingman-inspired ingress)
# =====================================================================


@api.get("/channels")
async def channels_list(include_inactive: bool = False) -> Dict[str, Any]:
    """List all channel bindings (file defaults + DB overrides merged)."""
    from channels import list_bindings
    items = await list_bindings(include_inactive=include_inactive)
    return {
        "count": len(items),
        "items": [b.to_dict() for b in items],
    }


class ChannelBindingRequest(BaseModel):
    channel_id: str
    channel_kind: str = "webhook"
    agent: str = "hermes"
    intent_filter: str = ""
    name: str = ""
    signing_secret: str = ""
    active: bool = True


@api.post("/channels/bindings")
async def channels_upsert(req: ChannelBindingRequest) -> Dict[str, Any]:
    """Create or update a runtime binding (stored in db.channel_bindings)."""
    from channels import upsert_binding, ChannelBinding
    b = ChannelBinding(
        channel_id=req.channel_id.strip(),
        channel_kind=req.channel_kind.strip() or "webhook",
        agent=(req.agent or "hermes").strip(),
        intent_filter=req.intent_filter or "",
        name=req.name or "",
        signing_secret=req.signing_secret or "",
        active=bool(req.active),
    )
    saved = await upsert_binding(b)
    return {"ok": True, "binding": saved.to_dict()}


@api.delete("/channels/bindings")
async def channels_delete(channel_id: str, intent_filter: str = "") -> Dict[str, Any]:
    from channels import delete_binding
    deleted = await delete_binding(channel_id, intent_filter)
    return {"ok": True, "deleted": deleted}


@api.post("/channels/webhook/{channel_id}")
async def channels_webhook_inbound(
    channel_id: str,
    request: Request,
) -> Dict[str, Any]:
    """
    Generic webhook ingress.

    External systems POST JSON `{ "text": "...", "user_id": "...", "lang": "ru" }`.
    The bindings registry picks the best agent (most-specific-first) and
    returns its reply in the same response.

    Optional HMAC verification: header `X-NXT8-Signature: sha256=<hex>`
    is checked against the matching binding's `signing_secret`.
    """
    from channels import get_binding, invoke_agent_for_binding
    from channels.webhook import WebhookAdapter
    import time as _time

    t0 = _time.time()
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body or b"{}")
        if not isinstance(payload, dict):
            payload = {"text": str(payload)}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    text_preview = (payload.get("text") or payload.get("message") or "").strip()
    if not text_preview:
        raise HTTPException(status_code=400, detail="Missing `text` field")

    binding = await get_binding(channel_id, text_preview)
    if not binding:
        raise HTTPException(status_code=404, detail=f"No active binding for channel '{channel_id}'")

    # HMAC verification when the binding declares a signing_secret.
    if binding.signing_secret:
        sig = request.headers.get("x-nxt8-signature") or request.headers.get("X-NXT8-Signature")
        if not WebhookAdapter.verify_signature(raw_body, sig, binding.signing_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

    adapter = WebhookAdapter()
    event = await adapter.parse(channel_id, payload, dict(request.headers))
    reply = await invoke_agent_for_binding(binding, event)

    # Lightweight audit so the Ops dashboard can show channel activity.
    try:
        await TenantAwareCRUD(get_db().channel_events, company_id=getattr(request.state, "company_id", None)).insert_one({
            "id": f"ch_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "channel_kind": "webhook",
            "external_user_id": event.external_user_id,
            "session_id": event.session_id,
            "binding_agent": binding.agent,
            "binding_filter": binding.intent_filter,
            "text_in": text_preview[:500],
            "text_out": (reply.text or "")[:500],
            "tokens_total": reply.tokens_total,
            "latency_ms": int((_time.time() - t0) * 1000),
            "routed_to": reply.routed_to,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        logging.getLogger("nxt8.server").warning("channel_events audit failed: %s", e)

    return await adapter.format(reply, event)


@api.get("/channels/{channel_id}/events")
async def channels_recent_events(channel_id: str, limit: int = 20, user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user)) -> Dict[str, Any]:
    """Recent inbound events for a given channel (for Ops dashboard)."""
    limit = max(1, min(int(limit or 20), 200))
    items: List[Dict[str, Any]] = []
    async for r in TenantAwareCRUD(get_db().channel_events, company_id=None if user.is_admin else user.company_id, force_admin=user.is_admin).find({"channel_id": channel_id}).sort("ts", -1).limit(limit):
        r.pop("_id", None)
        items.append(r)
    return {"channel_id": channel_id, "count": len(items), "items": items}


@api.post("/hermes/chat")
async def hermes_chat(req: HermesChatRequest) -> Dict[str, Any]:
    """Enhanced Hermes COO endpoint with tool-calling and multi-tenant context."""
    import time as _time
    t0 = _time.time()

    # Validate the payload — empty messages list means the client sent
    # nothing to react to. Returning a generic CEO greeting here just hides
    # the bug (was: every "missing field" curl looked like a working answer).
    if not req.messages or not any(
        isinstance(m, dict) and (m.get("content") or "").strip()
        for m in req.messages
    ):
        raise HTTPException(
            status_code=400,
            detail="messages must contain at least one non-empty {role, content}",
        )

    # M1: stable session_id from the client (browser localStorage) so the
    # 4-layer memory + short-term history actually accumulate across turns.
    # Fallback to a generated id only when the client doesn't supply one.
    sid = req.session_id or f"hermes_{uuid.uuid4().hex[:10]}"

    # If the caller passed attachment_ids, hydrate them and inject a
    # short system block describing each attachment so Hermes can refer
    # to it in its reply.
    messages = list(req.messages or [])
    if req.attachment_ids:
        from agents import attachments as _att
        recs: List[Dict[str, Any]] = []
        for aid in req.attachment_ids[:8]:
            r = await _att.get_attachment(aid)
            if r:
                recs.append(r)
        block = _att.build_hermes_context_block(recs)
        if block:
            messages = [{"role": "system", "content": block}] + messages

    result = await hermes_coo_agent.enhanced_chat(
        messages=messages,
        company_id=req.company_id,
        user_id=req.user_id,
        mode=req.mode,
        temperature=req.temperature,
        model=req.model,
    )

    # If the classifier delegated this turn to the JOKER sandbox, we
    # deliberately SKIP the universal pipeline hook so that sandbox
    # traffic never lands in `db.requests`, `db.costs`, or the ROI
    # dashboard. JOKER keeps its own ledger (`db.joker_audit`).
    if result.get("routed_to") == "joker":
        result["request_id"] = f"joker_{uuid.uuid4().hex[:10]}"
        result["confidence_level"] = "sandbox"
        result["should_escalate"] = False
        result["session_id"] = sid
        return result

    # Universal pipeline hook
    last_user_msg = ""
    for m in reversed(req.messages or []):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user_msg = m.get("content") or ""
            break

    # M1: persist this turn into short-term memory bound to user_id
    # so cross-session continuity works.
    try:
        mem = memory_agent.get_memory()
        hc_company_id = await _resolve_company_id(req.user_id)
        if last_user_msg:
            await mem.append_message(sid, "user", last_user_msg,
                                     user_id=req.user_id, company_id=hc_company_id)
        reply_text = result.get("content") or ""
        if reply_text:
            await mem.append_message(sid, "assistant", reply_text,
                                     user_id=req.user_id, company_id=hc_company_id)
    except Exception as mem_err:  # noqa: BLE001
        logger.warning("hermes_chat memory append failed: %s", mem_err)

    usage = (result.get("usage") or {}) if isinstance(result.get("usage"), dict) else {}
    tokens_total = int(result.get("tokens_total") or usage.get("total_tokens") or 0)
    hook_res = await finalize_llm_turn(
        channel="hermes_chat",
        agent="hermes_coo",
        user_id=req.user_id or "anonymous",
        session_id=sid,
        message=last_user_msg,
        response_text=result.get("content", ""),
        tokens_total=tokens_total,
        deepseek_confidence=float(result.get("confidence", 0.7) or 0.7),
        evidence_count=len(result.get("tool_calls") or []),
        intent="hermes",
        agent_chain=["hermes_coo"],
        mock=bool(result.get("mock")),
        latency_ms=int((_time.time() - t0) * 1000),
        extra={"company_id": req.company_id, "mode": req.mode, "fallback": result.get("fallback")},
    )
    result["request_id"] = hook_res.get("request_id")
    result["confidence_level"] = hook_res.get("confidence_level")
    result["should_escalate"] = hook_res.get("should_escalate", False)
    result["session_id"] = sid
    return result


@api.post("/hermes/daily-digest")
async def hermes_daily_digest(req: HermesDigestRequest) -> Dict[str, Any]:
    """Trigger an operational digest for a given recipient/company."""
    seed = (
        f"Сгенерируй {('недельный' if req.period == 'weekly' else 'сегодняшний')} "
        f"operational digest для компании. Вызови tool generate_daily_digest с "
        f"recipient_user_id='{req.user_id}', period='{req.period}', "
        f"company_id='{req.company_id or 'default'}', затем оформи итог по формату "
        f"(summary / что важно / действия / ожидаемый эффект)."
    )
    return await hermes_coo_agent.enhanced_chat(
        messages=[{"role": "user", "content": seed}],
        company_id=req.company_id,
        user_id=req.user_id,
        mode="operational",
        temperature=0.3,
    )


# --- Hermes Ultra (LangGraph) ----------------------------------------


class HermesUltraRequest(BaseModel):
    message: str
    company_id: str = "default"
    user_id: str = "anonymous"
    session_id: Optional[str] = None
    autonomy_level: str = "assistant"  # read_only | assistant | controlled_automation


@api.post("/hermes/ultra")
async def hermes_ultra_endpoint(req: HermesUltraRequest) -> Dict[str, Any]:
    """Ultra Hermes COO orchestrator (LangGraph supervisor → hermes → tools)."""
    import time as _time
    t0 = _time.time()
    allowed = {"read_only", "assistant", "controlled_automation"}
    autonomy = req.autonomy_level if req.autonomy_level in allowed else "assistant"
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    try:
        result = await run_nxt8_ultra(
            message=req.message,
            company_id=req.company_id,
            user_id=req.user_id,
            session_id=session_id,
            autonomy_level=autonomy,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("hermes_ultra failed")
        return {
            "success": False,
            "content": "Извините, произошла ошибка при обработке запроса.",
            "error": str(e),
            "thread_id": session_id,
            "autonomy_level": autonomy,
        }

    # Persist user + assistant turns into short-term memory (best effort)
    try:
        mem = memory_agent.get_memory()
        hu_company_id = await _resolve_company_id(req.user_id)
        await mem.append_message(session_id, "user", req.message,
                                 user_id=req.user_id, company_id=hu_company_id)
        if result.get("content"):
            await mem.append_message(session_id, "assistant", result["content"],
                                     user_id=req.user_id, company_id=hu_company_id)
    except Exception as mem_err:  # noqa: BLE001
        logger.warning("memory append failed: %s", mem_err)

    # Universal pipeline hook
    hook_res = await finalize_llm_turn(
        channel="hermes_ultra",
        agent="hermes_ultra",
        user_id=req.user_id,
        session_id=session_id,
        message=req.message,
        response_text=result.get("content", ""),
        tokens_total=int(result.get("tokens_total") or 0),
        deepseek_confidence=float(result.get("confidence", 0.7) or 0.7),
        evidence_count=len(result.get("tool_traces") or []),
        intent="hermes_ultra",
        agent_chain=["langgraph", "hermes", "tools"],
        mock=bool(result.get("mock")),
        latency_ms=int((_time.time() - t0) * 1000),
        extra={
            "company_id": req.company_id,
            "autonomy_level": autonomy,
            "iterations": result.get("iterations", 0),
            "fallback": result.get("fallback"),
        },
    )

    return {
        "success": True,
        "content": result.get("content", ""),
        "autonomy_level": autonomy,
        "thread_id": result.get("thread_id", session_id),
        "iterations": result.get("iterations", 0),
        "confidence": hook_res.get("confidence", result.get("confidence", 0.7)),
        "confidence_level": hook_res.get("confidence_level"),
        "should_escalate": hook_res.get("should_escalate", False),
        "request_id": hook_res.get("request_id"),
        "tool_traces": result.get("tool_traces") or [],
        "requires_human_approval": bool(result.get("requires_human_approval")),
        "fallback": result.get("fallback"),
    }


@api.get("/hermes/jobs")
async def hermes_jobs_list() -> Dict[str, Any]:
    return await hermes_agent.list_jobs()


@api.post("/hermes/jobs")
async def hermes_jobs_create(req: HermesJobRequest) -> Dict[str, Any]:
    return await hermes_agent.create_job(req.model_dump(exclude_none=True))


# =====================================================================
# Personas Layer (marketing-aligned 8 agents + tariff gate)
# =====================================================================


class PersonaChatRequest(BaseModel):
    message: str
    company_id: str = "default"
    user_id: str = "anonymous"
    session_id: Optional[str] = None
    plan_id: Optional[str] = None  # basic|simple|pro|enterprise


@api.get("/personas")
async def personas_list(plan_id: Optional[str] = None) -> Dict[str, Any]:
    """List all 8 personas with availability flag for the given plan."""
    plan = personas_agent.get_plan(plan_id)
    return {
        "plan": plan,
        "plans": [
            {"id": pid, **{k: v for k, v in p.items() if k != "personas"}, "personas": p["personas"]}
            for pid, p in personas_agent.PLANS.items()
        ],
        "personas": personas_agent.list_personas(plan_id),
    }


@api.get("/agents/manifests")
async def agents_manifests() -> Dict[str, Any]:
    """Return constitutional manifests for ALL agents (personas + graph nodes).

    Each manifest is the agent's passport: specialty, expertise, functions,
    must-not, data access matrix, chain of command, decision authority.
    The frontend agent-passport modal reads from this endpoint.
    """
    from agents import manifests as _m
    return {
        "count":     len(_m.list_all_manifests()),
        "manifests": _m.list_all_manifests(),
        "high_impact_actions": sorted(_m.HIGH_IMPACT_ACTIONS),
        "low_impact_actions":  sorted(_m.LOW_IMPACT_ACTIONS),
        "authority_levels": [
            _m.AUTHORITY_ADVISORY,
            _m.AUTHORITY_WITH_APPROVAL,
            _m.AUTHORITY_AUTONOMOUS,
        ],
    }


@api.get("/agents/{agent_id}/manifest")
async def agent_manifest(agent_id: str) -> Dict[str, Any]:
    """Return one agent's full manifest + the prompt-ready render of it."""
    from agents import manifests as _m
    manifest = _m.get_manifest(agent_id)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"manifest not found: {agent_id}")
    return {
        "id":       agent_id,
        "manifest": manifest,
        "prompt_block": _m.render_manifest_for_prompt(agent_id),
    }


class ApprovalDecision(BaseModel):
    decided_by: str = "hermes"
    reason: Optional[str] = None


@api.get("/approvals")
async def approvals_list(
    status: str = "pending",
    agent_id: Optional[str] = None,
    limit: int = 50,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    """List approval-gate records (pending by default) scoped to the
    caller's tenant."""
    from core import approval_gate as _ag
    items = await _ag.list_pending(
        status=status,
        company_id=user.company_id,
        agent_id=agent_id,
        limit=limit,
    )
    return {"count": len(items), "status": status, "items": items}


@api.get("/approvals/stats")
async def approvals_stats(
    window_hours: int = 24,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import approval_gate as _ag
    return await _ag.stats(window_hours=window_hours)


@api.get("/approvals/{approval_id}")
async def approvals_get(
    approval_id: str,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import approval_gate as _ag
    rec = await _ag.get_pending(approval_id)
    if not rec:
        raise HTTPException(status_code=404, detail="approval not found")
    # Cross-tenant access prevention. Admins can still see everything.
    if (
        not user.is_admin
        and rec.get("company_id")
        and rec.get("company_id") != user.company_id
    ):
        raise HTTPException(status_code=404, detail="approval not found")
    return rec


@api.post("/approvals/{approval_id}/approve")
async def approvals_approve(
    approval_id: str,
    payload: ApprovalDecision,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    """Approve a pending action and execute it via the matching tool callable."""
    from core import approval_gate as _ag
    from agents.hermes import HERMES_TOOLS

    rec = await _ag.get_pending(approval_id)
    if not rec:
        raise HTTPException(status_code=404, detail="approval not found")
    if (
        not user.is_admin
        and rec.get("company_id")
        and rec.get("company_id") != user.company_id
    ):
        raise HTTPException(status_code=404, detail="approval not found")

    async def _executor(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        fn = HERMES_TOOLS.get(action)
        if not fn:
            return {"ok": False, "error": f"unknown tool: {action}"}
        return await fn(args)

    return await _ag.approve(
        approval_id,
        decided_by=payload.decided_by or user.email or "hermes",
        reason=payload.reason,
        executor=_executor,
    )


@api.post("/approvals/{approval_id}/reject")
async def approvals_reject(
    approval_id: str,
    payload: ApprovalDecision,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import approval_gate as _ag
    rec = await _ag.get_pending(approval_id)
    if not rec:
        raise HTTPException(status_code=404, detail="approval not found")
    if (
        not user.is_admin
        and rec.get("company_id")
        and rec.get("company_id") != user.company_id
    ):
        raise HTTPException(status_code=404, detail="approval not found")
    return await _ag.reject(
        approval_id,
        decided_by=payload.decided_by or user.email or "hermes",
        reason=payload.reason,
    )


@api.get("/company-settings")
async def company_settings_get(company_id: str = "default") -> Dict[str, Any]:
    """Return the active company context (region, industry, currency,
    channels, applicable regulations). All personas read this before answering."""
    from core import company_context as _cc
    settings = await _cc.get_settings(company_id)
    return {
        "settings": settings,
        "regulations": _cc.REGIONAL_REGULATIONS.get(
            (settings.get("region") or "GLOBAL").upper()
        ) or _cc.REGIONAL_REGULATIONS["GLOBAL"],
        "prompt_block": _cc.render_company_block(settings),
    }


@api.put("/company-settings")
async def company_settings_put(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert company settings. Auto-derives currency + channels from region
    if not supplied. Personas pick up changes on their next invocation."""
    from core import company_context as _cc
    company_id = (payload.get("company_id") or "default").strip() or "default"
    patch = {k: v for k, v in payload.items() if k != "company_id"}
    settings = await _cc.update_settings(company_id, patch)
    return {"settings": settings,
            "prompt_block": _cc.render_company_block(settings)}


@api.get("/hermes/evolution/roadmap")
async def hermes_evolution_roadmap(area: Optional[str] = None,
                                   status: Optional[str] = None,
                                   limit: int = 100) -> Dict[str, Any]:
    """Read Hermes Evolution Journal — what improvements were proposed,
    grouped by area (capability/agent/integration/architecture/product/process/policy)."""
    from agents import hermes_evolution as _ev
    return await _ev.list_evolution_roadmap(
        {"area": area, "status": status, "limit": limit}
    )


@api.get("/hermes/evolution/policies")
async def hermes_policy_proposals(status: Optional[str] = None,
                                  limit: int = 50) -> Dict[str, Any]:
    """Read policy proposals Hermes has filed for human review."""
    from agents import hermes_evolution as _ev
    return await _ev.list_policy_proposals({"status": status, "limit": limit})


@api.post("/hermes/evolution/approve")
async def hermes_evolution_approve(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Approve / reject / mark-done an evolution proposal. Human-only in
    practice; Hermes can also use this to close his own loops."""
    from agents import hermes_evolution as _ev
    res = await _ev.approve_proposal(payload or {})
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "approve failed"))
    return res


@api.get("/hermes/self-assessment")
async def hermes_self_assessment_endpoint(window: int = 200) -> Dict[str, Any]:
    """Live snapshot of Hermes' operational metrics — confidence, escalations,
    mock_rate, Evolution Journal counts, and honest signals."""
    from agents import hermes_evolution as _ev
    return await _ev.hermes_self_assessment({"window": window})


@api.post("/personas/{persona_id}/chat")
async def persona_chat(persona_id: str, req: PersonaChatRequest) -> Dict[str, Any]:
    """Chat with a specific persona. Enforces tariff gate."""
    import time as _time
    t0 = _time.time()
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    result = await personas_agent.run_persona(
        persona_id=persona_id,
        message=req.message,
        company_id=req.company_id,
        user_id=req.user_id,
        session_id=req.session_id,
        plan_id=req.plan_id,
    )
    if not result.get("success") and any(
        k in (result.get("error") or "").lower() for k in ("не доступна", "недоступна")
    ):
        # Tariff gate — return 402 Payment Required
        return Response(
            content=json.dumps(result, ensure_ascii=False),
            status_code=402,
            media_type="application/json",
        )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "persona chat failed")

    # Universal pipeline hook
    hook_res = await finalize_llm_turn(
        channel="persona",
        agent=f"persona:{persona_id}",
        user_id=req.user_id,
        session_id=result.get("session_id", f"persona_{uuid.uuid4().hex[:10]}"),
        message=req.message,
        response_text=result.get("content", ""),
        tokens_total=int(result.get("tokens_total") or 0),
        deepseek_confidence=float(result.get("confidence", 0.7) or 0.7),
        evidence_count=len(result.get("tool_traces") or []),
        intent=f"persona:{persona_id}",
        agent_chain=["personas", persona_id],
        mock=bool(result.get("mock")),
        latency_ms=int((_time.time() - t0) * 1000),
        extra={
            "persona_id": persona_id,
            "company_id": req.company_id,
            "plan_id": result.get("plan_id"),
            "iterations": result.get("iterations", 0),
        },
    )
    result["request_id"] = hook_res.get("request_id")
    result["confidence_level"] = hook_res.get("confidence_level")
    result["should_escalate"] = hook_res.get("should_escalate", False)
    return result


# =====================================================================
# Documents — upload + LLM risk review for Compliance persona
# =====================================================================


@api.post("/documents/upload")
async def documents_upload(
    file: UploadFile = File(...),
    company_id: str = Form("default"),
    user_id: str = Form("anonymous"),
    title: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Ingest a document (PDF/DOCX/TXT/MD), run LLM compliance review,
    store chunks in MemPalace (wing=documents)."""
    import time as _time
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    t0 = _time.time()
    try:
        result = await documents_agent.ingest_document(
            filename=file.filename or "upload.bin",
            content=raw,
            company_id=company_id,
            user_id=user_id,
            title=title,
            notes=notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("document ingest failed: %s", e)
        raise HTTPException(status_code=500, detail=f"ingest_failed: {e}")

    # Universal pipeline hook (cost + unified audit, NO reliability assess —
    # we already have a structured verdict)
    try:
        hook_res = await finalize_llm_turn(
            channel="documents",
            agent="compliance",
            user_id=user_id,
            session_id=f"doc_{result['id']}",
            message=f"upload:{file.filename}",
            response_text=result.get("summary") or "",
            tokens_total=int(result.get("tokens_total", 0) or 0),
            deepseek_confidence=float(result.get("confidence", 0.7) or 0.7),
            intent="document_review",
            agent_chain=["documents", "compliance"],
            mock=bool(result.get("mock")),
            latency_ms=int((_time.time() - t0) * 1000),
            extra={
                "document_id": result["id"],
                "severity": result.get("severity"),
                "findings_count": len(result.get("findings", [])),
                "filename": file.filename,
            },
        )
        result["request_id"] = hook_res.get("request_id")
    except Exception as e:  # noqa: BLE001
        logger.warning("documents hook failed: %s", e)
    return result


@api.get("/documents")
async def documents_list(company_id: Optional[str] = None,
                         limit: int = 50) -> Dict[str, Any]:
    items = await documents_agent.list_documents(company_id=company_id, limit=limit)
    return {"count": len(items), "documents": items}


@api.get("/documents/{document_id}")
async def documents_get(document_id: str) -> Dict[str, Any]:
    doc = await documents_agent.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


# =====================================================================
# Universal attachments (chat paperclip)
# =====================================================================


@api.post("/attachments/upload")
async def attachments_upload(
    file: UploadFile = File(...),
    company_id: str = Form("default"),
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Ingest one file from the chat paperclip.

    Returns a chip-friendly record: {id, kind, filename, summary, tags,
    severity?, document_id?}. Documents are also pushed through the
    Compliance pipeline; images get a Vision caption.
    """
    from agents import attachments as _att
    raw = await file.read()
    try:
        rec = await _att.ingest_attachment(
            filename=file.filename or "upload.bin",
            content=raw,
            company_id=company_id,
            user_id=user_id,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("attachment ingest failed: %s", e)
        raise HTTPException(status_code=500, detail=f"ingest_failed: {e}")
    # Strip the on-disk path before returning — the UI doesn't need it.
    rec.pop("path", None)
    return rec


@api.get("/attachments/{attachment_id}")
async def attachments_get(attachment_id: str) -> Dict[str, Any]:
    from agents import attachments as _att
    rec = await _att.get_attachment(attachment_id)
    if not rec:
        raise HTTPException(status_code=404, detail="attachment not found")
    rec.pop("path", None)
    return rec


@api.get("/attachments/{attachment_id}/raw")
async def attachments_raw(attachment_id: str) -> Response:
    """Serve the original bytes for previews (chip thumbnails)."""
    from agents import attachments as _att
    rec = await _att.get_attachment(attachment_id)
    if not rec:
        raise HTTPException(status_code=404, detail="attachment not found")
    path = rec.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file missing on disk")
    with open(path, "rb") as f:
        return Response(content=f.read(),
                        media_type=rec.get("mime", "application/octet-stream"))


# =====================================================================
# Payments — Stripe Checkout Sessions
# =====================================================================


class CheckoutSessionRequest(BaseModel):
    plan_id: str
    quantity: int = 1
    origin: str    # window.location.origin from the browser
    user_id: Optional[str] = None
    company_id: Optional[str] = None


@api.get("/payments/plans")
async def payments_plans() -> Dict[str, Any]:
    from agents import payments as _pay
    return _pay.plan_catalog()


@api.post("/payments/checkout/session")
async def payments_create_session(req: CheckoutSessionRequest,
                                   http_request: Request) -> Dict[str, Any]:
    from agents import payments as _pay
    host_url = str(http_request.base_url)
    try:
        return await _pay.create_session(
            plan_id=req.plan_id,
            quantity=req.quantity,
            origin=req.origin,
            host_url=host_url,
            user_id=req.user_id,
            company_id=req.company_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("stripe create session failed: %s", e)
        raise HTTPException(status_code=502, detail=f"stripe_failed: {e}")


@api.get("/payments/checkout/status/{session_id}")
async def payments_get_status(session_id: str,
                               http_request: Request) -> Dict[str, Any]:
    from agents import payments as _pay
    host_url = str(http_request.base_url)
    try:
        return await _pay.get_status(session_id=session_id, host_url=host_url)
    except Exception as e:  # noqa: BLE001
        logger.exception("stripe status check failed: %s", e)
        raise HTTPException(status_code=502, detail=f"stripe_status_failed: {e}")


@api.post("/webhook/stripe")
async def stripe_webhook(http_request: Request) -> Dict[str, Any]:
    from agents import payments as _pay
    body = await http_request.body()
    sig = http_request.headers.get("Stripe-Signature")
    host_url = str(http_request.base_url)
    try:
        return await _pay.handle_webhook(body, sig, host_url)
    except ValueError as e:
        # Signature failure / missing header / missing secret → 400.
        logger.warning("stripe webhook rejected: %s", e)
        raise HTTPException(status_code=400, detail=f"webhook_invalid: {e}")
    except Exception as e:  # noqa: BLE001
        logger.exception("stripe webhook failed: %s", e)
        raise HTTPException(status_code=400, detail=f"webhook_invalid: {e}")


# =====================================================================
# Inter-agent dialogues & escalations (read-side)
# =====================================================================


@api.get("/agents/dialogues")
async def list_agent_dialogues(limit: int = 50, agent_id: Optional[str] = None):
    """List recent inter-agent dialogues (delegate / escalate / ask)."""
    from agents.inter_agent import list_dialogues
    items = await list_dialogues(limit=limit, agent_id=agent_id)
    return {"ok": True, "count": len(items), "items": items}


@api.get("/agents/escalations")
async def list_agent_escalations(limit: int = 50, status: Optional[str] = None):
    """List recent escalations from subordinates to Hermes."""
    from agents.inter_agent import list_escalations
    items = await list_escalations(limit=limit, status=status)
    return {"ok": True, "count": len(items), "items": items}


# =====================================================================
# Demo Tour — landing page "Test Drive" checklist + funnel analytics
# =====================================================================


class TourEventRequest(BaseModel):
    client_id: str
    event: str
    step_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@api.get("/tour/catalogue")
async def tour_catalogue() -> Dict[str, Any]:
    from core import tour as _t
    return _t.catalogue()


@api.post("/tour/events")
async def tour_event_create(req: TourEventRequest) -> Dict[str, Any]:
    from core import tour as _t
    try:
        return await _t.record_event(
            client_id=req.client_id,
            step_id=req.step_id,
            event=req.event,
            metadata=req.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api.get("/tour/funnel")
async def tour_funnel(window_hours: int = 168) -> Dict[str, Any]:
    from core import tour as _t
    return await _t.funnel(window_hours=max(1, min(window_hours, 24 * 90)))


# =====================================================================
# Share-My-Journey — viral marketing channel after the Test Drive
# =====================================================================


class ShareMintRequest(BaseModel):
    client_id: str
    completed_steps: Optional[List[str]] = None
    headline: Optional[str] = None
    locale: str = "ru"


class ShareConversionRequest(BaseModel):
    share_id: str
    kind: str = "checkout"


@api.post("/share/journey")
async def share_mint(req: ShareMintRequest) -> Dict[str, Any]:
    from core import share as _sh
    res = await _sh.mint_share(
        client_id=req.client_id,
        completed_steps=req.completed_steps,
        headline=req.headline,
        locale=req.locale,
    )
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error") or "mint_failed")
    return res


@api.get("/share/stats")
async def share_stats(window_hours: int = 24 * 30) -> Dict[str, Any]:
    from core import share as _sh
    return await _sh.stats(window_hours=max(1, min(window_hours, 24 * 365)))


@api.get("/share/{share_id}")
async def share_get(
    share_id: str,
    request: Request,
    ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Public read for the share record — also records an open event."""
    from core import share as _sh
    rec = await _sh.get_share(share_id)
    if not rec:
        raise HTTPException(status_code=404, detail="share_not_found")
    # Record open in the background — never block the read.
    try:
        ua = request.headers.get("user-agent", "")
        await _sh.record_open(share_id, ref=ref, user_agent=ua)
    except Exception as e:  # noqa: BLE001
        logger.warning("share open record failed: %s", e)
    return {
        "ok":              True,
        "share_id":        rec["share_id"],
        "headline":        rec.get("headline"),
        "completed_steps": rec.get("completed_steps") or [],
        "locale":          rec.get("locale", "ru"),
        "created_at":      rec.get("created_at"),
        "opens":           int(rec.get("opens", 0)),
        "og_image_path":   f"/api/share/{share_id}/og.png",
    }


@api.get("/share/{share_id}/og.png")
async def share_og(share_id: str) -> Response:
    """1200×630 PNG card for Open Graph / Twitter / WhatsApp previews."""
    from core import share as _sh
    rec = await _sh.get_share(share_id)
    if not rec:
        raise HTTPException(status_code=404, detail="share_not_found")
    png = _sh.render_og_card_png(rec.get("headline") or "", share_id=share_id)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            # Cache aggressively — the headline is immutable for a share id.
            "Cache-Control": "public, max-age=86400, immutable",
        },
    )


@api.get("/s/{share_id}")
async def share_ssr(share_id: str, request: Request) -> Response:
    """SSR HTML wrapper that exposes Open Graph meta tags to messenger
    crawlers (Telegram / WhatsApp / Twitter / Slack) and redirects real
    browsers to the SPA with `?ref=<share_id>` for attribution.

    Crawlers don't run JS — they just scrape the static `<head>` for
    `og:image`/`og:title`/`og:description`. Browsers also see the head,
    then the meta-refresh + JS redirect lands them on the landing page.
    """
    from core import share as _sh
    rec = await _sh.get_share(share_id)
    if not rec:
        raise HTTPException(status_code=404, detail="share_not_found")

    # Record open in the background (best effort).
    try:
        ua = request.headers.get("user-agent", "")
        await _sh.record_open(share_id, ref="ssr", user_agent=ua)
    except Exception as e:  # noqa: BLE001
        logger.warning("share ssr open record failed: %s", e)

    base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
    # Fall back to the request's scheme+host so previews work even before
    # PUBLIC_BASE_URL is set on a new env (preview pods, etc.).
    if not base:
        base = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")

    og_image = f"{base}/api/share/{share_id}/og.png"
    canonical = f"{base}/api/s/{share_id}"
    spa_landing = f"{base}/?ref={share_id}"

    headline = (rec.get("headline") or "Я попробовал NXT8 — AI-команда для бизнеса")
    description = (
        "NXT8 — AI-команда из 8 агентов, которая берёт операционку компании "
        "на себя: Hermes CEO, HR, бухгалтерия, маркетинг, аналитика. "
        "Посмотри сам — бесплатный Test Drive 3 минуты."
    )

    # Escape minimal HTML in user-controlled strings.
    def _esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
        )

    h = _esc(headline)
    d = _esc(description)
    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{h} — NXT8</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">

<meta property="og:type"        content="website">
<meta property="og:site_name"   content="NXT8">
<meta property="og:url"         content="{canonical}">
<meta property="og:title"       content="{h}">
<meta property="og:description" content="{d}">
<meta property="og:image"       content="{og_image}">
<meta property="og:image:type"  content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale"      content="ru_RU">

<meta name="twitter:card"        content="summary_large_image">
<meta name="twitter:title"       content="{h}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image"       content="{og_image}">

<meta http-equiv="refresh" content="0; url={spa_landing}">
<style>
  body {{ background:#0a0a0b; color:#e5e7eb; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; margin:0; padding:0; display:flex; align-items:center; justify-content:center; min-height:100vh; }}
  .wrap {{ max-width: 640px; padding: 32px; text-align: center; }}
  .badge {{ display:inline-block; font-size:11px; letter-spacing:2px; padding:4px 10px; background:rgba(56,189,248,.12); color:#7dd3fc; border:1px solid rgba(56,189,248,.4); border-radius:9999px; }}
  h1 {{ font-size: 28px; margin: 18px 0 12px; line-height:1.2; }}
  p  {{ color:#9ca3af; line-height:1.5; }}
  a  {{ color:#7dd3fc; text-decoration:none; }}
  img {{ max-width: 100%; border-radius: 16px; border:1px solid rgba(255,255,255,.08); margin-top: 24px; }}
</style>
</head>
<body>
<div class="wrap">
  <span class="badge">NXT8 · SHARED JOURNEY</span>
  <h1>{h}</h1>
  <p>{d}</p>
  <p><a href="{spa_landing}">Открыть NXT8 →</a></p>
  <img src="{og_image}" alt="NXT8 — shared journey card" loading="eager">
</div>
<script>
  // Belt-and-suspenders: in case meta-refresh is blocked, JS-redirect after a tick.
  setTimeout(function () {{ window.location.replace({spa_landing!r}); }}, 80);
</script>
</body>
</html>"""

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300, stale-while-revalidate=86400",
            "X-Robots-Tag": "noindex",
        },
    )


@api.post("/share/conversion")
async def share_conversion(req: ShareConversionRequest) -> Dict[str, Any]:
    from core import share as _sh
    res = await _sh.track_conversion(req.share_id, kind=req.kind)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error") or "share_not_found")
    return res


# =====================================================================
# Telegram Channel — 1-click bot link for clients
# =====================================================================


class TelegramConnectRequest(BaseModel):
    # `client_id` body field kept for back-compat but is IGNORED — the
    # bound user_id always comes from the authenticated session.
    client_id: Optional[str] = None


class TelegramDisconnectRequest(BaseModel):
    client_id: Optional[str] = None


@api.post("/telegram/connect")
async def telegram_connect(
    req: TelegramConnectRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    """Mint a one-time Telegram deep-link bound to the authenticated user."""
    from core import telegram_bot as _tg
    if not _tg.is_enabled():
        raise HTTPException(status_code=503, detail="telegram_disabled")
    res = await _tg.mint_link_token(user.user_id)
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error") or "mint_failed")
    return res


@api.get("/telegram/status")
async def telegram_status(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import telegram_bot as _tg
    info = await _tg.get_bot_info()
    chat = await _tg.get_chat_for_client(user.user_id)
    return {
        "ok": True,
        "enabled": _tg.is_enabled(),
        "bot_username": info.get("username"),
        "connected": bool(chat),
        "chat": (
            {
                "first_name": chat.get("first_name"),
                "username": chat.get("username"),
                "bound_at": chat.get("bound_at"),
            }
            if chat
            else None
        ),
    }


@api.post("/telegram/disconnect")
async def telegram_disconnect(
    req: TelegramDisconnectRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import telegram_bot as _tg
    return await _tg.unbind(user.user_id)


@api.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> Dict[str, Any]:
    """Inbound updates from Telegram (set via setWebhook)."""
    from core import telegram_bot as _tg
    if not _tg.is_enabled():
        raise HTTPException(status_code=503, detail="telegram_disabled")
    expected = (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip() or "nxt8"
    if secret != expected:
        raise HTTPException(status_code=403, detail="bad_secret")
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    # Process in the background — Telegram only needs a quick 200.
    asyncio.create_task(_tg.handle_update(payload))
    return {"ok": True}


@api.post("/telegram/install-webhook")
async def telegram_install_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Admin helper: re-register the webhook URL (uses PUBLIC_BASE_URL by default)."""
    from core import telegram_bot as _tg
    if not _tg.is_enabled():
        raise HTTPException(status_code=503, detail="telegram_disabled")
    base_url = (payload or {}).get("base_url") or (
        os.environ.get("PUBLIC_BASE_URL") or ""
    )
    if not base_url:
        raise HTTPException(status_code=400, detail="base_url required")
    return await _tg.install_webhook(base_url)


# =====================================================================
# WhatsApp Channel — 1-click bot link for clients (Twilio sandbox/prod)
# =====================================================================


class WhatsAppConnectRequest(BaseModel):
    client_id: Optional[str] = None


class WhatsAppDisconnectRequest(BaseModel):
    client_id: Optional[str] = None


@api.post("/whatsapp/connect")
async def whatsapp_connect(
    req: WhatsAppConnectRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    """Mint a one-time WhatsApp deep-link bound to the authenticated user."""
    from core import whatsapp_bot as _wa
    if not _wa.is_enabled():
        raise HTTPException(status_code=503, detail="whatsapp_disabled")
    res = await _wa.mint_link_token(user.user_id)
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error") or "mint_failed")
    return res


@api.get("/whatsapp/status")
async def whatsapp_status(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import whatsapp_bot as _wa
    chat = await _wa.get_chat_for_client(user.user_id)
    return {
        "ok": True,
        "enabled": _wa.is_enabled(),
        "from": _wa._phone_from_wa(_wa._from()) if _wa.is_enabled() else None,
        "connected": bool(chat),
        "chat": (
            {
                "profile_name": chat.get("profile_name"),
                "wa_id": chat.get("wa_id"),
                "bound_at": chat.get("bound_at"),
            }
            if chat
            else None
        ),
    }


@api.post("/whatsapp/disconnect")
async def whatsapp_disconnect(
    req: WhatsAppDisconnectRequest,
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from core import whatsapp_bot as _wa
    return await _wa.unbind(user.user_id)


@api.post("/whatsapp/webhook/{secret}")
async def whatsapp_webhook(secret: str, request: Request) -> Dict[str, Any]:
    """Inbound Twilio WhatsApp webhook (form-encoded POST).

    Twilio also signs the request with `X-Twilio-Signature`. We validate
    it when the auth token is present; otherwise rely on the URL secret.
    """
    from core import whatsapp_bot as _wa
    if not _wa.is_enabled():
        raise HTTPException(status_code=503, detail="whatsapp_disabled")
    expected = (os.environ.get("TWILIO_WHATSAPP_WEBHOOK_SECRET") or "").strip() or "nxt8"
    if secret != expected:
        raise HTTPException(status_code=403, detail="bad_secret")

    form = dict((await request.form()).items())
    # Best-effort signature check (don't reject if header missing — many
    # test/sandbox setups omit it; we still got past the URL secret).
    sig = request.headers.get("X-Twilio-Signature", "")
    if sig:
        url = str(request.url)
        if not _wa.verify_twilio_signature(url, form, sig):
            logger.warning("whatsapp signature mismatch for %s", url)

    asyncio.create_task(_wa.handle_inbound(form))
    # Twilio expects TwiML or 200 OK. Empty 200 is fine — we already
    # respond out-of-band via the REST API.
    return Response(content="<Response/>", media_type="application/xml")


# =====================================================================
# Scheduler — Pulse + Daily Digest (admin-only manual triggers)
# =====================================================================


@api.post("/scheduler/pulse/run")
async def scheduler_run_pulse(
    payload: Optional[Dict[str, Any]] = None,
    _admin: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_admin),
) -> Dict[str, Any]:
    """Force a single Pulse tick. With `{"company_id": "..."}` runs for one
    tenant; otherwise runs the global tick loop just like the scheduler."""
    from agents import pulse as _pulse
    from core import scheduler as _sch
    cid = (payload or {}).get("company_id") if isinstance(payload, dict) else None
    if cid:
        return await _pulse.pulse_tick(str(cid))
    tenants = await _sch.list_active_tenants(force=True)
    results: List[Dict[str, Any]] = []
    for t in tenants:
        try:
            results.append(await _pulse.pulse_tick(t))
        except Exception as e:  # noqa: BLE001
            results.append({"company_id": t, "error": str(e)})
    return {"ok": True, "tenants": len(tenants), "results": results}


@api.post("/scheduler/digest/preview")
async def scheduler_digest_preview(
    payload: Dict[str, Any],
    _admin: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_admin),
) -> Dict[str, Any]:
    """Build a digest WITHOUT sending it — used for QA / first-look review."""
    from agents import digest as _digest
    cid = str(payload.get("company_id") or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="company_id required")
    return await _digest.build_preview(cid)


@api.post("/scheduler/digest/send")
async def scheduler_digest_send(
    payload: Dict[str, Any],
    _admin: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_admin),
) -> Dict[str, Any]:
    """Force a real digest send for the given tenant (bypasses dedup)."""
    from agents import digest as _digest
    cid = str(payload.get("company_id") or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="company_id required")
    return await _digest.build_and_send(cid)


@api.get("/scheduler/status")
async def scheduler_status(
    _admin: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_admin),
) -> Dict[str, Any]:
    from core import scheduler as _sch
    sch = _sch.get_scheduler()
    jobs = []
    if sch:
        for j in sch.get_jobs():
            jobs.append({
                "id": j.id, "name": j.name,
                "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
            })
    return {
        "running": sch is not None and sch.running,
        "active_tenants": await _sch.list_active_tenants(),
        "jobs": jobs,
        "config": {
            "pulse_enabled": _sch.PULSE_ENABLED,
            "digest_enabled": _sch.DIGEST_ENABLED,
            "pulse_interval_minutes": _sch.PULSE_INTERVAL_MINUTES,
            "digest_hour": _sch.DIGEST_HOUR,
            "tz": _sch.DEFAULT_TZ,
        },
    }



# =====================================================================
# AI-Mentor — user learning profile
# =====================================================================


@api.get("/mentor/profile")
async def mentor_profile(
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    from agents import ai_mentor as _aim
    profile = await _aim.get_profile(user.user_id, user.company_id)
    return {
        "ok": True,
        "ai_grade": int(profile.get("ai_grade", 0)),
        "skill_points": int(profile.get("skill_points", 0)),
        "patterns_used": profile.get("patterns_used") or [],
        "points_to_next_level": _aim.points_to_next_level(profile),
    }


@api.post("/mentor/assess")
async def mentor_assess(
    payload: Dict[str, Any],
    user: "_auth_mod.AuthedUser" = Depends(_auth_mod.require_user),
) -> Dict[str, Any]:
    """Force-reassess the caller's ai_grade from a fresh batch of messages."""
    from agents import ai_mentor as _aim
    msgs = payload.get("messages") or []
    if not isinstance(msgs, list) or not msgs:
        raise HTTPException(status_code=400, detail="messages[] required")
    grade = _aim.compute_ai_grade([str(m) for m in msgs])
    await _aim.set_grade(user.user_id, user.company_id, grade)
    return {"ok": True, "computed_grade": grade}



# =====================================================================
# Mount + CORS
# =====================================================================


# Mount auth router (login/session/me/logout) inside the /api prefix.
api.include_router(_auth_mod.router)

app.include_router(api)

# Install the auth middleware AFTER routes are mounted so it intercepts
# everything. Public paths and webhooks are whitelisted inside the gate.
_auth_mod.install_auth_middleware(app)
_cors_raw = os.environ.get("CORS_ORIGINS", "https://nxt8.pro").strip()
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip() and o.strip() != "*"]
if not _cors_origins:
    # Fail-closed default — production domain only. NEVER `*` with credentials.
    _cors_origins = ["https://nxt8.pro"]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
