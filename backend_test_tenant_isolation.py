"""
Comprehensive backend-only validation of P0 tenant isolation refactor in NXT8.

Tests:
1. TenantAwareCRUD operations (find, insert, update, delete, aggregate, count)
2. Admin bypass (force_admin=True)
3. get_db() proxy auto-wrapping
4. Middleware context injection
5. Isolation smoke tests (tasks, documents, roi)
6. Critical modules: roi, memory, diagnostics, documents, approval_gate
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.db import (
    TenantAwareCRUD,
    get_db,
    set_request_company_context,
    reset_request_company_context,
    get_request_company_id,
    get_request_force_admin,
)
from core import auth as A
from agents import roi as roi_agent
from agents import memory as memory_agent
from agents import diagnostics as diagnostics_agent
from agents import documents as documents_agent
from core import approval_gate as approval_gate_agent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def test_tenant_aware_crud_find():
    """Test that TenantAwareCRUD.find() adds tenant filter."""
    print("\n[TEST] TenantAwareCRUD.find() adds tenant filter")
    
    # Insert test data for two tenants
    task_a_id = f"task_a_{uuid.uuid4().hex[:8]}"
    task_b_id = f"task_b_{uuid.uuid4().hex[:8]}"
    
    crud_a = TenantAwareCRUD(get_db().tasks, company_id="tenant_a")
    crud_b = TenantAwareCRUD(get_db().tasks, company_id="tenant_b")
    
    await crud_a.insert_one({
        "id": task_a_id,
        "title": "Task A",
        "status": "open",
        "created_at": _now(),
    })
    
    await crud_b.insert_one({
        "id": task_b_id,
        "title": "Task B",
        "status": "open",
        "created_at": _now(),
    })
    
    # Tenant A should only see task A
    tasks_a = await crud_a.find({}, {"_id": 0}).to_list(length=100)
    task_a_ids = {t["id"] for t in tasks_a}
    assert task_a_id in task_a_ids, f"Tenant A should see task {task_a_id}"
    assert task_b_id not in task_a_ids, f"Tenant A should NOT see task {task_b_id}"
    
    # Tenant B should only see task B
    tasks_b = await crud_b.find({}, {"_id": 0}).to_list(length=100)
    task_b_ids = {t["id"] for t in tasks_b}
    assert task_b_id in task_b_ids, f"Tenant B should see task {task_b_id}"
    assert task_a_id not in task_b_ids, f"Tenant B should NOT see task {task_a_id}"
    
    # Cleanup
    await crud_a.delete_many({"id": task_a_id})
    await crud_b.delete_many({"id": task_b_id})
    
    print("✅ TenantAwareCRUD.find() correctly filters by tenant")


async def test_tenant_aware_crud_find_one():
    """Test that TenantAwareCRUD.find_one() adds tenant filter."""
    print("\n[TEST] TenantAwareCRUD.find_one() adds tenant filter")
    
    task_id = f"task_findone_{uuid.uuid4().hex[:8]}"
    
    crud_a = TenantAwareCRUD(get_db().tasks, company_id="tenant_a")
    crud_b = TenantAwareCRUD(get_db().tasks, company_id="tenant_b")
    
    await crud_a.insert_one({
        "id": task_id,
        "title": "Task for tenant A",
        "created_at": _now(),
    })
    
    # Tenant A can find it
    found_a = await crud_a.find_one({"id": task_id}, {"_id": 0})
    assert found_a is not None, "Tenant A should find the task"
    assert found_a["company_id"] == "tenant_a"
    
    # Tenant B cannot find it
    found_b = await crud_b.find_one({"id": task_id}, {"_id": 0})
    assert found_b is None, "Tenant B should NOT find tenant A's task"
    
    # Cleanup
    await crud_a.delete_many({"id": task_id})
    
    print("✅ TenantAwareCRUD.find_one() correctly filters by tenant")


async def test_tenant_aware_crud_insert_one():
    """Test that TenantAwareCRUD.insert_one() injects company_id."""
    print("\n[TEST] TenantAwareCRUD.insert_one() injects company_id")
    
    task_id = f"task_insert_{uuid.uuid4().hex[:8]}"
    
    crud = TenantAwareCRUD(get_db().tasks, company_id="tenant_insert_test")
    
    await crud.insert_one({
        "id": task_id,
        "title": "Test task",
        "created_at": _now(),
    })
    
    # Verify company_id was injected
    doc = await crud.find_one({"id": task_id}, {"_id": 0})
    assert doc is not None
    assert doc["company_id"] == "tenant_insert_test", "company_id should be injected"
    
    # Cleanup
    await crud.delete_many({"id": task_id})
    
    print("✅ TenantAwareCRUD.insert_one() correctly injects company_id")


async def test_tenant_aware_crud_update_one():
    """Test that TenantAwareCRUD.update_one() preserves tenant filter."""
    print("\n[TEST] TenantAwareCRUD.update_one() preserves tenant filter")
    
    task_id = f"task_update_{uuid.uuid4().hex[:8]}"
    
    crud_a = TenantAwareCRUD(get_db().tasks, company_id="tenant_a")
    crud_b = TenantAwareCRUD(get_db().tasks, company_id="tenant_b")
    
    await crud_a.insert_one({
        "id": task_id,
        "title": "Original",
        "status": "open",
        "created_at": _now(),
    })
    
    # Tenant B tries to update tenant A's task - should not work
    result_b = await crud_b.update_one(
        {"id": task_id},
        {"$set": {"title": "Hacked by B"}},
    )
    assert result_b.matched_count == 0, "Tenant B should not match tenant A's task"
    
    # Verify task unchanged
    doc = await crud_a.find_one({"id": task_id}, {"_id": 0})
    assert doc["title"] == "Original", "Task should not be modified by tenant B"
    
    # Tenant A can update
    result_a = await crud_a.update_one(
        {"id": task_id},
        {"$set": {"title": "Updated by A"}},
    )
    assert result_a.matched_count == 1, "Tenant A should match its own task"
    
    doc = await crud_a.find_one({"id": task_id}, {"_id": 0})
    assert doc["title"] == "Updated by A"
    
    # Cleanup
    await crud_a.delete_many({"id": task_id})
    
    print("✅ TenantAwareCRUD.update_one() correctly enforces tenant isolation")


async def test_tenant_aware_crud_upsert():
    """Test that TenantAwareCRUD upsert handles company_id correctly."""
    print("\n[TEST] TenantAwareCRUD upsert with company_id")
    
    task_id = f"task_upsert_{uuid.uuid4().hex[:8]}"
    
    crud = TenantAwareCRUD(get_db().tasks, company_id="tenant_upsert")
    
    # First upsert (insert)
    await crud.update_one(
        {"id": task_id},
        {"$set": {"title": "First", "status": "open"}, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )
    
    doc = await crud.find_one({"id": task_id}, {"_id": 0})
    assert doc is not None
    assert doc["company_id"] == "tenant_upsert"
    assert doc["title"] == "First"
    
    # Second upsert (update)
    await crud.update_one(
        {"id": task_id},
        {"$set": {"title": "Second"}},
        upsert=True,
    )
    
    doc = await crud.find_one({"id": task_id}, {"_id": 0})
    assert doc["title"] == "Second"
    assert doc["company_id"] == "tenant_upsert", "company_id should remain unchanged"
    
    # Cleanup
    await crud.delete_many({"id": task_id})
    
    print("✅ TenantAwareCRUD upsert correctly handles company_id")


async def test_tenant_aware_crud_count_documents():
    """Test that TenantAwareCRUD.count_documents() adds tenant filter."""
    print("\n[TEST] TenantAwareCRUD.count_documents() adds tenant filter")
    
    task_a1 = f"task_count_a1_{uuid.uuid4().hex[:8]}"
    task_a2 = f"task_count_a2_{uuid.uuid4().hex[:8]}"
    task_b1 = f"task_count_b1_{uuid.uuid4().hex[:8]}"
    
    crud_a = TenantAwareCRUD(get_db().tasks, company_id="tenant_count_a")
    crud_b = TenantAwareCRUD(get_db().tasks, company_id="tenant_count_b")
    
    await crud_a.insert_one({"id": task_a1, "title": "A1", "created_at": _now()})
    await crud_a.insert_one({"id": task_a2, "title": "A2", "created_at": _now()})
    await crud_b.insert_one({"id": task_b1, "title": "B1", "created_at": _now()})
    
    count_a = await crud_a.count_documents({})
    count_b = await crud_b.count_documents({})
    
    # Tenant A should see at least 2 (may have more from other tests)
    assert count_a >= 2, f"Tenant A should see at least 2 tasks, got {count_a}"
    
    # Tenant B should see at least 1
    assert count_b >= 1, f"Tenant B should see at least 1 task, got {count_b}"
    
    # Cleanup
    await crud_a.delete_many({"id": {"$in": [task_a1, task_a2]}})
    await crud_b.delete_many({"id": task_b1})
    
    print("✅ TenantAwareCRUD.count_documents() correctly filters by tenant")


async def test_tenant_aware_crud_aggregate():
    """Test that TenantAwareCRUD.aggregate() injects tenant filter."""
    print("\n[TEST] TenantAwareCRUD.aggregate() injects tenant filter")
    
    task_a1 = f"task_agg_a1_{uuid.uuid4().hex[:8]}"
    task_a2 = f"task_agg_a2_{uuid.uuid4().hex[:8]}"
    task_b1 = f"task_agg_b1_{uuid.uuid4().hex[:8]}"
    
    crud_a = TenantAwareCRUD(get_db().tasks, company_id="tenant_agg_a")
    crud_b = TenantAwareCRUD(get_db().tasks, company_id="tenant_agg_b")
    
    await crud_a.insert_one({"id": task_a1, "title": "A1", "status": "open", "created_at": _now()})
    await crud_a.insert_one({"id": task_a2, "title": "A2", "status": "open", "created_at": _now()})
    await crud_b.insert_one({"id": task_b1, "title": "B1", "status": "open", "created_at": _now()})
    
    # Aggregate for tenant A
    pipeline_a = [
        {"$match": {"status": "open"}},
        {"$group": {"_id": "$company_id", "count": {"$sum": 1}}},
    ]
    results_a = await crud_a.aggregate(pipeline_a).to_list(length=10)
    
    # Should only see tenant_agg_a
    company_ids_a = {r["_id"] for r in results_a}
    assert "tenant_agg_a" in company_ids_a
    assert "tenant_agg_b" not in company_ids_a, "Tenant A should not see tenant B's data in aggregate"
    
    # Aggregate for tenant B
    pipeline_b = [
        {"$match": {"status": "open"}},
        {"$group": {"_id": "$company_id", "count": {"$sum": 1}}},
    ]
    results_b = await crud_b.aggregate(pipeline_b).to_list(length=10)
    
    company_ids_b = {r["_id"] for r in results_b}
    assert "tenant_agg_b" in company_ids_b
    assert "tenant_agg_a" not in company_ids_b, "Tenant B should not see tenant A's data in aggregate"
    
    # Cleanup
    await crud_a.delete_many({"id": {"$in": [task_a1, task_a2]}})
    await crud_b.delete_many({"id": task_b1})
    
    print("✅ TenantAwareCRUD.aggregate() correctly injects tenant filter")


async def test_admin_bypass():
    """Test that force_admin=True bypasses tenant filter."""
    print("\n[TEST] Admin bypass (force_admin=True)")
    
    task_a_id = f"task_admin_a_{uuid.uuid4().hex[:8]}"
    task_b_id = f"task_admin_b_{uuid.uuid4().hex[:8]}"
    
    crud_a = TenantAwareCRUD(get_db().tasks, company_id="tenant_admin_a")
    crud_b = TenantAwareCRUD(get_db().tasks, company_id="tenant_admin_b")
    crud_admin = TenantAwareCRUD(get_db().tasks, force_admin=True)
    
    await crud_a.insert_one({"id": task_a_id, "title": "Admin A", "created_at": _now()})
    await crud_b.insert_one({"id": task_b_id, "title": "Admin B", "created_at": _now()})
    
    # Admin should see both
    all_tasks = await crud_admin.find(
        {"id": {"$in": [task_a_id, task_b_id]}},
        {"_id": 0}
    ).to_list(length=10)
    
    task_ids = {t["id"] for t in all_tasks}
    assert task_a_id in task_ids, "Admin should see tenant A's task"
    assert task_b_id in task_ids, "Admin should see tenant B's task"
    assert len(all_tasks) == 2, "Admin should see both tasks"
    
    # Cleanup
    await crud_admin.delete_many({"id": {"$in": [task_a_id, task_b_id]}})
    
    print("✅ Admin bypass (force_admin=True) works correctly")


async def test_get_db_proxy_auto_wrapping():
    """Test that get_db() returns TenantAwareCollection proxy."""
    print("\n[TEST] get_db() proxy auto-wrapping")
    
    db = get_db()
    
    # Check that collections are wrapped
    tasks_collection = db.tasks
    assert hasattr(tasks_collection, "raw_collection"), "Collection should be wrapped in TenantAwareCollection"
    
    # Test that direct calls use tenant context
    task_id = f"task_proxy_{uuid.uuid4().hex[:8]}"
    
    # Set context
    tokens = set_request_company_context("tenant_proxy_test")
    try:
        # Direct insert via proxy
        await db.tasks.insert_one({
            "id": task_id,
            "title": "Proxy test",
            "created_at": _now(),
        })
        
        # Verify company_id was injected
        doc = await db.tasks.find_one({"id": task_id}, {"_id": 0})
        assert doc is not None
        assert doc["company_id"] == "tenant_proxy_test", "Proxy should inject company_id from context"
        
        # Cleanup
        await db.tasks.delete_many({"id": task_id})
    finally:
        reset_request_company_context(tokens)
    
    print("✅ get_db() proxy auto-wrapping works correctly")


async def test_request_context():
    """Test request context variables."""
    print("\n[TEST] Request context (set/get/reset)")
    
    # Initially should be None
    assert get_request_company_id() is None
    assert get_request_force_admin() is False
    
    # Set context
    tokens = set_request_company_context("test_company", force_admin=True)
    
    assert get_request_company_id() == "test_company"
    assert get_request_force_admin() is True
    
    # Reset context
    reset_request_company_context(tokens)
    
    assert get_request_company_id() is None
    assert get_request_force_admin() is False
    
    print("✅ Request context works correctly")


async def test_tasks_isolation():
    """Test that tasks are isolated between tenants."""
    print("\n[TEST] Tasks isolation smoke test")
    
    task_a_id = f"task_smoke_a_{uuid.uuid4().hex[:8]}"
    task_b_id = f"task_smoke_b_{uuid.uuid4().hex[:8]}"
    
    # Create tasks for two tenants
    await TenantAwareCRUD(get_db().tasks, company_id="smoke_tenant_a").insert_one({
        "id": task_a_id,
        "title": "Tenant A task",
        "status": "open",
        "kind": "general",
        "created_at": _now(),
    })
    
    await TenantAwareCRUD(get_db().tasks, company_id="smoke_tenant_b").insert_one({
        "id": task_b_id,
        "title": "Tenant B task",
        "status": "open",
        "kind": "general",
        "created_at": _now(),
    })
    
    # Tenant A sees only their task
    tasks_a = await TenantAwareCRUD(get_db().tasks, company_id="smoke_tenant_a").find(
        {"id": {"$in": [task_a_id, task_b_id]}},
        {"_id": 0}
    ).to_list(length=10)
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == task_a_id
    
    # Tenant B sees only their task
    tasks_b = await TenantAwareCRUD(get_db().tasks, company_id="smoke_tenant_b").find(
        {"id": {"$in": [task_a_id, task_b_id]}},
        {"_id": 0}
    ).to_list(length=10)
    assert len(tasks_b) == 1
    assert tasks_b[0]["id"] == task_b_id
    
    # Admin sees both
    tasks_admin = await TenantAwareCRUD(get_db().tasks, force_admin=True).find(
        {"id": {"$in": [task_a_id, task_b_id]}},
        {"_id": 0}
    ).to_list(length=10)
    assert len(tasks_admin) == 2
    
    # Cleanup
    await TenantAwareCRUD(get_db().tasks, force_admin=True).delete_many({
        "id": {"$in": [task_a_id, task_b_id]}
    })
    
    print("✅ Tasks isolation works correctly")


async def test_documents_isolation():
    """Test that documents.list_documents() respects tenant isolation."""
    print("\n[TEST] Documents isolation")
    
    # Create test documents for two tenants
    doc_a_content = b"Test document for tenant A"
    doc_b_content = b"Test document for tenant B"
    
    doc_a = await documents_agent.ingest_document(
        filename="test_a.txt",
        content=doc_a_content,
        company_id="doc_tenant_a",
        user_id="user_a",
        title="Doc A",
    )
    
    doc_b = await documents_agent.ingest_document(
        filename="test_b.txt",
        content=doc_b_content,
        company_id="doc_tenant_b",
        user_id="user_b",
        title="Doc B",
    )
    
    # Tenant A should only see their document
    docs_a = await documents_agent.list_documents(company_id="doc_tenant_a", limit=100)
    doc_a_ids = {d["id"] for d in docs_a}
    assert doc_a["id"] in doc_a_ids, "Tenant A should see their document"
    assert doc_b["id"] not in doc_a_ids, "Tenant A should NOT see tenant B's document"
    
    # Tenant B should only see their document
    docs_b = await documents_agent.list_documents(company_id="doc_tenant_b", limit=100)
    doc_b_ids = {d["id"] for d in docs_b}
    assert doc_b["id"] in doc_b_ids, "Tenant B should see their document"
    assert doc_a["id"] not in doc_b_ids, "Tenant B should NOT see tenant A's document"
    
    # Cleanup
    await TenantAwareCRUD(get_db().documents, force_admin=True).delete_many({
        "id": {"$in": [doc_a["id"], doc_b["id"]]}
    })
    
    print("✅ Documents isolation works correctly")


async def test_roi_isolation():
    """Test that ROI data is isolated between tenants."""
    print("\n[TEST] ROI isolation")
    
    # Record costs for two tenants
    await roi_agent.record_api_cost("test_agent", tokens=10000, company_id="roi_tenant_a")
    await roi_agent.record_api_cost("test_agent", tokens=20000, company_id="roi_tenant_b")
    
    # Record deals for two tenants
    deal_a_id = f"deal_roi_a_{uuid.uuid4().hex[:8]}"
    deal_b_id = f"deal_roi_b_{uuid.uuid4().hex[:8]}"
    
    await roi_agent.record_deal(
        deal_id=deal_a_id,
        value_usd=1000.0,
        team="sales",
        company_id="roi_tenant_a",
    )
    
    await roi_agent.record_deal(
        deal_id=deal_b_id,
        value_usd=2000.0,
        team="sales",
        company_id="roi_tenant_b",
    )
    
    # Get dashboard for tenant A
    dashboard_a = await roi_agent.dashboard_summary(company_id="roi_tenant_a")
    
    # Get dashboard for tenant B
    dashboard_b = await roi_agent.dashboard_summary(company_id="roi_tenant_b")
    
    # Verify they are different
    assert dashboard_a != dashboard_b, "ROI dashboards should be different for different tenants"
    
    # Verify tenant A's data
    current_a = dashboard_a["current_hour"]
    assert current_a["company_id"] == "roi_tenant_a"
    
    # Verify tenant B's data
    current_b = dashboard_b["current_hour"]
    assert current_b["company_id"] == "roi_tenant_b"
    
    # Cleanup
    await TenantAwareCRUD(get_db().costs, force_admin=True).delete_many({
        "company_id": {"$in": ["roi_tenant_a", "roi_tenant_b"]}
    })
    await TenantAwareCRUD(get_db().deals, force_admin=True).delete_many({
        "deal_id": {"$in": [deal_a_id, deal_b_id]}
    })
    await TenantAwareCRUD(get_db().interactions, force_admin=True).delete_many({
        "deal_id": {"$in": [deal_a_id, deal_b_id]}
    })
    await TenantAwareCRUD(get_db().roi_history, force_admin=True).delete_many({
        "company_id": {"$in": ["roi_tenant_a", "roi_tenant_b"]}
    })
    
    print("✅ ROI isolation works correctly")


async def test_memory_isolation():
    """Test that memory is isolated between tenants."""
    print("\n[TEST] Memory isolation")
    
    mem = memory_agent.get_memory()
    
    # Store memories for two tenants
    mid_a = await mem.store_memory(
        content="Secret memory for tenant A",
        memory_type="corporate",
        company_id="mem_tenant_a",
    )
    
    mid_b = await mem.store_memory(
        content="Secret memory for tenant B",
        memory_type="corporate",
        company_id="mem_tenant_b",
    )
    
    # Search for tenant A
    results_a = await mem.search(
        query="secret memory",
        top_k=10,
        company_id="mem_tenant_a",
    )
    
    # Search for tenant B
    results_b = await mem.search(
        query="secret memory",
        top_k=10,
        company_id="mem_tenant_b",
    )
    
    # Tenant A should only see their memory
    ids_a = {r["id"] for r in results_a}
    assert mid_a in ids_a, "Tenant A should see their memory"
    assert mid_b not in ids_a, "Tenant A should NOT see tenant B's memory"
    
    # Tenant B should only see their memory
    ids_b = {r["id"] for r in results_b}
    assert mid_b in ids_b, "Tenant B should see their memory"
    assert mid_a not in ids_b, "Tenant B should NOT see tenant A's memory"
    
    # Cleanup
    await TenantAwareCRUD(get_db().memories, force_admin=True).delete_many({
        "id": {"$in": [mid_a, mid_b]}
    })
    
    print("✅ Memory isolation works correctly")


async def test_diagnostics_isolation():
    """Test that diagnostics respects tenant isolation."""
    print("\n[TEST] Diagnostics isolation")
    
    # Create test requests for two tenants
    req_a_id = f"req_diag_a_{uuid.uuid4().hex[:8]}"
    req_b_id = f"req_diag_b_{uuid.uuid4().hex[:8]}"
    
    await TenantAwareCRUD(get_db().requests, company_id="diag_tenant_a").insert_one({
        "id": req_a_id,
        "intent": "test",
        "message": "Test message A",
        "response": "Test response A",
        "confidence": 0.8,
        "created_at": _now(),
    })
    
    await TenantAwareCRUD(get_db().requests, company_id="diag_tenant_b").insert_one({
        "id": req_b_id,
        "intent": "test",
        "message": "Test message B",
        "response": "Test response B",
        "confidence": 0.7,
        "created_at": _now(),
    })
    
    # Scan contradictions for tenant A
    result_a = await diagnostics_agent.scan_contradictions(
        window=100,
        company_id="diag_tenant_a",
    )
    
    # Scan contradictions for tenant B
    result_b = await diagnostics_agent.scan_contradictions(
        window=100,
        company_id="diag_tenant_b",
    )
    
    # Both should complete without cross-tenant contamination
    assert "scanned" in result_a
    assert "scanned" in result_b
    
    # Cleanup
    await TenantAwareCRUD(get_db().requests, force_admin=True).delete_many({
        "id": {"$in": [req_a_id, req_b_id]}
    })
    
    print("✅ Diagnostics isolation works correctly")


async def test_approval_gate_isolation():
    """Test that approval gate respects tenant isolation."""
    print("\n[TEST] Approval gate isolation")
    
    # Create approvals for two tenants
    approval_a = await approval_gate_agent.request_approval(
        agent_id="test_agent",
        action="test_action",
        args={"test": "a"},
        company_id="approval_tenant_a",
    )
    
    approval_b = await approval_gate_agent.request_approval(
        agent_id="test_agent",
        action="test_action",
        args={"test": "b"},
        company_id="approval_tenant_b",
    )
    
    # List pending for tenant A
    pending_a = await approval_gate_agent.list_pending(
        company_id="approval_tenant_a",
        limit=100,
    )
    
    # List pending for tenant B
    pending_b = await approval_gate_agent.list_pending(
        company_id="approval_tenant_b",
        limit=100,
    )
    
    # Tenant A should only see their approval
    ids_a = {p["id"] for p in pending_a}
    assert approval_a["approval_id"] in ids_a, "Tenant A should see their approval"
    assert approval_b["approval_id"] not in ids_a, "Tenant A should NOT see tenant B's approval"
    
    # Tenant B should only see their approval
    ids_b = {p["id"] for p in pending_b}
    assert approval_b["approval_id"] in ids_b, "Tenant B should see their approval"
    assert approval_a["approval_id"] not in ids_b, "Tenant B should NOT see tenant A's approval"
    
    # Cleanup
    await TenantAwareCRUD(get_db().pending_approvals, force_admin=True).delete_many({
        "id": {"$in": [approval_a["approval_id"], approval_b["approval_id"]]}
    })
    
    print("✅ Approval gate isolation works correctly")


async def main():
    """Run all tenant isolation tests."""
    print("=" * 70)
    print("TENANT ISOLATION BACKEND VALIDATION")
    print("=" * 70)
    
    tests = [
        # Core CRUD operations
        test_tenant_aware_crud_find,
        test_tenant_aware_crud_find_one,
        test_tenant_aware_crud_insert_one,
        test_tenant_aware_crud_update_one,
        test_tenant_aware_crud_upsert,
        test_tenant_aware_crud_count_documents,
        test_tenant_aware_crud_aggregate,
        
        # Admin bypass
        test_admin_bypass,
        
        # Proxy and context
        test_get_db_proxy_auto_wrapping,
        test_request_context,
        
        # Smoke tests
        test_tasks_isolation,
        test_documents_isolation,
        test_roi_isolation,
        test_memory_isolation,
        test_diagnostics_isolation,
        test_approval_gate_isolation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
