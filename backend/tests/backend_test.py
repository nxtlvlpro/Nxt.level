"""
NXT8 backend integration tests.

Covers: health, seed, chat+session, memory store/search/list,
mentor (employees, patterns, performance, detect, recommend),
ROI (current, dashboard, deal+interaction attribution),
alerts, reliability assess, voice stubs.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback read from frontend env so pytest works regardless
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


@pytest.fixture(scope="session", autouse=True)
def _seed(client, admin_headers):
    # Idempotent seed — required by other tests
    r = client.post(f"{API}/seed", headers=admin_headers, timeout=60)
    assert r.status_code == 200, f"seed failed: {r.status_code} {r.text}"
    return r.json()


# ---------------- System ----------------

def test_health(client):
    r = client.get(f"{API}/health", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mongo"] is True
    # DeepSeek may be live or mock — both are acceptable. We do NOT assert mock_mode.
    assert "deepseek" in data
    ds = data["deepseek"]
    # iter3: active_provider + providers list required
    assert "active_provider" in ds
    assert isinstance(ds.get("providers"), list) and len(ds["providers"]) >= 1
    # Voice block — required by review_request iter 2
    assert "voice" in data
    v = data["voice"]
    assert v.get("enabled") is True
    assert v.get("stt_model") == "whisper-1"
    assert v.get("tts_model") == "tts-1"


def test_seed_idempotent(client, _seed, admin_headers):
    r = client.post(f"{API}/seed", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"seeded", "already_seeded"}


# ---------------- Chat / sessions ----------------

def test_chat_returns_mock_response(client):
    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    payload = {"user_id": "tester", "session_id": session_id, "message": "Привет, скажи политику возвратов"}
    r = client.post(f"{API}/chat", json=payload, timeout=200)
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ["request_id", "content", "intent", "confidence", "confidence_level",
                "should_escalate", "verification_status", "signals", "latency_ms", "mock"]:
        assert key in d, f"missing key {key} in chat response"
    assert isinstance(d["mock"], bool)
    assert isinstance(d["confidence"], (int, float))
    assert d["content"]  # non-empty whether live or mock


def test_session_persistence(client):
    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    msg = "Что у нас по ARR компании?"
    r = client.post(f"{API}/chat", json={"user_id": "u1", "session_id": session_id, "message": msg}, timeout=200)
    assert r.status_code == 200
    # small wait for write
    time.sleep(0.3)
    r2 = client.get(f"{API}/sessions/{session_id}", timeout=15)
    assert r2.status_code == 200
    d = r2.json()
    assert d["session_id"] == session_id
    assert isinstance(d["messages"], list)
    assert len(d["messages"]) >= 1


# ---------------- Memory ----------------

def test_memory_store_and_search_roundtrip(client):
    content = f"TEST_DOC unique-marker {uuid.uuid4().hex[:6]} рейтинг ARR клиенты"
    r = client.post(f"{API}/memory/store", json={"content": content, "type": "corporate"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "stored"

    r2 = client.post(f"{API}/memory/search", json={"query": "ARR клиенты рейтинг", "top_k": 5}, timeout=15)
    assert r2.status_code == 200
    d = r2.json()
    assert d["count"] >= 1


def test_memory_list_seeded(client):
    r = client.get(f"{API}/memory/list?type=corporate", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 6


# ---------------- Mentor ----------------

def test_mentor_list_employees(client):
    r = client.get(f"{API}/mentor/employees", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 4
    levels = {e["level"] for e in d["employees"]}
    assert {"junior", "mid", "senior", "lead"}.issubset(levels)


def test_mentor_patterns_for_junior(client):
    # ensure detection ran
    client.post(f"{API}/mentor/detect/emp_jr", timeout=15)
    r = client.get(f"{API}/mentor/patterns", timeout=15)
    assert r.status_code == 200
    items = r.json()["patterns"]
    jr_patterns = [p for p in items if p.get("employee_id") == "emp_jr"]
    assert len(jr_patterns) >= 1
    types = {p.get("pattern") or p.get("type") or p.get("name") for p in jr_patterns}
    # at least one of expected
    assert any(t in {"repeating_errors", "low_accuracy", "high_escalation"} for t in types if t)


def test_mentor_employee_summary(client):
    r = client.get(f"{API}/mentor/employees/emp_jr", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "history" in d
    assert "open_patterns" in d


def test_mentor_record_performance(client):
    payload = {
        "employee_id": "emp_jr",
        "accuracy": 0.6,
        "speed": 1.4,
        "escalation_rate": 0.3,
        "error_repeat": 1,
        "tasks_completed": 10,
        "tasks_reviewed": 5,
    }
    r = client.post(f"{API}/mentor/performance", json=payload, timeout=15)
    assert r.status_code == 200


def test_mentor_detect_patterns(client):
    r = client.post(f"{API}/mentor/detect/emp_jr", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["employee_id"] == "emp_jr"
    assert isinstance(d["patterns"], list)


def test_mentor_recommendation_schema(client):
    r = client.get(f"{API}/mentor/recommend/emp_jr/repeating_errors", timeout=15)
    assert r.status_code == 200
    d = r.json()
    for key in ["employee_id", "level", "weak_pattern", "confidence", "suggested_action", "link_to_doc", "timestamp"]:
        assert key in d, f"missing recommendation key {key}"
    assert d["employee_id"] == "emp_jr"
    assert d["weak_pattern"] == "repeating_errors"


# ---------------- ROI ----------------

def test_roi_current_has_costs(client):
    r = client.get(f"{API}/roi/current", timeout=20)
    assert r.status_code == 200
    d = r.json()
    for key in ["roi", "total_cost", "total_revenue", "by_agent_cost", "by_agent_roi", "alert"]:
        assert key in d, f"missing ROI key {key}"
    assert d["total_cost"] > 0


def test_roi_dashboard(client):
    r = client.get(f"{API}/roi/dashboard", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "current_hour" in d
    assert "trend_24h" in d


def test_roi_deal_interaction_attribution(client):
    deal_id = f"deal_test_{uuid.uuid4().hex[:8]}"
    # record interactions FIRST
    for agent in ["orchestrator", "memory", "orchestrator"]:
        r = client.post(f"{API}/roi/interactions",
                        json={"deal_id": deal_id, "agent": agent}, timeout=15)
        assert r.status_code == 200
    # then close the deal
    r2 = client.post(f"{API}/roi/deals",
                     json={"deal_id": deal_id, "value_usd": 1000.0, "team": "sales"}, timeout=20)
    assert r2.status_code == 200
    d = r2.json()
    # attribution should populate by_agent_revenue
    assert "by_agent_revenue" in d or "attribution" in d or "deal_id" in d


# ---------------- Alerts ----------------

def test_alerts_list(client):
    r = client.get(f"{API}/alerts", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 1


# ---------------- Reliability ----------------

def test_reliability_assess(client):
    payload = {
        "response": "ARR компании сейчас составляет $4.8M, цель — $7.5M.",
        "deepseek_confidence": 0.8,
        "evidence_count": 2,
        "past_responses": ["ARR $4.8M текущий"],
        "memory_context": ["Текущий ARR компании: $4.8M"],
    }
    r = client.post(f"{API}/reliability/assess", json=payload, timeout=15)
    assert r.status_code == 200
    d = r.json()
    for key in ["score", "level", "should_escalate", "has_contradiction", "verification_status", "signals"]:
        assert key in d, f"missing reliability key {key}"
    assert 0.0 <= d["score"] <= 1.0


# ---------------- Voice (Whisper STT + OpenAI TTS via Emergent key) ----------------


@pytest.fixture(scope="session")
def multipart_client(auth_headers):
    """A separate session without forced JSON content-type for multipart uploads."""
    s = requests.Session()
    s.headers.update(auth_headers)
    return s


@pytest.fixture(scope="session")
def tts_audio_mp3(client):
    """Generate a real mp3 once via /api/voice/tts and reuse for STT / converse tests."""
    payload = {"text": "Hello world from NXT8 voice test.",
               "voice": "nova", "speed": 1.0, "model": "tts-1"}
    r = client.post(f"{API}/voice/tts", json=payload, timeout=60)
    assert r.status_code == 200, f"TTS bootstrap failed: {r.status_code} {r.text[:200]}"
    assert r.headers.get("content-type", "").startswith("audio/mpeg"), r.headers
    audio = r.content
    assert len(audio) > 1000, "TTS audio suspiciously small"
    magic2 = audio[:2]
    assert (magic2[0] == 0xFF and (magic2[1] & 0xF0) == 0xF0) or audio[:3] == b"ID3", (
        f"Not a valid MP3 stream — first bytes={audio[:4].hex()}"
    )
    return audio


def test_voice_tts_returns_mp3(client, tts_audio_mp3):
    # Already verified inside the fixture, but assert again for explicit reporting
    assert isinstance(tts_audio_mp3, (bytes, bytearray))
    assert len(tts_audio_mp3) > 1000


def test_voice_tts_rejects_empty_text(client):
    r = client.post(f"{API}/voice/tts",
                    json={"text": "", "voice": "nova"}, timeout=15)
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"


def test_voice_tts_rejects_whitespace_text(client):
    r = client.post(f"{API}/voice/tts",
                    json={"text": "   "}, timeout=15)
    assert r.status_code == 400


def test_voice_tts_clamps_voice_and_speed(client):
    # Unknown voice should be coerced to default 'nova' inside synthesize() — status must be 200.
    r = client.post(f"{API}/voice/tts",
                    json={"text": "ok", "voice": "not_a_voice", "speed": 999.0},
                    timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/mpeg")


def test_voice_stt_transcribes_audio(multipart_client, tts_audio_mp3):
    files = {"file": ("audio.mp3", tts_audio_mp3, "audio/mpeg")}
    data = {"language": "en"}
    r = multipart_client.post(f"{API}/voice/stt", files=files, data=data, timeout=120)
    assert r.status_code == 200, f"STT failed: {r.status_code} {r.text[:300]}"
    d = r.json()
    for key in ["text", "language", "duration", "model"]:
        assert key in d, f"missing key {key} in STT response"
    assert isinstance(d["text"], str) and len(d["text"]) > 0
    assert d["model"] == "whisper-1"
    assert any(tok.lower() in d["text"].lower() for tok in ["nxt", "world", "hello"])


def test_voice_stt_rejects_empty_file(multipart_client):
    files = {"file": ("audio.webm", b"", "audio/webm")}
    r = multipart_client.post(f"{API}/voice/stt", files=files, timeout=15)
    assert r.status_code == 400, r.text


def test_voice_converse_full_loop(multipart_client, tts_audio_mp3):
    import base64 as _b64
    files = {"file": ("audio.mp3", tts_audio_mp3, "audio/mpeg")}
    data = {"user_id": "tester", "language": "en", "voice": "nova"}
    r = multipart_client.post(f"{API}/voice/converse", files=files, data=data, timeout=180)
    assert r.status_code == 200, f"converse failed: {r.status_code} {r.text[:300]}"
    d = r.json()
    for key in ["session_id", "transcript", "language", "reply",
                "confidence", "should_escalate", "audio_b64",
                "audio_format", "tts_error"]:
        assert key in d, f"missing key {key} in converse response"
    assert d["session_id"].startswith("sess_")
    assert isinstance(d["transcript"], str) and len(d["transcript"]) > 0
    assert isinstance(d["reply"], str) and len(d["reply"]) > 0
    if d.get("tts_error"):
        pytest.fail(f"TTS leg of converse failed: {d['tts_error']}")
    assert d["audio_format"] == "mp3"
    assert isinstance(d["audio_b64"], str) and len(d["audio_b64"]) > 100
    decoded = _b64.b64decode(d["audio_b64"])
    assert len(decoded) > 1000
    assert (decoded[0] == 0xFF and (decoded[1] & 0xF0) == 0xF0) or decoded[:3] == b"ID3", (
        f"converse audio_b64 not valid mp3, head={decoded[:4].hex()}"
    )


def test_voice_converse_rejects_empty_file(multipart_client):
    files = {"file": ("audio.webm", b"", "audio/webm")}
    r = multipart_client.post(f"{API}/voice/converse", files=files,
                              data={"user_id": "tester"}, timeout=15)
    assert r.status_code == 400


# =====================================================================
# Iter 3 — SSE /chat/stream
# =====================================================================


def test_chat_stream_sse_frames(client):
    """Hit /api/chat/stream, parse SSE frames, verify meta/delta/done arrive
    and that an audit row is persisted to db.requests."""
    import json as _json

    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    payload = {
        "user_id": "tester_stream",
        "session_id": session_id,
        "message": "Привет! Кратко скажи политику возвратов компании.",
    }
    # use stream=True so we can read events as they arrive
    with client.post(
        f"{API}/chat/stream", json=payload, stream=True, timeout=90
    ) as r:
        assert r.status_code == 200, r.text[:300]
        ctype = r.headers.get("content-type", "")
        assert "text/event-stream" in ctype, f"bad content-type: {ctype}"

        events = {"meta": 0, "delta": 0, "done": 0, "error": 0}
        done_payload = None
        buf = []
        # raw line-by-line
        for raw in r.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            if raw == "":
                # frame separator — process buffered frame
                if not buf:
                    continue
                evt = None
                data_line = None
                for line in buf:
                    if line.startswith("event:"):
                        evt = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data_line = line.split(":", 1)[1].strip()
                buf = []
                if evt in events:
                    events[evt] += 1
                if evt == "done" and data_line:
                    try:
                        done_payload = _json.loads(data_line)
                    except Exception:
                        pass
                    break  # done is terminal
                if evt == "error" and data_line:
                    pytest.fail(f"stream produced error frame: {data_line}")
            else:
                buf.append(raw)

    assert events["meta"] >= 1, f"no meta frame, got {events}"
    assert events["delta"] >= 1, f"no delta frames, got {events}"
    assert events["done"] == 1, f"expected exactly 1 done, got {events}"
    assert events["error"] == 0, f"unexpected error frames, got {events}"
    assert done_payload is not None
    for key in [
        "request_id", "session_id", "intent", "confidence",
        "confidence_level", "should_escalate", "verification_status",
        "latency_ms", "provider",
    ]:
        assert key in done_payload, f"missing {key} in done payload"
    assert done_payload["session_id"] == session_id

    # audit row persisted
    time.sleep(0.5)
    r2 = client.get(f"{API}/sessions/{session_id}", timeout=15)
    assert r2.status_code == 200
    msgs = r2.json().get("messages", [])
    assert any(m.get("role") == "assistant" for m in msgs), msgs


# =====================================================================
# Iter 3 — Cross-Department Coordinator
# =====================================================================


def test_cross_dept_detect_sales_support(client):
    r = client.get(
        f"{API}/cross-dept/detect",
        params={"query": "Расскажи про продажи и поддержку клиентов"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("departments"), list)
    depts = set(d["departments"])
    assert "sales" in depts and "support" in depts, depts
    assert d["multi_department"] is True


def test_cross_dept_coordinate_multi(client):
    payload = {
        "query": "Расскажи про продажи и поддержку",
        "user_id": "tester",
        "session_id": f"sess_{uuid.uuid4().hex[:10]}",
    }
    r = client.post(f"{API}/cross-dept/coordinate", json=payload, timeout=180)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    for key in [
        "task_id", "departments", "multi_department", "findings",
        "synthesis", "confidence", "provider", "mock", "created_at",
    ]:
        assert key in d, f"missing {key} in coordinate response: {list(d.keys())}"
    depts = set(d["departments"])
    assert "sales" in depts and "support" in depts, depts
    assert d["multi_department"] is True
    assert isinstance(d["findings"], list) and len(d["findings"]) >= 2
    assert isinstance(d["synthesis"], str) and len(d["synthesis"]) > 0
    assert isinstance(d["confidence"], (int, float))


def test_cross_dept_tasks_list(client):
    r = client.get(f"{API}/cross-dept/tasks", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "count" in d and "tasks" in d
    assert isinstance(d["tasks"], list)
    # No mongo _id leak
    for t in d["tasks"]:
        assert "_id" not in t


# =====================================================================
# Iter 3 — Diagnostics
# =====================================================================


def test_diagnostics_scan_idempotent(client):
    # warm up a couple of chats so there is audit data
    for msg in ["Что у нас по ARR?", "Скажи ARR компании", "Политика возвратов?"]:
        client.post(
            f"{API}/chat",
            json={"user_id": "diag", "session_id": f"sess_{uuid.uuid4().hex[:6]}", "message": msg},
            timeout=120,
        )

    r1 = client.post(
        f"{API}/diagnostics/scan",
        params={"window": 50, "sim_threshold": 0.3, "divergence_threshold": 0.3},
        timeout=60,
    )
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    for key in ["count", "contradictions", "scanned"]:
        assert key in d1
    assert d1["count"] >= 0 and d1["scanned"] >= 0

    # rerun — must not crash on dup pair_key
    r2 = client.post(
        f"{API}/diagnostics/scan",
        params={"window": 50, "sim_threshold": 0.3, "divergence_threshold": 0.3},
        timeout=60,
    )
    assert r2.status_code == 200, r2.text


def test_diagnostics_contradictions_list(client):
    r = client.get(f"{API}/diagnostics/contradictions", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "count" in d and isinstance(d["contradictions"], list)
    for item in d["contradictions"]:
        assert "_id" not in item


def test_diagnostics_summary(client):
    r = client.get(f"{API}/diagnostics/summary", timeout=20)
    assert r.status_code == 200
    d = r.json()
    for key in ["scanned", "avg_confidence", "escalation_rate", "mock_rate", "noisy_intents"]:
        assert key in d, f"missing {key} in diagnostics summary"
    assert isinstance(d["noisy_intents"], list)


# =====================================================================
# Iter 3 — Skill Creator
# =====================================================================


def test_skills_scan_no_crash(client):
    r = client.post(f"{API}/skills/scan", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    # agent currently returns {created: N, skills: [...]}; review_request
    # description says count=0 is acceptable when no patterns hit threshold.
    n = d.get("count", d.get("created"))
    assert n is not None, f"neither count nor created in {d}"
    assert isinstance(n, int) and n >= 0
    assert "skills" in d and isinstance(d["skills"], list)


def test_skills_create_and_list_and_toggle(client):
    payload = {
        "name": f"TEST_skill_{uuid.uuid4().hex[:6]}",
        "intent": "knowledge",
        "signature_terms": ["arr", "policy", "refund"],
        "prompt_template": "Ответь кратко по теме: {query}",
        "memory_filter": {"type": "corporate"},
    }
    r = client.post(f"{API}/skills", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    created = r.json()
    assert "id" in created
    assert created.get("name", "").startswith("TEST_skill_")
    skill_id = created["id"]

    # list
    r2 = client.get(f"{API}/skills", timeout=15)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["count"] >= 1
    ids = [s.get("id") for s in d2["skills"]]
    assert skill_id in ids
    for s in d2["skills"]:
        assert "_id" not in s

    # toggle off
    r3 = client.post(
        f"{API}/skills/{skill_id}/toggle", params={"enabled": "false"}, timeout=15
    )
    assert r3.status_code == 200, r3.text
    assert r3.json().get("enabled") in (False, "false", 0)

    # filter enabled=true should NOT include this one now
    r4 = client.get(f"{API}/skills", params={"enabled": "true"}, timeout=15)
    assert r4.status_code == 200
    ids_enabled = [s.get("id") for s in r4.json()["skills"]]
    assert skill_id not in ids_enabled

    # toggle unknown -> 404
    r5 = client.post(
        f"{API}/skills/skill_does_not_exist_xyz/toggle",
        params={"enabled": "true"}, timeout=15,
    )
    assert r5.status_code == 404, r5.text


# =====================================================================
# Iter 3 — Market Radar
# =====================================================================


def test_market_ingest_signal_and_list(client):
    payload = {
        "headline": f"TEST_signal NXT8 launches new AI module {uuid.uuid4().hex[:6]}",
        "source": "pytest",
        "category": "ai",
        "url": "https://example.com/news/1",
        "score": 0.71,
    }
    r = client.post(f"{API}/market/signals", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "id" in d
    assert d.get("headline", "").startswith("TEST_signal")

    r2 = client.get(f"{API}/market/signals", timeout=15)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["count"] >= 1
    for s in d2["signals"]:
        assert "_id" not in s


def test_market_ingest_empty_headline_rejected(client):
    r = client.post(
        f"{API}/market/signals",
        json={"headline": "", "category": "ai"},
        timeout=15,
    )
    assert r.status_code == 400, r.text


def test_market_scan_returns_digest(client):
    r = client.post(
        f"{API}/market/scan", params={"window_hours": 72}, timeout=90
    )
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for key in [
        "id", "period_hours", "signals_count", "digest",
        "confidence", "provider", "created_at",
    ]:
        assert key in d, f"missing {key} in market scan: {list(d.keys())}"
    assert isinstance(d["digest"], str) and len(d["digest"]) > 0


def test_market_digests_list(client):
    r = client.get(f"{API}/market/digests", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "count" in d and isinstance(d["digests"], list)
    for item in d["digests"]:
        assert "_id" not in item



# =====================================================================
# Iter 5 — Hermes Agent proxy (module 15, additive)
# =====================================================================


def test_hermes_health_online(client):
    """Hermes proxy must stay graceful whether the sidecar is online or not."""
    r = client.get(f"{API}/hermes/health", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("status") in {"online", "offline", "degraded"}, d
    assert d.get("base_url") == "http://127.0.0.1:8642", d
    if d.get("status") == "online":
        h = d.get("hermes") or {}
        assert isinstance(h, dict)
    else:
        assert isinstance(d.get("error") or d.get("http_status"), (str, int))


def test_hermes_jobs_list(client):
    """GET /api/hermes/jobs must degrade gracefully when Hermes is offline."""
    r = client.get(f"{API}/hermes/jobs", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "ok" in d, d
    assert isinstance(d.get("jobs"), list)
    assert isinstance(d.get("status_code"), int)
    assert d["status_code"] in range(200, 600)


def test_hermes_job_create_no_crash(client):
    """POST /api/hermes/jobs with minimal payload — must not crash with 5xx.

    Hermes may reject the body (missing cron/etc.), but proxy must respond
    gracefully with ok=false and an http status_code, never raise."""
    payload = {"prompt": "TEST: ping", "deliver": "log"}
    r = client.post(f"{API}/hermes/jobs", json=payload, timeout=30)
    assert r.status_code == 200, r.text  # proxy itself returns 200
    d = r.json()
    assert "ok" in d
    assert "status_code" in d
    assert isinstance(d["status_code"], int)
    # Whether Hermes accepted or rejected, proxy must report a code
    assert d["status_code"] in range(200, 600)
