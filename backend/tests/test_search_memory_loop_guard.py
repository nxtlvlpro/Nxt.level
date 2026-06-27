"""
Test: search_memory Tool Loop Guard in nxt8_graph.py

Verifies that search_memory tool can only be called once per request
to prevent runaway loops and token waste on empty memory.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

# Test the tools_node function directly
from core.nxt8_graph import tools_node, AgentState, _extract_tool_calls


class TestAgentStateToolCounts:
    """Verify AgentState includes tool_counts field"""
    
    def test_agent_state_has_tool_counts_field(self):
        """AgentState TypedDict should include tool_counts: Dict[str, int]"""
        # Create a valid AgentState with tool_counts
        state: AgentState = {
            "messages": [],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "tokens_total": 0,
            "confidence": 0.7,
            "allowed_tools": ["search_memory"],
            "iterations": 0,
            "tool_counts": {"search_memory": 0},
            "mock": False,
        }
        assert "tool_counts" in state
        assert isinstance(state["tool_counts"], dict)


class TestToolsNodeCountsInitialization:
    """Verify tools_node initializes counts from state.get('tool_counts', {})"""
    
    @pytest.mark.asyncio
    async def test_tools_node_initializes_counts_from_empty_state(self):
        """When tool_counts is missing, should initialize to empty dict"""
        state: AgentState = {
            "messages": [{"role": "assistant", "content": "No tool call here"}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 0,
        }
        
        result = await tools_node(state)
        
        # Should return tool_counts in result
        assert "tool_counts" in result
        assert isinstance(result["tool_counts"], dict)
    
    @pytest.mark.asyncio
    async def test_tools_node_preserves_existing_counts(self):
        """When tool_counts exists, should preserve and build upon it"""
        state: AgentState = {
            "messages": [{"role": "assistant", "content": "No tool call here"}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 0,
            "tool_counts": {"other_tool": 5},
        }
        
        result = await tools_node(state)
        
        # Should preserve existing counts
        assert result["tool_counts"].get("other_tool") == 5


class TestToolsNodeIncrementsCount:
    """Verify tools_node increments counts[name] for each tool call"""
    
    @pytest.mark.asyncio
    async def test_tools_node_increments_count_on_first_call(self):
        """First search_memory call should increment count to 1"""
        tool_call_content = '''Here is a tool call:
```json
{"tool": "search_memory", "args": {"query": "test"}}
```
'''
        state: AgentState = {
            "messages": [{"role": "assistant", "content": tool_call_content}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 0,
            "tool_counts": {},
        }
        
        # Mock the HERMES_TOOLS to avoid actual execution
        mock_search_memory = AsyncMock(return_value={"ok": True, "results": []})
        
        with patch("core.nxt8_graph.HERMES_TOOLS", {"search_memory": mock_search_memory}):
            with patch("core.nxt8_graph.check_access", return_value=(True, None)):
                result = await tools_node(state)
        
        # Count should be incremented to 1
        assert result["tool_counts"]["search_memory"] == 1
        # Tool should have been executed
        mock_search_memory.assert_called_once()


class TestSearchMemoryGuard:
    """Verify search_memory guard prevents execution when counts > 1"""
    
    @pytest.mark.asyncio
    async def test_search_memory_blocked_on_second_call(self):
        """Second search_memory call should be skipped, not executed"""
        tool_call_content = '''Here is a tool call:
```json
{"tool": "search_memory", "args": {"query": "test"}}
```
'''
        state: AgentState = {
            "messages": [{"role": "assistant", "content": tool_call_content}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 0,
            "tool_counts": {"search_memory": 1},  # Already called once
        }
        
        mock_search_memory = AsyncMock(return_value={"ok": True, "results": []})
        
        with patch("core.nxt8_graph.HERMES_TOOLS", {"search_memory": mock_search_memory}):
            with patch("core.nxt8_graph.check_access", return_value=(True, None)):
                result = await tools_node(state)
        
        # Count should be incremented to 2
        assert result["tool_counts"]["search_memory"] == 2
        
        # Tool should NOT have been executed
        mock_search_memory.assert_not_called()
        
        # Should have a tool message with skipped result
        tool_messages = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        
        tool_result = json.loads(tool_messages[0]["content"])
        assert tool_result["ok"] is True
        assert tool_result["skipped"] is True
        assert "limit reached" in tool_result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_search_memory_allowed_on_first_call(self):
        """First search_memory call should execute normally"""
        tool_call_content = '''Here is a tool call:
```json
{"tool": "search_memory", "args": {"query": "test"}}
```
'''
        state: AgentState = {
            "messages": [{"role": "assistant", "content": tool_call_content}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 0,
            "tool_counts": {},  # No previous calls
        }
        
        mock_search_memory = AsyncMock(return_value={"ok": True, "results": ["memory1"]})
        
        with patch("core.nxt8_graph.HERMES_TOOLS", {"search_memory": mock_search_memory}):
            with patch("core.nxt8_graph.check_access", return_value=(True, None)):
                result = await tools_node(state)
        
        # Tool should have been executed
        mock_search_memory.assert_called_once()
        
        # Result should contain actual tool output
        tool_messages = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        
        tool_result = json.loads(tool_messages[0]["content"])
        assert tool_result["ok"] is True
        assert "skipped" not in tool_result
    
    @pytest.mark.asyncio
    async def test_other_tools_not_affected_by_guard(self):
        """Other tools should not be affected by search_memory guard"""
        tool_call_content = '''Here is a tool call:
```json
{"tool": "award_skill_points", "args": {"pattern": "test", "points": 10, "reason": "test"}}
```
'''
        state: AgentState = {
            "messages": [{"role": "assistant", "content": tool_call_content}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["award_skill_points"],
            "iterations": 0,
            "tool_counts": {"award_skill_points": 5},  # Called 5 times already
        }
        
        mock_award_points = AsyncMock(return_value={"ok": True, "points_awarded": 10})
        
        with patch("core.nxt8_graph.HERMES_TOOLS", {"award_skill_points": mock_award_points}):
            with patch("core.nxt8_graph.check_access", return_value=(True, None)):
                result = await tools_node(state)
        
        # Tool should still be executed (no guard for award_skill_points)
        mock_award_points.assert_called_once()
        
        # Count should be incremented
        assert result["tool_counts"]["award_skill_points"] == 6


class TestToolsNodeReturnPayload:
    """Verify tools_node return payload preserves existing keys and includes tool_counts"""
    
    @pytest.mark.asyncio
    async def test_return_payload_includes_tool_counts(self):
        """Return payload should include tool_counts"""
        state: AgentState = {
            "messages": [{"role": "assistant", "content": "No tool call"}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 2,
            "tool_counts": {"search_memory": 1},
        }
        
        result = await tools_node(state)
        
        # Must include tool_counts
        assert "tool_counts" in result
        # Must include messages
        assert "messages" in result
    
    @pytest.mark.asyncio
    async def test_return_payload_preserves_iterations(self):
        """Return payload should preserve iterations"""
        tool_call_content = '''```json
{"tool": "search_memory", "args": {"query": "test"}}
```'''
        state: AgentState = {
            "messages": [{"role": "assistant", "content": tool_call_content}],
            "skill_id": "general",
            "company_id": "test_co",
            "user_id": "test_user",
            "session_id": "test_session",
            "allowed_tools": ["search_memory"],
            "iterations": 2,
            "tool_counts": {},
        }
        
        mock_search_memory = AsyncMock(return_value={"ok": True, "results": []})
        
        with patch("core.nxt8_graph.HERMES_TOOLS", {"search_memory": mock_search_memory}):
            with patch("core.nxt8_graph.check_access", return_value=(True, None)):
                result = await tools_node(state)
        
        # iterations should be preserved
        assert result.get("iterations") == 2


class TestMaxIterationsUnchanged:
    """Verify MAX_ITERATIONS was not changed"""
    
    def test_max_iterations_is_3(self):
        """MAX_ITERATIONS should remain at 3"""
        from core.nxt8_graph import MAX_ITERATIONS
        assert MAX_ITERATIONS == 3


class TestExtractToolCalls:
    """Verify _extract_tool_calls helper function"""
    
    def test_extract_search_memory_call(self):
        """Should extract search_memory tool call from content"""
        content = '''Let me search for that:
```json
{"tool": "search_memory", "args": {"query": "sales data"}}
```
'''
        calls = _extract_tool_calls(content, ["search_memory"])
        
        assert len(calls) == 1
        assert calls[0]["name"] == "search_memory"
        assert calls[0]["args"]["query"] == "sales data"
    
    def test_extract_ignores_disallowed_tools(self):
        """Should ignore tools not in allowed_tools list"""
        content = '''```json
{"tool": "dangerous_tool", "args": {}}
```'''
        calls = _extract_tool_calls(content, ["search_memory"])
        
        assert len(calls) == 0
