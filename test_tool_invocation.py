#!/usr/bin/env python3
"""
Focused test to verify tool invocation for analyst and client_manager.
"""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
ROOT_DIR = Path(__file__).parent / "backend"
load_dotenv(ROOT_DIR / ".env")

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


async def test_analyst_tool_invocation():
    """Test analyst with explicit tool invocation request."""
    print("\n" + "=" * 80)
    print("TEST: Analyst tool invocation (evaluate_action_roi)")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # More explicit message that should trigger evaluate_action_roi
    test_message = """Мне нужно оценить ROI следующего действия: 
    "Запустить email-кампанию по реактивации dormant B2B лидов за последние 6 месяцев"
    
    Используй инструмент evaluate_action_roi для оценки."""
    
    result = await personas_agent.run_persona(
        persona_id="analyst",
        message=test_message,
        company_id="test_tool_analyst",
        user_id="test_tool_user",
        session_id="test_tool_session_001",
        plan_id="headquarters",
    )
    
    print(f"\n✓ Response received")
    print(f"  - success: {result.get('success')}")
    print(f"  - provider: {result.get('provider')}")
    print(f"  - iterations: {result.get('iterations')}")
    print(f"  - tool_traces count: {len(result.get('tool_traces', []))}")
    
    tool_traces = result.get("tool_traces", [])
    if tool_traces:
        print(f"\n✓ Tools called:")
        for trace in tool_traces:
            print(f"  - {trace.get('name')}: ok={trace.get('result', {}).get('ok')}")
    else:
        print(f"\n⚠ No tools were called")
        print(f"\nResponse content preview:")
        print(f"  {result.get('content', '')[:500]}")
    
    return result


async def test_client_manager_tool_invocation():
    """Test client_manager with explicit tool invocation request."""
    print("\n" + "=" * 80)
    print("TEST: Client Manager tool invocation (create_task)")
    print("=" * 80)
    
    from agents import personas as personas_agent
    
    # Explicit message that should trigger create_task
    test_message = """Создай задачу: 
    Отправить follow-up письмо клиенту TechCorp с резюме встречи и предложением следующего звонка на пятницу.
    
    Используй инструмент create_task."""
    
    result = await personas_agent.run_persona(
        persona_id="client_manager",
        message=test_message,
        company_id="test_tool_cm",
        user_id="test_tool_user_cm",
        session_id="test_tool_session_cm_001",
        plan_id="team",
    )
    
    print(f"\n✓ Response received")
    print(f"  - success: {result.get('success')}")
    print(f"  - provider: {result.get('provider')}")
    print(f"  - iterations: {result.get('iterations')}")
    print(f"  - tool_traces count: {len(result.get('tool_traces', []))}")
    
    tool_traces = result.get("tool_traces", [])
    if tool_traces:
        print(f"\n✓ Tools called:")
        for trace in tool_traces:
            print(f"  - {trace.get('name')}: ok={trace.get('result', {}).get('ok')}")
            if trace.get('name') == 'create_task':
                print(f"    args: {trace.get('args', {})}")
    else:
        print(f"\n⚠ No tools were called")
        print(f"\nResponse content preview:")
        print(f"  {result.get('content', '')[:500]}")
    
    return result


async def main():
    """Run focused tool invocation tests."""
    print("\n" + "=" * 80)
    print("FOCUSED TEST: Tool invocation for analyst & client_manager")
    print("=" * 80)
    
    try:
        await test_analyst_tool_invocation()
        await test_client_manager_tool_invocation()
        
        print("\n" + "=" * 80)
        print("✅ TOOL INVOCATION TESTS COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
