#!/usr/bin/env python3
"""
Backend test for Phase 2 extraction: list_personas moved to config/personas.py

Verification scope:
1. Python imports compile cleanly
2. GET /api/personas payload shape
3. list_personas behavior for all plan_ids
4. Field preservation (id, name, role, description, icon, color, tools_count, available_on_plan, min_plan)
5. Persona ordering unchanged
6. No Phase 3+ changes (PERSONAS, _FETCHER_DISPATCH, fetcher functions, run_persona unchanged)
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import httpx


async def test_phase2_extraction():
    """Test Phase 2 extraction of list_personas to config/personas.py"""
    
    print("=" * 80)
    print("Phase 2 Extraction Test: list_personas → config/personas.py")
    print("=" * 80)
    
    results = {
        "passed": [],
        "failed": [],
    }
    
    # ========================================================================
    # Test 1: Python imports compile cleanly
    # ========================================================================
    print("\n[Test 1] Python imports compile cleanly")
    try:
        # Import config.personas (new file)
        from config import personas as config_personas
        print("  ✓ config.personas imports successfully")
        
        # Import agents.legacy.personas_legacy (modified file)
        from agents.legacy import personas_legacy
        print("  ✓ agents.legacy.personas_legacy imports successfully")
        
        # Import agents.personas (should be unchanged)
        from agents import personas as personas_agent
        print("  ✓ agents.personas imports successfully")
        
        # Import core.scheduler (should be unchanged)
        from core import scheduler
        print("  ✓ core.scheduler imports successfully")
        
        # Import agents.inter_agent (should be unchanged)
        from agents import inter_agent
        print("  ✓ agents.inter_agent imports successfully")
        
        results["passed"].append("Python imports compile cleanly")
        print("  ✅ PASS: All imports successful")
    except Exception as e:
        results["failed"].append(f"Python imports: {e}")
        print(f"  ❌ FAIL: Import error: {e}")
        return results
    
    # ========================================================================
    # Test 2: GET /api/personas payload shape (programmatic)
    # ========================================================================
    print("\n[Test 2] GET /api/personas payload shape (programmatic)")
    try:
        from agents import personas as personas_agent
        
        # Simulate what the endpoint does
        plan_id = None  # default
        plan = personas_agent.get_plan(plan_id)
        personas_list = personas_agent.list_personas(plan_id)
        
        # Build the response structure
        data = {
            "plan": plan,
            "plans": [
                {"id": pid, **{k: v for k, v in p.items() if k != "personas"}, "personas": p["personas"]}
                for pid, p in personas_agent.PLANS.items()
            ],
            "personas": personas_list,
        }
        
        # Check top-level keys
        required_keys = {"plan", "plans", "personas"}
        if not required_keys.issubset(data.keys()):
            raise Exception(f"Missing keys. Expected {required_keys}, got {set(data.keys())}")
        print(f"  ✓ Top-level keys present: {required_keys}")
        
        # Check plan structure
        plan = data["plan"]
        if not isinstance(plan, dict) or "id" not in plan or "personas" not in plan:
            raise Exception(f"Invalid plan structure: {plan}")
        print(f"  ✓ Plan structure valid: id={plan['id']}, personas count={len(plan['personas'])}")
        
        # Check personas list
        personas = data["personas"]
        if not isinstance(personas, list) or len(personas) == 0:
            raise Exception(f"Invalid personas list: {personas}")
        print(f"  ✓ Personas list valid: {len(personas)} personas")
        
        results["passed"].append("GET /api/personas payload shape")
        print("  ✅ PASS: Payload shape correct")
    except Exception as e:
        results["failed"].append(f"GET /api/personas: {e}")
        print(f"  ❌ FAIL: {e}")
        return results
    
    # ========================================================================
    # Test 3: list_personas behavior for all plan_ids
    # ========================================================================
    print("\n[Test 3] list_personas behavior for all plan_ids")
    try:
        from agents import personas as personas_agent
        
        test_plans = [
            None,  # default (headquarters)
            "personal",
            "team",
            "operations",
            "headquarters",
            "basic",  # legacy alias for personal
            "simple",  # legacy alias for team
            "pro",  # legacy alias for operations
            "enterprise",  # legacy alias for headquarters
        ]
        
        for plan_id in test_plans:
            personas = personas_agent.list_personas(plan_id)
            if not isinstance(personas, list):
                raise Exception(f"list_personas({plan_id}) returned non-list: {type(personas)}")
            
            # Verify each persona has required fields
            for p in personas:
                required_fields = {
                    "id", "name", "role", "description", "icon", "color",
                    "tools_count", "available_on_plan", "min_plan"
                }
                if not required_fields.issubset(p.keys()):
                    raise Exception(
                        f"Persona {p.get('id', '?')} missing fields. "
                        f"Expected {required_fields}, got {set(p.keys())}"
                    )
            
            print(f"  ✓ list_personas({plan_id!r}): {len(personas)} personas, all fields present")
        
        results["passed"].append("list_personas behavior for all plan_ids")
        print("  ✅ PASS: list_personas works for all plan_ids")
    except Exception as e:
        results["failed"].append(f"list_personas behavior: {e}")
        print(f"  ❌ FAIL: {e}")
        return results
    
    # ========================================================================
    # Test 4: Field preservation and values
    # ========================================================================
    print("\n[Test 4] Field preservation and values")
    try:
        from agents import personas as personas_agent
        
        # Get personas for headquarters plan (all personas available)
        personas = personas_agent.list_personas("headquarters")
        
        # Expected persona IDs (8 personas)
        expected_ids = {
            "hermes", "hr_mentor", "client_manager", "project_coord",
            "analyst", "bookkeeper", "marketer", "compliance"
        }
        actual_ids = {p["id"] for p in personas}
        
        if expected_ids != actual_ids:
            raise Exception(
                f"Persona IDs mismatch. Expected {expected_ids}, got {actual_ids}"
            )
        print(f"  ✓ All 8 personas present: {expected_ids}")
        
        # Verify field types and values for each persona
        for p in personas:
            # id: string
            if not isinstance(p["id"], str) or not p["id"]:
                raise Exception(f"Invalid id for {p}: {p['id']}")
            
            # name: string
            if not isinstance(p["name"], str) or not p["name"]:
                raise Exception(f"Invalid name for {p['id']}: {p['name']}")
            
            # role: string
            if not isinstance(p["role"], str) or not p["role"]:
                raise Exception(f"Invalid role for {p['id']}: {p['role']}")
            
            # description: string
            if not isinstance(p["description"], str) or not p["description"]:
                raise Exception(f"Invalid description for {p['id']}: {p['description']}")
            
            # icon: string or None
            if p["icon"] is not None and not isinstance(p["icon"], str):
                raise Exception(f"Invalid icon for {p['id']}: {p['icon']}")
            
            # color: string or None
            if p["color"] is not None and not isinstance(p["color"], str):
                raise Exception(f"Invalid color for {p['id']}: {p['color']}")
            
            # tools_count: int >= 0
            if not isinstance(p["tools_count"], int) or p["tools_count"] < 0:
                raise Exception(f"Invalid tools_count for {p['id']}: {p['tools_count']}")
            
            # available_on_plan: bool
            if not isinstance(p["available_on_plan"], bool):
                raise Exception(f"Invalid available_on_plan for {p['id']}: {p['available_on_plan']}")
            
            # min_plan: string
            if not isinstance(p["min_plan"], str) or not p["min_plan"]:
                raise Exception(f"Invalid min_plan for {p['id']}: {p['min_plan']}")
            
            print(f"  ✓ {p['id']}: all fields valid (tools_count={p['tools_count']}, min_plan={p['min_plan']})")
        
        results["passed"].append("Field preservation and values")
        print("  ✅ PASS: All fields preserved with correct types and values")
    except Exception as e:
        results["failed"].append(f"Field preservation: {e}")
        print(f"  ❌ FAIL: {e}")
        return results
    
    # ========================================================================
    # Test 5: Persona ordering unchanged
    # ========================================================================
    print("\n[Test 5] Persona ordering unchanged")
    try:
        from agents import personas as personas_agent
        
        # Get personas for headquarters plan
        personas = personas_agent.list_personas("headquarters")
        actual_order = [p["id"] for p in personas]
        
        # Expected order (from PERSONAS dict iteration order in personas_legacy.py)
        # Python 3.7+ dicts maintain insertion order
        expected_order = [
            "hermes", "hr_mentor", "client_manager", "project_coord",
            "analyst", "bookkeeper", "marketer", "compliance"
        ]
        
        if actual_order != expected_order:
            raise Exception(
                f"Persona ordering changed.\n"
                f"Expected: {expected_order}\n"
                f"Got:      {actual_order}"
            )
        
        print(f"  ✓ Persona order preserved: {actual_order}")
        results["passed"].append("Persona ordering unchanged")
        print("  ✅ PASS: Persona ordering unchanged")
    except Exception as e:
        results["failed"].append(f"Persona ordering: {e}")
        print(f"  ❌ FAIL: {e}")
        return results
    
    # ========================================================================
    # Test 6: No Phase 3+ changes (PERSONAS, _FETCHER_DISPATCH, run_persona)
    # ========================================================================
    print("\n[Test 6] No Phase 3+ changes leaked")
    try:
        from agents.legacy import personas_legacy
        
        # Verify PERSONAS dict still exists and has 8 personas
        if not hasattr(personas_legacy, "PERSONAS"):
            raise Exception("PERSONAS dict missing from personas_legacy")
        
        personas_dict = personas_legacy.PERSONAS
        if len(personas_dict) != 8:
            raise Exception(f"PERSONAS dict size changed: expected 8, got {len(personas_dict)}")
        print(f"  ✓ PERSONAS dict unchanged: {len(personas_dict)} personas")
        
        # Verify _FETCHER_DISPATCH still exists
        if not hasattr(personas_legacy, "_FETCHER_DISPATCH"):
            raise Exception("_FETCHER_DISPATCH missing from personas_legacy")
        
        fetcher_dispatch = personas_legacy._FETCHER_DISPATCH
        expected_fetchers = {
            "mentor_overview", "user_skill_profile", "diagnostics_summary",
            "roi_current", "roi_dashboard", "market_intel", "compliance_context"
        }
        actual_fetchers = set(fetcher_dispatch.keys())
        if expected_fetchers != actual_fetchers:
            raise Exception(
                f"_FETCHER_DISPATCH changed.\n"
                f"Expected: {expected_fetchers}\n"
                f"Got:      {actual_fetchers}"
            )
        print(f"  ✓ _FETCHER_DISPATCH unchanged: {len(fetcher_dispatch)} fetchers")
        
        # Verify run_persona function still exists
        if not hasattr(personas_legacy, "run_persona"):
            raise Exception("run_persona function missing from personas_legacy")
        
        import inspect
        run_persona_sig = inspect.signature(personas_legacy.run_persona)
        expected_params = {"persona_id", "message", "company_id", "user_id", "session_id", "plan_id"}
        actual_params = set(run_persona_sig.parameters.keys())
        if expected_params != actual_params:
            raise Exception(
                f"run_persona signature changed.\n"
                f"Expected: {expected_params}\n"
                f"Got:      {actual_params}"
            )
        print(f"  ✓ run_persona signature unchanged: {list(run_persona_sig.parameters.keys())}")
        
        # Verify fetcher functions still exist
        for fetcher_name in expected_fetchers:
            if fetcher_name == "user_skill_profile":
                continue  # This is a lambda, skip
            
            func_name = f"_fetch_{fetcher_name}"
            if not hasattr(personas_legacy, func_name):
                raise Exception(f"Fetcher function {func_name} missing")
        print(f"  ✓ All fetcher functions present")
        
        results["passed"].append("No Phase 3+ changes leaked")
        print("  ✅ PASS: No Phase 3+ changes detected")
    except Exception as e:
        results["failed"].append(f"Phase 3+ changes check: {e}")
        print(f"  ❌ FAIL: {e}")
        return results
    
    # ========================================================================
    # Test 7: Verify plan-specific availability
    # ========================================================================
    print("\n[Test 7] Plan-specific availability")
    try:
        from agents import personas as personas_agent
        
        # Test personal plan (only hermes)
        personal_personas = personas_agent.list_personas("personal")
        available_personal = [p["id"] for p in personal_personas if p["available_on_plan"]]
        if available_personal != ["hermes"]:
            raise Exception(f"Personal plan availability wrong: {available_personal}")
        print(f"  ✓ Personal plan: {available_personal}")
        
        # Test team plan (hermes, hr_mentor, client_manager)
        team_personas = personas_agent.list_personas("team")
        available_team = [p["id"] for p in team_personas if p["available_on_plan"]]
        expected_team = ["hermes", "hr_mentor", "client_manager"]
        if available_team != expected_team:
            raise Exception(f"Team plan availability wrong: expected {expected_team}, got {available_team}")
        print(f"  ✓ Team plan: {available_team}")
        
        # Test operations plan (hermes, hr_mentor, client_manager, bookkeeper, marketer, compliance)
        ops_personas = personas_agent.list_personas("operations")
        available_ops = [p["id"] for p in ops_personas if p["available_on_plan"]]
        expected_ops = ["hermes", "hr_mentor", "client_manager", "bookkeeper", "marketer", "compliance"]
        if available_ops != expected_ops:
            raise Exception(f"Operations plan availability wrong: expected {expected_ops}, got {available_ops}")
        print(f"  ✓ Operations plan: {available_ops}")
        
        # Test headquarters plan (all 8 personas)
        hq_personas = personas_agent.list_personas("headquarters")
        available_hq = [p["id"] for p in hq_personas if p["available_on_plan"]]
        expected_hq = ["hermes", "hr_mentor", "client_manager", "project_coord", "analyst", "bookkeeper", "marketer", "compliance"]
        if available_hq != expected_hq:
            raise Exception(f"Headquarters plan availability wrong: expected {expected_hq}, got {available_hq}")
        print(f"  ✓ Headquarters plan: {available_hq}")
        
        results["passed"].append("Plan-specific availability")
        print("  ✅ PASS: Plan-specific availability correct")
    except Exception as e:
        results["failed"].append(f"Plan-specific availability: {e}")
        print(f"  ❌ FAIL: {e}")
        return results
    
    return results


async def main():
    results = await test_phase2_extraction()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if results["failed"]:
        print(f"\n❌ FAILED: {len(results['failed'])} test(s) failed")
        for failure in results["failed"]:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"\n✅ PASSED: All {len(results['passed'])} tests passed")
        for test in results["passed"]:
            print(f"  - {test}")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
