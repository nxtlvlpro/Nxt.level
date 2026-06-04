"""
Voice module for NXT8 — dual-provider STT/TTS with `gpt-4o-mini-tts`
style-instructions support.

Two transports supported, chosen automatically at startup:

* **native OpenAI SDK** — preferred for production / self-hosted VPS.
  Activated when `OPENAI_API_KEY` is set.
  Pros: works anywhere, official SDK, full feature parity.

* **emergentintegrations + litellm** — fallback for Emergent dev environment.
  Activated when only `EMERGENT_LLM_KEY` is set (no OPENAI_API_KEY).
  STT goes through `OpenAISpeechToText` (full feature parity with native).
  TTS bypasses `OpenAITextToSpeech.generate_speech()` and goes DIRECTLY
  through `litellm.aspeech(...)` so we can pass the new `instructions`
  parameter required by `gpt-4o-mini-tts` (the emergentintegrations
  helper whitelists only `tts-1` / `tts-1-hd` and drops `instructions`).

This dual-path lets the same codebase run both inside Emergent (cheap dev)
and on a customer VPS (production) without code changes — only an env swap.

Public API (used by `server.py`):
    transcribe(file_bytes, filename, language)         -> {text, language, duration, model}
    synthesize(text, voice, speed, model, instructions, lang) -> bytes (mp3)
    reset_client()                                     -> drop cached client (tests)
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger("nxt8.voice")

# Whisper accepts these audio container extensions.
ALLOWED_AUDIO_EXT = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg"}
ALLOWED_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}
DEFAULT_VOICE = "onyx"

# Default model is now `gpt-4o-mini-tts` — the only OpenAI TTS model that
# supports the `instructions` style/tone parameter. Falls back gracefully
# to tts-1 if the caller explicitly requests it (legacy /api/voice/tts).
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
LEGACY_TTS_MODELS = {"tts-1", "tts-1-hd"}
INSTRUCTIONS_CAPABLE_MODELS = {"gpt-4o-mini-tts"}
MAX_TTS_CHARS = 4000

# Style-instruction defaults — applied automatically when the caller does
# not pass an explicit `instructions` string. Two languages, picked from
# the `lang` argument. Tuned for the NXT8 "Hermes COO" persona:
# calm, confident, warm, conversational, no theatrics.
DEFAULT_INSTRUCTIONS_EN = (
    "Voice: a calm, confident chief operations officer giving a short "
    "briefing to a trusted colleague.\n"
    "Tone: warm, measured, lightly upbeat — like a senior advisor who "
    "knows the answer.\n"
    "Pacing: natural conversational speed, slightly slower on numbers and "
    "names; small pauses between clauses.\n"
    "Style: no theatrics, no shouting, no robotic monotone. A faint smile "
    "in the voice. Sound human."
)
DEFAULT_INSTRUCTIONS_RU = (
    "Голос: спокойный, уверенный операционный директор, кратко докладывает "
    "доверенному коллеге.\n"
    "Тон: тёплый, размеренный, с лёгким позитивом — как старший советник, "
    "который знает ответ.\n"
    "Темп: естественная разговорная скорость, чуть медленнее на цифрах и "
    "именах; небольшие паузы между смысловыми блоками.\n"
    "Стиль: без театральности, без крика, без роботизированной монотонности. "
    "Лёгкая улыбка в голосе. Звучи по-человечески."
)

_MIME_BY_EXT = {
    "mp3": "audio/mpeg", "mpga": "audio/mpeg", "mpeg": "audio/mpeg",
    "wav": "audio/wav", "m4a": "audio/mp4", "mp4": "audio/mp4",
    "ogg": "audio/ogg", "webm": "audio/webm",
}


# =====================================================================
# Fish Audio — PRIMARY TTS provider (OpenAI kept as fallback below).
# =====================================================================

FISH_TTS_URL = "https://api.fish.audio/v1/tts"

# Public default voices that Fish Audio ships out-of-the-box, per-language.
# Used when `FISH_DEFAULT_VOICE_ID` env var isn't set. Keys are short ISO
# codes (`ru`, `en`); falls back to `en` for anything else.
FISH_BUILTIN_VOICE = {
    # Studio voices — picked from fish.audio/app/default-voices/.
    # Russian: a calm, professional male voice that matches the Hermes COO persona.
    "ru": None,  # let Fish Audio's auto-detect + S1 default kick in
    "en": None,
}


async def _fish_synthesize(text: str, lang: Optional[str]) -> bytes:
    """Call Fish Audio TTS. Raises on any non-2xx or transport error so the
    outer synth() can transparently fall back to OpenAI."""
    api_key = (os.environ.get("FISH_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("FISH_API_KEY not configured")

    import httpx  # local import — keeps voice.py lazy

    model = (os.environ.get("FISH_TTS_MODEL") or "s1").strip()
    voice_id = (os.environ.get("FISH_DEFAULT_VOICE_ID") or "").strip()
    if not voice_id:
        voice_id = FISH_BUILTIN_VOICE.get((lang or "en").split("-")[0].lower()) or ""

    payload = {
        "text": text,
        "format": "mp3",
        "mp3_bitrate": 128,
        # `normal` favours quality; switch to `balanced` for lower latency.
        "latency": "normal",
        "chunk_length": 200,
    }
    if voice_id:
        payload["reference_id"] = voice_id

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": model,
    }
    timeout = httpx.Timeout(connect=5.0, read=45.0, write=5.0, pool=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(FISH_TTS_URL, json=payload, headers=headers)

    if resp.status_code >= 300:
        body = (resp.text or "")[:200]
        raise RuntimeError(f"Fish Audio HTTP {resp.status_code}: {body}")
    audio = resp.content or b""
    if not audio:
        raise RuntimeError("Fish Audio returned empty audio")
    return audio


# =====================================================================
# Provider selection (OpenAI / Emergent — kept as fallback)
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
_emergent_proxy_url: Optional[str] = None
_emergent_key: Optional[str] = None
_provider_in_use: Optional[str] = None


def _get_clients():
    global _openai_client, _emergent_stt, _emergent_proxy_url, _emergent_key, _provider_in_use
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
        # STT keeps using the emergent helper (no special params needed).
        from emergentintegrations.llm.openai import (  # type: ignore
            OpenAISpeechToText,
            OpenAITextToSpeech,
        )
        _emergent_stt = OpenAISpeechToText(api_key=key)
        # For TTS we steal the proxy URL from the helper so we can talk
        # to the same endpoint directly via litellm with the full param
        # surface (including `instructions`).
        probe = OpenAITextToSpeech(api_key=key)
        _emergent_proxy_url = probe.emergent_proxy_url
        _emergent_key = key
        logger.info(
            "voice: emergentintegrations STT + litellm TTS via proxy %s",
            _emergent_proxy_url,
        )
    _provider_in_use = provider
    return provider


def reset_client() -> None:
    global _openai_client, _emergent_stt, _emergent_proxy_url, _emergent_key, _provider_in_use
    _openai_client = None
    _emergent_stt = None
    _emergent_proxy_url = None
    _emergent_key = None
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


def _pick_instructions(lang: Optional[str], explicit: Optional[str]) -> str:
    if explicit:
        return explicit.strip()
    return DEFAULT_INSTRUCTIONS_RU if (lang or "").lower().startswith("ru") else DEFAULT_INSTRUCTIONS_EN


async def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    model: str = DEFAULT_TTS_MODEL,
    instructions: Optional[str] = None,
    lang: Optional[str] = None,
) -> bytes:
    """
    Generate speech audio from `text`.

    * `model="gpt-4o-mini-tts"` (default) enables the `instructions`
      parameter — style/tone control. We auto-pick an EN or RU default
      from `lang` if the caller does not pass one explicitly.
    * `model="tts-1"` / `"tts-1-hd"` keep the legacy behaviour
      (no `instructions`, plain narration).

    Robust to provider-level model whitelists: if the chosen model is
    rejected (e.g. `gpt-4o-mini-tts` not yet enabled on the Emergent
    LLM proxy), we transparently retry with `tts-1-hd` so the caller
    never sees a 502.
    """
    if not text or not text.strip():
        raise ValueError("text is required for TTS")
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    speed = max(0.25, min(4.0, float(speed)))
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    # Normalise model identifier — accept legacy aliases gracefully.
    model = (model or DEFAULT_TTS_MODEL).strip()
    if model not in LEGACY_TTS_MODELS and model not in INSTRUCTIONS_CAPABLE_MODELS:
        logger.warning("unknown TTS model '%s' — using %s", model, DEFAULT_TTS_MODEL)
        model = DEFAULT_TTS_MODEL

    # ── PRIMARY: Fish Audio ─────────────────────────────────────────
    # The customer-provided Fish Audio key is the new primary engine.
    # On any failure (no key, HTTP error, transport error, empty audio)
    # we transparently fall back to OpenAI / Emergent so the caller
    # never sees a 502 during the migration.
    fish_key = (os.environ.get("FISH_API_KEY") or "").strip()
    if fish_key:
        try:
            audio = await _fish_synthesize(text=text, lang=lang)
            logger.info("TTS via Fish Audio: %d bytes", len(audio))
            return audio
        except Exception as fish_err:  # noqa: BLE001
            logger.warning(
                "Fish Audio TTS failed, falling back to OpenAI: %s",
                fish_err,
            )

    # ── FALLBACK: OpenAI / Emergent (legacy path kept as safety net) ─
    try:
        return await _do_synthesize(
            text=text, voice=voice, speed=speed, model=model,
            instructions=instructions, lang=lang,
        )
    except Exception as e:  # noqa: BLE001
        # Provider-side rejection of the model (e.g. proxy whitelist):
        # gracefully downgrade to tts-1-hd which is universally available.
        msg = str(e).lower()
        if model != "tts-1-hd" and ("invalid model" in msg or "400" in msg):
            logger.warning(
                "TTS model '%s' rejected by provider — falling back to tts-1-hd: %s",
                model, e,
            )
            return await _do_synthesize(
                text=text, voice=voice, speed=speed, model="tts-1-hd",
                instructions=None, lang=lang,
            )
        raise


async def _do_synthesize(
    text: str,
    voice: str,
    speed: float,
    model: str,
    instructions: Optional[str],
    lang: Optional[str],
) -> bytes:
    """Inner TTS call — single attempt, no fallback logic."""
    use_instructions = model in INSTRUCTIONS_CAPABLE_MODELS
    effective_instructions = (
        _pick_instructions(lang, instructions) if use_instructions else None
    )

    provider = _get_clients()

    if provider == "openai":
        kwargs = {
            "model": model,
            "voice": voice,
            "input": text,
            "speed": speed,
            "response_format": "mp3",
        }
        if effective_instructions:
            kwargs["instructions"] = effective_instructions
        resp = await _openai_client.audio.speech.create(**kwargs)
        if hasattr(resp, "aread"):
            audio_bytes = await resp.aread()
        elif hasattr(resp, "read"):
            audio_bytes = resp.read()
        else:
            audio_bytes = getattr(resp, "content", b"")
    else:
        # Emergent path — go straight through litellm so we can pass
        # `instructions` (the emergent helper drops it).
        import litellm  # type: ignore

        params = {
            "model": f"openai/{model}",
            "input": text,
            "voice": voice,
            "api_key": _emergent_key,
            "api_base": _emergent_proxy_url,
            "custom_llm_provider": "openai",
        }
        if speed != 1.0:
            params["speed"] = speed
        if effective_instructions:
            params["instructions"] = effective_instructions

        resp = await litellm.aspeech(**params)

        if hasattr(resp, "content") and resp.content is not None:
            audio_bytes = resp.content
        elif hasattr(resp, "read"):
            audio_bytes = resp.read()
        else:
            audio_bytes = bytes(resp) if resp else b""

    if not audio_bytes:
        raise RuntimeError("TTS returned empty audio payload")
    return audio_bytes
