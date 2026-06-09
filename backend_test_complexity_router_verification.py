"""
Comprehensive verification of complexity_router.py backend fix.
Tests all requirements from the review request.
"""

import sys
sys.path.insert(0, '/app/backend')

from core import complexity_router as router

def test_new_constants_exist():
    """Verify new constants are defined."""
    assert hasattr(router, 'ANALYTICAL_INTENTS'), "ANALYTICAL_INTENTS not defined"
    assert hasattr(router, 'INTENT_REASONER_HINTS'), "INTENT_REASONER_HINTS not defined"
    
    assert 'analyst' in router.ANALYTICAL_INTENTS, "analyst not in ANALYTICAL_INTENTS"
    assert 'bookkeeper' in router.ANALYTICAL_INTENTS, "bookkeeper not in ANALYTICAL_INTENTS"
    
    assert 'planner' in router.INTENT_REASONER_HINTS, "planner not in INTENT_REASONER_HINTS"
    assert 'deep_reasoning' in router.INTENT_REASONER_HINTS, "deep_reasoning not in INTENT_REASONER_HINTS"
    assert 'validation' in router.INTENT_REASONER_HINTS, "validation not in INTENT_REASONER_HINTS"
    assert 'analyst' in router.INTENT_REASONER_HINTS, "analyst not in INTENT_REASONER_HINTS"
    
    print("✅ New constants ANALYTICAL_INTENTS and INTENT_REASONER_HINTS exist")


def test_analyst_patterns_exist():
    """Verify _ANALYST_PATTERNS includes finance/code keywords."""
    assert hasattr(router, '_ANALYST_PATTERNS'), "_ANALYST_PATTERNS not defined"
    
    # Test that patterns match expected keywords
    test_keywords = [
        'MRR', 'ARR', 'CAC', 'LTV', 'churn', 'retention', 'cohort', 'funnel',
        'conversion', 'payback', 'margin', 'burn', 'runway', 'unit economics',
        'pricing', 'forecast', 'sensitivity', 'A/B test', 'stat sig', 'p-value',
        'north star', 'SQL', 'Python', 'schema', 'query', 'debug', 'traceback',
        'stack trace', 'root cause', 'refactor', 'architecture',
        'юнит-экономик', 'когорт', 'ретеншн', 'конверс', 'отток', 'маржин',
        'выручк', 'прогноз', 'чувствительност', 'ценообразован', 'статзначим',
    ]
    
    matched = 0
    for keyword in test_keywords:
        if any(p.search(keyword) for p in router._ANALYST_PATTERNS):
            matched += 1
    
    assert matched >= 20, f"Only {matched}/{len(test_keywords)} analyst keywords matched"
    print(f"✅ _ANALYST_PATTERNS includes finance/code keywords ({matched}/{len(test_keywords)} matched)")


def test_numeric_fragment_regex_exists():
    """Verify _NUMERIC_FRAGMENT_RE exists and matches numeric/money patterns."""
    assert hasattr(router, '_NUMERIC_FRAGMENT_RE'), "_NUMERIC_FRAGMENT_RE not defined"
    
    test_cases = [
        ('100 USD', True),
        ('25%', True),
        ('1500 руб', True),
        ('€500', True),
        ('MRR', True),
        ('ARR', True),
        ('CAC', True),
        ('LTV', True),
        ('hello', False),
    ]
    
    for text, should_match in test_cases:
        matches = router._NUMERIC_FRAGMENT_RE.findall(text)
        if should_match:
            assert len(matches) > 0, f"Expected to match '{text}' but didn't"
        else:
            assert len(matches) == 0, f"Expected not to match '{text}' but did"
    
    print("✅ _NUMERIC_FRAGMENT_RE exists and matches numeric/money patterns")


def test_score_based_routing_analyst_intent():
    """Verify score-based routing for analyst intent."""
    router.reset_stats()
    
    # Simple ping should stay cheap
    result1 = router.pick_model([{'role': 'user', 'content': 'Ping'}], intent='analyst')
    assert result1 == router.MODEL_CHEAP, "Simple analyst ping should use cheap model"
    
    # Finance keywords should route to reasoner
    result2 = router.pick_model(
        [{'role': 'user', 'content': 'Посчитай MRR, CAC, LTV'}],
        intent='analyst'
    )
    assert result2 == router.MODEL_REASONER, "Finance keywords + analyst should use reasoner"
    
    # Code debug should route to reasoner
    result3 = router.pick_model(
        [{'role': 'user', 'content': 'Debug SQL and find root cause'}],
        intent='analyst'
    )
    assert result3 == router.MODEL_REASONER, "Code debug + analyst should use reasoner"
    
    print("✅ Score-based routing works for analyst intent")


def test_score_based_routing_bookkeeper_intent():
    """Verify score-based routing for bookkeeper intent."""
    router.reset_stats()
    
    # Simple ping should stay cheap
    result1 = router.pick_model([{'role': 'user', 'content': 'Ping'}], intent='bookkeeper')
    assert result1 == router.MODEL_CHEAP, "Simple bookkeeper ping should use cheap model"
    
    # Finance keywords should route to reasoner
    result2 = router.pick_model(
        [{'role': 'user', 'content': 'Посчитай unit economics'}],
        intent='bookkeeper'
    )
    assert result2 == router.MODEL_REASONER, "Finance keywords + bookkeeper should use reasoner"
    
    print("✅ Score-based routing works for bookkeeper intent")


def test_simple_requests_not_reasoner_by_default():
    """Verify simple/cheap requests don't accidentally route to reasoner."""
    router.reset_stats()
    
    cheap_cases = [
        ('Привет', 'general'),
        ('Hi', 'general'),
        ('Спасибо', 'general'),
        ('Ping', 'analyst'),
        ('Hello', 'bookkeeper'),
        ('Как дела?', 'analyst'),
    ]
    
    for content, intent in cheap_cases:
        result = router.pick_model([{'role': 'user', 'content': content}], intent=intent)
        assert result == router.MODEL_CHEAP, \
            f"Simple request '{content}' with intent='{intent}' should use cheap model"
    
    print("✅ Simple requests don't accidentally route to reasoner")


def test_execute_node_uses_pick_model():
    """Verify nxt8_graph.execute_node uses pick_model result."""
    import asyncio
    from core import nxt8_graph
    
    seen_model = []
    
    async def fake_chat(**kwargs):
        seen_model.append(kwargs.get('model_override'))
        return {'content': 'ok', 'tokens_total': 10, 'confidence': 0.9, 'mock': False}
    
    class FakeDS:
        chat = staticmethod(fake_chat)
    
    original_get_deepseek = nxt8_graph.get_deepseek
    original_load_skill = nxt8_graph.load_skill
    
    nxt8_graph.get_deepseek = lambda: FakeDS()
    nxt8_graph.load_skill = lambda skill_id: ("prompt", {"allowed_tools": []})
    
    try:
        router.reset_stats()
        seen_model.clear()
        
        # Test with finance query that should route to reasoner
        state = {
            'skill_id': 'analyst',
            'messages': [{'role': 'user', 'content': 'Посчитай MRR и CAC'}],
            'tokens_total': 0,
        }
        
        asyncio.get_event_loop().run_until_complete(nxt8_graph.execute_node(state))
        
        assert len(seen_model) == 1, "Should have called deepseek once"
        assert seen_model[0] == router.MODEL_REASONER, \
            f"Expected {router.MODEL_REASONER}, got {seen_model[0]}"
        
        print("✅ nxt8_graph.execute_node uses pick_model result and passes to deepseek")
        
    finally:
        nxt8_graph.get_deepseek = original_get_deepseek
        nxt8_graph.load_skill = original_load_skill


def test_no_import_regressions():
    """Verify no import errors or circular dependencies."""
    try:
        from core import complexity_router
        from core import nxt8_graph
        from core.deepseek import get_deepseek
        
        # Verify key functions exist
        assert callable(complexity_router.pick_model), "pick_model not callable"
        assert callable(complexity_router.stats), "stats not callable"
        assert callable(complexity_router.reset_stats), "reset_stats not callable"
        assert callable(nxt8_graph.execute_node), "execute_node not callable"
        
        print("✅ No import regressions or circular dependencies")
        
    except ImportError as e:
        raise AssertionError(f"Import error: {e}")


def test_router_api_signature_unchanged():
    """Verify pick_model signature is backward compatible."""
    import inspect
    
    sig = inspect.signature(router.pick_model)
    params = list(sig.parameters.keys())
    
    assert 'messages' in params, "messages parameter missing"
    assert 'force' in params, "force parameter missing"
    assert 'intent' in params, "intent parameter missing"
    assert 'role' in params, "role parameter missing"
    
    # Verify defaults
    assert sig.parameters['force'].default is None, "force default should be None"
    assert sig.parameters['intent'].default == "", "intent default should be empty string"
    assert sig.parameters['role'].default == "", "role default should be empty string"
    
    print("✅ Router API signature unchanged (backward compatible)")


def test_review_request_examples():
    """Test specific examples from review request."""
    router.reset_stats()
    
    # Example 1: Simple analyst ping should use cheap
    result1 = router.pick_model([{'role': 'user', 'content': 'Ping'}], intent='analyst')
    assert result1 == router.MODEL_CHEAP, "Simple analyst ping should use cheap"
    
    # Example 2: Finance/cohort request should use reasoner
    result2 = router.pick_model(
        [{'role': 'user', 'content': 'Сделай cohort-анализ по MRR, CAC, LTV и churn, сравни 3 сценария ценообразования и посчитай payback period.'}],
        intent='analyst'
    )
    assert result2 == router.MODEL_REASONER, "Finance/cohort request should use reasoner"
    
    # Example 3: Code/debug request should use reasoner
    result3 = router.pick_model(
        [{'role': 'user', 'content': 'Найди root cause по stack trace, предложи refactor SQL query и объясни архитектурный trade-off.'}],
        intent='analyst'
    )
    assert result3 == router.MODEL_REASONER, "Code/debug request should use reasoner"
    
    print("✅ Review request examples work correctly")


def run_all_tests():
    """Run all verification tests."""
    print("\n" + "="*80)
    print("COMPLEXITY ROUTER BACKEND FIX VERIFICATION")
    print("="*80 + "\n")
    
    test_new_constants_exist()
    test_analyst_patterns_exist()
    test_numeric_fragment_regex_exists()
    test_score_based_routing_analyst_intent()
    test_score_based_routing_bookkeeper_intent()
    test_simple_requests_not_reasoner_by_default()
    test_execute_node_uses_pick_model()
    test_no_import_regressions()
    test_router_api_signature_unchanged()
    test_review_request_examples()
    
    print("\n" + "="*80)
    print("ALL VERIFICATION TESTS PASSED ✅")
    print("="*80 + "\n")
    
    print("SUMMARY:")
    print("✅ New constants ANALYTICAL_INTENTS and INTENT_REASONER_HINTS added")
    print("✅ _ANALYST_PATTERNS includes finance/code/Russian keywords")
    print("✅ _NUMERIC_FRAGMENT_RE matches numeric/money patterns")
    print("✅ Score-based routing works for analyst/bookkeeper intents")
    print("✅ Simple requests stay on cheap model (no accidental reasoner routing)")
    print("✅ nxt8_graph.execute_node uses pick_model and passes to deepseek")
    print("✅ No import regressions or circular dependencies")
    print("✅ Router API signature unchanged (backward compatible)")
    print("✅ Review request examples work correctly")


if __name__ == "__main__":
    run_all_tests()
