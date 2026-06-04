"""
Channel adapter base types — normalised event shapes shared by every
inbound channel (webhook, Slack, WhatsApp, Email, CRM, …).

Adapter implementations must produce `InboundEvent` instances and accept
`OutboundReply` instances back, never raw dicts. This isolation lets the
core agent layer (Hermes, JOKER, personas) stay channel-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Normalised event shapes
# ---------------------------------------------------------------------


@dataclass
class InboundEvent:
    """A channel-agnostic event landing on the gateway."""

    channel_id: str
    channel_kind: str            # "webhook" | "slack" | "whatsapp" | "email" | "crm" | ...
    external_user_id: str        # who sent it on the external side
    text: str                    # main payload — the user utterance
    session_id: str              # stable per (channel_id, external_user_id) pair
    received_at: str             # ISO timestamp
    headers: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)   # original payload (audit only)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    lang: Optional[str] = None


@dataclass
class OutboundReply:
    """A channel-agnostic reply from an agent back to the originator."""

    text: str
    agent: str                   # "hermes" | "joker" | "persona:hr_mentor" | ...
    routed_to: Optional[str] = None  # if classifier intercepted
    tokens_total: int = 0
    confidence: float = 0.7
    request_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    sent_at: Optional[str] = None


@dataclass
class ChannelBinding:
    """
    A binding maps an `(channel_id, intent_filter)` tuple to a single
    target agent. Most-specific-first matching (longer / more specific
    `intent_filter` wins). Empty `intent_filter` matches everything.
    """

    channel_id: str
    channel_kind: str
    agent: str                   # one of: "hermes" | "joker" | "persona:<id>" | "auto"
    intent_filter: str = ""      # regex (case-insensitive)
    name: str = ""
    signing_secret: str = ""     # HMAC secret for webhook channels
    active: bool = True
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "channel_kind": self.channel_kind,
            "agent": self.agent,
            "intent_filter": self.intent_filter,
            "name": self.name,
            "signing_secret": "***" if self.signing_secret else "",
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------
# Adapter contract
# ---------------------------------------------------------------------


class ChannelAdapter(ABC):
    """Each transport (webhook, slack, …) ships its own adapter subclass."""

    kind: str = "base"

    @abstractmethod
    async def parse(
        self,
        channel_id: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> InboundEvent:
        """Translate raw HTTP payload into a normalised InboundEvent."""

    @abstractmethod
    async def format(
        self,
        reply: OutboundReply,
        event: InboundEvent,
    ) -> Dict[str, Any]:
        """Translate an OutboundReply into the channel's response shape."""

    @staticmethod
    def make_session_id(channel_id: str, external_user_id: str) -> str:
        # Stable, deterministic session id so a returning external user keeps
        # context across calls without us having to negotiate one out-of-band.
        return f"{channel_id}:{external_user_id or 'anon'}"
