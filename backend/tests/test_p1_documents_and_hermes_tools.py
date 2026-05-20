"""P1 wave tests: Document upload UI backend + 5 real-LLM Hermes tools."""
from __future__ import annotations

import io
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TIMEOUT = 90


@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    return s


SAMPLE_TXT = (
    "Контракт TEST_P1\n"
    "1. Стороны обязуются исполнять условия в полном объеме.\n"
    "2. Штраф за нарушение конфиденциальности — 50,000 USD, без ограничения ответственности.\n"
    "3. Право на расторжение в одностороннем порядке без уведомления.\n"
    "4. Персональные данные передаются третьим лицам без согласия субъекта.\n"
)


# ---------- /api/documents ----------
class TestDocumentsEndpoints:
    doc_id: str = ""

    def test_upload_txt_returns_full_shape(self, session):
        files = {"file": ("TEST_p1.txt", io.BytesIO(SAMPLE_TXT.encode("utf-8")), "text/plain")}
        data = {"company_id": "default", "user_id": "TEST_p1_user", "title": "TEST_p1 contract"}
        r = session.post(f"{BASE_URL}/api/documents/upload", files=files, data=data, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("id", "severity", "summary", "findings", "recommended_actions", "request_id"):
            assert k in body, f"missing key {k} in {body.keys()}"
        assert isinstance(body["findings"], list)
        assert isinstance(body["recommended_actions"], list)
        assert body["severity"] in ("critical", "high", "medium", "low", "unknown")
        TestDocumentsEndpoints.doc_id = body["id"]

    def test_upload_empty_returns_400(self, session):
        files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
        r = session.post(f"{BASE_URL}/api/documents/upload", files=files, timeout=30)
        assert r.status_code == 400, r.text

    def test_upload_too_large_returns_400(self, session):
        big = b"a" * (11 * 1024 * 1024)
        files = {"file": ("big.txt", io.BytesIO(big), "text/plain")}
        r = session.post(f"{BASE_URL}/api/documents/upload", files=files, timeout=60)
        assert r.status_code in (400, 413), r.text

    def test_list_documents_includes_uploaded(self, session):
        assert TestDocumentsEndpoints.doc_id, "previous upload must have succeeded"
        r = session.get(f"{BASE_URL}/api/documents?limit=50", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "count" in data and "documents" in data
        ids = [d.get("id") for d in data["documents"]]
        assert TestDocumentsEndpoints.doc_id in ids
        # sorted desc — uploaded doc near top
        top5 = ids[:5]
        assert TestDocumentsEndpoints.doc_id in top5

    def test_get_document_by_id(self, session):
        assert TestDocumentsEndpoints.doc_id
        r = session.get(f"{BASE_URL}/api/documents/{TestDocumentsEndpoints.doc_id}", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == TestDocumentsEndpoints.doc_id
        for k in ("severity", "summary", "findings", "recommended_actions"):
            assert k in body

    def test_get_document_unknown_returns_404(self, session):
        r = session.get(f"{BASE_URL}/api/documents/{uuid.uuid4().hex}", timeout=15)
        assert r.status_code == 404


# ---------- 5 real-LLM-backed Hermes tools (direct unit test) ----------
class TestRealHermesTools:
    @pytest.mark.asyncio
    async def test_generate_communication_summary_real(self):
        from agents.hermes import HERMES_TOOLS
        res = await HERMES_TOOLS["generate_communication_summary"]({
            "text": "Клиент Acme спросил про скидку 15%. Менеджер обещал ответ в пятницу.",
        })
        assert res.get("ok") is True, res
        assert isinstance(res.get("summary"), str) and res["summary"]
        assert "sentiment" in res and "key_topics" in res

    @pytest.mark.asyncio
    async def test_suggest_next_best_action_real(self):
        from agents.hermes import HERMES_TOOLS
        res = await HERMES_TOOLS["suggest_next_best_action"]({
            "context": "Сделка зависла на согласовании цены.",
            "goal": "закрыть до конца недели",
        })
        assert res.get("ok") is True, res
        assert res.get("action")
        assert "rationale" in res
        assert "urgency" in res

    @pytest.mark.asyncio
    async def test_find_opportunities_in_contact_real(self):
        from agents.hermes import HERMES_TOOLS
        res = await HERMES_TOOLS["find_opportunities_in_contact"]({
            "contact_id": "contact_acme",
            "context": "Базовый план 6 мес, активно используют API.",
        })
        assert res.get("ok") is True, res
        assert isinstance(res.get("opportunities"), list)

    @pytest.mark.asyncio
    async def test_suggest_reply_template_real(self):
        from agents.hermes import HERMES_TOOLS
        res = await HERMES_TOOLS["suggest_reply_template"]({
            "last_message": "Здравствуйте, можно ли получить расширенную лицензию?",
            "intent": "квалифицировать запрос",
            "tone": "professional",
        })
        assert res.get("ok") is True, res
        assert res.get("template") or res.get("body")

    @pytest.mark.asyncio
    async def test_evaluate_action_roi_real(self):
        from agents.hermes import HERMES_TOOLS
        res = await HERMES_TOOLS["evaluate_action_roi"]({
            "action": "Запустить email-кампанию для 500 trial",
            "expected_cost_usd": 200,
            "expected_revenue_usd": 4000,
            "horizon_days": 14,
        })
        assert res.get("ok") is True, res
        assert res.get("estimated_roi") in ("low", "medium", "high", "negative")

    @pytest.mark.asyncio
    async def test_empty_args_rejected(self):
        from agents.hermes import HERMES_TOOLS
        for name in (
            "generate_communication_summary",
            "suggest_next_best_action",
            "find_opportunities_in_contact",
            "evaluate_action_roi",
        ):
            res = await HERMES_TOOLS[name]({})
            assert res.get("ok") is False, f"{name} should reject empty args"

    @pytest.mark.asyncio
    async def test_suggest_reply_template_canned_fallback(self):
        from agents.hermes import HERMES_TOOLS
        res = await HERMES_TOOLS["suggest_reply_template"]({})
        assert res.get("ok") is True
        assert res.get("context_used") is False
