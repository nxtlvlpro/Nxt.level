"""
Набор тестов для архитектурных инвариантов и качества кода.
Запускается как часть CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest


QUALITY_TEST_MODULES = (
    "test_no_silent_exceptions.py",
    "test_no_legacy_source_disabled.py",
)


def run_quality_suite() -> bool:
    """Запускает все проверки качества через pytest."""
    base_dir = Path(__file__).resolve().parent
    results = []

    for module_name in QUALITY_TEST_MODULES:
        module_path = base_dir / module_name
        exit_code = pytest.main([str(module_path), "-q"])
        status = "PASS" if exit_code == 0 else "FAIL"
        results.append({"module": module_name, "status": status, "exit_code": exit_code})

    passed = len([r for r in results if r["status"] == "PASS"])
    print(f"\n📊 Quality Audit Suite Result: {passed}/{len(results)} tests passed")
    for r in results:
        print(f"  {r['module'].replace('.py', '')}: {r['status']}")

    return all(r["status"] == "PASS" for r in results)


if __name__ == "__main__":
    raise SystemExit(0 if run_quality_suite() else 1)