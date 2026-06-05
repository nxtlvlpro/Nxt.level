"""
NXT8 LLM client — provider chain: OpenRouter → DeepSeek direct → mock.

ТЗ requires DeepSeek as reasoning core. We keep that contract but route through
OpenRouter (free tier `deepseek/deepseek-chat:free`) as the primary edge to bypass
DeepSeek's direct-balance gate. Direct DeepSeek API is kept as fallback for when
the user tops up that account or OpenRouter is unavailable.

Confidence:
- Direct DeepSeek returns logprobs → real exp(avg logprob) confidence.
- OpenRouter `:free` does NOT return logprobs → we use a heuristic based on
  response length + token usage. Final confidence is still re-weighted by the
  Reliability agent (memory consistency + contradiction check) downstream.
"""

from __future__ import annotations


class LLMUnavailable(Exception):
    """All configured LLM providers failed (or none configured) and
    `ALLOW_LLM_MOCK` is disabled. Caught by FastAPI handler in server.py
    and surfaced to clients as HTTP 503 + `{"detail": "llm_unavailable"}`."""

    def __init__(self, errors: str = "", *, note: str = "all_providers_failed") -> None:
        self.errors = errors
        self.note = note
        super().__init__(f"{note}: {errors}" if errors else note)


def _allow_mock() -> bool:
    import os
    raw = (os.environ.get("ALLOW_LLM_MOCK") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


import logging
import math
import os
import random
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("nxt8.deepseek")

PLACEHOLDER_KEYS = {"", "your-key-here", "placeholder", "todo", "changeme"}


def _is_real(key: str) -> bool:
    return bool(key) and key.lower() not in PLACEHOLDER_KEYS


class _Provider:
    name: str
    api_key: str
    base_url: str
    model: str
    supports_logprobs: bool

    def __init__(self, name: str, api_key: str, base_url: str, model: str,
                 supports_logprobs: bool, extra_headers: Optional[Dict[str, str]] = None):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.supports_logprobs = supports_logprobs
        self.extra_headers = extra_headers or {}


class DeepSeekClient:
    """Async LLM client with provider chain + heuristic/logprob confidence."""

    def __init__(self) -> None:
        providers: List[_Provider] = []

        # Primary: direct DeepSeek API (api.deepseek.com) — when both keys are
        # configured, the direct provider goes first. OpenRouter remains the
        # automatic fallback if the direct API is unreachable / quota-exhausted.
        ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if _is_real(ds_key):
            providers.append(_Provider(
                name="deepseek_direct",
                api_key=ds_key,
                base_url=os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1"),
                model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                supports_logprobs=True,
            ))

        or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if _is_real(or_key):
            providers.append(_Provider(
                name="openrouter",
                api_key=or_key,
                base_url=os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1"),
                model=os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat:free"),
                supports_logprobs=True,  # paid v3-0324 returns logprobs; heuristic kicks in if absent
                extra_headers={
                    "HTTP-Referer": os.environ.get("OPENROUTER_REFERRER", "https://nxt8.local"),
                    "X-Title": "NXT8",
                },
            ))

        self.providers: List[_Provider] = providers
        self.mock_mode: bool = len(providers) == 0
        self.last_error: Optional[str] = None
        self.active_provider: Optional[str] = None

        # Backward-compat fields used by /api/health and tests
        self.model: str = providers[0].model if providers else "mock-deepseek"

        if self.mock_mode:
            logger.warning("LLM client in MOCK mode — no provider keys configured")
        else:
            logger.info(
                "LLM provider chain: %s",
                " → ".join(f"{p.name}({p.model})" for p in providers),
            )

    # ---------- public API ----------

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        request_logprobs: bool = True,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.mock_mode:
            if _allow_mock():
                return self._mock_response(messages)
            raise LLMUnavailable("no providers configured", note="llm_no_providers")

        errors: List[str] = []
        for p in self.providers:
            try:
                data = await self._call(p, messages, temperature, max_tokens, request_logprobs, model_override)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else "?"
                reason = {
                    401: "unauthorized",
                    402: "payment_required",
                    403: "forbidden",
                    429: "rate_limited",
                    500: "server_error",
                    502: "bad_gateway",
                    503: "service_unavailable",
                }.get(status, f"http_{status}")
                msg = f"{p.name}:{reason}"
                # Try to capture body for diagnostics
                try:
                    body = e.response.text[:200] if e.response is not None else ""
                    if body:
                        msg += f" ({body.strip()})"
                except Exception:
                    pass
                errors.append(msg)
                logger.warning("provider %s failed: %s — trying next", p.name, msg)
                continue
            except httpx.HTTPError as e:
                errors.append(f"{p.name}:network_error:{e}")
                logger.warning("provider %s network error: %s — trying next", p.name, e)
                continue

            # success
            self.last_error = None
            self.active_provider = p.name
            return self._parse(data, p)

        # all providers failed
        self.last_error = "; ".join(errors) or "all_providers_failed"
        self.active_provider = None
        if _allow_mock():
            logger.error("all LLM providers failed: %s — falling back to mock", self.last_error)
            return self._mock_response(messages, note=self.last_error)
        logger.error("all LLM providers failed: %s — raising LLMUnavailable", self.last_error)
        raise LLMUnavailable(self.last_error, note="all_providers_failed")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        usage_out: Optional[Dict[str, int]] = None,
    ):
        """Async generator yielding incremental content chunks (strings).

        First successful provider streams its delta tokens. On total failure
        falls back to a single mock chunk to keep client UX consistent.

        If `usage_out` is a mutable dict, the final `usage` block from the
        provider (`prompt_tokens` / `completion_tokens` / `total_tokens`)
        is stored there. This is the only way to recover real token counts
        from a streaming call (the streamed chunks themselves carry no
        usage metadata). Used by ROI accounting in /chat/stream so we
        stop under-counting LLM cost by ~98%.
        """
        if self.mock_mode:
            if _allow_mock():
                content = self._mock_response(messages)["content"]
                if usage_out is not None:
                    # rough mock parity with non-stream path
                    last_user = ""
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            last_user = m.get("content", "")
                            break
                    usage_out["total_tokens"] = max(40, (len(last_user) + len(content)) // 4)
                yield content
                return
            raise LLMUnavailable("no providers configured", note="llm_no_providers")

        errors: List[str] = []
        for p in self.providers:
            try:
                async for chunk in self._call_stream(
                    p, messages, temperature, max_tokens, usage_out=usage_out
                ):
                    if chunk:
                        yield chunk
                self.last_error = None
                self.active_provider = p.name
                return
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else "?"
                errors.append(f"{p.name}:http_{status}")
                logger.warning("stream provider %s failed: http_%s — trying next", p.name, status)
                continue
            except httpx.HTTPError as e:
                errors.append(f"{p.name}:network_error:{e}")
                logger.warning("stream provider %s network: %s — trying next", p.name, e)
                continue

        self.last_error = "; ".join(errors) or "all_providers_failed_stream"
        self.active_provider = None
        if _allow_mock():
            yield self._mock_response(messages, note=self.last_error)["content"]
            return
        raise LLMUnavailable(self.last_error, note="all_providers_failed_stream")

    # ---------- internals ----------

    async def _call(
        self,
        p: _Provider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        request_logprobs: bool,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Per-call model override — only applied when the provider is the
        # direct DeepSeek API (which actually offers `deepseek-reasoner`).
        # OpenRouter routes by its own model id (`deepseek/deepseek-...`)
        # so we keep its configured default there.
        effective_model = p.model
        if model_override and p.name == "deepseek_direct":
            effective_model = model_override
        payload: Dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # deepseek-reasoner does NOT accept logprobs; only deepseek-chat does.
        if request_logprobs and p.supports_logprobs and "reasoner" not in effective_model:
            payload["logprobs"] = True
            payload["top_logprobs"] = 5

        headers = {
            "Authorization": f"Bearer {p.api_key}",
            "Content-Type": "application/json",
            **p.extra_headers,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{p.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    async def _call_stream(
        self,
        p: _Provider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        usage_out: Optional[Dict[str, int]] = None,
    ):
        """Async generator: yields delta content strings via SSE from provider."""
        import json as _json

        payload: Dict[str, Any] = {
            "model": p.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if usage_out is not None:
            # OpenAI/DeepSeek-compatible: emit a final SSE chunk carrying usage.
            payload["stream_options"] = {"include_usage": True}
        headers = {
            "Authorization": f"Bearer {p.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            **p.extra_headers,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{p.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        obj = _json.loads(data)
                    except _json.JSONDecodeError:
                        continue
                    # Final usage chunk: empty choices + usage block.
                    usage = obj.get("usage")
                    if usage and usage_out is not None:
                        usage_out["prompt_tokens"] = int(usage.get("prompt_tokens", 0) or 0)
                        usage_out["completion_tokens"] = int(usage.get("completion_tokens", 0) or 0)
                        usage_out["total_tokens"] = int(usage.get("total_tokens", 0) or 0)
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content

    def _parse(self, data: Dict[str, Any], p: _Provider) -> Dict[str, Any]:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        content = (message.get("content") or "").strip()

        # confidence
        confidence = 0.7
        logprobs = choice.get("logprobs") or {}
        token_data = logprobs.get("content") or []
        if token_data:
            lps = [
                t.get("logprob", 0.0)
                for t in token_data
                if isinstance(t, dict) and t.get("logprob") is not None
            ]
            if lps:
                avg = sum(lps) / len(lps)
                confidence = max(0.05, min(0.99, math.exp(avg)))
        else:
            # heuristic confidence when no logprobs (OpenRouter :free)
            confidence = self._heuristic_confidence(content, choice)

        usage = data.get("usage", {})
        return {
            "content": content,
            "confidence": round(float(confidence), 4),
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "tokens_total": usage.get("total_tokens", 0),
            "model": data.get("model", p.model),
            "provider": p.name,
            "mock": False,
        }

    @staticmethod
    def _heuristic_confidence(content: str, choice: Dict[str, Any]) -> float:
        if not content:
            return 0.2
        finish = choice.get("finish_reason", "")
        # baseline by length
        L = len(content)
        base = 0.7
        if L < 40:
            base = 0.55
        elif L < 200:
            base = 0.72
        elif L < 800:
            base = 0.82
        else:
            base = 0.78  # very long can drift
        if finish == "length":
            base -= 0.05  # was truncated
        # tiny stochastic jitter so UI doesn't show identical numbers
        jitter = random.uniform(-0.02, 0.02)
        return max(0.1, min(0.95, base + jitter))

    # ---------- mock ----------

    def _mock_response(
        self, messages: List[Dict[str, str]], note: Optional[str] = None
    ) -> Dict[str, Any]:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        system_prompt = next(
            (m.get("content", "") for m in messages if m.get("role") == "system"), ""
        )
        if "Classify" in system_prompt or "classify" in system_prompt:
            content = self._mock_classify(last_user)
            return {
                "content": content, "confidence": 0.82,
                "tokens_in": 50, "tokens_out": 5, "tokens_total": 55,
                "model": "mock-deepseek", "provider": "mock", "mock": True, "note": note,
            }
        content = self._mock_general(last_user)
        confidence = round(random.uniform(0.55, 0.92), 3)
        return {
            "content": content, "confidence": confidence,
            "tokens_in": max(20, len(last_user) // 4),
            "tokens_out": max(20, len(content) // 4),
            "tokens_total": max(40, (len(last_user) + len(content)) // 4),
            "model": "mock-deepseek", "provider": "mock", "mock": True, "note": note,
        }

    @staticmethod
    def _mock_classify(text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["roi", "выручк", "доход", "стоимост", "cost", "revenue"]):
            return "roi"
        if any(w in t for w in ["сотрудник", "ментор", "обуч", "training", "employee"]):
            return "mentor"
        if any(w in t for w in ["задача", "task", "запланир", "schedule"]):
            return "task"
        if any(w in t for w in ["голос", "voice", "произнес"]):
            return "voice"
        if any(w in t for w in ["знани", "документ", "политик", "knowledge", "policy"]):
            return "knowledge"
        return "general"

    @staticmethod
    def _mock_general(text: str) -> str:
        if not text:
            return "Готов помочь. Опишите задачу."
        snippet = text.strip()[:160]
        return (
            f"Принято: «{snippet}». В рабочем режиме здесь будет ответ DeepSeek с "
            f"учётом корпоративной памяти и confidence scoring. Сейчас система "
            f"работает в demo-режиме (API ключ ещё не подключён)."
        )


_client: Optional[DeepSeekClient] = None


def get_deepseek() -> DeepSeekClient:
    global _client
    if _client is None:
        _client = DeepSeekClient()
    assert _client is not None  # for type checkers
    return _client
