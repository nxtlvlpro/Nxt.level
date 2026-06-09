"""
Comprehensive backend test for inter-agent depth counter fix (NXT8).

Tests:
1. Depth counter increments correctly during nested calls
2. Depth counter resets after successful delegation
3. Depth counter resets after exception in delegation
4. Depth counter resets after exception in ask_colleague
5. Depth limit (3) blocks further delegation
6. Depth limit (3) blocks further ask_colleague
7. Error messages are correct
8. Multiple sequential calls don't accumulate depth
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend is importable
ROOT = Path(__file__).resolve().parent / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def test_depth_counter_comprehensive():
    """Comprehensive test of depth counter behavior."""
    from agents import inter_agent
    import agents.personas as personas
    
    print("\n=== Test 1: Initial depth is 0 ===")
    initial_depth = inter_agent.delegation_depth.get()
    print(f"Initial depth: {initial_depth}")
    assert initial_depth == 0, f"Expected 0, got {initial_depth}"
    print("✅ PASS")
    
    print("\n=== Test 2: MAX_DELEGATION_DEPTH is 3 ===")
    print(f"MAX_DELEGATION_DEPTH: {inter_agent.MAX_DELEGATION_DEPTH}")
    assert inter_agent.MAX_DELEGATION_DEPTH == 3, f"Expected 3, got {inter_agent.MAX_DELEGATION_DEPTH}"
    print("✅ PASS")
    
    print("\n=== Test 3: Depth increments during call (mocked success) ===")
    depth_during_call = None
    
    async def mock_run_persona_success(**kwargs):
        nonlocal depth_during_call
        depth_during_call = inter_agent.delegation_depth.get()
        return {
            "content": "Mock response",
            "confidence": 0.95,
            "tokens_total": 10,
            "tool_traces": [],
        }
    
    async def mock_log_dialogue(**kwargs):
        return "mock_dialog_id"
    
    original_run_persona = personas.run_persona
    original_log_dialogue = inter_agent._log_dialogue
    
    personas.run_persona = mock_run_persona_success
    inter_agent._log_dialogue = mock_log_dialogue
    
    try:
        before = inter_agent.delegation_depth.get()
        result = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "Test task",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        after = inter_agent.delegation_depth.get()
        
        print(f"Depth before call: {before}")
        print(f"Depth during call: {depth_during_call}")
        print(f"Depth after call: {after}")
        print(f"Result ok: {result['ok']}")
        
        assert before == 0, f"Expected before=0, got {before}"
        assert depth_during_call == 1, f"Expected during=1, got {depth_during_call}"
        assert after == 0, f"Expected after=0, got {after}"
        assert result["ok"] is True, f"Expected ok=True, got {result}"
        print("✅ PASS")
    finally:
        personas.run_persona = original_run_persona
        inter_agent._log_dialogue = original_log_dialogue
    
    print("\n=== Test 4: Depth resets after exception ===")
    
    async def mock_run_persona_exception(**kwargs):
        current_depth = inter_agent.delegation_depth.get()
        print(f"  Inside mock (before exception): depth={current_depth}")
        raise RuntimeError("Simulated failure")
    
    personas.run_persona = mock_run_persona_exception
    
    try:
        before = inter_agent.delegation_depth.get()
        result = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "Test exception handling",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        after = inter_agent.delegation_depth.get()
        
        print(f"Depth before call: {before}")
        print(f"Depth after call: {after}")
        print(f"Result: {result}")
        
        assert before == 0, f"Expected before=0, got {before}"
        assert after == 0, f"Expected after=0, got {after}"
        assert result["ok"] is False, f"Expected ok=False, got {result}"
        assert "delegation_failed" in result["error"], f"Expected 'delegation_failed' in error, got {result['error']}"
        print("✅ PASS")
    finally:
        personas.run_persona = original_run_persona
    
    print("\n=== Test 5: Depth limit blocks at depth=3 (delegate_to_agent) ===")
    token = inter_agent.delegation_depth.set(3)
    try:
        current = inter_agent.delegation_depth.get()
        print(f"Set depth to: {current}")
        
        result = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "Should be blocked",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        
        print(f"Result: {result}")
        assert result["ok"] is False, f"Expected ok=False, got {result}"
        assert "Max delegation depth (3) reached" == result["error"], f"Expected exact error message, got {result['error']}"
        
        after = inter_agent.delegation_depth.get()
        print(f"Depth after blocked call: {after}")
        assert after == 3, f"Expected depth still 3, got {after}"
        print("✅ PASS")
    finally:
        inter_agent.delegation_depth.reset(token)
    
    print("\n=== Test 6: Depth limit blocks at depth=3 (ask_colleague) ===")
    token = inter_agent.delegation_depth.set(3)
    try:
        current = inter_agent.delegation_depth.get()
        print(f"Set depth to: {current}")
        
        result = await inter_agent.ask_colleague({
            "from_agent": "bookkeeper",
            "agent_id": "analyst",
            "question": "Should be blocked",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        
        print(f"Result: {result}")
        assert result["ok"] is False, f"Expected ok=False, got {result}"
        assert "Max delegation depth (3) reached" == result["error"], f"Expected exact error message, got {result['error']}"
        
        after = inter_agent.delegation_depth.get()
        print(f"Depth after blocked call: {after}")
        assert after == 3, f"Expected depth still 3, got {after}"
        print("✅ PASS")
    finally:
        inter_agent.delegation_depth.reset(token)
    
    print("\n=== Test 7: ask_colleague depth resets after exception ===")
    
    async def mock_run_persona_exception(**kwargs):
        current_depth = inter_agent.delegation_depth.get()
        print(f"  Inside mock (before exception): depth={current_depth}")
        raise RuntimeError("Peer call failed")
    
    personas.run_persona = mock_run_persona_exception
    
    try:
        before = inter_agent.delegation_depth.get()
        result = await inter_agent.ask_colleague({
            "from_agent": "bookkeeper",
            "agent_id": "analyst",
            "question": "Test exception in ask_colleague",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        after = inter_agent.delegation_depth.get()
        
        print(f"Depth before call: {before}")
        print(f"Depth after call: {after}")
        print(f"Result: {result}")
        
        assert before == 0, f"Expected before=0, got {before}"
        assert after == 0, f"Expected after=0, got {after}"
        assert result["ok"] is False, f"Expected ok=False, got {result}"
        assert "ask_failed" in result["error"], f"Expected 'ask_failed' in error, got {result['error']}"
        print("✅ PASS")
    finally:
        personas.run_persona = original_run_persona
    
    print("\n=== Test 8: Multiple sequential calls don't accumulate depth ===")
    personas.run_persona = mock_run_persona_success
    inter_agent._log_dialogue = mock_log_dialogue
    
    try:
        for i in range(5):
            before = inter_agent.delegation_depth.get()
            result = await inter_agent.delegate_to_agent({
                "from_agent": "hermes",
                "agent_id": "analyst",
                "task": f"Sequential call {i+1}",
                "company_id": "test_co",
                "user_id": "test_user",
            })
            after = inter_agent.delegation_depth.get()
            
            print(f"Call {i+1}: before={before}, after={after}, ok={result['ok']}")
            assert before == 0, f"Call {i+1}: Expected before=0, got {before}"
            assert after == 0, f"Call {i+1}: Expected after=0, got {after}"
            assert result["ok"] is True, f"Call {i+1}: Expected ok=True"
        
        print("✅ PASS - All 5 sequential calls maintained depth=0")
    finally:
        personas.run_persona = original_run_persona
        inter_agent._log_dialogue = original_log_dialogue
    
    print("\n=== Test 9: Verify depth at exactly 2 still allows one more call ===")
    token = inter_agent.delegation_depth.set(2)
    personas.run_persona = mock_run_persona_success
    inter_agent._log_dialogue = mock_log_dialogue
    
    try:
        before = inter_agent.delegation_depth.get()
        print(f"Set depth to: {before}")
        
        # This should succeed because depth=2, and we increment to 3 (which is still <= MAX)
        result = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "At depth 2, should work",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        
        after = inter_agent.delegation_depth.get()
        print(f"Result ok: {result['ok']}")
        print(f"Depth after call: {after}")
        
        assert result["ok"] is True, f"Expected ok=True at depth=2, got {result}"
        assert after == 2, f"Expected depth back to 2, got {after}"
        print("✅ PASS")
    finally:
        inter_agent.delegation_depth.reset(token)
        personas.run_persona = original_run_persona
        inter_agent._log_dialogue = original_log_dialogue
    
    print("\n=== Test 10: Final depth check ===")
    final_depth = inter_agent.delegation_depth.get()
    print(f"Final depth: {final_depth}")
    assert final_depth == 0, f"Expected final depth=0, got {final_depth}"
    print("✅ PASS")
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED ✅")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_depth_counter_comprehensive())
