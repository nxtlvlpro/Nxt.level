"""
Test that escalate_to_hermes preserves depth counter context.

This verifies that when a subordinate escalates to Hermes, and Hermes
then delegates to another agent, the depth counter is correctly maintained
across the escalation boundary.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def test_escalate_preserves_depth_context():
    """Test that escalate_to_hermes preserves depth counter."""
    from agents import inter_agent
    import agents.hermes as hermes_module
    
    print("\n=== Test: escalate_to_hermes preserves depth context ===")
    
    # Track depth at various points
    depths_observed = []
    
    async def mock_hermes_chat(messages, **kwargs):
        """Mock hermes_chat that observes depth and tries to delegate."""
        depth_in_hermes = inter_agent.delegation_depth.get()
        depths_observed.append(("hermes_chat", depth_in_hermes))
        print(f"  Inside hermes_chat: depth={depth_in_hermes}")
        
        # Hermes tries to delegate - this should respect the current depth
        delegate_result = await inter_agent.delegate_to_agent({
            "from_agent": "hermes",
            "agent_id": "analyst",
            "task": "Handle this escalation",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        
        depth_after_delegate = inter_agent.delegation_depth.get()
        depths_observed.append(("after_delegate_in_hermes", depth_after_delegate))
        print(f"  After delegate in hermes_chat: depth={depth_after_delegate}")
        
        return {
            "content": f"Hermes verdict: delegated to analyst (ok={delegate_result['ok']})",
            "confidence": 0.9,
        }
    
    async def mock_run_persona(**kwargs):
        """Mock run_persona that observes depth."""
        depth_in_persona = inter_agent.delegation_depth.get()
        depths_observed.append(("run_persona", depth_in_persona))
        print(f"  Inside run_persona: depth={depth_in_persona}")
        return {
            "content": "Analyst response",
            "confidence": 0.95,
            "tokens_total": 10,
            "tool_traces": [],
        }
    
    async def mock_log_dialogue(**kwargs):
        return "mock_dialog_id"
    
    async def mock_db_insert_one(doc):
        pass
    
    async def mock_db_update_one(query, update):
        pass
    
    # Mock database
    class MockCollection:
        async def insert_one(self, doc):
            await mock_db_insert_one(doc)
        
        async def update_one(self, query, update):
            await mock_db_update_one(query, update)
    
    class MockDB:
        def __init__(self):
            self.escalations = MockCollection()
            self.agent_dialogues = MockCollection()
    
    # Save originals FIRST
    import agents.personas as personas
    original_hermes_chat = hermes_module.hermes_chat
    original_run_persona = personas.run_persona
    original_log_dialogue = inter_agent._log_dialogue
    
    # Patch get_db in inter_agent module (not in db module, since it's already imported)
    import core.db as db_module
    original_get_db = inter_agent.get_db
    inter_agent.get_db = lambda: MockDB()
    
    # Apply other mocks
    hermes_module.hermes_chat = mock_hermes_chat
    personas.run_persona = mock_run_persona
    inter_agent._log_dialogue = mock_log_dialogue
    
    try:
        # Scenario 1: Escalate from depth=0
        print("\n--- Scenario 1: Escalate from depth=0 ---")
        depths_observed.clear()
        
        before = inter_agent.delegation_depth.get()
        print(f"Before escalate: depth={before}")
        
        result = await inter_agent.escalate_to_hermes({
            "from_agent": "bookkeeper",
            "reason": "Need CEO decision",
            "company_id": "test_co",
            "user_id": "test_user",
        })
        
        after = inter_agent.delegation_depth.get()
        print(f"After escalate: depth={after}")
        print(f"Result ok: {result['ok']}")
        print(f"Depths observed: {depths_observed}")
        
        assert before == 0, f"Expected before=0, got {before}"
        assert after == 0, f"Expected after=0, got {after}"
        assert result["ok"] is True, f"Expected ok=True"
        
        # Verify depth progression
        assert depths_observed[0] == ("hermes_chat", 0), "hermes_chat should see depth=0"
        assert depths_observed[1] == ("run_persona", 1), "run_persona should see depth=1 (incremented by delegate)"
        assert depths_observed[2] == ("after_delegate_in_hermes", 0), "after delegate should reset to 0"
        
        print("✅ PASS - Escalate from depth=0 works correctly")
        
        # Scenario 2: Escalate from depth=2 (simulating nested delegation)
        print("\n--- Scenario 2: Escalate from depth=2 ---")
        depths_observed.clear()
        
        token = inter_agent.delegation_depth.set(2)
        try:
            before = inter_agent.delegation_depth.get()
            print(f"Before escalate: depth={before}")
            
            result = await inter_agent.escalate_to_hermes({
                "from_agent": "bookkeeper",
                "reason": "Need CEO decision at depth 2",
                "company_id": "test_co",
                "user_id": "test_user",
            })
            
            after = inter_agent.delegation_depth.get()
            print(f"After escalate: depth={after}")
            print(f"Result ok: {result['ok']}")
            print(f"Depths observed: {depths_observed}")
            
            assert before == 2, f"Expected before=2, got {before}"
            assert after == 2, f"Expected after=2, got {after}"
            assert result["ok"] is True, f"Expected ok=True"
            
            # Verify depth progression
            assert depths_observed[0] == ("hermes_chat", 2), "hermes_chat should see depth=2"
            assert depths_observed[1] == ("run_persona", 3), "run_persona should see depth=3 (incremented by delegate)"
            assert depths_observed[2] == ("after_delegate_in_hermes", 2), "after delegate should reset to 2"
            
            print("✅ PASS - Escalate from depth=2 works correctly")
        finally:
            inter_agent.delegation_depth.reset(token)
        
        # Scenario 3: Escalate from depth=3 (at limit)
        print("\n--- Scenario 3: Escalate from depth=3 (at limit) ---")
        depths_observed.clear()
        
        # Modify mock_hermes_chat to handle blocked delegation
        async def mock_hermes_chat_at_limit(messages, **kwargs):
            depth_in_hermes = inter_agent.delegation_depth.get()
            depths_observed.append(("hermes_chat", depth_in_hermes))
            print(f"  Inside hermes_chat: depth={depth_in_hermes}")
            
            # Hermes tries to delegate - this should be BLOCKED at depth=3
            delegate_result = await inter_agent.delegate_to_agent({
                "from_agent": "hermes",
                "agent_id": "analyst",
                "task": "Handle this escalation",
                "company_id": "test_co",
                "user_id": "test_user",
            })
            
            depths_observed.append(("delegate_result", delegate_result))
            print(f"  Delegate result: {delegate_result}")
            
            return {
                "content": f"Hermes verdict: delegation blocked (ok={delegate_result['ok']})",
                "confidence": 0.9,
            }
        
        hermes_module.hermes_chat = mock_hermes_chat_at_limit
        
        token = inter_agent.delegation_depth.set(3)
        try:
            before = inter_agent.delegation_depth.get()
            print(f"Before escalate: depth={before}")
            
            result = await inter_agent.escalate_to_hermes({
                "from_agent": "bookkeeper",
                "reason": "Need CEO decision at depth 3",
                "company_id": "test_co",
                "user_id": "test_user",
            })
            
            after = inter_agent.delegation_depth.get()
            print(f"After escalate: depth={after}")
            print(f"Result ok: {result['ok']}")
            print(f"Depths observed: {depths_observed}")
            
            assert before == 3, f"Expected before=3, got {before}"
            assert after == 3, f"Expected after=3, got {after}"
            assert result["ok"] is True, f"Expected escalate ok=True (escalation itself succeeds)"
            
            # Verify delegation was blocked
            delegate_result = depths_observed[1][1]
            assert delegate_result["ok"] is False, "Delegation should be blocked at depth=3"
            assert "Max delegation depth (3) reached" == delegate_result["error"]
            
            print("✅ PASS - Escalate from depth=3 correctly blocks further delegation")
        finally:
            inter_agent.delegation_depth.reset(token)
        
        print("\n" + "="*60)
        print("ALL ESCALATE DEPTH TESTS PASSED ✅")
        print("="*60)
        
    finally:
        # Restore originals
        hermes_module.hermes_chat = original_hermes_chat
        personas.run_persona = original_run_persona
        inter_agent._log_dialogue = original_log_dialogue
        inter_agent.get_db = original_get_db


if __name__ == "__main__":
    asyncio.run(test_escalate_preserves_depth_context())
