"""Debug intent reasoner hints."""

import sys
sys.path.insert(0, '/app/backend')

from core import complexity_router as router

# Test the failing case
content = "Проверь правильность"
intent = "validation"

router.reset_stats()

# Check patterns
print(f"\nContent: {content}")
print(f"Intent: {intent}")
print(f"Intent in INTENT_REASONER_HINTS: {intent in router.INTENT_REASONER_HINTS}")

# Check reasoning patterns
reasoning_hits = sum(1 for p in router._REASONING_PATTERNS if p.search(content))
print(f"Reasoning hits: {reasoning_hits}")

# Check analyst patterns
analyst_hits = sum(1 for p in router._ANALYST_PATTERNS if p.search(content))
print(f"Analyst hits: {analyst_hits}")

# Calculate score
score = reasoning_hits
if analyst_hits:
    score += min(2, analyst_hits)
print(f"Score: {score}")

# Make decision
chosen = router.pick_model([{"role": "user", "content": content}], intent=intent)
print(f"Chosen model: {chosen}")

# Test with more explicit reasoning verb
content2 = "Проверь и объясни почему это правильно"
router.reset_stats()
reasoning_hits2 = sum(1 for p in router._REASONING_PATTERNS if p.search(content2))
print(f"\nContent2: {content2}")
print(f"Reasoning hits: {reasoning_hits2}")
chosen2 = router.pick_model([{"role": "user", "content": content2}], intent=intent)
print(f"Chosen model: {chosen2}")
