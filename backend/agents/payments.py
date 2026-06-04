"""
NXT8 payments — Stripe Checkout Sessions.

Fixed plan catalogue (price set by backend ONLY, never accepted from the
client — per Stripe integration security checklist). Each plan maps to a
flat monthly price in USD; the frontend only sends `plan_id` + `quantity`
(seats / employees) + the page origin.

Flow:
1.  Client → `POST /api/payments/checkout/session` with `{plan_id, quantity, origin}`.
2.  Backend looks up `PLANS[plan_id]`, computes amount, creates a pending
    `db.payment_transactions` row, then calls `StripeCheckout.create_checkout_session`.
3.  Backend returns `{ url, session_id }` to the client, which redirects.
4.  After payment, Stripe redirects user back to
    `<origin>/payment/return?session_id={CHECKOUT_SESSION_ID}`. The
    frontend then polls `GET /api/payments/checkout/status/{session_id}`
    until status flips to `paid` (or `expired`).
5.  Polling endpoint asks Stripe for the truth, updates the row exactly
    once (idempotent), and returns the final payment status.
6.  `POST /api/webhook/stripe` is exposed for Stripe → us push (Stripe
    is also queried directly by the polling path so the webhook is
    redundant but kept for production hygiene).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.db import get_db

logger = logging.getLogger("nxt8.payments")


# Fixed catalogue — keep in sync with the frontend pricing cards.
PLANS: Dict[str, Dict[str, Any]] = {
    "personal":     {"name": "Personal",     "amount_usd": 9.00,  "currency": "usd"},
    "team":         {"name": "Team",         "amount_usd": 14.00, "currency": "usd"},
    "operations":   {"name": "Operations",   "amount_usd": 19.00, "currency": "usd"},
    "headquarters": {"name": "Headquarters", "amount_usd": 24.00, "currency": "usd"},
}

MAX_QUANTITY = 500   # safety cap on seats per checkout


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stripe_key() -> str:
    key = (os.environ.get("STRIPE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("STRIPE_API_KEY not configured")
    return key


def _get_checkout(host_url: str):
    """Lazily import to keep cold-start cheap and avoid hard dep at
    module load if the library is missing."""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout  # type: ignore
    webhook_url = host_url.rstrip("/") + "/api/webhook/stripe"
    return StripeCheckout(api_key=_stripe_key(), webhook_url=webhook_url)


async def create_session(
    *,
    plan_id: str,
    quantity: int,
    origin: str,
    host_url: str,
    user_id: Optional[str] = None,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    plan = PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"unknown plan: {plan_id}")
    try:
        qty = max(1, min(int(quantity or 1), MAX_QUANTITY))
    except Exception:
        qty = 1

    amount = round(float(plan["amount_usd"]) * qty, 2)
    currency = plan["currency"]

    origin = (origin or "").rstrip("/")
    success_url = f"{origin}/payment/return?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{origin}/payment/cancel?plan={plan_id}"

    from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest  # type: ignore

    sc = _get_checkout(host_url)
    metadata = {
        "plan_id":    plan_id,
        "plan_name":  plan["name"],
        "quantity":   str(qty),
        "user_id":    user_id or "",
        "company_id": company_id or "",
        "source":     "nxt8_home_pricing",
    }
    req = CheckoutSessionRequest(
        amount=amount,
        currency=currency,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    resp = await sc.create_checkout_session(req)

    txn_id = str(uuid.uuid4())
    await get_db().payment_transactions.insert_one({
        "id":             txn_id,
        "session_id":     resp.session_id,
        "plan_id":        plan_id,
        "plan_name":      plan["name"],
        "quantity":       qty,
        "amount":         amount,
        "currency":       currency,
        "metadata":       metadata,
        "user_id":        user_id,
        "company_id":     company_id,
        "status":         "initiated",
        "payment_status": "pending",
        "created_at":     _now(),
        "updated_at":     _now(),
    })

    return {"url": resp.url, "session_id": resp.session_id, "transaction_id": txn_id}


async def get_status(*, session_id: str, host_url: str) -> Dict[str, Any]:
    """Poll Stripe + persist the result (idempotent).

    We bypass the emergentintegrations wrapper here because its
    `CheckoutStatusResponse` model fails to coerce Stripe's
    `StripeObject` metadata into a plain dict. We call the stripe SDK
    directly. For the legacy `sk_test_emergent` placeholder key we
    still mirror the library's emergent-proxy routing, but for real
    `sk_test_...` keys the SDK talks to Stripe directly.

    Falls back to the local snapshot only on real network failures —
    with a real Stripe key, retrieve answers correctly and the
    fallback path is never triggered.
    """
    import stripe
    api_key = _stripe_key()
    stripe.api_key = api_key
    if "sk_test_emergent" in api_key:
        stripe.api_base = "https://integrations.emergentagent.com/stripe"

    db = get_db()
    existing = await db.payment_transactions.find_one({"session_id": session_id})

    try:
        sess = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:  # noqa: BLE001
        # Graceful degradation — return our local snapshot.
        logger.info("stripe retrieve unavailable (%s); falling back to local state", e)
        if not existing:
            return {
                "session_id":     session_id,
                "status":         "unknown",
                "payment_status": "pending",
                "amount_total":   0,
                "currency":       "usd",
                "metadata":       {},
                "fallback":       "stripe_retrieve_unavailable",
            }
        return {
            "session_id":     session_id,
            "status":         existing.get("status") or "open",
            "payment_status": existing.get("payment_status") or "pending",
            "amount_total":   int((existing.get("amount") or 0) * 100),
            "currency":       existing.get("currency") or "usd",
            "metadata":       existing.get("metadata") or {},
            "fallback":       "stripe_retrieve_unavailable",
        }

    sess_status     = getattr(sess, "status", None) or "open"
    payment_status  = getattr(sess, "payment_status", None) or "unpaid"
    amount_total    = int(getattr(sess, "amount_total", 0) or 0)
    currency        = getattr(sess, "currency", "usd") or "usd"
    meta_raw        = getattr(sess, "metadata", None) or {}
    # Normalise StripeObject → plain dict. StripeObject empty-cases break
    # plain dict() on some SDK versions, so use to_dict_recursive() when
    # available and fall back to safe key iteration otherwise.
    metadata: Dict[str, str] = {}
    try:
        if hasattr(meta_raw, "to_dict_recursive"):
            metadata = {str(k): str(v) for k, v in meta_raw.to_dict_recursive().items()}
        elif hasattr(meta_raw, "keys"):
            metadata = {str(k): str(meta_raw[k]) for k in list(meta_raw.keys())}
        else:
            metadata = {str(k): str(v) for k, v in dict(meta_raw).items()}
    except Exception:
        metadata = {}

    # Merge: prefer values from Stripe, fall back to whatever we already
    # have locally (so the UI can still surface plan_name even if Stripe
    # responds with an empty metadata bag).
    merged_metadata = {**(existing.get("metadata") if existing else {} or {}), **metadata}

    if existing and existing.get("payment_status") != "paid":
        # Only update once — never flip a paid row backwards.
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status":         sess_status,
                "payment_status": payment_status,
                "amount_total":   amount_total,
                "updated_at":     _now(),
                "metadata":       merged_metadata,
            }},
        )

    return {
        "session_id":     session_id,
        "status":         sess_status,
        "payment_status": payment_status,
        "amount_total":   amount_total,
        "currency":       currency,
        "metadata":       merged_metadata,
    }


async def handle_webhook(body: bytes, signature: Optional[str], host_url: str) -> Dict[str, Any]:
    sc = _get_checkout(host_url)
    resp = await sc.handle_webhook(body, signature)
    # Best-effort persist — webhook is supplementary; the poll-based
    # update remains the source of truth.
    try:
        db = get_db()
        if resp.session_id:
            await db.payment_transactions.update_one(
                {"session_id": resp.session_id},
                {"$set": {
                    "webhook_event":   resp.event_type,
                    "payment_status":  resp.payment_status or "pending",
                    "updated_at":      _now(),
                }},
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("payments webhook persist failed: %s", e)
    return {
        "event_type":     resp.event_type,
        "event_id":       resp.event_id,
        "session_id":     resp.session_id,
        "payment_status": resp.payment_status,
    }


def plan_catalog() -> Dict[str, Any]:
    return {
        "plans": [
            {"id": pid, **{k: v for k, v in p.items()}}
            for pid, p in PLANS.items()
        ],
        "max_quantity": MAX_QUANTITY,
    }
