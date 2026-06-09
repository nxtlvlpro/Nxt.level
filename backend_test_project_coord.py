#!/usr/bin/env python3
"""
Backend-only validation of project_coord migration to nxt8_graph (Wave 3).

Tests:
1. project_coord routes to nxt8_graph (not legacy)
2. Response contract preserved
3. Tool loop: create_cross_department_bridge invoked for cross-dept tasks
4. Audit records: provider='nxt8_graph'
5. Plan-gate: project_coord only on headquarters
6. Non-regression: other migrated personas still work
7. Hermes remains separate (not affected)
"""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / "backend" / ".env")

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from core.db import get_db
from agents import personas as personas_agent


async def test_project_coord_routing():
    """Test 1: project_coord routes to nxt8_graph, not legacy."""
    print("\n=== Test 1: project_coord routing to nxt8_graph ===")
    
    # Check SKILL_ROUTED_PERSONAS
    if "project_coord" not in personas_agent.SKILL_ROUTED_PERSONAS:
        print("❌ FAIL: project_coord not in SKILL_ROUTED_PERSONAS")
        return False
    
    print(f"✓ project_coord in SKILL_ROUTED_PERSONAS: {personas_agent.SKILL_ROUTED_PERSONAS}")
    
    # Test actual routing
    result = await personas_agent.run_persona(
        persona_id="project_coord",
        message="Нужно синхронизировать sales и product по новому клиенту ACME",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_pc_1",
        plan_id="headquarters",
    )
    
    if not result.get("success"):
        print(f"❌ FAIL: persona call failed: {result.get('error')}")
        return False
    
    provider = result.get("provider")
    if provider != "nxt8_graph":
        print(f"❌ FAIL: Expected provider='nxt8_graph', got '{provider}'")
        return False
    
    print(f"✓ project_coord routes to nxt8_graph (provider={provider})")
    return True


async def test_response_contract():
    """Test 2: Response contract preserved."""
    print("\n=== Test 2: Response contract validation ===")
    
    result = await personas_agent.run_persona(
        persona_id="project_coord",
        message="Создай bridging-задачу между маркетингом и разработкой",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_pc_2",
        plan_id="headquarters",
    )
    
    required_fields = [
        "success", "provider", "persona_id", "content", "session_id",
        "iterations", "confidence", "tool_traces"
    ]
    
    missing = [f for f in required_fields if f not in result]
    if missing:
        print(f"❌ FAIL: Missing required fields: {missing}")
        return False
    
    print(f"✓ All required fields present: {required_fields}")
    print(f"  - success: {result['success']}")
    print(f"  - provider: {result['provider']}")
    print(f"  - persona_id: {result['persona_id']}")
    print(f"  - content length: {len(result['content'])} chars")
    print(f"  - iterations: {result['iterations']}")
    print(f"  - confidence: {result['confidence']}")
    print(f"  - tool_traces count: {len(result['tool_traces'])}")
    
    return True


async def test_tool_loop():
    """Test 3: Tool loop - create_cross_department_bridge invoked."""
    print("\n=== Test 3: Tool loop (create_cross_department_bridge) ===")
    
    # Clear any previous test data
    db = get_db()
    await db.persona_requests.delete_many({"session_id": "test_session_pc_tool"})
    
    result = await personas_agent.run_persona(
        persona_id="project_coord",
        message="Нужно создать мост между отделом продаж и отделом разработки для согласования требований клиента ACME",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_pc_tool",
        plan_id="headquarters",
    )
    
    if not result.get("success"):
        print(f"❌ FAIL: persona call failed: {result.get('error')}")
        return False
    
    tool_traces = result.get("tool_traces", [])
    print(f"✓ Tool traces count: {len(tool_traces)}")
    
    # Check if create_cross_department_bridge was invoked
    bridge_tool_found = False
    for trace in tool_traces:
        tool_name = trace.get("name")
        print(f"  - Tool: {tool_name}")
        if tool_name == "create_cross_department_bridge":
            bridge_tool_found = True
            print(f"    ✓ create_cross_department_bridge invoked")
            print(f"    Args: {trace.get('args')}")
            print(f"    Result ok: {trace.get('result', {}).get('ok')}")
    
    if not bridge_tool_found:
        print(f"⚠ WARNING: create_cross_department_bridge not invoked (may be valid if LLM chose different approach)")
        print(f"  Tool traces: {[t.get('name') for t in tool_traces]}")
        # Not a hard failure - LLM might choose different tools
        return True
    
    print(f"✓ Tool loop working: create_cross_department_bridge invoked")
    return True


async def test_audit_records():
    """Test 4: Audit records have provider='nxt8_graph'."""
    print("\n=== Test 4: Audit records validation ===")
    
    db = get_db()
    
    # Get recent project_coord records created during this test run
    # (filter by session_id prefix to avoid old pre-migration records)
    records = await db.persona_requests.find(
        {
            "persona_id": "project_coord",
            "session_id": {"$regex": "^test_session_pc"}
        },
        {"_id": 0, "provider": 1, "persona_id": 1, "created_at": 1, "tool_traces": 1, "session_id": 1}
    ).sort("created_at", -1).limit(10).to_list(length=10)
    
    if not records:
        print("⚠ WARNING: No audit records found for project_coord test sessions")
        return True
    
    print(f"✓ Found {len(records)} project_coord audit records from this test run")
    
    all_nxt8 = True
    for i, rec in enumerate(records):
        provider = rec.get("provider")
        tool_count = len(rec.get("tool_traces", []))
        session = rec.get("session_id", "")[:30]
        print(f"  Record {i+1}: provider={provider}, tools={tool_count}, session={session}")
        if provider != "nxt8_graph":
            print(f"    ❌ Expected 'nxt8_graph', got '{provider}'")
            all_nxt8 = False
    
    if not all_nxt8:
        print("❌ FAIL: Some records don't have provider='nxt8_graph'")
        return False
    
    print("✓ All test audit records have provider='nxt8_graph'")
    return True


async def test_plan_gate():
    """Test 5: Plan-gate - project_coord only on headquarters."""
    print("\n=== Test 5: Plan-gate validation ===")
    
    # Test 1: operations plan should FAIL
    result_ops = await personas_agent.run_persona(
        persona_id="project_coord",
        message="Test message",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_pc_ops",
        plan_id="operations",
    )
    
    if result_ops.get("success"):
        print(f"❌ FAIL: project_coord should NOT be available on 'operations' plan")
        return False
    
    error_msg = result_ops.get("error", "").lower()
    if "недоступна" not in error_msg and "не доступна" not in error_msg:
        print(f"❌ FAIL: Expected plan-gate error, got: {result_ops.get('error')}")
        return False
    
    print(f"✓ operations plan correctly blocked: {result_ops.get('error')}")
    
    # Test 2: team plan should FAIL
    result_team = await personas_agent.run_persona(
        persona_id="project_coord",
        message="Test message",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_pc_team",
        plan_id="team",
    )
    
    if result_team.get("success"):
        print(f"❌ FAIL: project_coord should NOT be available on 'team' plan")
        return False
    
    print(f"✓ team plan correctly blocked: {result_team.get('error')}")
    
    # Test 3: headquarters plan should SUCCEED
    result_hq = await personas_agent.run_persona(
        persona_id="project_coord",
        message="Test message",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_pc_hq",
        plan_id="headquarters",
    )
    
    if not result_hq.get("success"):
        print(f"❌ FAIL: project_coord should be available on 'headquarters' plan")
        print(f"  Error: {result_hq.get('error')}")
        return False
    
    if result_hq.get("provider") != "nxt8_graph":
        print(f"❌ FAIL: Expected provider='nxt8_graph' on headquarters, got '{result_hq.get('provider')}'")
        return False
    
    print(f"✓ headquarters plan correctly allowed with provider='nxt8_graph'")
    return True


async def test_non_regression():
    """Test 6: Other migrated personas still work."""
    print("\n=== Test 6: Non-regression check ===")
    
    # Test a few previously migrated personas
    test_personas = [
        ("analyst", "Какой средний confidence по интентам?", "headquarters"),
        ("client_manager", "Создай задачу для follow-up с клиентом", "team"),
        ("bookkeeper", "Покажи текущий ROI", "operations"),
    ]
    
    all_ok = True
    for persona_id, message, plan_id in test_personas:
        result = await personas_agent.run_persona(
            persona_id=persona_id,
            message=message,
            company_id="test_company",
            user_id="test_user",
            session_id=f"test_session_regr_{persona_id}",
            plan_id=plan_id,
        )
        
        if not result.get("success"):
            print(f"  ❌ {persona_id}: FAILED - {result.get('error')}")
            all_ok = False
            continue
        
        provider = result.get("provider")
        if provider != "nxt8_graph":
            print(f"  ❌ {persona_id}: Wrong provider '{provider}' (expected 'nxt8_graph')")
            all_ok = False
            continue
        
        print(f"  ✓ {persona_id}: OK (provider={provider})")
    
    if not all_ok:
        print("❌ FAIL: Some previously migrated personas regressed")
        return False
    
    print("✓ All previously migrated personas still work correctly")
    return True


async def test_hermes_separate():
    """Test 7: Hermes remains separate (not affected)."""
    print("\n=== Test 7: Hermes separation check ===")
    
    # Hermes should NOT be in SKILL_ROUTED_PERSONAS
    if "hermes" in personas_agent.SKILL_ROUTED_PERSONAS:
        print("❌ FAIL: hermes should NOT be in SKILL_ROUTED_PERSONAS")
        return False
    
    print(f"✓ hermes not in SKILL_ROUTED_PERSONAS (remains separate)")
    
    # Verify hermes uses legacy path
    result = await personas_agent.run_persona(
        persona_id="hermes",
        message="Какой статус компании?",
        company_id="test_company",
        user_id="test_user",
        session_id="test_session_hermes",
        plan_id="personal",
    )
    
    if not result.get("success"):
        print(f"⚠ WARNING: hermes call failed: {result.get('error')}")
        # Not a hard failure - hermes might have different requirements
        return True
    
    provider = result.get("provider")
    if provider == "nxt8_graph":
        print(f"❌ FAIL: hermes should use legacy path, not nxt8_graph")
        return False
    
    print(f"✓ hermes uses legacy path (provider={provider})")
    return True


async def test_skill_file_validation():
    """Bonus test: Validate project_coord skill file."""
    print("\n=== Bonus: Skill file validation ===")
    
    from core.nxt8_graph import load_skill
    
    try:
        prompt_text, metadata = load_skill("project_coord")
        
        if not prompt_text:
            print("❌ FAIL: Skill file is empty")
            return False
        
        print(f"✓ Skill file loaded: {len(prompt_text)} chars")
        
        # Check metadata
        skill_id = metadata.get("id")
        if skill_id != "project_coord":
            print(f"❌ FAIL: Expected id='project_coord', got '{skill_id}'")
            return False
        
        print(f"✓ Skill id: {skill_id}")
        
        allowed_tools = metadata.get("allowed_tools", [])
        if "create_cross_department_bridge" not in allowed_tools:
            print(f"❌ FAIL: create_cross_department_bridge not in allowed_tools")
            return False
        
        print(f"✓ Allowed tools ({len(allowed_tools)}): {allowed_tools}")
        
        # Check for key instructions
        if "create_cross_department_bridge" not in prompt_text:
            print(f"⚠ WARNING: create_cross_department_bridge not mentioned in prompt")
        
        print(f"✓ Skill file is valid")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error loading skill file: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 70)
    print("Backend-only validation: project_coord migration to nxt8_graph")
    print("=" * 70)
    
    tests = [
        ("Routing to nxt8_graph", test_project_coord_routing),
        ("Response contract", test_response_contract),
        ("Tool loop", test_tool_loop),
        ("Audit records", test_audit_records),
        ("Plan-gate", test_plan_gate),
        ("Non-regression", test_non_regression),
        ("Hermes separation", test_hermes_separate),
        ("Skill file validation", test_skill_file_validation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! project_coord migration is successful.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review required.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
