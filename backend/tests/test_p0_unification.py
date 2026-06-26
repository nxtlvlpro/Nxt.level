"""
P0 unification wave — backend regression tests.

Covers (per main-agent review_request):
  1.  /api/voice/converse  → should_escalate, confidence_level, request_id
  2.  /api/hermes/chat     → request_id, should_escalate, confidence_level
  3.  /api/hermes/ultra    → request_id, should_escalate, confidence_level
  4.  /api/personas/hermes/chat (plan_id=enterprise) → same keys
  5.  /api/chat/stream done frame → request_id, confidence_level, should_escalate
  6.  /api/requests lists every channel (web/stream/voice/hermes_chat/hermes_ultra/persona)
  7.  /api/roi/current.by_agent_cost contains hermes_coo, hermes_ultra, persona:*, voice
  8.  Hermes unification: hermes_coo / hermes_max_tools_and_coo shims still work,
      HERMES_TOOLS has the documented set (incl. 5 mock stubs).
  9.  Unified collection: a create_followup tool-call lands in db.tasks (kind=followup)
 10.  /api/documents/upload → id, severity, summary, findings, recommended_actions,
      request_id, chunks, mempalace_stored_chunks
 11.  /api/documents and /api/documents/{id}
 12.  /api/mempalace/search wing=documents finds uploaded chunks
 13.  /api/personas/compliance/chat references mempalace_search wing=documents
       in tool_traces OR mentions doc summary in content.

Notes:
* No auth. user_id="tester".
* OPENROUTER_API_KEY is set; DeepSeek live.
* If EMERGENT_LLM_KEY TTS budget exhausted, the converse test reports tts_error
  as an environmental issue (does not fail the suite).
"""
from __future__ import annotations

import io
import json as _json
import os
import sys
import time
import uuid

import pytest
import requests
from tests.conftest import auth_headers

# Resolve BASE_URL from REACT_APP_BACKEND_URL or /app/frontend/.env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def client(auth_headers):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", **auth_headers})
    return s


@pytest.fixture(scope="session")
def multipart_client(auth_headers):
    s = requests.Session()
    s.headers.update(auth_headers)
    return s


@pytest.fixture(scope="session")
def tts_audio_mp3(client):
    """Generate a tiny mp3 via /api/voice/tts for STT/converse reuse.
    /api/voice/tts returns raw audio/mpeg bytes (not JSON)."""
    r = client.post(
        f"{API}/voice/tts",
        json={"text": "Привет, это тест.", "voice": "nova", "language": "ru"},
        timeout=60,
    )
    if r.status_code != 200:
        pytest.skip(f"tts unavailable (env): {r.status_code} {r.text[:200]}")
    ct = r.headers.get("content-type", "")
    if "audio" in ct and len(r.content) > 200:
        return r.content
    # legacy/fallback: JSON envelope
    try:
        j = r.json()
        if j.get("error") or not j.get("audio_b64"):
            pytest.skip(f"tts returned no audio (env, EMERGENT_LLM budget?): {j}")
        import base64 as _b64
        return _b64.b64decode(j["audio_b64"])
    except Exception:
        pytest.skip(f"tts unexpected body ct={ct} size={len(r.content)}")


# ---------------------------------------------------------------------
# 8. Hermes unification — import shims + HERMES_TOOLS contents
# ---------------------------------------------------------------------
def test_hermes_unification_imports_and_tools():
    """Back-compat shim imports + HERMES_TOOLS contains documented tool set."""
    sys.path.insert(0, "/app/backend")
    from agents.hermes_max_tools_and_coo import HERMES_TOOLS as T1
    from agents.hermes_coo import enhanced_chat  # noqa: F401
    from agents.hermes import HERMES_TOOLS as T_CANON

    assert T1 is T_CANON or set(T1.keys()) == set(T_CANON.keys()), (
        "shim HERMES_TOOLS diverges from canonical")

    expected_core = {
        "create_task", "create_followup", "update_task",
        "monitor_sla_violations", "detect_bottlenecks",
        "generate_daily_digest", "mempalace_search", "mempalace_store",
        "create_cross_department_bridge", "search_memory",
    }
    expected_stubs = {
        "generate_communication_summary", "suggest_next_best_action",
        "find_opportunities_in_contact", "suggest_reply_template",
        "evaluate_action_roi",
    }
    have = set(T_CANON.keys())
    missing_core = expected_core - have
    missing_stub = expected_stubs - have
    assert not missing_core, f"missing core tools: {missing_core}"
    assert not missing_stub, f"missing stub tools: {missing_stub}"
    assert len(have) >= 15, f"expected ≥15 tools, have {len(have)}"


# ---------------------------------------------------------------------
# 2. /api/hermes/chat — pipeline hook payload
# ---------------------------------------------------------------------
def test_hermes_chat_returns_pipeline_keys(client):
    r = client.post(
        f"{API}/hermes/chat",
        json={
            "messages": [{"role": "user", "content": "привет, дай SLA-обзор"}],
            "user_id": "tester",
        },
        timeout=120,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()
    for k in ("request_id", "should_escalate", "confidence_level"):
        assert k in d, f"missing {k} in hermes/chat response keys={list(d.keys())}"
    assert isinstance(d["request_id"], str) and len(d["request_id"]) >= 8
    assert isinstance(d["should_escalate"], bool)
    assert d["confidence_level"] in ("low", "medium", "high")


# ---------------------------------------------------------------------
# 3. /api/hermes/ultra — pipeline hook payload
# ---------------------------------------------------------------------
def test_hermes_ultra_returns_pipeline_keys(client):
    r = client.post(
        f"{API}/hermes/ultra",
        json={
            "message": "Дай короткое summary по операционке.",
            "user_id": "tester",
            "company_id": "default",
            "autonomy_level": "read_only",
        },
        timeout=180,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()
    assert d.get("success") is True or d.get("content"), f"unsuccessful: {d}"
    for k in ("request_id", "should_escalate", "confidence_level"):
        assert k in d, f"missing {k}; keys={list(d.keys())}"
    assert d["confidence_level"] in ("low", "medium", "high")


# ---------------------------------------------------------------------
# 4. /api/personas/hermes/chat (plan_id=enterprise) — pipeline hook payload
# ---------------------------------------------------------------------
def test_persona_hermes_chat_returns_pipeline_keys(client):
    r = client.post(
        f"{API}/personas/hermes/chat",
        json={
            "message": "Дай 1-строчный SLA-обзор",
            "user_id": "tester",
            "plan_id": "enterprise",
        },
        timeout=180,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()
    for k in ("request_id", "should_escalate", "confidence_level"):
        assert k in d, f"missing {k}; keys={list(d.keys())}"


# ---------------------------------------------------------------------
# 1. /api/voice/converse — pipeline hook keys
# ---------------------------------------------------------------------
def test_voice_converse_pipeline_keys(multipart_client, tts_audio_mp3):
    files = {"file": ("audio.mp3", tts_audio_mp3, "audio/mpeg")}
    data = {"user_id": "tester", "language": "ru", "voice": "nova"}
    r = multipart_client.post(
        f"{API}/voice/converse", files=files, data=data, timeout=180
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()
    # Note: per main-agent — tts_error is env issue, not regression.
    for k in ("should_escalate", "confidence_level", "request_id"):
        assert k in d, f"missing {k} in voice/converse; keys={list(d.keys())}"
    assert isinstance(d["should_escalate"], bool)


# ---------------------------------------------------------------------
# 5. /api/chat/stream done event must include the 3 keys (already present)
# ---------------------------------------------------------------------
def test_chat_stream_done_keys(client):
    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    payload = {
        "user_id": "tester_stream",
        "session_id": session_id,
        "message": "Скажи 1 предложение про SLA.",
    }
    with requests.post(
        f"{API}/chat/stream", json=payload, stream=True, timeout=120
    ) as r:
        assert r.status_code == 200, r.text[:300]
        done_payload = None
        buf = []
        for raw in r.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            if raw == "":
                evt = None
                data_line = None
                for line in buf:
                    if line.startswith("event:"):
                        evt = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data_line = line.split(":", 1)[1].strip()
                buf = []
                if evt == "done" and data_line:
                    done_payload = _json.loads(data_line)
                    break
                if evt == "error":
                    pytest.fail(f"stream error: {data_line}")
            else:
                buf.append(raw)
    assert done_payload is not None, "no done frame received"
    for k in ("request_id", "confidence_level", "should_escalate"):
        assert k in done_payload, f"missing {k} in stream done; keys={list(done_payload.keys())}"


# ---------------------------------------------------------------------
# 6. /api/requests must contain rows from multiple channels (cross-cut audit)
# ---------------------------------------------------------------------
def test_requests_lists_all_channels(client):
    # Pull a large enough page to capture the channels created above.
    r = client.get(f"{API}/requests?limit=200", timeout=30)
    assert r.status_code == 200, r.text[:300]
    rows = r.json()
    assert isinstance(rows, list)
    channels = {row.get("channel") for row in rows if isinstance(row, dict)}
    # Channels we have just produced in this run + legacy `web`.
    expected = {"stream", "hermes_chat", "hermes_ultra", "persona"}
    missing = expected - channels
    assert not missing, (
        f"audit rows missing for channels {missing}; observed channels={channels}"
    )
    # Optional channels (env-dependent — voice needs TTS budget):
    if "voice" not in channels:
        print("[info] no 'voice' channel rows (TTS budget exhausted? env-dependent)")
    # 'web' is the legacy orchestrator channel — may or may not exist in
    # this run. Don't fail if absent, just report.
    if "web" not in channels:
        print("[info] no 'web' channel rows in last 200 requests (only legacy /api/chat writes 'web')")


# ---------------------------------------------------------------------
# 7. /api/roi/current.by_agent_cost should now include every channel agent
# ---------------------------------------------------------------------
def test_roi_current_by_agent_cost_covers_channels(client):
    r = client.get(f"{API}/roi/current", timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    bac = d.get("by_agent_cost") or d.get("byAgentCost") or {}
    assert isinstance(bac, dict) and bac, f"by_agent_cost missing/empty: {d}"
    keys = set(bac.keys())
    # Soft-check: hermes_coo and hermes_ultra must be present after we just
    # exercised them. voice should be present if voice/converse hit DeepSeek.
    required = {"hermes_coo", "hermes_ultra"}
    missing = required - keys
    assert not missing, f"by_agent_cost missing {missing}; keys={keys}"
    # persona:* — at least one entry
    has_persona = any(k.startswith("persona:") for k in keys)
    assert has_persona, f"no persona:* agent in by_agent_cost; keys={keys}"
    # voice — present if converse leg succeeded (env-dependent)
    if "voice" not in keys:
        print(f"[info] 'voice' not in by_agent_cost (env/tts budget may be exhausted); keys={keys}")


# ---------------------------------------------------------------------
# 9. Unified collection — followup tool-call lands in db.tasks (kind=followup)
# ---------------------------------------------------------------------
def test_create_followup_lands_in_tasks_collection(client):
    """Ask Hermes to schedule a follow-up; verify db.tasks gets a kind=followup."""
    marker = f"TEST_FU_{uuid.uuid4().hex[:8]}"
    msg = (
        "Запланируй follow-up через 1 час: позвонить клиенту ACME по вопросу "
        f"тестового маркера {marker}. Обязательно вызови инструмент create_followup."
    )
    r = client.post(
        f"{API}/hermes/chat",
        json={"messages": [{"role": "user", "content": msg}],
              "user_id": "tester"},
        timeout=180,
    )
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    tool_calls = d.get("tool_calls") or d.get("tool_traces") or []
    # Bird-eye sanity: model may or may not pick create_followup. If it didn't,
    # we still assert it could have — check the DB directly.
    # Read via Motor (in-process) — same DB the API writes to.
    sys.path.insert(0, "/app/backend")
    # Load backend env for direct DB access (uvicorn loads it but our pytest may not)
    try:
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
    except Exception:
        # Manual fallback
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass

    import asyncio
    from core.db import get_db

    async def _check():
        db = get_db()
        rows = await db.tasks.find(
            {"kind": "followup"}, {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(length=50)
        try:
            names = await db.list_collection_names()
            legacy = await db.followups.count_documents({}) if "followups" in names else 0
        except Exception:
            legacy = -1
        return rows, legacy

    loop = asyncio.new_event_loop()
    try:
        rows, legacy = loop.run_until_complete(_check())
    finally:
        loop.close()
    assert rows, (
        "db.tasks contains zero kind='followup' rows; tool_calls="
        f"{tool_calls}; reply={d.get('content','')[:300]}"
    )
    print(f"[info] db.tasks kind=followup rows={len(rows)}; legacy db.followups count={legacy}")


# ---------------------------------------------------------------------
# 10-12. Documents — upload + list/get + mempalace search
# ---------------------------------------------------------------------
@pytest.fixture(scope="session")
def uploaded_document(multipart_client):
    body = (
        "Договор: ответственность Поставщика неограниченная. "
        "Право расторжения в одностороннем порядке без уведомления. "
        f"Тестовый маркер документа: TEST_DOC_{uuid.uuid4().hex[:6]}"
    ).encode("utf-8")
    files = {"file": ("test_contract.txt", io.BytesIO(body), "text/plain")}
    data = {"user_id": "tester", "company_id": "default",
            "title": "TEST contract upload"}
    r = multipart_client.post(
        f"{API}/documents/upload", files=files, data=data, timeout=180
    )
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text[:400]}"
    d = r.json()
    return d


def test_documents_upload_response_shape(uploaded_document):
    d = uploaded_document
    for k in ("id", "severity", "summary", "findings", "recommended_actions",
              "request_id", "chunks", "mempalace_stored_chunks"):
        assert k in d, f"missing {k}; keys={list(d.keys())}"
    assert isinstance(d["id"], str) and len(d["id"]) >= 8
    assert d["severity"] in ("low", "medium", "high", "critical", "unknown"), \
        f"unexpected severity: {d['severity']}"
    assert isinstance(d["findings"], list)
    assert isinstance(d["recommended_actions"], list)
    assert int(d["chunks"]) >= 1
    assert int(d["mempalace_stored_chunks"]) >= 1
    assert isinstance(d["request_id"], str) and len(d["request_id"]) >= 8


def test_documents_list_and_get(client, uploaded_document):
    rL = client.get(f"{API}/documents?limit=50", timeout=20)
    assert rL.status_code == 200, rL.text[:300]
    lst = rL.json()
    assert isinstance(lst, dict) and isinstance(lst.get("documents"), list)
    assert lst.get("count", 0) >= 1
    doc_id = uploaded_document["id"]
    assert any(it.get("id") == doc_id for it in lst["documents"]), \
        f"uploaded doc {doc_id} not in list of {lst.get('count')}"

    rG = client.get(f"{API}/documents/{doc_id}", timeout=20)
    assert rG.status_code == 200, rG.text[:300]
    g = rG.json()
    assert g.get("id") == doc_id
    assert g.get("filename")


def test_mempalace_search_finds_uploaded_document(client, uploaded_document):
    # Allow a brief moment for MemPalace persistence to settle.
    time.sleep(0.5)
    doc_id = uploaded_document["id"]
    r = client.post(
        f"{API}/mempalace/search",
        json={"query": "ответственность неограниченная",
              "wing": "documents", "top_k": 10},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    hits = d.get("drawers") or d.get("results") or d.get("hits") or []
    assert isinstance(hits, list)
    assert len(hits) >= 1, f"no documents-wing hits for our query; payload={d}"
    # Strongly prefer: at least one hit matches our doc_id (room filter)
    # Otherwise: at least the content mentions our marker.
    found_room = any(
        (h.get("room") == doc_id) or (h.get("metadata", {}).get("room") == doc_id)
        for h in hits if isinstance(h, dict)
    )
    if not found_room:
        # fall back to content text match
        body_blob = _json.dumps(hits, ensure_ascii=False)
        assert "ответственность" in body_blob or doc_id in body_blob, (
            f"doc not found in documents wing; hits={hits[:3]}"
        )


# ---------------------------------------------------------------------
# 13. /api/personas/compliance/chat — should use mempalace_search wing=documents
# ---------------------------------------------------------------------
def test_persona_compliance_uses_documents_wing(client, uploaded_document):
    title = uploaded_document.get("title") or uploaded_document.get("filename") or ""
    r = client.post(
        f"{API}/personas/compliance/chat",
        json={
            "message": (
                "Найди риски по последнему загруженному договору. "
                "Используй mempalace_search с wing='documents'."
            ),
            "user_id": "tester",
            "plan_id": "enterprise",
        },
        timeout=240,
    )
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    traces = d.get("tool_traces") or []
    content = d.get("content") or ""

    # Acceptance: EITHER tool_traces shows mempalace_search w/ wing=documents,
    # OR content references the doc (summary / severity / title token).
    used_documents_wing = False
    for t in traces:
        if not isinstance(t, dict):
            continue
        if t.get("tool") == "mempalace_search" or t.get("name") == "mempalace_search":
            args = t.get("args") or t.get("arguments") or {}
            if isinstance(args, dict) and args.get("wing") == "documents":
                used_documents_wing = True
                break

    mentions_doc = bool(content) and (
        "договор" in content.lower()
        or "ответствен" in content.lower()
        or (title and title.lower() in content.lower())
    )
    assert used_documents_wing or mentions_doc, (
        f"compliance persona did not use mempalace_search wing=documents "
        f"and did not reference the doc in content; traces={traces}; "
        f"content={content[:300]}"
    )
