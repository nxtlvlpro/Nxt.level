"""Tests for the LLMUnavailable exception path (Iteration 2 / Task 4).

We don't make real LLM calls. Instead we drive the `DeepSeekClient`'s
public surface (`chat`, `chat_stream`) with a controlled provider list
and a monkey-patched `_call`/`_call_stream`.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import patch

import httpx
import pytest

from core import deepseek as ds


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_client(providers: int = 0) -> ds.DeepSeekClient:
    """Construct a client with N synthetic providers via env stubbing."""
    env_patch = {
        "DEEPSEEK_API_KEY": "k1" if providers >= 1 else "",
        "OPENROUTER_API_KEY": "k2" if providers >= 2 else "",
    }
    with patch.dict(os.environ, env_patch, clear=False):
        c = ds.DeepSeekClient()
    return c


# ---------------------------------------------------------------------
# _allow_mock flag
# ---------------------------------------------------------------------


def test_allow_mock_default_true() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": ""}, clear=False):
        assert ds._allow_mock() is True


def test_allow_mock_false() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "false"}, clear=False):
        assert ds._allow_mock() is False


def test_allow_mock_truthy_variants() -> None:
    for v in ["true", "1", "yes", "on", "TRUE"]:
        with patch.dict(os.environ, {"ALLOW_LLM_MOCK": v}, clear=False):
            assert ds._allow_mock() is True
    for v in ["false", "0", "no", "off"]:
        with patch.dict(os.environ, {"ALLOW_LLM_MOCK": v}, clear=False):
            assert ds._allow_mock() is False


# ---------------------------------------------------------------------
# chat() with zero providers
# ---------------------------------------------------------------------


def test_chat_no_providers_with_mock_allowed_returns_mock() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "true"}, clear=False):
        c = _make_client(providers=0)
        assert c.mock_mode is True
        out = _run(c.chat(messages=[{"role": "user", "content": "ping"}]))
        # Mock response shape includes 'content' or 'mock' marker.
        assert isinstance(out, dict)
        assert "content" in out


def test_chat_no_providers_with_mock_blocked_raises() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "false"}, clear=False):
        c = _make_client(providers=0)
        with pytest.raises(ds.LLMUnavailable) as e:
            _run(c.chat(messages=[{"role": "user", "content": "ping"}]))
        assert e.value.note == "llm_no_providers"


# ---------------------------------------------------------------------
# chat() with all providers failing
# ---------------------------------------------------------------------


def _force_provider_failure(c: ds.DeepSeekClient) -> None:
    """Patch `_call` to always raise an httpx error so the provider loop
    exhausts itself."""
    async def _boom(*_a: Any, **_kw: Any) -> Dict[str, Any]:
        raise httpx.HTTPError("simulated_network_outage")
    c._call = _boom  # type: ignore[assignment]


def test_chat_all_providers_fail_with_mock_allowed_returns_mock() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "true"}, clear=False):
        c = _make_client(providers=1)
        _force_provider_failure(c)
        out = _run(c.chat(messages=[{"role": "user", "content": "hi"}]))
        assert isinstance(out, dict)
        assert "content" in out


def test_chat_all_providers_fail_with_mock_blocked_raises() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "false"}, clear=False):
        c = _make_client(providers=1)
        _force_provider_failure(c)
        with pytest.raises(ds.LLMUnavailable) as e:
            _run(c.chat(messages=[{"role": "user", "content": "hi"}]))
        assert e.value.note == "all_providers_failed"
        assert "simulated_network_outage" in str(e.value.errors)


# ---------------------------------------------------------------------
# chat_stream() — same contract
# ---------------------------------------------------------------------


def _force_stream_failure(c: ds.DeepSeekClient) -> None:
    async def _boom(*_a: Any, **_kw: Any) -> AsyncIterator[str]:
        raise httpx.HTTPError("stream_outage")
        yield  # pragma: no cover — make this an async generator
    c._call_stream = _boom  # type: ignore[assignment]


def test_chat_stream_no_providers_blocked_raises() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "false"}, clear=False):
        c = _make_client(providers=0)

        async def _consume() -> List[str]:
            chunks: List[str] = []
            async for ch in c.chat_stream(messages=[{"role": "user", "content": "x"}]):
                chunks.append(ch)
            return chunks

        with pytest.raises(ds.LLMUnavailable):
            _run(_consume())


def test_chat_stream_all_providers_fail_blocked_raises() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "false"}, clear=False):
        c = _make_client(providers=1)
        _force_stream_failure(c)

        async def _consume() -> List[str]:
            chunks: List[str] = []
            async for ch in c.chat_stream(messages=[{"role": "user", "content": "x"}]):
                chunks.append(ch)
            return chunks

        with pytest.raises(ds.LLMUnavailable) as e:
            _run(_consume())
        assert e.value.note == "all_providers_failed_stream"


def test_chat_stream_all_providers_fail_with_mock_allowed_yields_mock() -> None:
    with patch.dict(os.environ, {"ALLOW_LLM_MOCK": "true"}, clear=False):
        c = _make_client(providers=1)
        _force_stream_failure(c)

        async def _consume() -> List[str]:
            chunks: List[str] = []
            async for ch in c.chat_stream(messages=[{"role": "user", "content": "x"}]):
                chunks.append(ch)
            return chunks

        chunks = _run(_consume())
        assert chunks
        assert any(c for c in chunks)  # got some content
