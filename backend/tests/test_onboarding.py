"""Onboarding survey + Hermes brief backend tests."""
import os
import re
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to internal preview if env not set in shell
    BASE_URL = "https://approval-gate-demo.preview.emergentagent.com"

API = f"{BASE_URL}/api"
HEADERS = {"Content-Type": "application/json"}
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


# --- Funnel ---
def test_funnel_stats():
    r = requests.get(f"{API}/onboarding/funnel", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("days", "total", "hot", "warm", "cold", "test_access"):
        assert k in data, f"missing {k}"
    assert isinstance(data["total"], int)


# --- Insights (static + LLM fallback) ---
def test_insight_static_en_ecommerce():
    r = requests.post(
        f"{API}/onboarding/insight",
        json={"qid": "industry", "answer": "ecommerce", "lang": "en"},
        headers=HEADERS, timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("source") == "static"
    assert "minute" in (data.get("text") or "").lower()


def test_insight_llm_fallback_ru():
    r = requests.post(
        f"{API}/onboarding/insight",
        json={"qid": "team_size", "answer": "unknown-value-xyz", "lang": "ru"},
        headers=HEADERS, timeout=45,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("source") in ("llm", "fallback"), data
    text = data.get("text") or ""
    if data.get("source") == "llm":
        assert CYRILLIC_RE.search(text), f"expected cyrillic in: {text}"
    else:
        pytest.skip(f"LLM unavailable; got fallback: {text}")


# --- Verify code ---
def test_verify_code_valid():
    r = requests.post(f"{API}/onboarding/verify-code",
                      json={"code": "888"}, headers=HEADERS, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("valid") is True
    assert data.get("label") == "Pilot 2026"


def test_verify_code_unknown():
    r = requests.post(f"{API}/onboarding/verify-code",
                      json={"code": "123"}, headers=HEADERS, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("valid") is False
    assert data.get("reason") == "unknown"


def test_verify_code_format():
    r = requests.post(f"{API}/onboarding/verify-code",
                      json={"code": "ab"}, headers=HEADERS, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("valid") is False
    assert data.get("reason") == "format"


# --- Profiles ---
def _profile_payload(**overrides):
    base = {
        "industry": "ecommerce",
        "team_size": "2-5",
        "management_structure": "flat",
        "communication_channels": ["whatsapp", "telegram"],
        "process_system": "spreadsheets",
        "knowledge_storage": "google_drive",
        "pain_points": ["leads_lost", "chaos", "no_followups"],
        # back-compat fields (still used by some tests / older saved profiles)
        "pain_primary": "leads_lost",
        "pain_secondary": "chaos",
        "tools_current": ["whatsapp", "crm"],
        "goal_90days": "grow_sales",
        "urgency": "hot",
        "name": "TEST_Alex",
        "phone": "+10000000001",
        "telegram": "@test_alex",
        "email": "test_alex@example.com",
        "lang": "ru",
        "selected_plan": "simple",
    }
    base.update(overrides)
    return base


def test_profile_save_with_access_code():
    # baseline funnel test_access count
    before = requests.get(f"{API}/onboarding/funnel", timeout=15).json()
    before_count = int(before.get("test_access", 0))

    # baseline used_count? we'll just check it increments via second call
    payload = _profile_payload(access_code="888")
    r = requests.post(f"{API}/onboarding/profiles", json=payload,
                      headers=HEADERS, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("test_access") is True
    assert data.get("profile_id")
    pytest.shared_profile_id = data["profile_id"]

    after = requests.get(f"{API}/onboarding/funnel", timeout=15).json()
    assert int(after.get("test_access", 0)) >= before_count + 1


def test_profile_save_without_access_code():
    payload = _profile_payload(name="TEST_NoCodeUser")
    r = requests.post(f"{API}/onboarding/profiles", json=payload,
                      headers=HEADERS, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("test_access") is False
    assert data.get("profile_id")


def test_profile_missing_required_field():
    payload = _profile_payload()
    payload.pop("industry")
    r = requests.post(f"{API}/onboarding/profiles", json=payload,
                      headers=HEADERS, timeout=20)
    # Pydantic missing field -> 422; explicit business validation -> 400.
    assert r.status_code in (400, 422), r.text


def test_profile_missing_industry_as_empty_string():
    # industry is required by Pydantic. To hit the business 400 path, send empty.
    payload = _profile_payload(industry="")
    r = requests.post(f"{API}/onboarding/profiles", json=payload,
                      headers=HEADERS, timeout=20)
    assert r.status_code == 400, r.text


# --- Brief + Hermes reply ---
def test_brief_and_hermes_reply_ru():
    pid = getattr(pytest, "shared_profile_id", None)
    if not pid:
        # create one
        payload = _profile_payload(name="TEST_BriefUser")
        r = requests.post(f"{API}/onboarding/profiles", json=payload,
                          headers=HEADERS, timeout=30)
        assert r.status_code == 200
        pid = r.json()["profile_id"]
        pytest.shared_profile_id = pid

    t0 = time.time()
    r = requests.post(f"{API}/onboarding/brief/{pid}", timeout=60)
    elapsed = time.time() - t0
    print(f"Brief generated in {elapsed:.1f}s")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("profile_id") == pid
    brief = data.get("brief") or {}
    reply = data.get("hermes_reply") or {}
    assert isinstance(brief.get("professions"), list) and brief["professions"]
    assert isinstance(brief.get("integrations"), list) and brief["integrations"]
    assert brief.get("cta", {}).get("label")
    assert brief.get("lang") == "ru"

    for k in ("intro", "block1_understood", "block2_team",
              "block3_in_30_days", "block4_potential", "block5_cta"):
        assert k in reply, f"missing {k} in hermes_reply"
    assert isinstance(reply["block2_team"], list) and reply["block2_team"]
    assert isinstance(reply["block3_in_30_days"], list)
    assert isinstance(reply["block4_potential"], str) and reply["block4_potential"]
    assert isinstance(reply["block5_cta"], str) and reply["block5_cta"]
    # cta label by urgency=hot (RU)
    cta_label = (brief.get("cta") or {}).get("label") or ""
    assert "Hermes" in cta_label or "Hermes" in (reply["block5_cta"] or "")
    # Russian content check
    assert CYRILLIC_RE.search(reply["intro"]) or CYRILLIC_RE.search(reply["block1_understood"]), \
        f"expected Russian text; intro={reply['intro']!r}"


def test_get_profile_persists_brief():
    pid = getattr(pytest, "shared_profile_id", None)
    assert pid, "previous test must have set shared_profile_id"
    r = requests.get(f"{API}/onboarding/profiles/{pid}", timeout=20)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc.get("id") == pid
    assert "brief" in doc and doc["brief"]
    assert "hermes_reply" in doc and doc["hermes_reply"]


def test_get_profile_not_found():
    r = requests.get(f"{API}/onboarding/profiles/nonexistent-id-xyz",
                     timeout=15)
    assert r.status_code == 404


# --- URGENCY CTA mapping (warm + cold) ---
@pytest.mark.parametrize("urgency,expected_ru_substring", [
    ("warm", "демо"),
    ("cold", "Следить"),
])
def test_brief_cta_by_urgency(urgency, expected_ru_substring):
    payload = _profile_payload(name=f"TEST_Urg_{urgency}", urgency=urgency)
    r = requests.post(f"{API}/onboarding/profiles", json=payload,
                      headers=HEADERS, timeout=30)
    assert r.status_code == 200, r.text
    pid = r.json()["profile_id"]
    rb = requests.post(f"{API}/onboarding/brief/{pid}", timeout=60)
    assert rb.status_code == 200, rb.text
    data = rb.json()
    cta = (data.get("brief") or {}).get("cta") or {}
    label = cta.get("label") or ""
    assert expected_ru_substring.lower() in label.lower(), (
        f"urgency={urgency} expected '{expected_ru_substring}' in cta.label, got {label!r}"
    )


# --- New 9-Q schema acceptance ---
def test_profile_save_with_new_9q_schema():
    payload = _profile_payload(
        name="TEST_NewSchema",
        management_structure="hierarchical",
        communication_channels=["telegram", "email", "slack"],
        process_system="notion",
        knowledge_storage="onedrive",
        pain_points=["leads_lost", "chaos", "no_followups"],
        email="schema_test@example.com",
        phone="+10000000002",
        telegram="@schema_test",
    )
    # drop legacy back-compat fields to ensure new schema alone works
    payload.pop("pain_primary", None)
    payload.pop("pain_secondary", None)
    payload.pop("tools_current", None)
    r = requests.post(f"{API}/onboarding/profiles", json=payload,
                      headers=HEADERS, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    pid = data["profile_id"]
    # GET to verify persistence
    g = requests.get(f"{API}/onboarding/profiles/{pid}", timeout=20)
    assert g.status_code == 200, g.text
    doc = g.json()
    assert doc.get("pain_points") == ["leads_lost", "chaos", "no_followups"]
    assert doc.get("communication_channels") == ["telegram", "email", "slack"]
    assert doc.get("management_structure") == "hierarchical"
    assert doc.get("process_system") == "notion"
    assert doc.get("knowledge_storage") == "onedrive"
    assert doc.get("email") == "schema_test@example.com"
