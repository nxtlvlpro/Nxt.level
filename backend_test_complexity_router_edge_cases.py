"""
Comprehensive edge case testing for complexity_router.py heuristics.
Tests analyst/bookkeeper routing, finance/code patterns, and score-based logic.
"""

import sys
sys.path.insert(0, '/app/backend')

from core import complexity_router as router

def test_simple_greetings_stay_cheap():
    """Simple greetings should always use cheap model."""
    test_cases = [
        "Привет",
        "Hi",
        "Hello",
        "Спасибо",
        "Thanks",
        "Thank you",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model([{"role": "user", "content": content}])
        assert chosen == router.MODEL_CHEAP, f"Failed for: {content}"
    print("✅ Simple greetings stay cheap")


def test_analyst_ping_without_heavy_keywords_stays_cheap():
    """Analyst intent with simple ping should stay on cheap model."""
    test_cases = [
        "Ping",
        "Привет, analyst",
        "Как дела?",
        "What's up?",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="analyst",
        )
        assert chosen == router.MODEL_CHEAP, f"Failed for: {content}"
    print("✅ Analyst ping without heavy keywords stays cheap")


def test_bookkeeper_ping_without_heavy_keywords_stays_cheap():
    """Bookkeeper intent with simple ping should stay on cheap model."""
    test_cases = [
        "Ping",
        "Привет, bookkeeper",
        "Как дела?",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="bookkeeper",
        )
        assert chosen == router.MODEL_CHEAP, f"Failed for: {content}"
    print("✅ Bookkeeper ping without heavy keywords stays cheap")


def test_finance_keywords_with_analyst_intent_routes_to_reasoner():
    """Finance keywords + analyst intent should route to reasoner."""
    test_cases = [
        "Посчитай MRR и ARR",
        "Проанализируй CAC и LTV",
        "Проанализируй churn rate",
        "Сделай cohort analysis",
        "Посчитай conversion funnel",
        "Оцени payback period",
        "Оцени unit economics",
        "Посчитай contribution margin",
        "Проанализируй margin",
        "Сделай прогноз выручки",
        "Проанализируй retention",
        "Посчитай конверсию",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="analyst",
        )
        assert chosen == router.MODEL_REASONER, f"Failed for: {content}"
    print("✅ Finance keywords + analyst intent routes to reasoner")


def test_code_debug_keywords_with_analyst_intent_routes_to_reasoner():
    """Code/debug keywords + analyst intent should route to reasoner."""
    test_cases = [
        "Найди root cause по stack trace",
        "Debug this SQL query",
        "Почему падает Python скрипт?",
        "Проанализируй traceback",
        "Refactor this code",
        "Оптимизируй архитектуру",
        "Найди exception в коде",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="analyst",
        )
        assert chosen == router.MODEL_REASONER, f"Failed for: {content}"
    print("✅ Code/debug keywords + analyst intent routes to reasoner")


def test_numeric_fragments_with_analyst_intent_routes_to_reasoner():
    """Numeric fragments (money, percentages) + analyst intent should route to reasoner."""
    test_cases = [
        "У нас 1500 USD MRR и 25% churn",
        "CAC составляет 500 руб, LTV 2000 руб",
        "Конверсия упала с 15% до 10%",
        "Выручка 100000 EUR, маржа 30%",
        "ROI составляет 250%, ROMI 180%",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="analyst",
        )
        assert chosen == router.MODEL_REASONER, f"Failed for: {content}"
    print("✅ Numeric fragments + analyst intent routes to reasoner")


def test_bookkeeper_with_finance_keywords_routes_to_reasoner():
    """Bookkeeper intent with finance keywords should route to reasoner."""
    test_cases = [
        "Посчитай unit economics",
        "Проанализируй маржинальность",
        "Какой у нас burn rate?",
        "Сделай прогноз выручки",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="bookkeeper",
        )
        assert chosen == router.MODEL_REASONER, f"Failed for: {content}"
    print("✅ Bookkeeper + finance keywords routes to reasoner")


def test_non_analytical_intent_with_finance_keywords_needs_higher_score():
    """Non-analytical intent needs higher score to route to reasoner."""
    # Single finance keyword without analytical intent should stay cheap
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": "Что такое MRR?"}],
        intent="general",
    )
    assert chosen == router.MODEL_CHEAP
    
    # Multiple finance keywords + reasoning pattern should route to reasoner
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": "Посчитай MRR, ARR, CAC и LTV для нашего продукта"}],
        intent="general",
    )
    assert chosen == router.MODEL_REASONER
    
    print("✅ Non-analytical intent needs higher score for reasoner")


def test_heavy_context_with_reasoning_signals_routes_to_reasoner():
    """Heavy context (>1500 chars) + reasoning signals should route to reasoner."""
    # Create a long message with reasoning signals
    long_content = "Проанализируй следующую ситуацию: " + "x" * 1500 + " и посчитай оптимальное решение"
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": long_content}],
        intent="general",
    )
    assert chosen == router.MODEL_REASONER
    print("✅ Heavy context + reasoning signals routes to reasoner")


def test_heavy_context_without_reasoning_signals_stays_cheap():
    """Heavy context without reasoning signals should stay cheap."""
    # Create a long message without reasoning signals
    long_content = "Привет, как дела? " + "Расскажи мне историю. " * 200
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": long_content}],
        intent="general",
    )
    assert chosen == router.MODEL_CHEAP
    print("✅ Heavy context without reasoning signals stays cheap")


def test_force_cheap_overrides_all_heuristics():
    """force='cheap' should override all heuristics."""
    # Even with heavy reasoning signals, force=cheap should win
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": "Посчитай MRR, ARR, CAC, LTV, churn, retention, cohort analysis"}],
        force="cheap",
        intent="analyst",
    )
    assert chosen == router.MODEL_CHEAP
    stats = router.stats()
    assert stats["force_cheap"] == 1
    print("✅ force='cheap' overrides all heuristics")


def test_force_reasoner_overrides_all_heuristics():
    """force='reasoner' should override all heuristics."""
    # Even with simple greeting, force=reasoner should win
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": "Привет"}],
        force="reasoner",
        intent="general",
    )
    assert chosen == router.MODEL_REASONER
    stats = router.stats()
    assert stats["force_reasoner"] == 1
    print("✅ force='reasoner' overrides all heuristics")


def test_system_messages_not_counted_in_heuristics():
    """System messages should not be counted in heuristics (only user messages)."""
    # System message with reasoning keywords should not trigger reasoner
    router.reset_stats()
    chosen = router.pick_model(
        [
            {"role": "system", "content": "Ты аналитик. Посчитай MRR, ARR, CAC, LTV, churn, retention."},
            {"role": "user", "content": "Привет"},
        ],
        intent="general",
    )
    assert chosen == router.MODEL_CHEAP
    print("✅ System messages not counted in heuristics")


def test_intent_reasoner_hints_with_score_routes_to_reasoner():
    """Intent hints (planner, deep_reasoning, validation, analyst) + score >= 1 should route to reasoner."""
    test_cases = [
        ("planner", "Спланируй задачу"),
        ("deep_reasoning", "Объясни почему это работает"),
        ("validation", "Докажи правильность решения"),
        ("analyst", "Посчитай метрики"),
    ]
    for intent, content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent=intent,
        )
        assert chosen == router.MODEL_REASONER, f"Failed for intent={intent}, content={content}"
    print("✅ Intent reasoner hints + score routes to reasoner")


def test_stats_tracking():
    """Stats should correctly track routing decisions."""
    router.reset_stats()
    
    # Make some routing decisions
    router.pick_model([{"role": "user", "content": "Привет"}])  # cheap
    router.pick_model([{"role": "user", "content": "Посчитай MRR"}], intent="analyst")  # reasoner
    router.pick_model([{"role": "user", "content": "Hi"}])  # cheap
    router.pick_model([{"role": "user", "content": "Debug SQL"}], intent="analyst")  # reasoner
    
    stats = router.stats()
    assert stats[router.MODEL_CHEAP] == 2
    assert stats[router.MODEL_REASONER] == 2
    assert stats["reasoner_share_pct"] == 50.0
    print("✅ Stats tracking works correctly")


def test_russian_finance_keywords():
    """Russian finance keywords with reasoning verbs should be recognized."""
    test_cases = [
        "Посчитай юнит-экономику",
        "Проанализируй когортный анализ",
        "Оцени retention",
        "Посчитай конверсию",
        "Оцени отток клиентов",
        "Проанализируй margin",
        "Спланируй прогноз выручки",
        "Проанализируй sensitivity",
        "Оптимизируй pricing",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="analyst",
        )
        assert chosen == router.MODEL_REASONER, f"Failed for: {content}"
    print("✅ Russian finance keywords recognized")


def test_ab_test_and_statistical_keywords():
    """A/B test and statistical significance keywords should route to reasoner."""
    test_cases = [
        "Проанализируй A/B test",
        "Посчитай statistical significance",
        "Посчитай p-value",
        "Оцени north star метрику",
        "Спланируй A/B тест",
        "Проанализируй stat sig",
    ]
    for content in test_cases:
        router.reset_stats()
        chosen = router.pick_model(
            [{"role": "user", "content": content}],
            intent="analyst",
        )
        assert chosen == router.MODEL_REASONER, f"Failed for: {content}"
    print("✅ A/B test and statistical keywords route to reasoner")


def test_complex_multi_scenario_request():
    """Complex multi-scenario request from review should route to reasoner."""
    content = "Сделай cohort-анализ по MRR, CAC, LTV и churn, сравни 3 сценария ценообразования и посчитай payback period."
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": content}],
        intent="analyst",
    )
    assert chosen == router.MODEL_REASONER
    print("✅ Complex multi-scenario request routes to reasoner")


def test_code_architecture_request():
    """Code architecture request from review should route to reasoner."""
    content = "Найди root cause по stack trace, предложи refactor SQL query и объясни архитектурный trade-off."
    router.reset_stats()
    chosen = router.pick_model(
        [{"role": "user", "content": content}],
        intent="analyst",
    )
    assert chosen == router.MODEL_REASONER
    print("✅ Code architecture request routes to reasoner")


def run_all_tests():
    """Run all edge case tests."""
    print("\n" + "="*80)
    print("COMPLEXITY ROUTER EDGE CASE TESTS")
    print("="*80 + "\n")
    
    test_simple_greetings_stay_cheap()
    test_analyst_ping_without_heavy_keywords_stays_cheap()
    test_bookkeeper_ping_without_heavy_keywords_stays_cheap()
    test_finance_keywords_with_analyst_intent_routes_to_reasoner()
    test_code_debug_keywords_with_analyst_intent_routes_to_reasoner()
    test_numeric_fragments_with_analyst_intent_routes_to_reasoner()
    test_bookkeeper_with_finance_keywords_routes_to_reasoner()
    test_non_analytical_intent_with_finance_keywords_needs_higher_score()
    test_heavy_context_with_reasoning_signals_routes_to_reasoner()
    test_heavy_context_without_reasoning_signals_stays_cheap()
    test_force_cheap_overrides_all_heuristics()
    test_force_reasoner_overrides_all_heuristics()
    test_system_messages_not_counted_in_heuristics()
    test_intent_reasoner_hints_with_score_routes_to_reasoner()
    test_stats_tracking()
    test_russian_finance_keywords()
    test_ab_test_and_statistical_keywords()
    test_complex_multi_scenario_request()
    test_code_architecture_request()
    
    print("\n" + "="*80)
    print("ALL EDGE CASE TESTS PASSED ✅")
    print("="*80 + "\n")


if __name__ == "__main__":
    run_all_tests()
