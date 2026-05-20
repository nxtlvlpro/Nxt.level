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
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
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
from core.db import close_db, ensure_indexes, get_db  # noqa: E402
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
    deepseek = get_deepseek()
    logger.info("DeepSeek mock_mode=%s model=%s", deepseek.mock_mode, deepseek.model)
    task = asyncio.create_task(_roi_scheduler())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        close_db()


app = FastAPI(title="NXT8 API", version="1.0.0", lifespan=lifespan)
api = APIRouter(prefix="/api")


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
async def seed_demo() -> Dict[str, Any]:
    """Insert demo corporate memory + employees + deals — for first WOW screen."""
    mem = memory_agent.get_memory()
    db = get_db()

    # idempotent
    existing = await db.memories.count_documents({})
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
        await mem.store_memory(content, memory_type="corporate", metadata=meta)

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
        await mentor_agent.upsert_employee(e)

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
        })
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
        })

    # demo deals + interactions
    for i, value in enumerate([2400, 600, 1800, 950]):
        deal_id = f"deal_demo_{i}"
        # interactions BEFORE the deal close (1-4 days before)
        for day, agent in enumerate(["orchestrator", "memory", "orchestrator"]):
            await db.interactions.insert_one({
                "id": str(uuid.uuid4()),
                "deal_id": deal_id,
                "agent": agent,
                "interaction_type": "touch",
                "interaction_time": (base - timedelta(days=day + 1, hours=i)).isoformat(),
                "attributed_revenue": None,
            })
        await roi_agent.record_deal(
            deal_id=deal_id,
            value_usd=float(value),
            team="sales",
            closed_at=(base - timedelta(hours=i)).isoformat(),
        )

    # synthetic costs over last hour to make ROI non-zero
    for _ in range(40):
        await roi_agent.record_api_cost("orchestrator", tokens=15000)
    for _ in range(8):
        await roi_agent.record_escalation_cost("support", minutes=5.0)

    # detect weak patterns for junior
    await mentor_agent.detect_weak_patterns("emp_jr")

    # generate first roi snapshot
    await roi_agent.calculate_hourly_roi()

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


@api.get("/requests")
async def list_requests(limit: int = 20) -> List[Dict[str, Any]]:
    return await orchestrator_agent.list_recent_requests(limit=limit)


@api.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    msgs = await memory_agent.get_memory().get_session(session_id, limit=200)
    return {"session_id": session_id, "messages": msgs}


# =====================================================================
# Memory
# =====================================================================


@api.post("/memory/store")
async def memory_store(req: MemoryStoreRequest) -> Dict[str, Any]:
    mid = await memory_agent.get_memory().store_memory(
        content=req.content, memory_type=req.type, metadata=req.metadata
    )
    return {"id": mid, "status": "stored"}


@api.post("/memory/search")
async def memory_search(req: MemorySearchRequest) -> Dict[str, Any]:
    res = await memory_agent.get_memory().search(
        query=req.query, top_k=req.top_k, memory_type=req.type
    )
    return {"count": len(res), "results": res}


@api.get("/memory/list")
async def memory_list(type: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    items = await memory_agent.get_memory().list_memories(memory_type=type, limit=limit)
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
async def mempalace_store(req: MemPalaceStoreRequest) -> Dict[str, Any]:
    if not (req.content or "").strip():
        raise HTTPException(status_code=400, detail="content must not be empty")
    return await mempalace_agent.get_mempalace().store(
        content=req.content,
        wing=req.wing,
        room=req.room,
        metadata=req.metadata,
        source=req.source,
    )


@api.post("/mempalace/search")
async def mempalace_search(req: MemPalaceSearchRequest) -> Dict[str, Any]:
    items = await mempalace_agent.get_mempalace().search(
        query=req.query, wing=req.wing, room=req.room, top_k=req.top_k
    )
    return {"count": len(items), "results": items}


@api.get("/mempalace/wings")
async def mempalace_wings() -> Dict[str, Any]:
    wings = await mempalace_agent.get_mempalace().list_wings()
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
async def mentor_upsert_employee(req: EmployeeRequest) -> Dict[str, Any]:
    return await mentor_agent.upsert_employee(req.model_dump())


@api.get("/mentor/employees")
async def mentor_list_employees() -> Dict[str, Any]:
    emps = await mentor_agent.list_employees()
    return {"count": len(emps), "employees": emps}


@api.get("/mentor/employees/{employee_id}")
async def mentor_employee_summary(employee_id: str) -> Dict[str, Any]:
    return await mentor_agent.employee_summary(employee_id)


@api.post("/mentor/performance")
async def mentor_record_performance(req: PerformanceRequest) -> Dict[str, Any]:
    return await mentor_agent.record_performance(req.model_dump())


@api.post("/mentor/detect/{employee_id}")
async def mentor_detect_patterns(employee_id: str) -> Dict[str, Any]:
    patterns = await mentor_agent.detect_weak_patterns(employee_id)
    return {"employee_id": employee_id, "patterns": patterns}


@api.get("/mentor/patterns")
async def mentor_list_patterns(limit: int = 50) -> Dict[str, Any]:
    items = await mentor_agent.list_open_patterns(limit=limit)
    return {"count": len(items), "patterns": items}


@api.get("/mentor/recommend/{employee_id}/{pattern}")
async def mentor_recommendation(employee_id: str, pattern: str) -> Dict[str, Any]:
    return await mentor_agent.generate_recommendation(employee_id, pattern)


# =====================================================================
# ROI / Profit Intelligence
# =====================================================================


@api.get("/roi/dashboard")
async def roi_dashboard() -> Dict[str, Any]:
    return await roi_agent.dashboard_summary()


@api.get("/roi/current")
async def roi_current() -> Dict[str, Any]:
    return await roi_agent.calculate_hourly_roi()


@api.get("/roi/trend")
async def roi_trend(hours: int = 24) -> Dict[str, Any]:
    items = await roi_agent.roi_trend(hours=hours)
    return {"count": len(items), "items": items}


@api.post("/roi/deals")
async def roi_create_deal(req: DealRequest) -> Dict[str, Any]:
    return await roi_agent.record_deal(
        deal_id=req.deal_id, value_usd=req.value_usd, team=req.team, closed_at=req.closed_at
    )


@api.post("/roi/interactions")
async def roi_record_interaction(req: InteractionRequest) -> Dict[str, Any]:
    await roi_agent.record_interaction(
        deal_id=req.deal_id, agent=req.agent, interaction_type=req.interaction_type
    )
    return {"status": "recorded"}


# =====================================================================
# Alerts
# =====================================================================


@api.get("/alerts")
async def list_alerts(limit: int = 20) -> Dict[str, Any]:
    items = await orchestrator_agent.list_alerts(limit=limit)
    return {"count": len(items), "alerts": items}


# =====================================================================
# Voice — Whisper STT + OpenAI TTS via Emergent Universal Key
# =====================================================================


class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"
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


VOICE_REPLY_MAX_CHARS = 350
VOICE_REPLY_MAX_SENTENCES = 3
VOICE_SYSTEM_HINT = (
    "ВАЖНО: это голосовой канал. Ответ должен быть КОРОТКИМ — максимум 2-3 предложения, "
    "разговорным тоном, без markdown, без нумерованных списков, без JSON и без кода. "
    "Никаких заголовков типа 'Summary' или '1.'. Только живая речь, как будто говоришь вслух."
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
    voice: str = Form("nova"),
    company_id: Optional[str] = Form(None),
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

    # Build conversation: prior session memory + voice hint + current turn
    history: List[Dict[str, Any]] = []
    try:
        mem = memory_agent.get_memory()
        prev = await mem.get_session(sid, limit=6)
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
            company_id=company_id,
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
        await mem.append_message(sid, "user", user_text)
        if reply_text:
            await mem.append_message(sid, "assistant", reply_text)
    except Exception as mem_err:  # noqa: BLE001
        logger.warning("voice memory append failed: %s", mem_err)

    audio_b64: Optional[str] = None
    tts_error: Optional[str] = None
    if reply_text:
        try:
            audio_bytes = await voice_agent.synthesize(text=reply_text, voice=voice)
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
            await mem.append_message(session_id, "user", req.message)
            ctx = await mem.get_optimal_context(req.message, session_id, max_chars=6000)

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
            async for delta in deepseek.chat_stream(
                messages=messages_for_llm,
                temperature=0.6,
                max_tokens=1024,
            ):
                full_chunks.append(delta)
                yield f"event: delta\ndata: {_json.dumps({'text': delta})}\n\n"

            full = "".join(full_chunks)
            await mem.append_message(session_id, "assistant", full)

            # Long-term memory: store the user/assistant exchange in MemPalace
            # under chats/{session_id}. Fire-and-forget; never blocks streaming.
            try:
                if len(req.message.strip()) >= 12 and len(full.strip()) >= 20:
                    asyncio.create_task(
                        mempalace_agent.get_mempalace().store(
                            content=f"USER: {req.message}\nASSISTANT: {full}",
                            wing="chats",
                            room=session_id,
                            metadata={
                                "user_id": req.user_id,
                                "intent": intent,
                                "channel": "stream",
                            },
                            source="chat_stream",
                        )
                    )
            except Exception as _mp_err:  # noqa: BLE001
                logger.debug("mempalace autosave skipped: %s", _mp_err)

            # post-stream reliability + cost + unified audit via hook
            past = [m["content"] for m in (await mem.get_session(session_id, limit=10))
                    if m.get("role") == "assistant"]
            mem_ctx_texts = [r.get("content", "") for r in ctx.get("retrieved", [])]
            latency_ms = int((_time.time() - t0) * 1000)
            hook_res = await finalize_llm_turn(
                channel="stream",
                agent="orchestrator_stream",
                user_id=req.user_id,
                session_id=session_id,
                message=req.message,
                response_text=full,
                tokens_total=int(intent_resp.get("tokens_total", 0) or 0),
                deepseek_confidence=0.78,  # streamed; no logprobs aggregate
                evidence_count=len(mem_ctx_texts),
                past_responses=past,
                memory_context=mem_ctx_texts,
                intent=intent,
                agent_chain=["orchestrator(stream)"],
                mock=False,
                latency_ms=latency_ms,
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
    window: int = 200, sim_threshold: float = 0.45, divergence_threshold: float = 0.3
) -> Dict[str, Any]:
    return await diagnostics_agent.scan_contradictions(
        window=window,
        sim_threshold=sim_threshold,
        divergence_threshold=divergence_threshold,
    )


@api.get("/diagnostics/contradictions")
async def diagnostics_list(limit: int = 30) -> Dict[str, Any]:
    items = await diagnostics_agent.list_contradictions(limit=limit)
    return {"count": len(items), "contradictions": items}


@api.get("/diagnostics/summary")
async def diagnostics_summary(window: int = 200) -> Dict[str, Any]:
    return await diagnostics_agent.summary(window=window)


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
    mode: str = "operational"
    temperature: float = 0.3
    model: Optional[str] = None


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


@api.post("/hermes/chat")
async def hermes_chat(req: HermesChatRequest) -> Dict[str, Any]:
    """Enhanced Hermes COO endpoint with tool-calling and multi-tenant context."""
    import time as _time
    t0 = _time.time()
    result = await hermes_coo_agent.enhanced_chat(
        messages=req.messages,
        company_id=req.company_id,
        user_id=req.user_id,
        mode=req.mode,
        temperature=req.temperature,
        model=req.model,
    )
    # Universal pipeline hook
    last_user_msg = ""
    for m in reversed(req.messages or []):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user_msg = m.get("content") or ""
            break
    usage = (result.get("usage") or {}) if isinstance(result.get("usage"), dict) else {}
    tokens_total = int(result.get("tokens_total") or usage.get("total_tokens") or 0)
    sid = f"hermes_{uuid.uuid4().hex[:10]}"
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
        await mem.append_message(session_id, "user", req.message)
        if result.get("content"):
            await mem.append_message(session_id, "assistant", result["content"])
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
    if not result.get("success") and "не доступна" in (result.get("error") or "").lower() or \
       (not result.get("success") and "недоступна" in (result.get("error") or "")):
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
# Mount + CORS
# =====================================================================


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
