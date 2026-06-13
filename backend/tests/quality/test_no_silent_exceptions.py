import ast
import os

import pytest


RUNTIME_MODULES = [
    "backend/server.py",
    "backend/core/auth.py",
    "backend/core/db.py",
    "backend/core/deepseek.py",
    "backend/core/telegram_bot.py",
    "backend/core/scheduler.py",
    "backend/agents/ai_mentor.py",
    "backend/agents/hermes_evolution.py",
    "backend/agents/hermes.py",
]


def has_silent_except(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if not node.body or all(isinstance(n, ast.Pass) for n in node.body):
                return True
    return False


@pytest.mark.parametrize("module", RUNTIME_MODULES)
def test_no_silent_except_in_module(module):
    if not os.path.exists(module):
        pytest.skip(f"File {module} does not exist")
    assert not has_silent_except(module), f"Silent 'except' found in {module}"