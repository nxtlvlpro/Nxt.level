"""Session-scoped event loop so Motor can reuse one async context."""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.db import get_db


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
def auth_session_token(event_loop):
    db = get_db()
    user_id = f"pytest_demo_user_{uuid.uuid4().hex[:12]}"
    session_token = f"pytest_demo_token_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)

    event_loop.run_until_complete(
        db.users.update_one(
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
    )
    event_loop.run_until_complete(
        db.user_sessions.update_one(
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
    )

    yield session_token

    event_loop.run_until_complete(
        db.user_sessions.delete_many({"session_token": session_token})
    )
    event_loop.run_until_complete(
        db.users.delete_many({"user_id": user_id})
    )


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
