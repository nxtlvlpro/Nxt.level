"""
Generic webhook channel adapter.

A webhook channel accepts any JSON payload that contains at minimum
a `text` field (the user utterance) and optionally a `user_id`. This is
the lowest-friction integration path — any system that can POST JSON
can talk to NXT8 agents.

Optional HMAC-SHA256 signature verification keeps the endpoint safe
when a `signing_secret` is configured for the binding:

    X-NXT8-Signature: sha256=<hex>

where `<hex>` is HMAC-SHA256 of the raw request body with the channel's
`signing_secret` as key.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from .base import ChannelAdapter, InboundEvent, OutboundReply, _now

logger = logging.getLogger("nxt8.channels.webhook")


class WebhookAdapter(ChannelAdapter):
    kind = "webhook"

    async def parse(
        self,
        channel_id: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> InboundEvent:
        text = (payload.get("text") or payload.get("message") or "").strip()
        external_user = (
            payload.get("user_id")
            or payload.get("user")
            or payload.get("from")
            or "anon"
        )
        lang = (payload.get("lang") or payload.get("language") or "").lower() or None
        attachments = payload.get("attachments") or []
        if not isinstance(attachments, list):
            attachments = []
        return InboundEvent(
            channel_id=channel_id,
            channel_kind=self.kind,
            external_user_id=str(external_user),
            text=text,
            session_id=self.make_session_id(channel_id, str(external_user)),
            received_at=_now(),
            headers={k.lower(): v for k, v in (headers or {}).items()},
            raw=payload,
            attachments=attachments,
            lang=lang,
        )

    async def format(
        self,
        reply: OutboundReply,
        event: InboundEvent,
    ) -> Dict[str, Any]:
        return {
            "ok": True,
            "channel_id": event.channel_id,
            "session_id": event.session_id,
            "reply": {
                "text": reply.text,
                "agent": reply.agent,
                "routed_to": reply.routed_to,
                "request_id": reply.request_id,
                "confidence": reply.confidence,
                "tokens_total": reply.tokens_total,
                "sent_at": reply.sent_at or _now(),
            },
        }

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: Optional[str], secret: str) -> bool:
        """Constant-time HMAC-SHA256 verification.

        Returns True if `secret` is empty (signing disabled) or if the
        provided header is a valid signature for `raw_body`.
        """
        if not secret:
            return True
        if not signature_header:
            return False
        # Allow both "sha256=<hex>" and bare "<hex>" formats.
        sig = signature_header.strip()
        if sig.lower().startswith("sha256="):
            sig = sig.split("=", 1)[1]
        try:
            expected = hmac.new(
                secret.encode("utf-8"), raw_body, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(sig, expected)
        except Exception as e:  # noqa: BLE001
            logger.warning("hmac verify failed: %s", e)
            return False
