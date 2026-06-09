"""Smoke test для проверки миграции Hermes на nxt8_graph (Sprint P2)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from agents.personas import SKILL_ROUTED_PERSONAS, run_persona


async def test_hermes_uses_graph():
    """Hermes должен быть в SKILL_ROUTED_PERSONAS."""
    assert "hermes" in SKILL_ROUTED_PERSONAS, "Hermes missing from SKILL_ROUTED_PERSONAS"
    print("✅ Hermes is in SKILL_ROUTED_PERSONAS")


async def test_hermes_responds_via_graph():
    """Проверяем, что Hermes отвечает и помечается как nxt8_graph."""
    res = await run_persona(
        persona_id="hermes",
        message="Привет. Как дела? (кратко)",
        company_id="test_p2",
        plan_id="enterprise",
        session_id="smoke_hermes_1",
    )
    assert res.get("success") is True, f"Hermes failed: {res.get('error')}"

    provider = res.get("provider")
    assert provider == "nxt8_graph", f"Expected provider='nxt8_graph', got '{provider}'"

    print(f"✅ Hermes responded via nxt8_graph (provider={provider})")


async def test_analyst_still_works():
    """Регрессия: Analyst всё еще работает."""
    res = await run_persona(
        persona_id="analyst",
        message="Ping",
        company_id="test_p2",
        plan_id="headquarters",
        session_id="smoke_analyst_1",
    )
    assert res.get("success") is True
    assert res.get("provider") == "nxt8_graph"
    print("✅ Analyst still works (nxt8_graph)")


async def main():
    print("--- Sprint P2 Integrity Check ---")
    try:
        await test_hermes_uses_graph()
        await test_hermes_responds_via_graph()
        await test_analyst_still_works()
        print("--- ALL CHECKS PASSED ---")
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"❌ EXCEPTION: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())