"""
Voice module for NXT8 — dual-provider STT/TTS.

Two transports supported, chosen automatically at startup:

* **native OpenAI SDK** — preferred for production / self-hosted VPS.
  Activated when `OPENAI_API_KEY` is set.
  Pros: works anywhere, official SDK, full feature parity.

* **emergentintegrations wrapper** — fallback for Emergent dev environment.
  Activated when only `EMERGENT_LLM_KEY` is set (no OPENAI_API_KEY).
  Pros: works inside Emergent platform without a separate OpenAI account.

This dual-path lets the same codebase run both inside Emergent (cheap dev)
and on a customer VPS (production) without code changes — only an env swap.

Public API (used by `server.py`):
    transcribe(file_bytes, filename, language)  -> {text, language, duration, model}
    synthesize(text, voice, speed, model)       -> bytes (mp3)
    reset_client()                              -> drop cached client (tests)
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger("nxt8.voice")

# Whisper accepts these audio container extensions.
ALLOWED_AUDIO_EXT = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg"}
ALLOWED_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}
DEFAULT_VOICE = "nova"
DEFAULT_TTS_MODEL = "tts-1"
MAX_TTS_CHARS = 4000

_MIME_BY_EXT = {
    "mp3": "audio/mpeg", "mpga": "audio/mpeg", "mpeg": "audio/mpeg",
    "wav": "audio/wav", "m4a": "audio/mp4", "mp4": "audio/mp4",
    "ogg": "audio/ogg", "webm": "audio/webm",
}


# =====================================================================
# Provider selection
# =====================================================================


def _resolve_provider() -> Tuple[str, str]:
    """
    Returns (provider, api_key).
    Priority: OPENAI_API_KEY (native) → EMERGENT_LLM_KEY (wrapper).
    """
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if openai_key and openai_key.lower() not in {"placeholder", "changeme", "your-key-here"}:
        return "openai", openai_key
    emergent_key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    if emergent_key:
        return "emergent", emergent_key
    raise RuntimeError(
        "Voice agent requires OPENAI_API_KEY (preferred) or EMERGENT_LLM_KEY in backend/.env"
    )


# Cached clients per provider — created lazily so import does not fail when no key is set.
_openai_client = None
_emergent_stt = None
_emergent_tts = None
_provider_in_use: Optional[str] = None


def _get_clients():
    global _openai_client, _emergent_stt, _emergent_tts, _provider_in_use
    if _provider_in_use is not None:
        return _provider_in_use
    provider, key = _resolve_provider()
    if provider == "openai":
        from openai import AsyncOpenAI  # local import — keeps cold-start fast
        kwargs = {"api_key": key}
        base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
        if base:
            kwargs["base_url"] = base
        _openai_client = AsyncOpenAI(**kwargs)
        logger.info("voice: native OpenAI SDK (key=OPENAI_API_KEY)")
    else:
        from emergentintegrations.llm.openai import (  # type: ignore
            OpenAISpeechToText,
            OpenAITextToSpeech,
        )
        _emergent_stt = OpenAISpeechToText(api_key=key)
        _emergent_tts = OpenAITextToSpeech(api_key=key)
        logger.info("voice: emergentintegrations wrapper (key=EMERGENT_LLM_KEY)")
    _provider_in_use = provider
    return provider


def reset_client() -> None:
    global _openai_client, _emergent_stt, _emergent_tts, _provider_in_use
    _openai_client = None
    _emergent_stt = None
    _emergent_tts = None
    _provider_in_use = None


# =====================================================================
# STT
# =====================================================================


async def transcribe(
    file_bytes: bytes,
    filename: str = "audio.webm",
    language: Optional[str] = None,
) -> dict:
    if not file_bytes:
        raise ValueError("empty audio payload")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    if ext not in ALLOWED_AUDIO_EXT:
        ext = "webm"
        filename = f"audio.{ext}"
    mime = _MIME_BY_EXT.get(ext, "audio/webm")

    provider = _get_clients()

    if provider == "openai":
        kwargs = {
            "file": (filename, file_bytes, mime),
            "model": "whisper-1",
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language
        resp = await _openai_client.audio.transcriptions.create(**kwargs)
        text = getattr(resp, "text", "") or ""
        detected = getattr(resp, "language", language or "")
        duration = getattr(resp, "duration", None)
    else:
        # emergentintegrations wrapper uses the openai SDK underneath and
        # expects a file-like object with a `.name` attribute (same as the
        # native SDK form).
        import io
        buf = io.BytesIO(file_bytes)
        buf.name = filename
        kwargs = {
            "file": buf,
            "model": "whisper-1",
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language
        resp = await _emergent_stt.transcribe(**kwargs)
        # The wrapper returns the underlying OpenAI Transcription object.
        if isinstance(resp, dict):
            text = resp.get("text") or ""
            detected = resp.get("language") or (language or "")
            duration = resp.get("duration")
        else:
            text = getattr(resp, "text", "") or ""
            detected = getattr(resp, "language", language or "")
            duration = getattr(resp, "duration", None)

    return {
        "text": (text or "").strip(),
        "language": detected,
        "duration": duration,
        "model": "whisper-1",
    }


# =====================================================================
# TTS
# =====================================================================


async def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    model: str = DEFAULT_TTS_MODEL,
) -> bytes:
    if not text or not text.strip():
        raise ValueError("text is required for TTS")
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    speed = max(0.25, min(4.0, float(speed)))
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    provider = _get_clients()

    if provider == "openai":
        resp = await _openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
            response_format="mp3",
        )
        if hasattr(resp, "aread"):
            audio_bytes = await resp.aread()
        elif hasattr(resp, "read"):
            audio_bytes = resp.read()
        else:
            audio_bytes = getattr(resp, "content", b"")
    else:
        audio_bytes = await _emergent_tts.generate_speech(
            text=text,
            model=model,
            voice=voice,
            speed=speed,
            response_format="mp3",
        )

    if not audio_bytes:
        raise RuntimeError("TTS returned empty audio payload")
    return audio_bytes
