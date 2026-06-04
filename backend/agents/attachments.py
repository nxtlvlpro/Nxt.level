"""
Universal attachment ingestion for the Hermes chat dialog.

Two purposes:
1. The Home / chat UI lets a user attach files (docs + images).
2. Hermes needs a short, human-readable summary of every attachment so
   it can reason about them in the conversation it answers next.

Routing:
* PDF / DOCX / TXT / MD  → delegate to `agents.documents.ingest_document`
                           (Compliance pipeline: extract text, chunk
                           into MemPalace, DeepSeek risk verdict).
* PNG / JPG / JPEG / WEBP → save on disk + OpenAI Vision (gpt-4o-mini)
                            short caption. Returns {caption, tags}.
* anything else          → save + register (no AI pass).

Files land under `/app/backend/uploads/attachments/<id>.<ext>` and are
served back via `GET /api/attachments/{id}` so the chat UI can preview
images.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.attachments")


UPLOAD_ROOT = Path("/app/backend/uploads/attachments")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 15 * 1024 * 1024  # 15 MB per attachment

DOC_EXTS = {".pdf", ".docx", ".txt", ".md"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TABLE_EXTS = {".csv", ".xlsx"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify(filename: str, mime: Optional[str]) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in DOC_EXTS:
        return "document"
    if ext in IMG_EXTS:
        return "image"
    if ext in TABLE_EXTS:
        return "table"
    if mime and mime.startswith("image/"):
        return "image"
    if mime in {"application/pdf", "text/plain", "text/markdown"}:
        return "document"
    return "other"


async def _vision_describe(image_path: Path, mime: str) -> Dict[str, Any]:
    """Run OpenAI gpt-4o-mini Vision on the saved image and return a
    short caption + tags. Returns {"caption": "", "tags": []} on any
    failure — the calling pipeline degrades gracefully."""
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not openai_key or openai_key.lower() in {"placeholder", "changeme", "your-key-here"}:
        return {"caption": "", "tags": [], "skipped": "no_openai_key"}
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai_key)
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime or 'image/png'};base64,{b64}"
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=180,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an attachment analyser for an enterprise AI assistant. "
                        "Given an image, return ONE short factual sentence describing what "
                        "is visible (max 35 words), followed by 3-6 lowercase comma-separated "
                        "tags on a new line prefixed with 'tags:'. No opinions, no greetings."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image for the chat context."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        caption = text
        tags: list[str] = []
        if "tags:" in text.lower():
            parts = text.split("tags:", 1) if "tags:" in text else text.split("Tags:", 1)
            caption = parts[0].strip().rstrip(".") + "."
            raw_tags = parts[1].strip()
            tags = [t.strip().lower() for t in raw_tags.split(",") if t.strip()][:6]
        return {"caption": caption, "tags": tags}
    except Exception as e:  # noqa: BLE001
        logger.warning("vision_describe failed: %s", e)
        return {"caption": "", "tags": [], "error": str(e)}


async def ingest_attachment(
    *,
    filename: str,
    content: bytes,
    company_id: str = "default",
    user_id: str = "anonymous",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Universal attachment ingest. Returns a dict the UI can chip and
    Hermes can read as context."""
    if not content:
        raise ValueError("empty file")
    if len(content) > MAX_BYTES:
        raise ValueError(f"file too large (max {MAX_BYTES // (1024 * 1024)} MB)")

    aid = str(uuid.uuid4())
    safe_name = filename or f"upload_{aid}"
    ext = Path(safe_name).suffix.lower() or ""
    mime = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    kind = _classify(safe_name, mime)

    # Persist to disk for all kinds — Hermes may want to re-read later.
    disk_path = UPLOAD_ROOT / f"{aid}{ext}"
    disk_path.write_bytes(content)

    record: Dict[str, Any] = {
        "id":         aid,
        "filename":   safe_name,
        "ext":        ext,
        "mime":       mime,
        "size":       len(content),
        "kind":       kind,
        "company_id": company_id,
        "user_id":    user_id,
        "session_id": session_id,
        "path":       str(disk_path),
        "created_at": _now(),
        "summary":    "",
        "tags":       [],
    }

    if kind == "document":
        from agents import documents as docs_agent
        try:
            doc = await docs_agent.ingest_document(
                filename=safe_name,
                content=content,
                company_id=company_id,
                user_id=user_id,
                title=None,
                notes=f"attached via chat session={session_id or '-'}",
            )
            record["document_id"] = doc.get("id")
            record["severity"]    = doc.get("severity")
            record["summary"]     = doc.get("summary") or ""
            record["findings"]    = doc.get("findings") or []
        except Exception as e:  # noqa: BLE001
            logger.warning("attachment->doc ingest failed: %s", e)
            record["summary"] = f"(не удалось разобрать документ: {e})"

    elif kind == "image":
        vis = await _vision_describe(disk_path, mime)
        record["summary"] = vis.get("caption") or ""
        record["tags"]    = vis.get("tags") or []
        if vis.get("skipped"):
            record["summary"] = "(image saved, vision analysis skipped)"

    else:
        record["summary"] = f"(file saved as-is, type {ext or mime})"

    # Persist a single row per attachment.
    try:
        await get_db().attachments.insert_one({**record})
    except Exception as e:  # noqa: BLE001
        logger.warning("attachments db insert failed: %s", e)

    return record


async def get_attachment(attachment_id: str) -> Optional[Dict[str, Any]]:
    doc = await get_db().attachments.find_one({"id": attachment_id}, {"_id": 0})
    return doc


async def list_attachments(session_id: Optional[str] = None,
                           limit: int = 50) -> list[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if session_id:
        q["session_id"] = session_id
    cur = get_db().attachments.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cur.to_list(length=limit)


def build_hermes_context_block(records: list[Dict[str, Any]]) -> str:
    """Compose a short system-message block describing the attached
    files so Hermes can refer to them in the reply."""
    if not records:
        return ""
    lines = ["The user attached the following files to this message:"]
    for r in records[:8]:
        bits = [f"- [{r.get('kind','file')}] {r.get('filename')}"]
        if r.get("summary"):
            bits.append(f": {r['summary']}")
        if r.get("severity"):
            bits.append(f" (compliance severity: {r['severity']})")
        if r.get("tags"):
            bits.append(f" — tags: {', '.join(r['tags'])}")
        lines.append("".join(bits))
    lines.append("Reference them naturally when relevant. Do not invent details "
                 "beyond what is summarised above.")
    return "\n".join(lines)
