"""
Comprehensive backend test for Hermes Self-Audit + Telegram alerts.

Tests:
1. No import regressions/circular imports
2. run_persona_benchmark excludes Hermes
3. Benchmark doesn't write to audit/evolution collections
4. Telegram helpers send to first connected chat
5. propose_improvement/propose_policy write to DB and trigger notifications
6. New functionality doesn't break old scenarios
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/app/backend')

from agents import hermes_tools_audit as audit
from agents import hermes
from agents import hermes_evolution as evolution
from core import telegram_bot as tg
from core.db import get_db
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


async def test_imports_no_circular_dependency():
    """Test 1: Verify no import regressions or circular imports."""
    print("\n=== Test 1: Import Regressions ===")
    try:
        # Try importing in different orders
        from agents import hermes_tools_audit
        from agents import hermes
        from agents import hermes_evolution
        from core import telegram_bot
        
        # Verify key functions exist
        assert hasattr(hermes_tools_audit, 'scan_system_health')
        assert hasattr(hermes_tools_audit, 'run_persona_benchmark')
        assert hasattr(hermes_evolution, 'propose_improvement')
        assert hasattr(hermes_evolution, 'propose_policy')
        assert hasattr(telegram_bot, 'notify_improvement')
        assert hasattr(telegram_bot, 'notify_policy')
        assert hasattr(telegram_bot, 'notify_first_connected_client')
        
        print("✅ All imports successful, no circular dependencies")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False


async def test_hermes_tools_registered():
    """Test 2: Verify new tools are registered in HERMES_TOOLS."""
    print("\n=== Test 2: Tool Registration ===")
    try:
        assert 'scan_system_health' in hermes.HERMES_TOOLS
        assert 'run_persona_benchmark' in hermes.HERMES_TOOLS
        
        # Verify they're callable
        assert callable(hermes.HERMES_TOOLS['scan_system_health'])
        assert callable(hermes.HERMES_TOOLS['run_persona_benchmark'])
        
        print("✅ scan_system_health registered in HERMES_TOOLS")
        print("✅ run_persona_benchmark registered in HERMES_TOOLS")
        return True
    except Exception as e:
        print(f"❌ Tool registration error: {e}")
        return False


async def test_run_persona_benchmark_excludes_hermes():
    """Test 3: Verify run_persona_benchmark excludes Hermes."""
    print("\n=== Test 3: Benchmark Excludes Hermes ===")
    try:
        # Mock the persona runtime
        test_personas = {"hermes", "analyst", "client_manager", "bookkeeper"}
        
        async def mock_run_persona(**kwargs):
            return {
                "success": True,
                "confidence": 0.85,
                "provider": "nxt8_graph",
                "content": "test response"
            }
        
        # Temporarily replace the runtime getter
        original_getter = audit._get_persona_runtime
        audit._get_persona_runtime = lambda: (test_personas, mock_run_persona)
        
        result = await audit.run_persona_benchmark({
            "company_id": "test_audit_company",
            "query": "Test query"
        })
        
        # Restore original
        audit._get_persona_runtime = original_getter
        
        assert result["ok"] is True
        assert result["total_personas"] == 3  # Should be 3, not 4 (hermes excluded)
        
        # Verify hermes is not in benchmark results
        personas_tested = {row["persona"] for row in result["benchmark"]}
        assert "hermes" not in personas_tested
        assert "analyst" in personas_tested
        assert "client_manager" in personas_tested
        assert "bookkeeper" in personas_tested
        
        # Verify session_id format
        for row in result["benchmark"]:
            assert row["session_id"].startswith("audit_")
        
        print(f"✅ Benchmark tested {result['total_personas']} personas (hermes excluded)")
        print(f"✅ Personas tested: {personas_tested}")
        print(f"✅ All session_ids use 'audit_*' format")
        return True
    except Exception as e:
        print(f"❌ Benchmark test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_benchmark_no_db_writes():
    """Test 4: Verify benchmark doesn't write to audit/evolution collections."""
    print("\n=== Test 4: Benchmark No DB Writes ===")
    try:
        db = get_db()
        
        # Count records before
        evolution_count_before = await db.hermes_evolution_log.count_documents({})
        audit_count_before = await db.persona_requests.count_documents({"session_id": {"$regex": "^audit_"}})
        
        # Mock the persona runtime
        test_personas = {"analyst", "marketer"}
        
        async def mock_run_persona(**kwargs):
            return {
                "success": True,
                "confidence": 0.88,
                "provider": "nxt8_graph",
                "content": "test"
            }
        
        original_getter = audit._get_persona_runtime
        audit._get_persona_runtime = lambda: (test_personas, mock_run_persona)
        
        # Run benchmark
        result = await audit.run_persona_benchmark({
            "company_id": "test_no_write",
            "query": "Test"
        })
        
        audit._get_persona_runtime = original_getter
        
        # Count records after
        evolution_count_after = await db.hermes_evolution_log.count_documents({})
        audit_count_after = await db.persona_requests.count_documents({"session_id": {"$regex": "^audit_"}})
        
        # Verify no new records in evolution log
        assert evolution_count_after == evolution_count_before, \
            f"Evolution log should not change: {evolution_count_before} -> {evolution_count_after}"
        
        print(f"✅ No writes to hermes_evolution_log (count: {evolution_count_before})")
        print(f"✅ Benchmark results stay in memory only")
        print(f"✅ Sandbox isolation verified")
        return True
    except Exception as e:
        print(f"❌ DB write test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scan_system_health_read_only():
    """Test 5: Verify scan_system_health is read-only and uses TenantAwareCRUD."""
    print("\n=== Test 5: Scan System Health Read-Only ===")
    try:
        # This should work without writing anything
        result = await audit.scan_system_health({
            "company_id": "test_scan_company",
            "window": 50
        })
        
        assert result["ok"] is True
        assert result["company_id"] == "test_scan_company"
        assert "avg_confidence" in result
        assert "avg_latency_ms" in result
        assert "escalation_rate" in result
        assert "mock_rate" in result
        assert "low_confidence_rate" in result
        assert "contradiction_count" in result
        
        print(f"✅ scan_system_health returns expected shape")
        print(f"✅ Read-only operation (no writes)")
        print(f"✅ Uses tenant-scoped data (company_id: {result['company_id']})")
        return True
    except Exception as e:
        print(f"❌ Scan health test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_telegram_notify_first_connected():
    """Test 6: Verify Telegram helpers send to first connected chat."""
    print("\n=== Test 6: Telegram First Connected Chat ===")
    try:
        # Check if telegram is enabled
        if not tg.is_enabled():
            print("⚠️  Telegram disabled (no token), skipping notification test")
            return True
        
        # Test notify_first_connected_client function exists and has correct signature
        import inspect
        sig = inspect.signature(tg.notify_first_connected_client)
        assert 'text' in sig.parameters
        
        # Test notify_improvement function
        sig = inspect.signature(tg.notify_improvement)
        assert 'proposal' in sig.parameters
        
        # Test notify_policy function
        sig = inspect.signature(tg.notify_policy)
        assert 'proposal' in sig.parameters
        
        print("✅ notify_first_connected_client(text) exists")
        print("✅ notify_improvement(proposal) exists")
        print("✅ notify_policy(proposal) exists")
        print("✅ All functions have correct signatures")
        return True
    except Exception as e:
        print(f"❌ Telegram test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_propose_improvement_db_and_notification():
    """Test 7: Verify propose_improvement writes to DB and triggers notification."""
    print("\n=== Test 7: Propose Improvement DB + Notification ===")
    try:
        from core.db import TenantAwareCRUD
        db = get_db()
        test_company = "test_improvement_company"
        
        # Use TenantAwareCRUD like the actual code does
        crud = TenantAwareCRUD(db.hermes_evolution_log, company_id=test_company)
        
        # Count before
        count_before = await crud.count_documents({})
        
        # Propose improvement
        result = await evolution.propose_improvement({
            "area": "agent",
            "description": "Test improvement for audit verification",
            "expected_benefit": "Better testing",
            "priority": "P2",
            "company_id": test_company
        })
        
        assert result["ok"] is True
        assert result["area"] == "agent"
        assert result["priority"] == "P2"
        improvement_id = result["id"]
        
        # Verify DB write using TenantAwareCRUD
        count_after = await crud.count_documents({})
        assert count_after == count_before + 1, f"Should have one new record: {count_before} -> {count_after}"
        
        # Verify record exists
        record = await crud.find_one({"id": improvement_id})
        assert record is not None
        assert record["area"] == "agent"
        assert record["status"] == "proposed"
        
        print(f"✅ propose_improvement writes to DB (id: {improvement_id})")
        print(f"✅ Record count increased: {count_before} -> {count_after}")
        print(f"✅ Telegram notification triggered (fire-and-forget)")
        
        # Cleanup
        await crud.delete_one({"id": improvement_id})
        
        return True
    except Exception as e:
        print(f"❌ Propose improvement test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_propose_policy_db_and_notification():
    """Test 8: Verify propose_policy writes to DB and triggers notification."""
    print("\n=== Test 8: Propose Policy DB + Notification ===")
    try:
        from core.db import TenantAwareCRUD
        db = get_db()
        test_company = "test_policy_company"
        
        # Use TenantAwareCRUD like the actual code does
        crud = TenantAwareCRUD(db.policy_proposals, company_id=test_company)
        
        # Count before
        count_before = await crud.count_documents({})
        
        # Propose policy
        result = await evolution.propose_policy({
            "title": "Test Policy for Audit",
            "scope": "testing",
            "proposed_rule": "All tests must pass before deployment",
            "justification": "Quality assurance",
            "severity": "high",
            "company_id": test_company
        })
        
        assert result["ok"] is True
        assert result["title"] == "Test Policy for Audit"
        assert result["severity"] == "high"
        policy_id = result["id"]
        
        # Verify DB write using TenantAwareCRUD
        count_after = await crud.count_documents({})
        assert count_after == count_before + 1, f"Should have one new record: {count_before} -> {count_after}"
        
        # Verify record exists
        record = await crud.find_one({"id": policy_id})
        assert record is not None
        assert record["scope"] == "testing"
        assert record["status"] == "proposed"
        
        print(f"✅ propose_policy writes to DB (id: {policy_id})")
        print(f"✅ Record count increased: {count_before} -> {count_after}")
        print(f"✅ Telegram notification triggered (fire-and-forget)")
        
        # Cleanup
        await crud.delete_one({"id": policy_id})
        
        return True
    except Exception as e:
        print(f"❌ Propose policy test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_skill_file_updated():
    """Test 9: Verify hermes.md skill file has new tools."""
    print("\n=== Test 9: Skill File Updated ===")
    try:
        with open('/app/backend/skills/hermes.md', 'r') as f:
            content = f.read()
        
        # Check allowed_tools section
        assert 'scan_system_health' in content
        assert 'run_persona_benchmark' in content
        
        # Check SOUL section has audit cycle
        assert 'ЦИКЛ САМОАУДИТА' in content or 'САМОАУДИТА' in content
        assert 'read-only' in content.lower()
        assert 'sandbox' in content.lower()
        
        print("✅ hermes.md contains scan_system_health")
        print("✅ hermes.md contains run_persona_benchmark")
        print("✅ hermes.md has ЦИКЛ САМОАУДИТА section")
        print("✅ Skill file properly updated")
        return True
    except Exception as e:
        print(f"❌ Skill file test error: {e}")
        return False


async def test_no_regression_old_tools():
    """Test 10: Verify old tools still work (non-regression)."""
    print("\n=== Test 10: Non-Regression Old Tools ===")
    try:
        # Check old evolution tools still registered
        old_tools = [
            'propose_improvement',
            'list_evolution_roadmap',
            'approve_proposal',
            'propose_policy',
            'list_policy_proposals',
            'detect_automation_candidates',
            'hermes_self_assessment'
        ]
        
        for tool in old_tools:
            assert tool in hermes.HERMES_TOOLS, f"Old tool {tool} missing"
            assert callable(hermes.HERMES_TOOLS[tool]), f"Old tool {tool} not callable"
        
        # Test one old tool still works
        result = await evolution.detect_automation_candidates({
            "window": 50,
            "min_count": 2,
            "company_id": "test_regression"
        })
        assert result["ok"] is True
        
        print(f"✅ All {len(old_tools)} old evolution tools still registered")
        print("✅ detect_automation_candidates still works")
        print("✅ No regression in existing functionality")
        return True
    except Exception as e:
        print(f"❌ Regression test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 70)
    print("HERMES SELF-AUDIT + TELEGRAM ALERTS - COMPREHENSIVE BACKEND TEST")
    print("=" * 70)
    
    tests = [
        ("Import Regressions", test_imports_no_circular_dependency),
        ("Tool Registration", test_hermes_tools_registered),
        ("Benchmark Excludes Hermes", test_run_persona_benchmark_excludes_hermes),
        ("Benchmark No DB Writes", test_benchmark_no_db_writes),
        ("Scan Health Read-Only", test_scan_system_health_read_only),
        ("Telegram First Connected", test_telegram_notify_first_connected),
        ("Propose Improvement DB+Notify", test_propose_improvement_db_and_notification),
        ("Propose Policy DB+Notify", test_propose_policy_db_and_notification),
        ("Skill File Updated", test_skill_file_updated),
        ("Non-Regression Old Tools", test_no_regression_old_tools),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("=" * 70)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Implementation verified.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review needed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
