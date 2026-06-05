"""
NXT8 — Emergent Google OAuth + session management.

Flow
----
1. Frontend redirects user to `https://auth.emergentagent.com/?redirect=<our_url>`.
2. After Google consent, user lands at `<our_url>#session_id=<id>`.
3. Frontend posts the `session_id` to `POST /api/auth/session`
   (header `X-Session-ID`); backend exchanges it via Emergent's
   `/auth/v1/env/oauth/session-data` endpoint.
4. Backend upserts `db.users` (custom UUID `user_id` field — never the
   Mongo `_id`), inserts `db.user_sessions` with 7-day expiry, sets an
   httpOnly `session_token` cookie.
5. Subsequent requests carry the cookie (or `Authorization: Bearer`);
   `require_user()` resolves both forms.

Public surface
--------------
    ensure_indexes()
    require_user()           — FastAPI Depends, returns AuthedUser
    require_admin()          — checks NXT8_ADMIN_EMAILS or X-Admin-Token
    optional_user()          — same as require_user but returns None
    is_public_path(path)
    router                   — APIRouter mounted under /api/auth
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel

from core.db import get_db

logger = logging.getLogger("nxt8.auth")

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

EMERGENT_AUTH_SESSION_URL = os.environ.get(
    "EMERGENT_AUTH_SESSION_URL",
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
)
COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "session_token")
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "7"))


def _admin_emails() -> set[str]:
    raw = (os.environ.get("NXT8_ADMIN_EMAILS") or "").strip()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _seed_admin_token() -> str:
    return (os.environ.get("SEED_ADMIN_TOKEN") or "").strip()


# Paths that bypass auth. Used both by the middleware and by docs.
# Always check against the `/api/...` prefixed path.
PUBLIC_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^/api/?$"),
    re.compile(r"^/api/health/?$"),
    re.compile(r"^/api/auth/.+"),
    re.compile(r"^/api/payments/webhook/?$"),
    re.compile(r"^/api/webhook/stripe/?$"),
    re.compile(r"^/api/telegram/webhook/[^/]+/?$"),
    re.compile(r"^/api/whatsapp/webhook/[^/]+/?$"),
    re.compile(r"^/api/share/[^/]+/?(og\.png)?/?$"),
    re.compile(r"^/api/s/[^/]+/?$"),
]


def is_public_path(path: str) -> bool:
    return any(p.match(path) for p in PUBLIC_PATH_PATTERNS)


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------


class AuthedUser(BaseModel):
    user_id: str
    email: str
    name: str = ""
    picture: str = ""
    is_admin: bool = False
    session_token: str = ""


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_indexes() -> None:
    db = get_db()
    try:
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email", unique=True)
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("user_id")
        # TTL: Mongo will purge expired sessions automatically.
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    except Exception as e:  # noqa: BLE001
        logger.warning("auth ensure_indexes failed: %s", e)


async def _upsert_user(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Look up by email; create if missing. Always returns a clean dict
    with the custom `user_id` (UUID) — never the Mongo `_id`."""
    db = get_db()
    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email_missing_from_oauth")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    is_admin = email in _admin_emails()
    now = _now()

    if existing:
        update = {
            "name": profile.get("name") or existing.get("name") or "",
            "picture": profile.get("picture") or existing.get("picture") or "",
            "is_admin": is_admin,
            "last_login_at": now.isoformat(),
        }
        await db.users.update_one({"user_id": existing["user_id"]}, {"$set": update})
        existing.update(update)
        return existing

    user_id = f"user_{uuid.uuid4().hex[:16]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "name": profile.get("name") or "",
        "picture": profile.get("picture") or "",
        "is_admin": is_admin,
        "created_at": now.isoformat(),
        "last_login_at": now.isoformat(),
    }
    await db.users.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def _create_session(user_id: str, session_token: str) -> Dict[str, Any]:
    db = get_db()
    expires_at = _now() + timedelta(days=SESSION_TTL_DAYS)
    sess = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": _now().isoformat(),
    }
    # If Emergent reuses session_tokens across calls, upsert defensively.
    await db.user_sessions.update_one(
        {"session_token": session_token}, {"$set": sess}, upsert=True
    )
    return sess


async def _delete_session(session_token: str) -> int:
    res = await get_db().user_sessions.delete_many({"session_token": session_token})
    return int(res.deleted_count or 0)


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _extract_token(
    cookie_value: Optional[str], authorization: Optional[str]
) -> Optional[str]:
    if cookie_value:
        return cookie_value.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


# ---------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------


async def _resolve_user_from_token(token: str) -> Optional[AuthedUser]:
    db = get_db()
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    expires_at = sess.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            return None
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < _now():
            return None
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        return None
    return AuthedUser(
        user_id=user["user_id"],
        email=user.get("email", ""),
        name=user.get("name", ""),
        picture=user.get("picture", ""),
        is_admin=bool(user.get("is_admin")),
        session_token=token,
    )


async def optional_user(
    session_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    authorization: Optional[str] = Header(default=None),
) -> Optional[AuthedUser]:
    """Return AuthedUser if a valid session exists, else None — never raises."""
    token = _extract_token(session_token, authorization)
    if not token:
        return None
    try:
        return await _resolve_user_from_token(token)
    except Exception as e:  # noqa: BLE001
        logger.warning("optional_user resolve failed: %s", e)
        return None


async def require_user(
    session_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    authorization: Optional[str] = Header(default=None),
) -> AuthedUser:
    token = _extract_token(session_token, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="not_authenticated")
    user = await _resolve_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="session_invalid_or_expired")
    return user


async def require_admin(
    session_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
) -> AuthedUser:
    """Admin gate. Two paths:
      • Service-to-service: `X-Admin-Token` header == SEED_ADMIN_TOKEN.
      • Interactive: logged-in user whose email is in NXT8_ADMIN_EMAILS.
    """
    seed = _seed_admin_token()
    if x_admin_token and seed and secrets.compare_digest(x_admin_token, seed):
        return AuthedUser(
            user_id="admin:service",
            email="admin@service",
            name="Service Admin",
            is_admin=True,
        )
    token = _extract_token(session_token, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="admin_token_required")
    user = await _resolve_user_from_token(token)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="admin_only")
    return user


# ---------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/session")
async def auth_session(
    response: Response,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> Dict[str, Any]:
    """Exchange a one-time Emergent `session_id` (URL fragment) for a
    persistent backend session. Idempotent — re-calling with the same
    session_id refreshes the user profile from Google."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="x_session_id_required")
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(
                EMERGENT_AUTH_SESSION_URL,
                headers={"X-Session-ID": x_session_id},
            )
    except Exception as e:  # noqa: BLE001
        logger.exception("emergent session exchange failed: %s", e)
        raise HTTPException(status_code=502, detail=f"oauth_exchange_failed: {e}")
    if r.status_code >= 400:
        logger.warning("emergent /session-data %s: %s", r.status_code, r.text[:300])
        raise HTTPException(status_code=401, detail="oauth_session_invalid")
    payload = r.json() if r.content else {}
    session_token = payload.get("session_token")
    if not session_token:
        raise HTTPException(status_code=502, detail="oauth_no_session_token")

    user = await _upsert_user(payload)
    await _create_session(user["user_id"], session_token)
    _set_session_cookie(response, session_token)
    return {
        "ok": True,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name") or "",
            "picture": user.get("picture") or "",
            "is_admin": bool(user.get("is_admin")),
        },
        # Returned so clients that can't read httpOnly cookies (e.g.
        # mobile webviews, native apps) can keep the token in localStorage
        # and use it as a Bearer header.
        "session_token": session_token,
    }


@router.get("/me")
async def auth_me(user: AuthedUser = Depends(require_user)) -> Dict[str, Any]:
    return {
        "ok": True,
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "is_admin": user.is_admin,
        },
    }


@router.post("/logout")
async def auth_logout(
    response: Response,
    user: Optional[AuthedUser] = Depends(optional_user),
) -> Dict[str, Any]:
    removed = 0
    if user and user.session_token:
        removed = await _delete_session(user.session_token)
    _clear_session_cookie(response)
    return {"ok": True, "removed": removed}


# ---------------------------------------------------------------------
# Middleware factory
# ---------------------------------------------------------------------


def install_auth_middleware(app: Any) -> None:
    """Reject any /api/* request that isn't whitelisted unless it carries
    a valid session token. Keeps `Depends(require_user)` working for typed
    user access but ensures we never accidentally leave a route open."""

    @app.middleware("http")
    async def _auth_gate(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        # Non-API surface (Static, /s/<id>, etc.) is handled by FastAPI routing.
        if not path.startswith("/api/"):
            return await call_next(request)
        if is_public_path(path):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        # Let endpoint-level `Depends(require_admin)` validate the
        # service-to-service token header — middleware just confirms the
        # request *claims* admin identity rather than letting it fall
        # through to the regular session check.
        if request.headers.get("X-Admin-Token"):
            return await call_next(request)
        # Resolve session — cookie or Bearer header.
        token = _extract_token(
            request.cookies.get(COOKIE_NAME),
            request.headers.get("authorization"),
        )
        if not token:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"detail": "not_authenticated"}, status_code=401
            )
        user = await _resolve_user_from_token(token)
        if not user:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"detail": "session_invalid_or_expired"}, status_code=401
            )
        # Stash on request.state so endpoints can read it without re-querying.
        request.state.user = user
        return await call_next(request)
