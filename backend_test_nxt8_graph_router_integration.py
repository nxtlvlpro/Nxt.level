"""
Integration test: verify nxt8_graph.execute_node uses complexity_router.pick_model
and passes the result to deepseek via model_override parameter.
"""

import sys
sys.path.insert(0, '/app/backend')

import asyncio
from core import complexity_router as router
from core import nxt8_graph

def test_execute_node_integration():
    """Test that execute_node correctly uses router and passes model_override to deepseek."""
    
    # Track what model_override was passed to deepseek
    seen_calls = []
    
    async def fake_chat(**kwargs):
        seen_calls.append({
            'model_override': kwargs.get('model_override'),
            'messages': kwargs.get('messages', []),
        })
        return {
            'content': 'Test response',
            'tokens_total': 10,
            'confidence': 0.85,
            'mock': False,
        }
    
    class FakeDeepSeek:
        chat = staticmethod(fake_chat)
    
    # Monkey patch
    original_get_deepseek = nxt8_graph.get_deepseek
    original_load_skill = nxt8_graph.load_skill
    
    nxt8_graph.get_deepseek = lambda: FakeDeepSeek()
    nxt8_graph.load_skill = lambda skill_id: ("System prompt", {"allowed_tools": []})
    
    try:
        # Reset stats once at the start
        router.reset_stats()
        
        # Test 1: Simple ping with analyst intent should use cheap model
        seen_calls.clear()
        
        state1 = {
            'skill_id': 'analyst',
            'messages': [{'role': 'user', 'content': 'Ping'}],
            'tokens_total': 0,
        }
        
        result1 = asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state1))
        
        assert len(seen_calls) == 1, "Should have made 1 deepseek call"
        assert seen_calls[0]['model_override'] == router.MODEL_CHEAP, \
            f"Expected {router.MODEL_CHEAP}, got {seen_calls[0]['model_override']}"
        print("✅ Test 1: Simple analyst ping uses cheap model")
        
        # Test 2: Finance analysis with analyst intent should use reasoner
        seen_calls.clear()
        
        state2 = {
            'skill_id': 'analyst',
            'messages': [{'role': 'user', 'content': 'Посчитай MRR, CAC, LTV и churn rate'}],
            'tokens_total': 0,
        }
        
        result2 = asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state2))
        
        assert len(seen_calls) == 1, "Should have made 1 deepseek call"
        assert seen_calls[0]['model_override'] == router.MODEL_REASONER, \
            f"Expected {router.MODEL_REASONER}, got {seen_calls[0]['model_override']}"
        print("✅ Test 2: Finance analysis uses reasoner model")
        
        # Test 3: Code debug with analyst intent should use reasoner
        seen_calls.clear()
        
        state3 = {
            'skill_id': 'analyst',
            'messages': [{'role': 'user', 'content': 'Debug SQL query and find root cause'}],
            'tokens_total': 0,
        }
        
        result3 = asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state3))
        
        assert len(seen_calls) == 1, "Should have made 1 deepseek call"
        assert seen_calls[0]['model_override'] == router.MODEL_REASONER, \
            f"Expected {router.MODEL_REASONER}, got {seen_calls[0]['model_override']}"
        print("✅ Test 3: Code debug uses reasoner model")
        
        # Test 4: Bookkeeper with finance keywords should use reasoner
        seen_calls.clear()
        
        state4 = {
            'skill_id': 'bookkeeper',
            'messages': [{'role': 'user', 'content': 'Посчитай unit economics'}],
            'tokens_total': 0,
        }
        
        result4 = asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state4))
        
        assert len(seen_calls) == 1, "Should have made 1 deepseek call"
        assert seen_calls[0]['model_override'] == router.MODEL_REASONER, \
            f"Expected {router.MODEL_REASONER}, got {seen_calls[0]['model_override']}"
        print("✅ Test 4: Bookkeeper with finance keywords uses reasoner model")
        
        # Test 5: General skill with simple greeting should use cheap model
        seen_calls.clear()
        
        state5 = {
            'skill_id': 'general',
            'messages': [{'role': 'user', 'content': 'Привет'}],
            'tokens_total': 0,
        }
        
        result5 = asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state5))
        
        assert len(seen_calls) == 1, "Should have made 1 deepseek call"
        assert seen_calls[0]['model_override'] == router.MODEL_CHEAP, \
            f"Expected {router.MODEL_CHEAP}, got {seen_calls[0]['model_override']}"
        print("✅ Test 5: General skill with greeting uses cheap model")
        
        # Test 6: Verify router stats are being tracked
        stats = router.stats()
        assert stats[router.MODEL_CHEAP] == 2, f"Should have 2 cheap calls, got {stats[router.MODEL_CHEAP]}"
        assert stats[router.MODEL_REASONER] == 3, f"Should have 3 reasoner calls, got {stats[router.MODEL_REASONER]}"
        print(f"✅ Test 6: Router stats tracked correctly: {stats}")
        
    finally:
        # Restore original functions
        nxt8_graph.get_deepseek = original_get_deepseek
        nxt8_graph.load_skill = original_load_skill


def test_router_called_with_correct_parameters():
    """Test that execute_node calls pick_model with correct parameters."""
    
    router_calls = []
    
    def fake_pick_model(messages, intent=None, **kwargs):
        router_calls.append({
            'messages': messages,
            'intent': intent,
        })
        # Return cheap for simple, reasoner for complex
        user_content = ' '.join(m.get('content', '') for m in messages if m.get('role') == 'user')
        if 'MRR' in user_content or 'CAC' in user_content:
            return router.MODEL_REASONER
        return router.MODEL_CHEAP
    
    async def fake_chat(**kwargs):
        return {
            'content': 'Test response',
            'tokens_total': 10,
            'confidence': 0.85,
            'mock': False,
        }
    
    class FakeDeepSeek:
        chat = staticmethod(fake_chat)
    
    # Monkey patch
    original_pick_model = nxt8_graph.pick_model
    original_get_deepseek = nxt8_graph.get_deepseek
    original_load_skill = nxt8_graph.load_skill
    
    nxt8_graph.pick_model = fake_pick_model
    nxt8_graph.get_deepseek = lambda: FakeDeepSeek()
    nxt8_graph.load_skill = lambda skill_id: ("System prompt", {"allowed_tools": []})
    
    try:
        router_calls.clear()
        
        state = {
            'skill_id': 'analyst',
            'messages': [{'role': 'user', 'content': 'Посчитай MRR'}],
            'tokens_total': 0,
        }
        
        result = asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state))
        
        assert len(router_calls) == 1, "Should have called pick_model once"
        assert router_calls[0]['intent'] == 'analyst', \
            f"Expected intent='analyst', got {router_calls[0]['intent']}"
        
        # Verify messages include system prompt + user message
        messages = router_calls[0]['messages']
        assert len(messages) >= 2, "Should have at least system + user messages"
        assert any(m.get('role') == 'system' for m in messages), "Should have system message"
        assert any(m.get('role') == 'user' for m in messages), "Should have user message"
        
        print("✅ Router called with correct parameters (intent=skill_id, messages)")
        
    finally:
        # Restore original functions
        nxt8_graph.pick_model = original_pick_model
        nxt8_graph.get_deepseek = original_get_deepseek
        nxt8_graph.load_skill = original_load_skill


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*80)
    print("NXT8_GRAPH + COMPLEXITY_ROUTER INTEGRATION TESTS")
    print("="*80 + "\n")
    
    test_execute_node_integration()
    test_router_called_with_correct_parameters()
    
    print("\n" + "="*80)
    print("ALL INTEGRATION TESTS PASSED ✅")
    print("="*80 + "\n")


if __name__ == "__main__":
    run_all_tests()
