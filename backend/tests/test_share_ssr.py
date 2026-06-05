"""SSR endpoint for share links — ensures Telegram/WhatsApp crawlers
get correct Open Graph meta tags."""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://company-os-9.preview.emergentagent.com").rstrip("/")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def share_id() -> str:
    async def _go() -> str:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                f"{API}/api/share/journey",
                json={
                    "client_id": "ssr_pytest_client",
                    "completed_steps": ["ask_hermes"],
                    "headline": "SSR test — НиктоUNICODE & <special>",
                    "locale": "ru",
                },
            )
        assert r.status_code == 200, r.text
        sid = r.json()["share_id"]
        assert sid
        return sid

    return _run(_go())


def test_ssr_html_has_og_tags(share_id: str) -> None:
    async def _go():
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.get(
                f"{API}/api/s/{share_id}",
                headers={"User-Agent": "TelegramBot (like TwitterBot)"},
            )
        return r

    r = _run(_go())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    # All four crawler-critical tags must be present.
    assert 'property="og:image"' in body
    assert f"/api/share/{share_id}/og.png" in body
    assert 'property="og:title"' in body
    assert 'property="og:type"' in body
    assert 'name="twitter:card"' in body
    # XSS sanity — angle brackets in headline must be escaped, not raw.
    assert "<special>" not in body
    assert "&lt;special&gt;" in body
    # Redirect path present for real browsers.
    assert f"?ref={share_id}" in body


def test_ssr_unknown_id_returns_404() -> None:
    async def _go():
        async with httpx.AsyncClient(timeout=15) as cli:
            return await cli.get(f"{API}/api/s/no_such_id_zzz")

    r = _run(_go())
    assert r.status_code == 404


def test_og_png_is_image(share_id: str) -> None:
    async def _go():
        async with httpx.AsyncClient(timeout=15) as cli:
            return await cli.get(f"{API}/api/share/{share_id}/og.png")

    r = _run(_go())
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    # PNG magic number.
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(r.content) > 1024  # not a stub
