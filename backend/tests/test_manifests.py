"""
Tests for Agent Manifests — Constitution v1.0.

Verifies:
- every persona has a valid manifest with required fields
- chain of command has no cycles
- reports_to refers to a known agent or special "human_operator"
- can_delegate_to white-list refers to known agents
- data_access is well-formed
- prompt rendering produces meaningful text
- approval gate routes high-impact actions correctly
"""

from __future__ import annotations

import pytest

from agents import manifests as M


REQUIRED_FIELDS = ["id", "name", "role", "specialty", "decision_authority"]
KNOWN_AUTHORITY = {M.AUTHORITY_ADVISORY, M.AUTHORITY_WITH_APPROVAL, M.AUTHORITY_AUTONOMOUS}


# ---------------------------------------------------------------- Structure


def test_all_personas_present():
    expected = {"hermes", "hr_mentor", "client_manager", "project_coord",
                "analyst", "bookkeeper", "marketer", "compliance"}
    assert set(M.MANIFESTS.keys()) == expected, \
        f"missing personas: {expected - set(M.MANIFESTS.keys())}"


def test_graph_nodes_present():
    expected = {"hermes_check", "planner", "executor", "reviewer",
                "fixer", "hermes_validation", "joker"}
    assert set(M.GRAPH_NODE_MANIFESTS.keys()) == expected


@pytest.mark.parametrize("pid", list(M.MANIFESTS.keys()))
def test_persona_required_fields(pid):
    m = M.MANIFESTS[pid]
    for field in REQUIRED_FIELDS:
        assert field in m and m[field], f"{pid} missing {field}"
    assert m["decision_authority"] in KNOWN_AUTHORITY, \
        f"{pid} has invalid authority: {m['decision_authority']}"


@pytest.mark.parametrize("pid", list(M.MANIFESTS.keys()))
def test_persona_data_access_shape(pid):
    da = M.MANIFESTS[pid].get("data_access") or {}
    assert isinstance(da.get("read", []), list), f"{pid}: data_access.read must be list"
    assert isinstance(da.get("write", []), list), f"{pid}: data_access.write must be list"


# ----------------------------------------------------------- Chain of command


KNOWN_AGENTS = (
    set(M.MANIFESTS.keys())
    | set(M.GRAPH_NODE_MANIFESTS.keys())
    | {"human_operator"}
)


@pytest.mark.parametrize("pid", list(M.MANIFESTS.keys()))
def test_reports_to_is_known(pid):
    rt = M.MANIFESTS[pid].get("reports_to")
    assert rt in KNOWN_AGENTS, f"{pid}.reports_to -> unknown agent: {rt}"


@pytest.mark.parametrize("pid", list(M.MANIFESTS.keys()))
def test_can_delegate_to_is_known(pid):
    for target in M.MANIFESTS[pid].get("can_delegate_to") or []:
        assert target in M.MANIFESTS, \
            f"{pid}.can_delegate_to -> unknown persona: {target}"


def test_no_cycle_in_reports_to():
    """Walk the reports_to chain — must terminate at human_operator."""
    for pid in M.MANIFESTS:
        visited = []
        cur = pid
        for _ in range(20):
            if cur in visited:
                pytest.fail(f"cycle detected starting at {pid}: {visited}")
            visited.append(cur)
            m = M.get_manifest(cur)
            nxt = m.get("reports_to")
            if not nxt or nxt == "human_operator":
                break
            cur = nxt
        else:
            pytest.fail(f"reports_to chain from {pid} did not terminate: {visited}")


def test_only_hermes_delegates():
    """Per constitution: only Hermes has a non-empty can_delegate_to."""
    for pid, m in M.MANIFESTS.items():
        if pid == "hermes":
            assert m.get("can_delegate_to"), "Hermes must be able to delegate"
        else:
            assert not m.get("can_delegate_to"), \
                f"{pid} should delegate via Hermes, not directly"


# --------------------------------------------------------- Decision authority


def test_only_hermes_is_autonomous():
    autonomous_personas = [pid for pid, m in M.MANIFESTS.items()
                           if m["decision_authority"] == M.AUTHORITY_AUTONOMOUS]
    assert autonomous_personas == ["hermes"], \
        f"only Hermes should be autonomous, got: {autonomous_personas}"


def test_requires_approval_logic():
    # Advisory agents — high-impact requires approval
    assert M.requires_approval("hr_mentor", "create_task") is True
    # Low-impact even for advisory — no approval needed
    assert M.requires_approval("hr_mentor", "search_memory") is False
    # Hermes is autonomous — no approval needed even for high-impact
    assert M.requires_approval("hermes", "create_task") is False
    # With-approval agent + high-impact = approval needed
    assert M.requires_approval("client_manager", "create_task") is True
    # With-approval agent + low-impact = no approval
    assert M.requires_approval("client_manager", "search_memory") is False


# --------------------------------------------------------- Data access matrix


def test_can_read_write_helpers():
    # Hermes has wildcard read
    assert M.can_read("hermes", "tasks") is True
    assert M.can_read("hermes", "anything") is True
    # Compliance can read documents
    assert M.can_read("compliance", "documents") is True
    # Compliance CANNOT write to tasks
    assert M.can_write("compliance", "tasks") is False
    # Client manager can write tasks (with approval gate enforced elsewhere)
    assert M.can_write("client_manager", "tasks") is True
    # Bookkeeper is read-only
    assert M.can_write("bookkeeper", "roi_history") is False
    assert M.can_read("bookkeeper", "roi_history") is True


# ----------------------------------------------------------- Prompt rendering


def test_prompt_block_non_empty():
    for pid in M.MANIFESTS:
        block = M.render_manifest_for_prompt(pid)
        assert "КТО ТЫ ЕСТЬ" in block, f"{pid} prompt block lost header"
        assert pid in block, f"{pid} self-id missing in prompt"
        assert "Approval Gate" in block, f"{pid} prompt missing approval gate"


def test_unknown_agent_empty_prompt():
    assert M.render_manifest_for_prompt("does_not_exist") == ""


def test_high_impact_low_impact_disjoint():
    assert not (M.HIGH_IMPACT_ACTIONS & M.LOW_IMPACT_ACTIONS), \
        "an action cannot be both high- and low-impact"
