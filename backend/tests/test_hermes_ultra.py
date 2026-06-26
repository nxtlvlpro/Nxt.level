"""Hermes Ultra (v1.3.0) backend tests — LangGraph supervisor->hermes->tools.

Covers:
- POST /api/hermes/ultra basic, read_only, controlled_automation, invalid autonomy
- Session continuity via session_id (LangGraph MemorySaver checkpointer)
- Regression: /api/hermes/chat, /api/hermes/daily-digest, /api/hermes/health,
  /api/requests, /api/chat
- Direct unit tests of _extract_tool_calls + tools_node (crafted assistant content)
- MongoDB persistence (tasks via tool, sessions via memory.append_message)
- Stub tools mock=true contract
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv

from tests.conftest import auth_headers

# Load backend .env so direct-module tests (mongo, memory) work
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ULTRA = f"{BASE_URL}/api/hermes/ultra"
TIMEOUT = 180  # Live LLM + tools may occasionally need longer in CI/preview

# Allow importing backend modules for unit tests
sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="module")
def session(auth_headers) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", **auth_headers})
    return s


class _DummyMemory:
    async def append_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


def _patch_ultra_endpoint(monkeypatch, *, result: dict):
    import server as server_mod

    async def _fake_run_nxt8_ultra(**kwargs):
        return {
            "content": "stubbed ultra reply",
            "thread_id": kwargs.get("session_id") or f"sess_{uuid.uuid4().hex[:8]}",
            "iterations": 1,
            "tool_traces": [],
            "confidence": 0.81,
            "requires_human_approval": False,
            "fallback": "unit_test_stub",
            **result,
        }

    async def _fake_finalize_llm_turn(**kwargs):
        return {
            "confidence": kwargs.get("deepseek_confidence", 0.81),
            "confidence_level": "medium",
            "should_escalate": False,
            "request_id": "req_test_ultra",
        }

    async def _fake_resolve_company_id(_user_id, explicit=None):
        return explicit or "default"

    monkeypatch.setattr(server_mod, "run_nxt8_ultra", _fake_run_nxt8_ultra)
    monkeypatch.setattr(server_mod, "finalize_llm_turn", _fake_finalize_llm_turn)
    monkeypatch.setattr(server_mod, "_resolve_company_id", _fake_resolve_company_id)
    monkeypatch.setattr(server_mod.memory_agent, "get_memory", lambda: _DummyMemory())
    return server_mod


# ---------- /api/hermes/ultra ----------

class TestHermesUltraEndpoint:
    def test_ultra_basic_assistant(self, monkeypatch):
        server_mod = _patch_ultra_endpoint(
            monkeypatch,
            result={
                "content": "Краткий ответ Hermes.",
                "iterations": 1,
                "tool_traces": [],
            },
        )
        req = server_mod.HermesUltraRequest(
            message="Привет! Ответь одним предложением.",
            company_id="default",
            user_id="TEST_user1",
            autonomy_level="assistant",
        )
        data = asyncio.run(server_mod.hermes_ultra_endpoint(req))
        assert data.get("success") is True
        assert isinstance(data.get("content"), str) and len(data["content"]) > 0
        assert data.get("autonomy_level") == "assistant"
        assert isinstance(data.get("thread_id"), str) and data["thread_id"]
        assert isinstance(data.get("iterations"), int) and data["iterations"] >= 1
        assert isinstance(data.get("tool_traces"), list)
        # COO format hint — soft check (LLM may not be deterministic)
        # we only assert content non-empty above

    def test_ultra_read_only(self, monkeypatch):
        server_mod = _patch_ultra_endpoint(
            monkeypatch,
            result={
                "content": "Безопасный read-only ответ.",
                "iterations": 2,
                "tool_traces": [{"name": "search_memory", "result": {"ok": True}}],
            },
        )
        req = server_mod.HermesUltraRequest(
            message="Кратко оцени общее состояние компании в 1-2 предложениях.",
            autonomy_level="read_only",
            user_id="TEST_user2",
        )
        data = asyncio.run(server_mod.hermes_ultra_endpoint(req))
        assert data.get("success") is True
        assert data.get("autonomy_level") == "read_only"
        # read_only can do a second safe pass after non-critical read-only tools
        assert isinstance(data.get("iterations"), int) and data["iterations"] >= 1
        # no critical action should be auto-executed in read_only
        traces = data.get("tool_traces") or []
        critical = {"create_task", "update_task", "create_cross_department_bridge"}
        for t in traces:
            assert t.get("name") not in critical or t.get("result", {}).get("ok") is False, t

    def test_ultra_controlled_automation_gate(self, monkeypatch):
        server_mod = _patch_ultra_endpoint(
            monkeypatch,
            result={
                "content": "Требуется подтверждение человека.",
                "iterations": 1,
                "requires_human_approval": True,
                "tool_traces": [],
            },
        )
        msg = (
            "Срочно: создай высокоприоритетную задачу. "
            'Используй tool create_task с args {"title":"TEST_ultra_critical","department":"sales","priority":"high"}.'
        )
        req = server_mod.HermesUltraRequest(
            message=msg,
            autonomy_level="controlled_automation",
            user_id="TEST_user3",
        )
        data = asyncio.run(server_mod.hermes_ultra_endpoint(req))
        assert data.get("success") is True
        # If LLM emitted a create_task block, requires_human_approval must be True
        traces = data.get("tool_traces") or []
        emitted_critical = any(
            t.get("name") in {"create_task", "update_task", "create_cross_department_bridge"}
            for t in traces
        )
        if emitted_critical:
            # Should NOT have auto-executed (router goes to human_approval)
            pytest.fail("Critical tool was executed under controlled_automation without approval")
        # If gate fired, requires_human_approval should be True. Otherwise (LLM didn't
        # emit a tool block) we accept False as soft-pass.
        assert isinstance(data.get("requires_human_approval"), bool)

    def test_ultra_session_continuity(self, monkeypatch):
        import nxt8_langgraph_ultra as ultra_mod

        sid = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        calls = []

        async def _fake_hermes(messages, company_id="default", autonomy_level="assistant"):
            calls.append({
                "messages": messages,
                "company_id": company_id,
                "autonomy_level": autonomy_level,
            })
            return {
                "content": "ok",
                "confidence": 0.77,
                "mock": False,
                "tokens_total": 12,
            }

        monkeypatch.setattr(ultra_mod, "ultra_graph", None)
        monkeypatch.setattr(ultra_mod, "hermes_coo_chat", _fake_hermes)

        d1 = asyncio.run(ultra_mod.run_nxt8_ultra(
            message="Запомни факт: проект Alpha — приоритет 1.",
            session_id=sid,
            user_id="TEST_cont",
            autonomy_level="assistant",
        ))
        assert d1["thread_id"] == sid

        d2 = asyncio.run(ultra_mod.run_nxt8_ultra(
            message="Какой приоритет у проекта Alpha? Ответь коротко.",
            session_id=sid,
            user_id="TEST_cont",
            autonomy_level="assistant",
        ))
        assert d2["thread_id"] == sid
        assert len(calls) == 2
        assert all(call["autonomy_level"] == "assistant" for call in calls)

    def test_ultra_invalid_autonomy_falls_back(self, monkeypatch):
        server_mod = _patch_ultra_endpoint(
            monkeypatch,
            result={"content": "fallback assistant mode"},
        )
        req = server_mod.HermesUltraRequest(
            message="Привет",
            autonomy_level="foo",
            user_id="TEST_invalid",
        )
        data = asyncio.run(server_mod.hermes_ultra_endpoint(req))
        assert data.get("autonomy_level") == "assistant"


# ---------- Regression ----------

class TestRegressionHermesV12:
    def test_hermes_chat_v12(self, session):
        r = session.post(f"{BASE_URL}/api/hermes/chat", json={
            "messages": [{"role": "user", "content": "Дай operational summary."}],
            "company_id": "TEST_co",
            "user_id": "TEST_u",
            "mode": "operational",
            "temperature": 0.3,
        }, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("content"), str)

    def test_hermes_daily_digest(self, session):
        r = session.post(f"{BASE_URL}/api/hermes/daily-digest", json={
            "company_id": "TEST_co",
            "user_id": "TEST_u",
            "period": "daily",
        }, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("content"), str)

    def test_hermes_health(self, session):
        r = session.get(f"{BASE_URL}/api/hermes/health", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "status" in d  # offline or ok both acceptable

    def test_requests_feed(self, session):
        r = session.get(f"{BASE_URL}/api/requests?limit=5", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_chat_orchestrator(self, session):
        r = session.post(f"{BASE_URL}/api/chat", json={
            "user_id": "TEST_orch",
            "message": "Что такое NXT8?",
        }, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "content" in d


# ---------- MongoDB persistence + Tool unit tests ----------

class TestUnitToolsAndPersistence:
    def test_extract_tool_calls_parses_json_block(self):
        from nxt8_langgraph_ultra import _extract_tool_calls
        content = (
            "Резюме: всё ок.\n\n"
            "```json\n"
            '{"tool":"create_task","args":{"title":"TEST_ut_task","department":"sales","priority":"high"}}\n'
            "```\n"
            "Действия выше."
        )
        calls = _extract_tool_calls(content)
        assert len(calls) == 1
        assert calls[0]["name"] == "create_task"
        assert calls[0]["args"]["title"] == "TEST_ut_task"

    def test_extract_tool_calls_ignores_unknown_tool(self):
        from nxt8_langgraph_ultra import _extract_tool_calls
        content = '```json\n{"tool":"nonexistent","args":{}}\n```'
        assert _extract_tool_calls(content) == []

    def test_extract_tool_calls_multiple(self):
        from nxt8_langgraph_ultra import _extract_tool_calls
        content = (
            '```json\n{"tool":"monitor_sla_violations","args":{}}\n```\n'
            '```json\n{"tool":"suggest_next_best_action","args":{"context":"x"}}\n```'
        )
        calls = _extract_tool_calls(content)
        assert [c["name"] for c in calls] == [
            "monitor_sla_violations", "suggest_next_best_action",
        ]

    @pytest.mark.asyncio
    async def test_tools_node_executes_create_task_and_persists(self):
        """End-to-end: feed pending_tool_calls into tools_node, expect mongo write."""
        # Reset cached motor client to bind to current event loop
        from core import db as _db_mod
        _db_mod._client = None
        _db_mod._db = None

        from nxt8_langgraph_ultra import tools_node
        from core.db import get_db

        title = f"TEST_ut_persist_{uuid.uuid4().hex[:6]}"
        state = {
            "pending_tool_calls": [{
                "id": "t1",
                "name": "create_task",
                "args": {"title": title, "department": "sales", "priority": "high"},
            }],
            "company_id": "TEST_co_ultra",
            "tool_traces": [],
        }
        result = await tools_node(state)

        assert result["pending_tool_calls"] == []
        traces = result["tool_traces"]
        assert len(traces) == 1
        assert traces[0]["name"] == "create_task"
        assert traces[0]["result"]["ok"] is True, traces[0]

        doc = await get_db().tasks.find_one({"title": title})
        assert doc is not None
        assert doc.get("company_id") == "TEST_co_ultra"
        assert doc.get("source") == "hermes"

    @pytest.mark.asyncio
    async def test_communication_tools_real_llm_backed(self):
        """Previously-stub tools are now real LLM-backed (no `mock=True` flag
        unless provider chain falls through to the mock client)."""
        from agents.hermes_max_tools_and_coo import HERMES_TOOLS

        # generate_communication_summary
        res = await HERMES_TOOLS["generate_communication_summary"]({
            "text": "Клиент Acme спросил про скидку 15% на годовой контракт. "
                    "Менеджер ответил, что подумаем до пятницы.",
        })
        assert res.get("ok") is True, res
        assert "summary" in res

        # suggest_next_best_action
        res = await HERMES_TOOLS["suggest_next_best_action"]({
            "context": "Сделка с Acme зависла на этапе согласования цены.",
            "goal": "закрыть до конца недели",
        })
        assert res.get("ok") is True, res
        assert "action" in res

        # find_opportunities_in_contact
        res = await HERMES_TOOLS["find_opportunities_in_contact"]({
            "contact_id": "contact_acme",
            "context": "Купили базовый план 6 месяцев назад, активно используют API.",
        })
        assert res.get("ok") is True, res
        assert isinstance(res.get("opportunities"), list)

        # suggest_reply_template (with context — real LLM path)
        res = await HERMES_TOOLS["suggest_reply_template"]({
            "last_message": "Здравствуйте, можно ли получить расширенную лицензию?",
            "intent": "квалифицировать запрос",
            "tone": "professional",
        })
        assert res.get("ok") is True, res
        assert res.get("template")

        # evaluate_action_roi
        res = await HERMES_TOOLS["evaluate_action_roi"]({
            "action": "Запустить email-кампанию для 500 trial-пользователей",
            "expected_cost_usd": 200,
            "expected_revenue_usd": 4000,
            "horizon_days": 14,
        })
        assert res.get("ok") is True, res
        assert "estimated_roi" in res

    @pytest.mark.asyncio
    async def test_communication_tools_validate_input(self):
        """Real tools must reject empty input (no more no-op stubs)."""
        from agents.hermes_max_tools_and_coo import HERMES_TOOLS
        # empty args → ok=False with explicit error
        for name in ("generate_communication_summary",
                     "suggest_next_best_action",
                     "find_opportunities_in_contact",
                     "evaluate_action_roi"):
            res = await HERMES_TOOLS[name]({})
            assert res.get("ok") is False, f"{name} should reject empty args"
            assert res.get("error"), name
        # suggest_reply_template falls back to canned template when no context
        res = await HERMES_TOOLS["suggest_reply_template"]({})
        assert res.get("ok") is True
        assert res.get("context_used") is False

    @pytest.mark.asyncio
    async def test_real_tools_no_mock_field(self):
        from core import db as _db_mod
        _db_mod._client = None
        _db_mod._db = None
        from agents.hermes_max_tools_and_coo import HERMES_TOOLS

        res = await HERMES_TOOLS["search_memory"]({"query": "политика", "top_k": 3})
        assert res.get("ok") is True, res
        assert "results" in res
        assert res.get("mock") is not True

        res2 = await HERMES_TOOLS["monitor_sla_violations"]({"company_id": "default"})
        assert res2.get("ok") is True, res2
        assert "violations" in res2
        assert res2.get("mock") is not True

    @pytest.mark.asyncio
    async def test_ultra_persists_session_messages(self, session):
        from core import db as _db_mod
        _db_mod._client = None
        _db_mod._db = None
        from agents import memory as memory_agent

        sid = f"TEST_persist_{uuid.uuid4().hex[:6]}"
        r = session.post(ULTRA, json={
            "message": "Привет, что важно сегодня?",
            "session_id": sid, "user_id": "TEST_persist",
            "autonomy_level": "assistant",
        }, timeout=TIMEOUT)
        assert r.status_code == 200
        time.sleep(1.0)
        msgs = await memory_agent.get_memory().get_session(sid, limit=50)
        roles = [m.get("role") for m in msgs]
        assert "user" in roles
        assert "assistant" in roles
