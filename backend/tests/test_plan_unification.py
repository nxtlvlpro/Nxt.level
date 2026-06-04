"""Plan unification regression.

After the 2026-06-04 sync, the canonical Stripe plan ids
(personal / team / operations / headquarters) MUST work everywhere
in the codebase, AND the legacy ids (basic / simple / pro / enterprise)
MUST keep working via aliases — otherwise old clients break.
"""

import asyncio

import pytest

from agents import personas as p
from agents.manifests import MANIFESTS
from agents.payments import PLANS as STRIPE_PLANS


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------- catalogue parity
def test_canonical_plans_match_stripe_catalogue():
    """personas.PLANS canonical keys must match agents.payments.PLANS."""
    canonical = {"personal", "team", "operations", "headquarters"}
    assert set(STRIPE_PLANS.keys()) == canonical
    # personas.PLANS exposes BOTH canonical and legacy keys
    for k in canonical:
        assert k in p.PLANS, f"missing canonical plan id: {k}"


def test_legacy_aliases_resolve_to_canonical():
    """Legacy ids must still return a plan (via PLAN_ALIASES)."""
    for legacy in ("basic", "simple", "pro", "enterprise"):
        assert legacy in p.PLANS, f"legacy alias missing: {legacy}"

    assert p.get_plan("basic")["id"] == "personal"
    assert p.get_plan("simple")["id"] == "team"
    assert p.get_plan("pro")["id"] == "operations"
    assert p.get_plan("enterprise")["id"] == "headquarters"
    assert p.get_plan("hq")["id"] == "headquarters"
    assert p.get_plan("pilot")["id"] == "personal"
    # garbage falls back to top tier
    assert p.get_plan("totally_unknown")["id"] == "headquarters"


# ---------------------------------------------------- price parity
@pytest.mark.parametrize("canonical,expected", [
    ("personal", 9),
    ("team", 14),
    ("operations", 19),
    ("headquarters", 24),
])
def test_personas_plan_prices_match_stripe(canonical, expected):
    assert p.PLANS[canonical]["price_usd"] == expected
    assert STRIPE_PLANS[canonical]["amount_usd"] == float(expected)


# ---------------------------------------------------- min_plan_for
def test_min_plan_for_uses_canonical_ids():
    """Sanity: the cheapest plan that includes each persona is canonical."""
    canonical = {"personal", "team", "operations", "headquarters"}
    assert p._min_plan_for("hermes") == "personal"
    assert p._min_plan_for("hr_mentor") == "team"
    assert p._min_plan_for("client_manager") == "team"
    assert p._min_plan_for("bookkeeper") == "operations"
    assert p._min_plan_for("marketer") == "operations"
    assert p._min_plan_for("compliance") == "operations"
    assert p._min_plan_for("project_coord") == "headquarters"
    assert p._min_plan_for("analyst") == "headquarters"
    # all returned ids are canonical
    for pid in p.PERSONAS.keys():
        assert p._min_plan_for(pid) in canonical


# ---------------------------------------------------- manifests tier sync
def test_manifest_tariff_tiers_are_canonical():
    """manifests[*].tariff_tier MUST be a canonical id."""
    canonical = {"personal", "team", "operations", "headquarters"}
    for pid, m in MANIFESTS.items():
        tier = m.get("tariff_tier")
        assert tier in canonical, f"{pid} has non-canonical tariff_tier={tier!r}"


def test_manifest_tier_matches_min_plan():
    """The manifest's tariff_tier MUST equal personas._min_plan_for(pid)."""
    for pid in MANIFESTS:
        if pid == "hermes":
            continue  # Hermes manifest says "personal" but Hermes is on every plan
        assert MANIFESTS[pid]["tariff_tier"] == p._min_plan_for(pid), pid


# ---------------------------------------------------- gating
def test_gating_via_canonical_plan():
    """Persona-on-plan checks must work with canonical ids."""
    assert "bookkeeper" not in p.get_plan("personal")["personas"]
    assert "bookkeeper" in p.get_plan("operations")["personas"]
    assert "analyst" not in p.get_plan("operations")["personas"]
    assert "analyst" in p.get_plan("headquarters")["personas"]


def test_gating_via_legacy_alias():
    """Old client passes plan_id='pro' → should grant Operations bundle."""
    assert "bookkeeper" in p.get_plan("pro")["personas"]
    assert "marketer" in p.get_plan("pro")["personas"]
    assert "analyst" not in p.get_plan("pro")["personas"]


def test_run_persona_rejects_persona_above_plan():
    async def _go():
        res = await p.run_persona(
            persona_id="analyst",
            message="ping",
            plan_id="team",
        )
        assert res["success"] is False
        # required_plan must be canonical
        assert res["required_plan"] == "headquarters"
        assert res["current_plan"] == "team"

    _run(_go())
