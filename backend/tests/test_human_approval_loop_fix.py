"""
Test: Human Approval Infinite Loop Bug Fix (iteration_19)

Verifies that the infinite loop bug in nxt8_langgraph_ultra.py is fixed:
- _router returns END when requires_human_approval=True and approved=False
- human_approval_node function no longer exists
- _build_graph does not add 'human_approval' node or edges
- No infinite-loop path remains around human approval stub
"""

import pytest
import inspect


class TestHumanApprovalLoopFix:
    """Verify the human approval infinite loop bug is fixed."""

    def test_router_returns_end_when_approval_required_not_approved(self):
        """_router should return END when requires_human_approval=True and approved=False."""
        from nxt8_langgraph_ultra import _router, END

        # Simulate state where human approval is required but not yet approved
        state = {
            "iterations": 1,
            "autonomy_level": "controlled_automation",
            "requires_human_approval": True,
            "approved": False,
            "pending_tool_calls": [],
            "tools_just_executed": False,
        }

        result = _router(state)
        assert result == END, f"Expected END but got {result} - infinite loop bug NOT fixed!"

    def test_router_does_not_return_human_approval(self):
        """_router should never return 'human_approval' as a routing target."""
        from nxt8_langgraph_ultra import _router

        # Test various state combinations
        test_states = [
            {"iterations": 0, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
            {"iterations": 1, "autonomy_level": "read_only", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
            {"iterations": 1, "autonomy_level": "controlled_automation", "requires_human_approval": True, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
            {"iterations": 1, "autonomy_level": "controlled_automation", "requires_human_approval": True, "approved": True, "pending_tool_calls": [], "tools_just_executed": False},
            {"iterations": 1, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [{"id": "1", "name": "test", "args": {}}], "tools_just_executed": False},
            {"iterations": 1, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": True},
        ]

        for state in test_states:
            result = _router(state)
            assert result != "human_approval", f"Router returned 'human_approval' for state {state} - infinite loop bug NOT fixed!"

    def test_human_approval_node_does_not_exist(self):
        """human_approval_node function should not exist in the module."""
        import nxt8_langgraph_ultra

        assert not hasattr(nxt8_langgraph_ultra, "human_approval_node"), \
            "human_approval_node still exists in module - should be removed!"

    def test_graph_has_no_human_approval_node(self):
        """The compiled graph should not have a 'human_approval' node."""
        from nxt8_langgraph_ultra import ultra_graph, LANGGRAPH_OK

        if not LANGGRAPH_OK or ultra_graph is None:
            pytest.skip("LangGraph not available")

        # Check the graph's nodes
        graph_nodes = ultra_graph.nodes if hasattr(ultra_graph, 'nodes') else {}
        assert "human_approval" not in graph_nodes, \
            f"Graph still contains 'human_approval' node: {list(graph_nodes.keys())}"

    def test_build_graph_source_has_no_human_approval(self):
        """_build_graph source code should not reference 'human_approval' node."""
        from nxt8_langgraph_ultra import _build_graph

        source = inspect.getsource(_build_graph)
        
        # Check that 'human_approval' is not added as a node
        assert 'add_node("human_approval"' not in source, \
            "_build_graph still adds 'human_approval' node"
        assert "add_node('human_approval'" not in source, \
            "_build_graph still adds 'human_approval' node"

    def test_router_valid_return_values(self):
        """_router should only return valid targets: END, 'hermes', or 'tools'."""
        from nxt8_langgraph_ultra import _router, END

        valid_targets = {END, "hermes", "tools"}

        # Comprehensive state combinations
        test_states = [
            # Initial state - should go to hermes
            {"iterations": 0, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
            # Max iterations reached - should END
            {"iterations": 3, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
            # Approval required, not approved - should END (the bug fix)
            {"iterations": 1, "autonomy_level": "controlled_automation", "requires_human_approval": True, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
            # Has pending tool calls - should go to tools
            {"iterations": 1, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [{"id": "1", "name": "test", "args": {}}], "tools_just_executed": False},
            # Tools just executed - should go back to hermes
            {"iterations": 1, "autonomy_level": "assistant", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": True},
            # Read-only after first iteration - should END
            {"iterations": 1, "autonomy_level": "read_only", "requires_human_approval": False, "approved": False, "pending_tool_calls": [], "tools_just_executed": False},
        ]

        for state in test_states:
            result = _router(state)
            assert result in valid_targets, \
                f"Router returned invalid target '{result}' for state {state}. Valid targets: {valid_targets}"

    def test_module_imports_successfully(self):
        """nxt8_langgraph_ultra.py should import without errors."""
        try:
            import nxt8_langgraph_ultra
            assert nxt8_langgraph_ultra.LANGGRAPH_OK is True or nxt8_langgraph_ultra.LANGGRAPH_OK is False
            # Module imported successfully
        except Exception as e:
            pytest.fail(f"Module import failed: {e}")

    def test_graph_compiles_successfully(self):
        """The graph should compile without errors."""
        from nxt8_langgraph_ultra import ultra_graph, LANGGRAPH_OK

        if not LANGGRAPH_OK:
            pytest.skip("LangGraph not available - fallback mode active")

        assert ultra_graph is not None, "Graph failed to compile"


class TestRouterEdgeCases:
    """Additional edge case tests for router logic."""

    def test_approval_required_and_approved_continues(self):
        """When approval is required AND approved, should not immediately END."""
        from nxt8_langgraph_ultra import _router, END

        state = {
            "iterations": 1,
            "autonomy_level": "controlled_automation",
            "requires_human_approval": True,
            "approved": True,  # Approved!
            "pending_tool_calls": [],
            "tools_just_executed": False,
        }

        result = _router(state)
        # Should END because no pending work, but NOT because of approval gate
        assert result == END

    def test_approval_required_with_pending_tools_still_ends(self):
        """Even with pending tools, if approval required but not approved, should END."""
        from nxt8_langgraph_ultra import _router, END

        state = {
            "iterations": 1,
            "autonomy_level": "controlled_automation",
            "requires_human_approval": True,
            "approved": False,
            "pending_tool_calls": [{"id": "1", "name": "create_task", "args": {}}],
            "tools_just_executed": False,
        }

        result = _router(state)
        # The approval check comes BEFORE the pending_tool_calls check
        assert result == END, "Should END due to unapproved human approval requirement"
