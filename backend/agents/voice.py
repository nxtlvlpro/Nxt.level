"""
Voice module for NXT8.

Wraps OpenAI Whisper (STT) and OpenAI TTS via Emergent Universal LLM key.
Exposes two coroutines used by the FastAPI router in server.py:
    transcribe(file_bytes, filename, language) -> {text, language, duration}
    synthesize(text, voice, speed) -> bytes (mp3)
"""

from __future__ import annotations

import io
import logging
import os
from typing import Optional

from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

logger = logging.getLogger("nxt8.voice")

# Whisper accepts: mp3, mp4, mpeg, mpga, m4a, wav, webm
ALLOWED_AUDIO_EXT = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg"}
ALLOWED_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}
DEFAULT_VOICE = "nova"
DEFAULT_TTS_MODEL = "tts-1"
MAX_TTS_CHARS = 4000


def _api_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured in backend/.env")
    return key


_stt_client: Optional[OpenAISpeechToText] = None
_tts_client: Optional[OpenAITextToSpeech] = None


def _stt() -> OpenAISpeechToText:
    global _stt_client
    if _stt_client is None:
        _stt_client = OpenAISpeechToText(api_key=_api_key())
    assert _stt_client is not None  # for type checkers
    return _stt_client


def _tts() -> OpenAITextToSpeech:
    global _tts_client
    if _tts_client is None:
        _tts_client = OpenAITextToSpeech(api_key=_api_key())
    assert _tts_client is not None  # for type checkers
    return _tts_client


async def transcribe(
    file_bytes: bytes,
    filename: str = "audio.webm",
    language: Optional[str] = None,
) -> dict:
    """Whisper STT — returns transcript + metadata."""
    if not file_bytes:
        raise ValueError("empty audio payload")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    if ext not in ALLOWED_AUDIO_EXT:
        # browsers often produce audio/webm;codecs=opus — coerce to webm
        ext = "webm"
        filename = f"audio.{ext}"

    buf = io.BytesIO(file_bytes)
    buf.name = filename  # OpenAI SDK looks at .name for format detection

    kwargs = {"file": buf, "model": "whisper-1", "response_format": "verbose_json"}
    if language:
        kwargs["language"] = language

    resp = await _stt().transcribe(**kwargs)

    text = getattr(resp, "text", "") or ""
    detected_lang = getattr(resp, "language", language or "")
    duration = getattr(resp, "duration", None)

    return {
        "text": text.strip(),
        "language": detected_lang,
        "duration": duration,
        "model": "whisper-1",
    }


async def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    model: str = DEFAULT_TTS_MODEL,
) -> bytes:
    """OpenAI TTS — returns mp3 bytes."""
    if not text or not text.strip():
        raise ValueError("text is required for TTS")
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    speed = max(0.25, min(4.0, float(speed)))
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    audio_bytes = await _tts().generate_speech(
        text=text,
        model=model,
        voice=voice,
        speed=speed,
        response_format="mp3",
    )
    return audio_bytes
