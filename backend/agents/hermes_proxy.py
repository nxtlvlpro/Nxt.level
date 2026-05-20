"""
Hermes Agent proxy for NXT8 (module 15, additive).

Exposes a thin async forwarder to a local Hermes Agent gateway that runs as a
separate supervisor service on HERMES_PORT (default 8642). Falls back to a
degraded-status response when Hermes is unreachable — never raises, so NXT8
stays green when Hermes is down.

Env vars:
    HERMES_BASE_URL   default http://127.0.0.1:8642
    HERMES_API_KEY    bearer token for the Hermes API server
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("nxt8.hermes_proxy")

DEFAULT_BASE_URL = "http://127.0.0.1:8642"
DEFAULT_TIMEOUT = 60.0


def _base_url() -> str:
    return os.environ.get("HERMES_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("HERMES_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


async def health() -> Dict[str, Any]:
    """Composite health: pings Hermes /health and reports reachability."""
    url = f"{_base_url()}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code == 200:
            return {
                "status": "online",
                "hermes": r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text},
                "base_url": _base_url(),
            }
        return {
            "status": "degraded",
            "http_status": r.status_code,
            "base_url": _base_url(),
        }
    except httpx.HTTPError as e:
        return {
            "status": "offline",
            "error": str(e),
            "base_url": _base_url(),
        }


async def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward to POST /v1/chat/completions (OpenAI-compatible)."""
    url = f"{_base_url()}/v1/chat/completions"
    body = dict(payload)
    body.setdefault("model", "hermes-agent")
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            r = await client.post(url, headers=_headers(), json=body)
        return {
            "ok": r.status_code < 400,
            "status_code": r.status_code,
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text},
        }
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e), "status_code": 502}


async def list_jobs() -> Dict[str, Any]:
    """GET /api/jobs — list scheduled jobs."""
    url = f"{_base_url()}/api/jobs"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=_headers())
        if r.status_code >= 400:
            return {"ok": False, "status_code": r.status_code, "jobs": []}
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"jobs": []}
        jobs = data.get("jobs") if isinstance(data, dict) else data
        return {"ok": True, "jobs": jobs if isinstance(jobs, list) else [], "raw": data}
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e), "jobs": [], "status_code": 502}


async def create_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /api/jobs — create a scheduled background job."""
    url = f"{_base_url()}/api/jobs"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, headers=_headers(), json=payload)
        return {
            "ok": r.status_code < 400,
            "status_code": r.status_code,
            "job": r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text},
        }
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e), "status_code": 502}
