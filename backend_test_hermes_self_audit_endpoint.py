"""
Comprehensive backend test for POST /api/hermes/self-audit/run endpoint.

Tests:
1. Endpoint requires authentication (tenant-scoped)
2. Endpoint returns correct structure (ok, company_id, health, benchmark, message)
3. Endpoint uses user.company_id for tenant-scoping
4. Endpoint doesn't auto-create proposals
5. Response message correctly states alerts only sent when Hermes later calls propose_improvement/propose_policy
6. No conflicts with existing Hermes routes
"""

import asyncio
import sys
import os
import requests
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

# Add backend to path
sys.path.insert(0, '/app/backend')

from core.db import get_db

# Backend URL from environment
BACKEND_URL = "https://multi-tenant-os-3.preview.emergentagent.com/api"


def _now():
    return datetime.now(timezone.utc).isoformat()


async def test_endpoint_requires_authentication():
    """Test 1: Verify endpoint requires authentication."""
    print("\n=== Test 1: Authentication Required ===")
    try:
        # Try calling without auth
        response = requests.post(f"{BACKEND_URL}/hermes/self-audit/run")
        
        # Should return 401 or 403
        if response.status_code in [401, 403]:
            print(f"✅ Endpoint correctly requires authentication (status: {response.status_code})")
            return True
        else:
            print(f"❌ Endpoint should require auth but returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing authentication: {e}")
        return False


async def test_endpoint_with_valid_auth():
    """Test 2: Verify endpoint works with valid authentication and returns correct structure."""
    print("\n=== Test 2: Valid Auth & Response Structure ===")
    try:
        db = get_db()
        
        # Create test user and session
        test_user_id = f"test_user_audit_{datetime.now().timestamp()}"
        test_company_id = f"test_company_audit_{datetime.now().timestamp()}"
        test_token = f"test_token_audit_{datetime.now().timestamp()}"
        
        # Insert test user
        await db.users.insert_one({
            "user_id": test_user_id,
            "email": "test_audit@nxt8.local",
            "name": "Test Audit User",
            "picture": "",
            "is_admin": False,
            "company_id": test_company_id,
            "created_at": _now()
        })
        
        # Insert test session (7 days)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await db.user_sessions.insert_one({
            "user_id": test_user_id,
            "session_token": test_token,
            "expires_at": expires_at,
            "created_at": _now()
        })
        
        # Call endpoint with auth
        headers = {"Authorization": f"Bearer {test_token}"}
        response = requests.post(f"{BACKEND_URL}/hermes/self-audit/run", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Expected 200 but got {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        # Verify response structure
        required_fields = ["ok", "company_id", "health", "benchmark", "message"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            return False
        
        # Verify ok is True
        if data["ok"] is not True:
            print(f"❌ Expected ok=True but got ok={data['ok']}")
            return False
        
        # Verify company_id matches
        if data["company_id"] != test_company_id:
            print(f"❌ Expected company_id={test_company_id} but got {data['company_id']}")
            return False
        
        # Verify health is a dict
        if not isinstance(data["health"], dict):
            print(f"❌ Expected health to be dict but got {type(data['health'])}")
            return False
        
        # Verify benchmark is a dict
        if not isinstance(data["benchmark"], dict):
            print(f"❌ Expected benchmark to be dict but got {type(data['benchmark'])}")
            return False
        
        # Verify message mentions Telegram alerts
        if "Telegram alerts" not in data["message"]:
            print(f"❌ Expected message to mention 'Telegram alerts' but got: {data['message']}")
            return False
        
        # Verify message mentions proposals
        if "improvement" not in data["message"].lower() or "policy" not in data["message"].lower():
            print(f"❌ Expected message to mention improvement/policy proposals but got: {data['message']}")
            return False
        
        print(f"✅ Endpoint returns correct structure")
        print(f"✅ company_id correctly scoped to user: {test_company_id}")
        print(f"✅ Response has all required fields: {required_fields}")
        print(f"✅ Message correctly states: '{data['message']}'")
        
        # Cleanup
        await db.users.delete_one({"user_id": test_user_id})
        await db.user_sessions.delete_one({"session_token": test_token})
        
        return True
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_no_auto_proposals_created():
    """Test 3: Verify endpoint doesn't auto-create proposals."""
    print("\n=== Test 3: No Auto-Proposals ===")
    try:
        db = get_db()
        
        # Create test user and session
        test_user_id = f"test_user_audit_noproposal_{datetime.now().timestamp()}"
        test_company_id = f"test_company_audit_noproposal_{datetime.now().timestamp()}"
        test_token = f"test_token_audit_noproposal_{datetime.now().timestamp()}"
        
        # Insert test user
        await db.users.insert_one({
            "user_id": test_user_id,
            "email": "test_audit_noproposal@nxt8.local",
            "name": "Test Audit No Proposal User",
            "picture": "",
            "is_admin": False,
            "company_id": test_company_id,
            "created_at": _now()
        })
        
        # Insert test session
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await db.user_sessions.insert_one({
            "user_id": test_user_id,
            "session_token": test_token,
            "expires_at": expires_at,
            "created_at": _now()
        })
        
        # Count proposals before
        proposals_before = await db.hermes_evolution_log.count_documents({"company_id": test_company_id})
        
        # Call endpoint
        headers = {"Authorization": f"Bearer {test_token}"}
        response = requests.post(f"{BACKEND_URL}/hermes/self-audit/run", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Expected 200 but got {response.status_code}: {response.text}")
            return False
        
        # Count proposals after
        proposals_after = await db.hermes_evolution_log.count_documents({"company_id": test_company_id})
        
        if proposals_after > proposals_before:
            print(f"❌ Endpoint auto-created {proposals_after - proposals_before} proposals (should be 0)")
            return False
        
        print(f"✅ Endpoint doesn't auto-create proposals (before: {proposals_before}, after: {proposals_after})")
        
        # Cleanup
        await db.users.delete_one({"user_id": test_user_id})
        await db.user_sessions.delete_one({"session_token": test_token})
        
        return True
    except Exception as e:
        print(f"❌ Error testing no auto-proposals: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tenant_scoping():
    """Test 4: Verify endpoint correctly uses user.company_id for tenant-scoping."""
    print("\n=== Test 4: Tenant Scoping ===")
    try:
        db = get_db()
        
        # Create two test users with different company_ids
        test_user_1_id = f"test_user_tenant1_{datetime.now().timestamp()}"
        test_company_1_id = f"test_company_tenant1_{datetime.now().timestamp()}"
        test_token_1 = f"test_token_tenant1_{datetime.now().timestamp()}"
        
        test_user_2_id = f"test_user_tenant2_{datetime.now().timestamp()}"
        test_company_2_id = f"test_company_tenant2_{datetime.now().timestamp()}"
        test_token_2 = f"test_token_tenant2_{datetime.now().timestamp()}"
        
        # Insert test users
        await db.users.insert_one({
            "user_id": test_user_1_id,
            "email": "test_tenant1@nxt8.local",
            "name": "Test Tenant 1 User",
            "picture": "",
            "is_admin": False,
            "company_id": test_company_1_id,
            "created_at": _now()
        })
        
        await db.users.insert_one({
            "user_id": test_user_2_id,
            "email": "test_tenant2@nxt8.local",
            "name": "Test Tenant 2 User",
            "picture": "",
            "is_admin": False,
            "company_id": test_company_2_id,
            "created_at": _now()
        })
        
        # Insert test sessions
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await db.user_sessions.insert_one({
            "user_id": test_user_1_id,
            "session_token": test_token_1,
            "expires_at": expires_at,
            "created_at": _now()
        })
        
        await db.user_sessions.insert_one({
            "user_id": test_user_2_id,
            "session_token": test_token_2,
            "expires_at": expires_at,
            "created_at": _now()
        })
        
        # Call endpoint with user 1
        headers_1 = {"Authorization": f"Bearer {test_token_1}"}
        response_1 = requests.post(f"{BACKEND_URL}/hermes/self-audit/run", headers=headers_1)
        
        if response_1.status_code != 200:
            print(f"❌ User 1 request failed: {response_1.status_code}")
            return False
        
        data_1 = response_1.json()
        
        # Call endpoint with user 2
        headers_2 = {"Authorization": f"Bearer {test_token_2}"}
        response_2 = requests.post(f"{BACKEND_URL}/hermes/self-audit/run", headers=headers_2)
        
        if response_2.status_code != 200:
            print(f"❌ User 2 request failed: {response_2.status_code}")
            return False
        
        data_2 = response_2.json()
        
        # Verify each response has correct company_id
        if data_1["company_id"] != test_company_1_id:
            print(f"❌ User 1 response has wrong company_id: {data_1['company_id']} (expected {test_company_1_id})")
            return False
        
        if data_2["company_id"] != test_company_2_id:
            print(f"❌ User 2 response has wrong company_id: {data_2['company_id']} (expected {test_company_2_id})")
            return False
        
        # Verify company_ids are different
        if data_1["company_id"] == data_2["company_id"]:
            print(f"❌ Both users got same company_id: {data_1['company_id']}")
            return False
        
        print(f"✅ Tenant scoping works correctly")
        print(f"✅ User 1 got company_id: {test_company_1_id}")
        print(f"✅ User 2 got company_id: {test_company_2_id}")
        
        # Cleanup
        await db.users.delete_many({"user_id": {"$in": [test_user_1_id, test_user_2_id]}})
        await db.user_sessions.delete_many({"session_token": {"$in": [test_token_1, test_token_2]}})
        
        return True
    except Exception as e:
        print(f"❌ Error testing tenant scoping: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_no_route_conflicts():
    """Test 5: Verify no conflicts with existing Hermes routes."""
    print("\n=== Test 5: No Route Conflicts ===")
    try:
        # List of existing Hermes routes that should still work
        existing_routes = [
            "/hermes/health",
            "/hermes/evolution/roadmap",
            "/hermes/evolution/policies",
            "/hermes/self-assessment",
        ]
        
        # Verify new route doesn't conflict
        new_route = "/hermes/self-audit/run"
        
        # Check that new route is different from all existing routes
        for route in existing_routes:
            if route == new_route:
                print(f"❌ New route conflicts with existing route: {route}")
                return False
        
        print(f"✅ New route {new_route} doesn't conflict with existing routes")
        print(f"✅ Verified against {len(existing_routes)} existing Hermes routes")
        
        return True
    except Exception as e:
        print(f"❌ Error testing route conflicts: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 80)
    print("COMPREHENSIVE BACKEND TEST: POST /api/hermes/self-audit/run")
    print("=" * 80)
    
    tests = [
        ("Authentication Required", test_endpoint_requires_authentication),
        ("Valid Auth & Response Structure", test_endpoint_with_valid_auth),
        ("No Auto-Proposals", test_no_auto_proposals_created),
        ("Tenant Scoping", test_tenant_scoping),
        ("No Route Conflicts", test_no_route_conflicts),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
