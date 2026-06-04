"""
NXT8 — Share-My-Journey (viral marketing channel).

When a visitor finishes the Test Drive tour, they can mint a public,
shareable link. The link:

  • carries a short, URL-safe `share_id`
  • renders a 1200×630 OG card (PNG via Pillow) so messengers and social
    networks preview a branded "Я попробовал NXT8" image
  • records `open` events (with optional `ref` source) and per-share
    conversion to checkout via `track_conversion()`.

We surface a top-level funnel stat — minted_shares → opens → conversions —
to evaluate the viral channel cheaply, without third-party trackers.
"""

from __future__ import annotations

import io
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.share")


SHARE_ID_LEN = 8       # ~48 bits of entropy — collision risk negligible for ≪1M shares
MAX_HEADLINE_LEN = 140
DEFAULT_HEADLINE = "Я попробовал NXT8 за 3 минуты — реальная AI-команда для бизнеса"

_VALID_SHARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,16}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_share_id() -> str:
    return secrets.token_urlsafe(SHARE_ID_LEN)[:SHARE_ID_LEN]


async def ensure_indexes() -> None:
    db = get_db()
    await db.shares.create_index("share_id", unique=True)
    await db.shares.create_index([("client_id", 1), ("created_at", -1)])
    await db.share_events.create_index([("share_id", 1), ("created_at", -1)])
    await db.share_events.create_index([("event", 1), ("created_at", -1)])


# ---------------------------------------------------------------- mint
async def mint_share(
    *,
    client_id: str,
    completed_steps: Optional[List[str]] = None,
    headline: Optional[str] = None,
    locale: str = "ru",
) -> Dict[str, Any]:
    """Mint a new shareable journey link for the given client."""
    db = get_db()
    safe_headline = (headline or DEFAULT_HEADLINE).strip()[:MAX_HEADLINE_LEN]
    safe_steps = [s for s in (completed_steps or []) if isinstance(s, str)][:20]

    # Best-effort uniqueness — retry a couple of times on the (very unlikely)
    # collision instead of crashing.
    for _ in range(4):
        sid = _new_share_id()
        try:
            doc = {
                "share_id":        sid,
                "client_id":       (client_id or "anon").strip()[:64] or "anon",
                "headline":        safe_headline,
                "completed_steps": safe_steps,
                "locale":          locale,
                "created_at":      _now(),
                "opens":           0,
                "conversions":     0,
            }
            await db.shares.insert_one(doc)
            return {
                "ok":         True,
                "share_id":   sid,
                "headline":   safe_headline,
                "created_at": doc["created_at"],
            }
        except Exception as e:  # noqa: BLE001
            # DuplicateKeyError or similar — try a fresh id.
            logger.warning("share mint retry: %s", e)
    return {"ok": False, "error": "could_not_mint"}


# ---------------------------------------------------------------- fetch
async def get_share(share_id: str) -> Optional[Dict[str, Any]]:
    if not _VALID_SHARE_ID_RE.match(share_id or ""):
        return None
    return await get_db().shares.find_one({"share_id": share_id}, {"_id": 0})


# ---------------------------------------------------------------- events
async def record_open(
    share_id: str,
    *,
    ref: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    if not _VALID_SHARE_ID_RE.match(share_id or ""):
        return {"ok": False, "error": "bad_share_id"}
    db = get_db()
    rec = await db.shares.find_one_and_update(
        {"share_id": share_id},
        {"$inc": {"opens": 1}, "$set": {"last_opened_at": _now()}},
        projection={"_id": 0, "share_id": 1, "opens": 1},
    )
    if not rec:
        return {"ok": False, "error": "not_found"}
    await db.share_events.insert_one({
        "share_id":  share_id,
        "event":     "open",
        "ref":       (ref or "")[:64] or None,
        "ua":        (user_agent or "")[:200] or None,
        "created_at": _now(),
    })
    return {"ok": True, "opens": int(rec.get("opens", 0)) + 1}


async def track_conversion(share_id: str, kind: str = "checkout") -> Dict[str, Any]:
    """Called by the checkout flow when a visitor arrived via ?ref=<share_id>."""
    if not _VALID_SHARE_ID_RE.match(share_id or ""):
        return {"ok": False, "error": "bad_share_id"}
    db = get_db()
    rec = await db.shares.find_one_and_update(
        {"share_id": share_id},
        {"$inc": {"conversions": 1}, "$set": {"last_conversion_at": _now()}},
        projection={"_id": 0, "share_id": 1, "conversions": 1},
    )
    if not rec:
        return {"ok": False, "error": "not_found"}
    await db.share_events.insert_one({
        "share_id":   share_id,
        "event":      "conversion",
        "kind":       kind,
        "created_at": _now(),
    })
    return {"ok": True, "conversions": int(rec.get("conversions", 0)) + 1}


# ---------------------------------------------------------------- aggregate
async def stats(window_hours: int = 24 * 30) -> Dict[str, Any]:
    db = get_db()
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(hours=window_hours)
    ).isoformat()
    minted = await db.shares.count_documents({"created_at": {"$gte": cutoff_iso}})

    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff_iso}}},
        {"$group": {"_id": "$event", "count": {"$sum": 1}}},
    ]
    counts = {row["_id"]: int(row["count"]) async for row in db.share_events.aggregate(pipeline)}
    opens = counts.get("open", 0)
    conversions = counts.get("conversion", 0)
    return {
        "ok":           True,
        "window_hours": window_hours,
        "minted":       minted,
        "opens":        opens,
        "conversions":  conversions,
        "open_per_mint":      round(opens / minted, 3) if minted else None,
        "conversion_per_open": round(conversions / opens, 3) if opens else None,
    }


# ---------------------------------------------------------------- OG card
def _load_font(size: int):
    """Best-effort font lookup — falls back to PIL default if Vera missing."""
    try:
        from PIL import ImageFont
        # reportlab ships Vera — usually present in the env.
        return ImageFont.truetype(
            "/opt/plugins-venv/lib/python3.11/site-packages/reportlab/fonts/Vera.ttf",
            size=size,
        )
    except Exception:  # noqa: BLE001
        try:
            from PIL import ImageFont
            return ImageFont.load_default()
        except Exception:  # noqa: BLE001
            return None


def render_og_card_png(headline: str, *, share_id: str) -> bytes:
    """Render the 1200×630 Open Graph card as PNG bytes."""
    from PIL import Image, ImageDraw

    W, H = 1200, 630
    bg = (8, 14, 18)            # near-black with cyan tint
    accent = (0, 240, 255)      # NXT8 turquoise
    text = (235, 245, 248)
    muted = (140, 168, 180)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img, "RGBA")

    # Decorative grid (very subtle)
    for x in range(0, W, 48):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 6), width=1)
    for y in range(0, H, 48):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 6), width=1)

    # Accent corner glow
    for i in range(0, 240, 12):
        draw.ellipse(
            [(-i, H - 240 - i), (240 + i, H + i)],
            outline=(0, 240, 255, max(0, 22 - i // 14)),
            width=2,
        )

    # Brand band
    draw.rectangle([(0, 0), (W, 6)], fill=accent)

    # Logo strip
    f_brand = _load_font(34)
    f_brand_dim = _load_font(24)
    if f_brand:
        draw.text((56, 56), "NXT8", font=f_brand, fill=accent)
        draw.text((146, 64), "// AI company OS", font=f_brand_dim, fill=muted)

    # Headline — wrap into 3 lines max
    f_h = _load_font(58)
    f_h_small = _load_font(46)
    headline_text = (headline or DEFAULT_HEADLINE).strip()
    lines = _wrap_text(headline_text, max_chars=42, max_lines=3)
    use_font = f_h if max(len(line) for line in lines) <= 36 else f_h_small
    y = 200
    for line in lines:
        draw.text((56, y), line, font=use_font, fill=text)
        y += (use_font.size if use_font else 56) + 12

    # Foot row — share_id chip + CTA
    f_meta = _load_font(22)
    if f_meta:
        chip_x = 56
        chip_y = H - 96
        chip_text = f"?ref={share_id}"
        # measure
        try:
            bbox = draw.textbbox((0, 0), chip_text, font=f_meta)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = 200, 24
        draw.rectangle(
            [(chip_x, chip_y), (chip_x + tw + 28, chip_y + th + 18)],
            outline=accent, width=2,
        )
        draw.text((chip_x + 14, chip_y + 8), chip_text, font=f_meta, fill=accent)

        cta = "nxt8.pro"
        try:
            bbox = draw.textbbox((0, 0), cta, font=f_meta)
            cta_w = bbox[2] - bbox[0]
        except Exception:
            cta_w = 120
        draw.text(
            (W - 56 - cta_w, chip_y + 8),
            cta, font=f_meta, fill=text,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _wrap_text(s: str, *, max_chars: int = 42, max_lines: int = 3) -> List[str]:
    words = (s or "").split()
    if not words:
        return [""]
    lines: List[str] = [""]
    for w in words:
        if not lines[-1]:
            lines[-1] = w
        elif len(lines[-1]) + 1 + len(w) <= max_chars:
            lines[-1] += " " + w
        elif len(lines) < max_lines:
            lines.append(w)
        else:
            # overflow → ellipsis on the last line
            if lines[-1].endswith("…"):
                continue
            if len(lines[-1]) + 1 < max_chars:
                lines[-1] += " …"
            break
    return lines
