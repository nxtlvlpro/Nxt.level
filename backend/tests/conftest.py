"""Session-scoped event loop so Motor can reuse one async context."""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.db import close_db, get_db


# ==========================================
# GLOBAL TEST CONSTANTS
# ==========================================
TEST_COMPANY_ID = "test_company_123"


def _load_env_file(env_path: str) -> None:
    if not os.path.exists(env_path):
        return
    for line in open(env_path):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def _load_dotenv():
    tests_dir = os.path.dirname(__file__)
    _load_env_file(os.path.join(tests_dir, "..", ".env"))
    _load_env_file(os.path.join(tests_dir, "..", "..", "frontend", ".env"))


_load_dotenv()
os.environ["REACT_APP_BACKEND_URL"] = os.environ.get(
    "PYTEST_REACT_APP_BACKEND_URL",
    "http://127.0.0.1:8001",
).rstrip("/")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    close_db()
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture(scope="session")
def company_id():
    return TEST_COMPANY_ID


@pytest.fixture(scope="session")
def auth_session_token(event_loop):
    user_id = f"pytest_demo_user_{uuid.uuid4().hex[:12]}"
    session_token = f"pytest_demo_token_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)

    async def _seed_auth_session() -> None:
        db = get_db()
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "email": f"{user_id}@nxt8.test",
                    "name": "Pytest Demo User",
                    "picture": "",
                    "is_admin": False,
                    "company_id": "demo",
                    "created_at": now.isoformat(),
                    "last_login_at": now.isoformat(),
                }
            },
            upsert=True,
        )
        await db.user_sessions.update_one(
            {"session_token": session_token},
            {
                "$set": {
                    "user_id": user_id,
                    "session_token": session_token,
                    "expires_at": now + timedelta(days=7),
                    "created_at": now.isoformat(),
                }
            },
            upsert=True,
        )

    event_loop.run_until_complete(_seed_auth_session())

    yield session_token

    async def _cleanup_auth_session() -> None:
        db = get_db()
        await db.user_sessions.delete_many({"session_token": session_token})
        await db.users.delete_many({"user_id": user_id})

    event_loop.run_until_complete(_cleanup_auth_session())


@pytest.fixture(scope="session")
def auth_headers(auth_session_token):
    return {"Authorization": f"Bearer {auth_session_token}"}


@pytest.fixture(scope="session")
def admin_token():
    token = os.environ.get("SEED_ADMIN_TOKEN", "").strip()
    assert token, "SEED_ADMIN_TOKEN is required for admin-only test flows"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"X-Admin-Token": admin_token}
