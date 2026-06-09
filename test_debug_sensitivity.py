"""Debug specific case."""

import sys
sys.path.insert(0, '/app/backend')

from core import complexity_router as router

content = "Проведи анализ чувствительности"
router.reset_stats()

# Check patterns
reasoning_hits = sum(1 for p in router._REASONING_PATTERNS if p.search(content))
analyst_hits = sum(1 for p in router._ANALYST_PATTERNS if p.search(content))
numeric_hits = len(router._NUMERIC_FRAGMENT_RE.findall(content))

print(f"Content: {content}")
print(f"Reasoning hits: {reasoning_hits}")
print(f"Analyst hits: {analyst_hits}")
print(f"Numeric hits: {numeric_hits}")

# Check if patterns match
for i, p in enumerate(router._REASONING_PATTERNS):
    if p.search(content):
        print(f"Reasoning pattern {i} matched: {p.pattern}")

for i, p in enumerate(router._ANALYST_PATTERNS):
    if p.search(content):
        print(f"Analyst pattern {i} matched: {p.pattern}")

chosen = router.pick_model([{"role": "user", "content": content}], intent="analyst")
print(f"Chosen: {chosen}")
