"""Debug specific routing decision."""

import sys
sys.path.insert(0, '/app/backend')

from core import complexity_router as router

def debug_routing(content, intent="analyst"):
    """Debug why a specific content routes to a specific model."""
    import re
    
    router.reset_stats()
    
    # Check patterns
    print(f"\nContent: {content}")
    print(f"Intent: {intent}")
    print(f"Length: {len(content)} chars")
    
    # Check cheap patterns
    cheap_hits = sum(1 for p in router._CHEAP_PATTERNS if p.search(content))
    print(f"Cheap hits: {cheap_hits}")
    
    # Check reasoning patterns
    reasoning_hits = sum(1 for p in router._REASONING_PATTERNS if p.search(content))
    print(f"Reasoning hits: {reasoning_hits}")
    
    # Check analyst patterns
    analyst_hits = sum(1 for p in router._ANALYST_PATTERNS if p.search(content))
    print(f"Analyst hits: {analyst_hits}")
    
    # Check numeric fragments
    numeric_hits = len(router._NUMERIC_FRAGMENT_RE.findall(content))
    print(f"Numeric hits: {numeric_hits}")
    
    # Check analytical intent
    is_analytical = intent in router.ANALYTICAL_INTENTS
    print(f"Is analytical intent: {is_analytical}")
    
    # Calculate score
    score = reasoning_hits
    if analyst_hits:
        score += min(2, analyst_hits)
    if numeric_hits >= 3:
        score += 1
    if len(content) >= router.HEAVY_CONTEXT_CHARS:
        score += 1
    if is_analytical and (analyst_hits >= 1 or numeric_hits >= 2 or reasoning_hits >= 1):
        score += 1
    
    print(f"Total score: {score}")
    
    # Make decision
    chosen = router.pick_model([{"role": "user", "content": content}], intent=intent)
    print(f"Chosen model: {chosen}")
    
    return chosen


# Test the failing case
debug_routing("Какая у нас маржинальность?", "analyst")

# Test similar cases
debug_routing("Посчитай маржинальность", "analyst")
debug_routing("Проанализируй маржинальность", "analyst")
