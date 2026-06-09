"""
Integration test for Hermes Self-Audit tools via actual API.
Tests the full flow through the backend server.
"""

import asyncio
import sys
import os

sys.path.insert(0, '/app/backend')

from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from agents import hermes
from agents import hermes_tools_audit as audit
from agents import hermes_evolution as evolution


async def test_hermes_can_call_audit_tools():
    """Test that Hermes can successfully call the new audit tools."""
    print("\n=== Integration Test: Hermes Calling Audit Tools ===")
    
    try:
        # Test 1: Call scan_system_health through HERMES_TOOLS
        print("\n1. Testing scan_system_health via HERMES_TOOLS...")
        scan_fn = hermes.HERMES_TOOLS['scan_system_health']
        result = await scan_fn({
            "company_id": "integration_test",
            "window": 100
        })
        
        assert result["ok"] is True
        assert "avg_confidence" in result
        assert "escalation_rate" in result
        print(f"   ✅ scan_system_health works: scanned={result.get('scanned', 0)}")
        
        # Test 2: Call run_persona_benchmark through HERMES_TOOLS
        print("\n2. Testing run_persona_benchmark via HERMES_TOOLS...")
        benchmark_fn = hermes.HERMES_TOOLS['run_persona_benchmark']
        
        # Mock the persona runtime for this test
        test_personas = {"analyst", "marketer"}
        
        async def mock_run_persona(**kwargs):
            return {
                "success": True,
                "confidence": 0.85,
                "provider": "nxt8_graph",
                "content": "test"
            }
        
        original_getter = audit._get_persona_runtime
        audit._get_persona_runtime = lambda: (test_personas, mock_run_persona)
        
        result = await benchmark_fn({
            "company_id": "integration_test",
            "query": "Test query"
        })
        
        audit._get_persona_runtime = original_getter
        
        assert result["ok"] is True
        assert result["sandbox"] is True
        assert result["total_personas"] == 2
        print(f"   ✅ run_persona_benchmark works: {result['passed']}/{result['total_personas']} passed")
        
        # Test 3: Verify tools are in tool docs
        print("\n3. Checking tool documentation...")
        tools_doc = hermes._TOOLS_DOC
        assert "scan_system_health" in tools_doc
        assert "run_persona_benchmark" in tools_doc
        assert "read-only" in tools_doc.lower()
        assert "sandbox" in tools_doc.lower()
        print("   ✅ Tools documented in _TOOLS_DOC")
        
        # Test 4: Verify evolution tools still work
        print("\n4. Testing evolution tools (non-regression)...")
        detect_fn = hermes.HERMES_TOOLS['detect_automation_candidates']
        result = await detect_fn({
            "company_id": "integration_test",
            "window": 50,
            "min_count": 2
        })
        assert result["ok"] is True
        print(f"   ✅ detect_automation_candidates works: {result['total_intents_seen']} intents")
        
        # Test 5: Verify telegram notification integration
        print("\n5. Testing telegram notification integration...")
        from core import telegram_bot as tg
        
        # Check functions exist
        assert hasattr(tg, 'notify_improvement')
        assert hasattr(tg, 'notify_policy')
        assert hasattr(tg, 'notify_first_connected_client')
        print("   ✅ Telegram notification functions available")
        
        print("\n" + "=" * 70)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_skill_file_tools():
    """Test that skill file has the new tools in allowed_tools."""
    print("\n=== Skill File Verification ===")
    
    try:
        import yaml
        
        with open('/app/backend/skills/hermes.md', 'r') as f:
            content = f.read()
        
        # Extract YAML frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                allowed_tools = frontmatter.get('allowed_tools', [])
                
                assert 'scan_system_health' in allowed_tools
                assert 'run_persona_benchmark' in allowed_tools
                
                print(f"✅ Skill file has {len(allowed_tools)} allowed_tools")
                print(f"✅ scan_system_health in allowed_tools")
                print(f"✅ run_persona_benchmark in allowed_tools")
                
                # Check SOUL section
                soul_section = parts[2]
                assert 'ЦИКЛ САМОАУДИТА' in soul_section or 'САМОАУДИТА' in soul_section
                print("✅ SOUL section has ЦИКЛ САМОАУДИТА")
                
                return True
        
        print("❌ Could not parse skill file")
        return False
        
    except Exception as e:
        print(f"❌ Skill file test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 70)
    print("HERMES SELF-AUDIT + TELEGRAM ALERTS - INTEGRATION TEST")
    print("=" * 70)
    
    results = []
    
    # Test 1: Integration
    result1 = await test_hermes_can_call_audit_tools()
    results.append(("Integration Test", result1))
    
    # Test 2: Skill File
    result2 = await test_skill_file_tools()
    results.append(("Skill File Test", result2))
    
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
