#!/usr/bin/env python3
"""
Verify database audit records for analyst and client_manager.
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

from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = "mongodb://127.0.0.1:27017"
DB_NAME = "nxt8"


async def get_db():
    """Get MongoDB connection."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


async def verify_audit_records():
    """Verify audit records in persona_requests collection."""
    print("\n" + "=" * 80)
    print("DATABASE AUDIT VERIFICATION")
    print("=" * 80)
    
    db = await get_db()
    
    # Check analyst records
    print("\n--- ANALYST RECORDS ---")
    analyst_records = await db.persona_requests.find(
        {"persona_id": "analyst"}
    ).sort("created_at", -1).limit(10).to_list(length=10)
    
    print(f"\nFound {len(analyst_records)} analyst records:")
    for i, record in enumerate(analyst_records, 1):
        print(f"\n{i}. Record ID: {record.get('id', 'unknown')[:12]}")
        print(f"   - provider: {record.get('provider')}")
        print(f"   - company_id: {record.get('company_id')}")
        print(f"   - user_id: {record.get('user_id')}")
        print(f"   - iterations: {record.get('iterations')}")
        print(f"   - confidence: {record.get('confidence')}")
        print(f"   - tool_traces: {len(record.get('tool_traces', []))} tools")
        
        for trace in record.get('tool_traces', []):
            print(f"     * {trace.get('name')}: ok={trace.get('result', {}).get('ok')}")
        
        print(f"   - message: {record.get('message', '')[:80]}...")
        print(f"   - created_at: {record.get('created_at')}")
    
    # Check client_manager records
    print("\n--- CLIENT_MANAGER RECORDS ---")
    cm_records = await db.persona_requests.find(
        {"persona_id": "client_manager"}
    ).sort("created_at", -1).limit(10).to_list(length=10)
    
    print(f"\nFound {len(cm_records)} client_manager records:")
    for i, record in enumerate(cm_records, 1):
        print(f"\n{i}. Record ID: {record.get('id', 'unknown')[:12]}")
        print(f"   - provider: {record.get('provider')}")
        print(f"   - company_id: {record.get('company_id')}")
        print(f"   - user_id: {record.get('user_id')}")
        print(f"   - iterations: {record.get('iterations')}")
        print(f"   - confidence: {record.get('confidence')}")
        print(f"   - tool_traces: {len(record.get('tool_traces', []))} tools")
        
        for trace in record.get('tool_traces', []):
            print(f"     * {trace.get('name')}: ok={trace.get('result', {}).get('ok')}")
        
        print(f"   - message: {record.get('message', '')[:80]}...")
        print(f"   - created_at: {record.get('created_at')}")
    
    # Verify all have provider='nxt8_graph'
    print("\n--- PROVIDER VERIFICATION ---")
    analyst_with_nxt8 = sum(1 for r in analyst_records if r.get('provider') == 'nxt8_graph')
    cm_with_nxt8 = sum(1 for r in cm_records if r.get('provider') == 'nxt8_graph')
    
    print(f"\nAnalyst records with provider='nxt8_graph': {analyst_with_nxt8}/{len(analyst_records)}")
    print(f"Client_manager records with provider='nxt8_graph': {cm_with_nxt8}/{len(cm_records)}")
    
    if analyst_with_nxt8 == len(analyst_records) and cm_with_nxt8 == len(cm_records):
        print("\n✅ All records have correct provider='nxt8_graph'")
    else:
        print("\n⚠ Some records have incorrect provider")
    
    # Check for tool invocations
    print("\n--- TOOL INVOCATION VERIFICATION ---")
    analyst_with_tools = sum(1 for r in analyst_records if len(r.get('tool_traces', [])) > 0)
    cm_with_tools = sum(1 for r in cm_records if len(r.get('tool_traces', [])) > 0)
    
    print(f"\nAnalyst records with tool invocations: {analyst_with_tools}/{len(analyst_records)}")
    print(f"Client_manager records with tool invocations: {cm_with_tools}/{len(cm_records)}")
    
    # Check specific tools
    analyst_evaluate_roi = sum(
        1 for r in analyst_records 
        if any(t.get('name') == 'evaluate_action_roi' for t in r.get('tool_traces', []))
    )
    cm_create_task = sum(
        1 for r in cm_records 
        if any(t.get('name') == 'create_task' for t in r.get('tool_traces', []))
    )
    
    print(f"\nAnalyst records with 'evaluate_action_roi': {analyst_evaluate_roi}")
    print(f"Client_manager records with 'create_task': {cm_create_task}")
    
    if analyst_evaluate_roi > 0 and cm_create_task > 0:
        print("\n✅ Tool invocations verified in audit records")
    else:
        print("\n⚠ Some expected tool invocations not found")


async def main():
    """Run audit verification."""
    try:
        await verify_audit_records()
        print("\n" + "=" * 80)
        print("✅ AUDIT VERIFICATION COMPLETED")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
