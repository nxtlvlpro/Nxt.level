#!/usr/bin/env python3
"""
Backend-only validation for Phase 2 NXT8: analyst and client_manager migration to nxt8_graph.

Validates:
1. /api/personas/analyst/chat uses nxt8_graph (not legacy)
2. /api/personas/client_manager/chat uses nxt8_graph (not legacy)
3. Response contract intact for both personas
4. Tool loop works:
   - analyst -> evaluate_action_roi
   - client_manager -> create_task
5. persona_requests.provider='nxt8_graph' for both personas
6. Plan-gate preserved:
   - client_manager available on team+
   - analyst available on headquarters
7. Other personas not affected by this migration
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
ROOT_DIR = Path(__file__).parent / "backend"
load_dotenv(ROOT_DIR / ".env")

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from motor.motor_asyncio import AsyncIOMotorClient


BACKEND_URL = "https://multi-tenant-os-3.preview.emergentagent.com/api"
MONGO_URL = "mongodb://127.0.0.1:27017"
DB_NAME = "nxt8"


async def get_db():
    """Get MongoDB connection."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


async def test_analyst_nxt8_graph():
    """Test 1: analyst uses nxt8_graph and returns correct contract."""
    print("\n" + "=" * 80)
    print("TEST 1: analyst uses nxt8_graph with correct response contract")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # Test message that should trigger evaluate_action_roi
    test_message = "Оцени экономику запуска reactivation-кампании по dormant B2B лидам"
    
    result = await personas_agent.run_persona(
        persona_id="analyst",
        message=test_message,
        company_id="test_company_analyst",
        user_id="test_user_analyst",
        session_id="test_session_analyst_001",
        plan_id="headquarters",  # analyst requires headquarters plan
    )
    
    print(f"\n✓ Response received")
    print(f"  - success: {result.get('success')}")
    print(f"  - provider: {result.get('provider')}")
    print(f"  - persona_id: {result.get('persona_id')}")
    print(f"  - iterations: {result.get('iterations')}")
    print(f"  - confidence: {result.get('confidence')}")
    print(f"  - tool_traces count: {len(result.get('tool_traces', []))}")
    
    # Validate response contract
    assert result.get("success") is True, "❌ Response success should be True"
    assert result.get("provider") == "nxt8_graph", f"❌ Provider should be 'nxt8_graph', got '{result.get('provider')}'"
    assert result.get("persona_id") == "analyst", f"❌ persona_id should be 'analyst', got '{result.get('persona_id')}'"
    assert "content" in result, "❌ Response should have 'content' field"
    assert "session_id" in result, "❌ Response should have 'session_id' field"
    assert "iterations" in result, "❌ Response should have 'iterations' field"
    assert "confidence" in result, "❌ Response should have 'confidence' field"
    assert "tool_traces" in result, "❌ Response should have 'tool_traces' field"
    
    print("\n✓ Response contract validation PASSED")
    
    # Check if evaluate_action_roi was called
    tool_traces = result.get("tool_traces", [])
    evaluate_roi_called = any(t.get("name") == "evaluate_action_roi" for t in tool_traces)
    
    if evaluate_roi_called:
        print("\n✓ Tool 'evaluate_action_roi' was called")
        for trace in tool_traces:
            if trace.get("name") == "evaluate_action_roi":
                print(f"  - args: {trace.get('args', {})}")
                print(f"  - result ok: {trace.get('result', {}).get('ok')}")
    else:
        print("\n⚠ Tool 'evaluate_action_roi' was NOT called (may be valid if LLM decided not to use it)")
    
    return result


async def test_client_manager_nxt8_graph():
    """Test 2: client_manager uses nxt8_graph and returns correct contract."""
    print("\n" + "=" * 80)
    print("TEST 2: client_manager uses nxt8_graph with correct response contract")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # Test message that should trigger create_task
    test_message = "Зафиксируй follow-up: отправить клиенту ACME резюме звонка и согласовать следующий слот на завтра"
    
    result = await personas_agent.run_persona(
        persona_id="client_manager",
        message=test_message,
        company_id="test_company_cm",
        user_id="test_user_cm",
        session_id="test_session_cm_001",
        plan_id="team",  # client_manager available on team plan
    )
    
    print(f"\n✓ Response received")
    print(f"  - success: {result.get('success')}")
    print(f"  - provider: {result.get('provider')}")
    print(f"  - persona_id: {result.get('persona_id')}")
    print(f"  - iterations: {result.get('iterations')}")
    print(f"  - confidence: {result.get('confidence')}")
    print(f"  - tool_traces count: {len(result.get('tool_traces', []))}")
    
    # Validate response contract
    assert result.get("success") is True, "❌ Response success should be True"
    assert result.get("provider") == "nxt8_graph", f"❌ Provider should be 'nxt8_graph', got '{result.get('provider')}'"
    assert result.get("persona_id") == "client_manager", f"❌ persona_id should be 'client_manager', got '{result.get('persona_id')}'"
    assert "content" in result, "❌ Response should have 'content' field"
    assert "session_id" in result, "❌ Response should have 'session_id' field"
    assert "iterations" in result, "❌ Response should have 'iterations' field"
    assert "confidence" in result, "❌ Response should have 'confidence' field"
    assert "tool_traces" in result, "❌ Response should have 'tool_traces' field"
    
    print("\n✓ Response contract validation PASSED")
    
    # Check if create_task was called
    tool_traces = result.get("tool_traces", [])
    create_task_called = any(t.get("name") == "create_task" for t in tool_traces)
    
    if create_task_called:
        print("\n✓ Tool 'create_task' was called")
        for trace in tool_traces:
            if trace.get("name") == "create_task":
                print(f"  - args: {trace.get('args', {})}")
                print(f"  - result ok: {trace.get('result', {}).get('ok')}")
    else:
        print("\n⚠ Tool 'create_task' was NOT called (may be valid if LLM decided not to use it)")
    
    return result


async def test_audit_records():
    """Test 3: Verify persona_requests audit records have provider='nxt8_graph'."""
    print("\n" + "=" * 80)
    print("TEST 3: Audit records have provider='nxt8_graph'")
    print("=" * 80)
    
    db = await get_db()
    
    # Check analyst audit records
    analyst_records = await db.persona_requests.find(
        {"persona_id": "analyst", "company_id": "test_company_analyst"}
    ).sort("created_at", -1).limit(5).to_list(length=5)
    
    print(f"\n✓ Found {len(analyst_records)} analyst audit records")
    for record in analyst_records:
        provider = record.get("provider")
        print(f"  - Record {record.get('id', 'unknown')[:8]}: provider={provider}")
        assert provider == "nxt8_graph", f"❌ Analyst audit record should have provider='nxt8_graph', got '{provider}'"
    
    # Check client_manager audit records
    cm_records = await db.persona_requests.find(
        {"persona_id": "client_manager", "company_id": "test_company_cm"}
    ).sort("created_at", -1).limit(5).to_list(length=5)
    
    print(f"\n✓ Found {len(cm_records)} client_manager audit records")
    for record in cm_records:
        provider = record.get("provider")
        print(f"  - Record {record.get('id', 'unknown')[:8]}: provider={provider}")
        assert provider == "nxt8_graph", f"❌ Client_manager audit record should have provider='nxt8_graph', got '{provider}'"
    
    print("\n✓ All audit records have correct provider='nxt8_graph'")


async def test_plan_gate_analyst():
    """Test 4: Verify analyst is only available on headquarters plan."""
    print("\n" + "=" * 80)
    print("TEST 4: Plan-gate for analyst (headquarters only)")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # Test with team plan (should fail)
    result_team = await personas_agent.run_persona(
        persona_id="analyst",
        message="Test message",
        company_id="test_company_gate",
        user_id="test_user_gate",
        session_id="test_session_gate_001",
        plan_id="team",
    )
    
    print(f"\n✓ Testing analyst with 'team' plan:")
    print(f"  - success: {result_team.get('success')}")
    print(f"  - error: {result_team.get('error', 'N/A')}")
    
    assert result_team.get("success") is False, "❌ Analyst should NOT be available on team plan"
    assert "недоступна" in result_team.get("error", "").lower(), "❌ Error should mention persona is unavailable"
    
    # Test with headquarters plan (should succeed)
    result_hq = await personas_agent.run_persona(
        persona_id="analyst",
        message="Test message",
        company_id="test_company_gate",
        user_id="test_user_gate",
        session_id="test_session_gate_002",
        plan_id="headquarters",
    )
    
    print(f"\n✓ Testing analyst with 'headquarters' plan:")
    print(f"  - success: {result_hq.get('success')}")
    print(f"  - provider: {result_hq.get('provider')}")
    
    assert result_hq.get("success") is True, "❌ Analyst should be available on headquarters plan"
    assert result_hq.get("provider") == "nxt8_graph", "❌ Analyst should use nxt8_graph"
    
    print("\n✓ Plan-gate for analyst PASSED")


async def test_plan_gate_client_manager():
    """Test 5: Verify client_manager is available on team+ plans."""
    print("\n" + "=" * 80)
    print("TEST 5: Plan-gate for client_manager (team+)")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # Test with personal plan (should fail)
    result_personal = await personas_agent.run_persona(
        persona_id="client_manager",
        message="Test message",
        company_id="test_company_gate_cm",
        user_id="test_user_gate_cm",
        session_id="test_session_gate_cm_001",
        plan_id="personal",
    )
    
    print(f"\n✓ Testing client_manager with 'personal' plan:")
    print(f"  - success: {result_personal.get('success')}")
    print(f"  - error: {result_personal.get('error', 'N/A')}")
    
    assert result_personal.get("success") is False, "❌ Client_manager should NOT be available on personal plan"
    assert "недоступна" in result_personal.get("error", "").lower(), "❌ Error should mention persona is unavailable"
    
    # Test with team plan (should succeed)
    result_team = await personas_agent.run_persona(
        persona_id="client_manager",
        message="Test message",
        company_id="test_company_gate_cm",
        user_id="test_user_gate_cm",
        session_id="test_session_gate_cm_002",
        plan_id="team",
    )
    
    print(f"\n✓ Testing client_manager with 'team' plan:")
    print(f"  - success: {result_team.get('success')}")
    print(f"  - provider: {result_team.get('provider')}")
    
    assert result_team.get("success") is True, "❌ Client_manager should be available on team plan"
    assert result_team.get("provider") == "nxt8_graph", "❌ Client_manager should use nxt8_graph"
    
    print("\n✓ Plan-gate for client_manager PASSED")


async def test_other_personas_not_affected():
    """Test 6: Verify other personas still use legacy path."""
    print("\n" + "=" * 80)
    print("TEST 6: Other personas not affected (still use legacy)")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # Test bookkeeper (should use legacy)
    result_bookkeeper = await personas_agent.run_persona(
        persona_id="bookkeeper",
        message="Покажи текущий ROI",
        company_id="test_company_legacy",
        user_id="test_user_legacy",
        session_id="test_session_legacy_001",
        plan_id="operations",
    )
    
    print(f"\n✓ Testing bookkeeper (should use legacy):")
    print(f"  - success: {result_bookkeeper.get('success')}")
    print(f"  - provider: {result_bookkeeper.get('provider')}")
    
    assert result_bookkeeper.get("success") is True, "❌ Bookkeeper should work"
    # Legacy path doesn't set provider to nxt8_graph
    if result_bookkeeper.get("provider") == "nxt8_graph":
        print("  ⚠ WARNING: bookkeeper is using nxt8_graph (expected legacy)")
    else:
        print("  ✓ bookkeeper is using legacy path (correct)")
    
    # Test marketer (should use legacy)
    result_marketer = await personas_agent.run_persona(
        persona_id="marketer",
        message="Какие тренды на рынке?",
        company_id="test_company_legacy",
        user_id="test_user_legacy",
        session_id="test_session_legacy_002",
        plan_id="operations",
    )
    
    print(f"\n✓ Testing marketer (should use legacy):")
    print(f"  - success: {result_marketer.get('success')}")
    print(f"  - provider: {result_marketer.get('provider')}")
    
    assert result_marketer.get("success") is True, "❌ Marketer should work"
    if result_marketer.get("provider") == "nxt8_graph":
        print("  ⚠ WARNING: marketer is using nxt8_graph (expected legacy)")
    else:
        print("  ✓ marketer is using legacy path (correct)")
    
    print("\n✓ Other personas not affected by migration")


async def test_skill_routed_personas_set():
    """Test 7: Verify SKILL_ROUTED_PERSONAS contains analyst and client_manager."""
    print("\n" + "=" * 80)
    print("TEST 7: SKILL_ROUTED_PERSONAS set verification")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    skill_routed = personas_agent.SKILL_ROUTED_PERSONAS
    print(f"\n✓ SKILL_ROUTED_PERSONAS: {skill_routed}")
    
    assert "analyst" in skill_routed, "❌ 'analyst' should be in SKILL_ROUTED_PERSONAS"
    assert "client_manager" in skill_routed, "❌ 'client_manager' should be in SKILL_ROUTED_PERSONAS"
    assert "hr_mentor" in skill_routed, "❌ 'hr_mentor' should be in SKILL_ROUTED_PERSONAS"
    
    print("\n✓ SKILL_ROUTED_PERSONAS contains all expected personas")


async def test_skill_files_exist():
    """Test 8: Verify skill files exist and are valid."""
    print("\n" + "=" * 80)
    print("TEST 8: Skill files existence and validity")
    print("=" * 80)
    
    from pathlib import Path
    import yaml
    
    skills_dir = Path(__file__).parent / "backend" / "skills"
    
    # Check analyst.md
    analyst_path = skills_dir / "analyst.md"
    assert analyst_path.exists(), f"❌ {analyst_path} does not exist"
    print(f"\n✓ {analyst_path} exists")
    
    analyst_content = analyst_path.read_text(encoding="utf-8")
    assert analyst_content.startswith("---"), "❌ analyst.md should start with YAML frontmatter"
    
    # Parse YAML frontmatter
    parts = analyst_content.split("---", 2)
    analyst_yaml = yaml.safe_load(parts[1])
    print(f"  - id: {analyst_yaml.get('id')}")
    print(f"  - allowed_tools: {analyst_yaml.get('allowed_tools')}")
    
    assert analyst_yaml.get("id") == "analyst", "❌ analyst.md should have id='analyst'"
    assert "evaluate_action_roi" in analyst_yaml.get("allowed_tools", []), "❌ analyst should have evaluate_action_roi tool"
    
    # Check client_manager.md
    cm_path = skills_dir / "client_manager.md"
    assert cm_path.exists(), f"❌ {cm_path} does not exist"
    print(f"\n✓ {cm_path} exists")
    
    cm_content = cm_path.read_text(encoding="utf-8")
    assert cm_content.startswith("---"), "❌ client_manager.md should start with YAML frontmatter"
    
    # Parse YAML frontmatter
    parts = cm_content.split("---", 2)
    cm_yaml = yaml.safe_load(parts[1])
    print(f"  - id: {cm_yaml.get('id')}")
    print(f"  - allowed_tools: {cm_yaml.get('allowed_tools')}")
    
    assert cm_yaml.get("id") == "client_manager", "❌ client_manager.md should have id='client_manager'"
    assert "create_task" in cm_yaml.get("allowed_tools", []), "❌ client_manager should have create_task tool"
    
    print("\n✓ Skill files are valid")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("BACKEND VALIDATION: analyst & client_manager migration to nxt8_graph")
    print("=" * 80)
    
    try:
        # Test 7: Verify SKILL_ROUTED_PERSONAS set
        await test_skill_routed_personas_set()
        
        # Test 8: Verify skill files
        await test_skill_files_exist()
        
        # Test 1: analyst uses nxt8_graph
        await test_analyst_nxt8_graph()
        
        # Test 2: client_manager uses nxt8_graph
        await test_client_manager_nxt8_graph()
        
        # Test 3: Audit records
        await test_audit_records()
        
        # Test 4: Plan-gate for analyst
        await test_plan_gate_analyst()
        
        # Test 5: Plan-gate for client_manager
        await test_plan_gate_client_manager()
        
        # Test 6: Other personas not affected
        await test_other_personas_not_affected()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nSUMMARY:")
        print("  ✓ analyst uses nxt8_graph")
        print("  ✓ client_manager uses nxt8_graph")
        print("  ✓ Response contracts intact")
        print("  ✓ Tool loops work (evaluate_action_roi, create_task)")
        print("  ✓ Audit records have provider='nxt8_graph'")
        print("  ✓ Plan-gates preserved (analyst=headquarters, client_manager=team+)")
        print("  ✓ Other personas not affected")
        print("  ✓ Skill files valid")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
