#!/usr/bin/env python3
"""
Phase 1 Extraction Verification for NXT8
Backend-only validation of plan-layer symbol extraction.

Tests:
1. Python imports compile cleanly
2. Runtime behavior preserved (get_plan, _min_plan_for)
3. No Phase 2+ changes (PERSONAS, fetchers, run_persona unchanged)
"""

import sys
import traceback


def test_imports():
    """Test 1: Python imports compile cleanly."""
    print("\n" + "="*70)
    print("TEST 1: Python imports compile cleanly")
    print("="*70)
    
    errors = []
    
    # Test config.plans
    try:
        from config import plans
        print("✅ config.plans imports successfully")
        assert hasattr(plans, 'PLAN_ALIASES'), "PLAN_ALIASES missing"
        assert hasattr(plans, 'build_canonical_plans'), "build_canonical_plans missing"
        assert hasattr(plans, 'canonicalize_plan_id'), "canonicalize_plan_id missing"
        assert hasattr(plans, 'get_plan'), "get_plan missing"
        assert hasattr(plans, 'min_plan_for'), "min_plan_for missing"
        print("   - All expected symbols present in config.plans")
    except Exception as e:
        errors.append(f"config.plans import failed: {e}")
        print(f"❌ config.plans import failed: {e}")
        traceback.print_exc()
    
    # Test agents.legacy.personas_legacy
    try:
        from agents.legacy import personas_legacy
        print("✅ agents.legacy.personas_legacy imports successfully")
        assert hasattr(personas_legacy, 'PLAN_ALIASES'), "PLAN_ALIASES missing"
        assert hasattr(personas_legacy, 'PLANS'), "PLANS missing"
        assert hasattr(personas_legacy, 'get_plan'), "get_plan missing"
        assert hasattr(personas_legacy, '_min_plan_for'), "_min_plan_for missing"
        assert hasattr(personas_legacy, 'PERSONAS'), "PERSONAS missing"
        assert hasattr(personas_legacy, 'run_persona'), "run_persona missing"
        print("   - All expected symbols present in personas_legacy")
    except Exception as e:
        errors.append(f"personas_legacy import failed: {e}")
        print(f"❌ personas_legacy import failed: {e}")
        traceback.print_exc()
    
    # Test agents.personas (if it exists and imports from legacy)
    try:
        from agents import personas
        print("✅ agents.personas imports successfully")
    except Exception as e:
        print(f"⚠️  agents.personas import failed (may not exist): {e}")
    
    # Test core.scheduler (mentioned in review request)
    try:
        from core import scheduler
        print("✅ core.scheduler imports successfully")
    except Exception as e:
        print(f"⚠️  core.scheduler import failed (may not exist): {e}")
    
    # Test agents.inter_agent (mentioned in review request)
    try:
        from agents import inter_agent
        print("✅ agents.inter_agent imports successfully")
    except Exception as e:
        print(f"⚠️  agents.inter_agent import failed (may not exist): {e}")
    
    if errors:
        print(f"\n❌ TEST 1 FAILED: {len(errors)} import errors")
        return False
    else:
        print("\n✅ TEST 1 PASSED: All imports compile cleanly")
        return True


def test_runtime_behavior():
    """Test 2: Runtime behavior preserved."""
    print("\n" + "="*70)
    print("TEST 2: Runtime behavior preserved")
    print("="*70)
    
    from agents.legacy import personas_legacy as p
    
    errors = []
    
    # Test get_plan with aliases
    tests = [
        ("basic", "personal"),
        ("simple", "team"),
        ("pro", "operations"),
        ("enterprise", "headquarters"),
        ("hq", "headquarters"),
        ("pilot", "personal"),
    ]
    
    print("\nTesting get_plan() with aliases:")
    for alias, expected_canonical in tests:
        try:
            result = p.get_plan(alias)
            actual = result.get("id")
            if actual == expected_canonical:
                print(f"  ✅ get_plan('{alias}') -> {actual}")
            else:
                errors.append(f"get_plan('{alias}') returned {actual}, expected {expected_canonical}")
                print(f"  ❌ get_plan('{alias}') -> {actual} (expected {expected_canonical})")
        except Exception as e:
            errors.append(f"get_plan('{alias}') raised exception: {e}")
            print(f"  ❌ get_plan('{alias}') raised exception: {e}")
    
    # Test unknown plan fallback
    print("\nTesting unknown plan fallback:")
    try:
        result = p.get_plan("totally_unknown_plan")
        actual = result.get("id")
        if actual == "headquarters":
            print(f"  ✅ get_plan('totally_unknown_plan') -> {actual} (fallback)")
        else:
            errors.append(f"get_plan('totally_unknown_plan') returned {actual}, expected 'headquarters'")
            print(f"  ❌ get_plan('totally_unknown_plan') -> {actual} (expected 'headquarters')")
    except Exception as e:
        errors.append(f"get_plan('totally_unknown_plan') raised exception: {e}")
        print(f"  ❌ get_plan('totally_unknown_plan') raised exception: {e}")
    
    # Test _min_plan_for for all 8 personas
    print("\nTesting _min_plan_for() for all 8 personas:")
    persona_expected = [
        ("hermes", "personal"),
        ("hr_mentor", "team"),
        ("client_manager", "team"),
        ("project_coord", "headquarters"),
        ("analyst", "headquarters"),
        ("bookkeeper", "operations"),
        ("marketer", "operations"),
        ("compliance", "operations"),
    ]
    
    for persona_id, expected_plan in persona_expected:
        try:
            result = p._min_plan_for(persona_id)
            if result == expected_plan:
                print(f"  ✅ _min_plan_for('{persona_id}') -> {result}")
            else:
                errors.append(f"_min_plan_for('{persona_id}') returned {result}, expected {expected_plan}")
                print(f"  ❌ _min_plan_for('{persona_id}') -> {result} (expected {expected_plan})")
        except Exception as e:
            errors.append(f"_min_plan_for('{persona_id}') raised exception: {e}")
            print(f"  ❌ _min_plan_for('{persona_id}') raised exception: {e}")
    
    if errors:
        print(f"\n❌ TEST 2 FAILED: {len(errors)} runtime errors")
        for err in errors:
            print(f"   - {err}")
        return False
    else:
        print("\n✅ TEST 2 PASSED: All runtime behavior preserved")
        return True


def test_no_phase2_changes():
    """Test 3: Verify no Phase 2+ changes."""
    print("\n" + "="*70)
    print("TEST 3: No Phase 2+ changes")
    print("="*70)
    
    from agents.legacy import personas_legacy as p
    
    errors = []
    
    # Check PERSONAS still exists and has all 8 personas
    print("\nChecking PERSONAS dict:")
    expected_personas = {"hermes", "hr_mentor", "client_manager", "project_coord", 
                        "analyst", "bookkeeper", "marketer", "compliance"}
    actual_personas = set(p.PERSONAS.keys())
    
    if actual_personas == expected_personas:
        print(f"  ✅ PERSONAS has all 8 personas: {sorted(actual_personas)}")
    else:
        errors.append(f"PERSONAS mismatch: {actual_personas} vs {expected_personas}")
        print(f"  ❌ PERSONAS mismatch")
        print(f"     Expected: {sorted(expected_personas)}")
        print(f"     Actual: {sorted(actual_personas)}")
    
    # Check _FETCHER_DISPATCH still exists
    print("\nChecking _FETCHER_DISPATCH:")
    if hasattr(p, '_FETCHER_DISPATCH'):
        fetchers = set(p._FETCHER_DISPATCH.keys())
        expected_fetchers = {"mentor_overview", "user_skill_profile", "diagnostics_summary",
                           "roi_current", "roi_dashboard", "market_intel", "compliance_context"}
        if fetchers == expected_fetchers:
            print(f"  ✅ _FETCHER_DISPATCH has all 7 fetchers: {sorted(fetchers)}")
        else:
            errors.append(f"_FETCHER_DISPATCH mismatch: {fetchers} vs {expected_fetchers}")
            print(f"  ❌ _FETCHER_DISPATCH mismatch")
    else:
        errors.append("_FETCHER_DISPATCH missing")
        print(f"  ❌ _FETCHER_DISPATCH missing")
    
    # Check run_persona still exists
    print("\nChecking run_persona function:")
    if hasattr(p, 'run_persona'):
        print(f"  ✅ run_persona function exists")
    else:
        errors.append("run_persona function missing")
        print(f"  ❌ run_persona function missing")
    
    # Check fetcher functions still exist
    print("\nChecking fetcher functions:")
    fetcher_funcs = [
        "_fetch_mentor_overview",
        "_fetch_diagnostics_summary",
        "_fetch_roi_current",
        "_fetch_roi_dashboard",
        "_fetch_market_intel",
        "_fetch_compliance_context",
    ]
    
    for func_name in fetcher_funcs:
        if hasattr(p, func_name):
            print(f"  ✅ {func_name} exists")
        else:
            errors.append(f"{func_name} missing")
            print(f"  ❌ {func_name} missing")
    
    if errors:
        print(f"\n❌ TEST 3 FAILED: {len(errors)} issues found")
        for err in errors:
            print(f"   - {err}")
        return False
    else:
        print("\n✅ TEST 3 PASSED: No Phase 2+ changes detected")
        return True


async def test_run_persona_plan_gate():
    """Test 4: run_persona plan-gate behavior unchanged."""
    print("\n" + "="*70)
    print("TEST 4: run_persona plan-gate behavior")
    print("="*70)
    
    from agents.legacy import personas_legacy as p
    
    errors = []
    
    # Test analyst requires headquarters
    print("\nTesting analyst plan-gate (requires headquarters):")
    try:
        result = await p.run_persona(
            persona_id="analyst",
            message="ping",
            plan_id="team",
            company_id="test_phase1",
        )
        if result.get("success") is False:
            required = result.get("required_plan")
            if required == "headquarters":
                print(f"  ✅ analyst blocked on 'team' plan, required_plan={required}")
            else:
                errors.append(f"analyst required_plan={required}, expected 'headquarters'")
                print(f"  ❌ analyst required_plan={required} (expected 'headquarters')")
        else:
            errors.append("analyst should be blocked on 'team' plan but succeeded")
            print(f"  ❌ analyst should be blocked on 'team' plan but succeeded")
    except Exception as e:
        errors.append(f"analyst plan-gate test raised exception: {e}")
        print(f"  ❌ analyst plan-gate test raised exception: {e}")
        traceback.print_exc()
    
    if errors:
        print(f"\n❌ TEST 4 FAILED: {len(errors)} issues")
        for err in errors:
            print(f"   - {err}")
        return False
    else:
        print("\n✅ TEST 4 PASSED: run_persona plan-gate behavior unchanged")
        return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("PHASE 1 EXTRACTION VERIFICATION - NXT8")
    print("="*70)
    print("\nContext:")
    print("  - Only Phase 1 extraction allowed")
    print("  - Extracted plan-layer symbols to /app/backend/config/plans.py")
    print("  - Modified /app/backend/agents/legacy/personas_legacy.py")
    print("  - PERSONAS, fetchers, run_persona UNCHANGED")
    print("  - Expectation: Full runtime behavior preservation")
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports compile cleanly", test_imports()))
    
    # Test 2: Runtime behavior
    results.append(("Runtime behavior preserved", test_runtime_behavior()))
    
    # Test 3: No Phase 2+ changes
    results.append(("No Phase 2+ changes", test_no_phase2_changes()))
    
    # Test 4: run_persona plan-gate (async)
    import asyncio
    try:
        result = asyncio.get_event_loop().run_until_complete(test_run_persona_plan_gate())
        results.append(("run_persona plan-gate", result))
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED: Exception during async test: {e}")
        traceback.print_exc()
        results.append(("run_persona plan-gate", False))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ PHASE 1 EXTRACTION VERIFIED: All tests passed")
        print("   - Imports compile cleanly")
        print("   - Runtime behavior preserved")
        print("   - No Phase 2+ changes detected")
        print("   - Plan-gate behavior unchanged")
        return 0
    else:
        print(f"\n❌ PHASE 1 EXTRACTION FAILED: {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
