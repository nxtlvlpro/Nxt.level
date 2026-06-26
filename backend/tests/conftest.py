"""Session-scoped event loop so Motor can reuse one async context."""
import asyncio
import os
import pytest


# ==========================================
# GLOBAL TEST CONSTANTS
# ==========================================
TEST_COMPANY_ID = "test_company_123"


def _load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return
    for line in open(env_path):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


_load_dotenv()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def company_id():
    return TEST_COMPANY_ID


@pytest.fixture(scope="session")
def admin_token():
    token = os.environ.get("SEED_ADMIN_TOKEN", "").strip()
    assert token, "SEED_ADMIN_TOKEN is required for admin-only test flows"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"X-Admin-Token": admin_token}
