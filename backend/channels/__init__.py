"""
NXT8 Channel adapters — the ingress layer for inbound traffic from
external systems (webhooks, Slack, WhatsApp, Email, CRM, …).

Inspired by Wingman-AI's channel/bindings model, ported to FastAPI +
MongoDB + the existing NXT8 agent surface (Hermes / JOKER / Personas).

The flow is intentionally narrow and uniform:

    External system ──HTTP──▶ Channel adapter
                                   │
                                   │ normalise to InboundEvent
                                   ▼
                              Bindings registry  ◀── channels.json /
                                   │                  db.channel_bindings
                                   │
                                   ▼
                              Selected agent (hermes / joker / persona)
                                   │
                                   │ produces OutboundReply
                                   ▼
                              Channel adapter formats and returns it

Each adapter implements two methods:

    async def parse(self, payload: dict, headers: dict) -> InboundEvent
    async def format(self, reply: OutboundReply) -> dict

The registry resolves `binding.agent` to a concrete handler defined in
`channels.handlers`. This keeps the channels package free of upstream
imports and avoids any circular dependency with `agents/`.
"""

from .base import (
    InboundEvent,
    OutboundReply,
    ChannelAdapter,
    ChannelBinding,
)
from .registry import (
    list_bindings,
    get_binding,
    upsert_binding,
    delete_binding,
    invoke_agent_for_binding,
)

__all__ = [
    "InboundEvent",
    "OutboundReply",
    "ChannelAdapter",
    "ChannelBinding",
    "list_bindings",
    "get_binding",
    "upsert_binding",
    "delete_binding",
    "invoke_agent_for_binding",
]
