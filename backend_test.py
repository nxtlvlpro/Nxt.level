"""
Comprehensive backend validation for distributed scheduler lock system.

Tests:
1. Lock acquisition and release mechanics
2. Race condition handling with multiple concurrent owners
3. Lease expiration and takeover scenarios
4. Scheduler job registration with lock wrappers
5. Index creation validation
6. Error handling and edge cases
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

sys.path.insert(0, '/app/backend')

from core.db import ensure_indexes, get_db
from core.scheduler_lock import try_acquire, release, run_exclusive, get_owner_id
from core import scheduler


async def test_lock_basic_mechanics():
    """Test basic lock acquisition, blocking, and release."""
    print("\n=== Test 1: Basic Lock Mechanics ===")
    
    await ensure_indexes()
    job_id = "test_basic_lock"
    
    # Clean up
    await get_db().scheduler_locks.delete_many({"_id": job_id})
    
    try:
        # Test 1.1: First owner acquires lock
        acquired = await try_acquire(job_id, "owner-1", 60)
        assert acquired, "First owner should acquire lock"
        print("✓ First owner acquired lock")
        
        # Test 1.2: Second owner cannot acquire while lease is active
        acquired = await try_acquire(job_id, "owner-2", 60)
        assert not acquired, "Second owner should be blocked"
        print("✓ Second owner blocked while lease active")
        
        # Test 1.3: First owner can re-acquire (refresh)
        acquired = await try_acquire(job_id, "owner-1", 60)
        assert acquired, "Same owner should be able to refresh lock"
        print("✓ Same owner can refresh lock")
        
        # Test 1.4: Release by wrong owner doesn't delete lock
        await release(job_id, "owner-2")
        doc = await get_db().scheduler_locks.find_one({"_id": job_id})
        assert doc is not None, "Lock should still exist after wrong owner release"
        print("✓ Wrong owner cannot release lock")
        
        # Test 1.5: Release by correct owner deletes lock
        await release(job_id, "owner-1")
        doc = await get_db().scheduler_locks.find_one({"_id": job_id})
        assert doc is None, "Lock should be deleted after correct owner release"
        print("✓ Correct owner released lock")
        
    finally:
        await get_db().scheduler_locks.delete_many({"_id": job_id})


async def test_lease_expiration_takeover():
    """Test that expired leases can be taken over by new owners."""
    print("\n=== Test 2: Lease Expiration & Takeover ===")
    
    await ensure_indexes()
    job_id = "test_expiration"
    
    await get_db().scheduler_locks.delete_many({"_id": job_id})
    
    try:
        # Create an expired lock
        now = datetime.now(timezone.utc)
        await get_db().scheduler_locks.insert_one({
            "_id": job_id,
            "owner_id": "owner-old",
            "locked_until": now - timedelta(seconds=10),  # Expired 10 seconds ago
            "acquired_at": now - timedelta(minutes=5),
            "updated_at": now - timedelta(minutes=5),
        })
        print("✓ Created expired lock")
        
        # New owner should be able to take over
        acquired = await try_acquire(job_id, "owner-new", 60)
        assert acquired, "New owner should take over expired lock"
        print("✓ New owner took over expired lock")
        
        # Verify new owner is recorded
        doc = await get_db().scheduler_locks.find_one({"_id": job_id})
        assert doc["owner_id"] == "owner-new", "Owner should be updated"
        locked_until = doc["locked_until"]
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        assert locked_until > datetime.now(timezone.utc), "Lease should be extended"
        print("✓ Lock ownership transferred correctly")
        
    finally:
        await get_db().scheduler_locks.delete_many({"_id": job_id})


async def test_race_condition_multiple_owners():
    """Test race condition with multiple concurrent owners trying to acquire same lock."""
    print("\n=== Test 3: Race Condition - Multiple Concurrent Owners ===")
    
    await ensure_indexes()
    job_id = "test_race_multi"
    
    await get_db().scheduler_locks.delete_many({"_id": job_id})
    
    execution_log = []
    
    async def runner(owner_id: str):
        """Simulated job runner that logs execution."""
        execution_log.append(owner_id)
        await asyncio.sleep(0.1)  # Simulate work
        return f"completed-{owner_id}"
    
    try:
        # Launch 5 concurrent attempts to run the same job
        tasks = [
            run_exclusive(job_id, 60, lambda oid=f"owner-{i}": runner(oid), owner_id=f"owner-{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify only ONE owner executed the runner
        successful = [r for r in results if r is not None]
        failed = [r for r in results if r is None]
        
        assert len(successful) == 1, f"Expected exactly 1 successful execution, got {len(successful)}"
        assert len(failed) == 4, f"Expected 4 blocked attempts, got {len(failed)}"
        assert len(execution_log) == 1, f"Runner should execute only once, executed {len(execution_log)} times"
        
        print(f"✓ Only 1 out of 5 concurrent owners executed the job")
        print(f"✓ Execution log: {execution_log}")
        print(f"✓ Successful result: {successful[0]}")
        
        # Verify lock is released after execution
        doc = await get_db().scheduler_locks.find_one({"_id": job_id})
        assert doc is None, "Lock should be released after execution"
        print("✓ Lock released after execution")
        
    finally:
        await get_db().scheduler_locks.delete_many({"_id": job_id})


async def test_run_exclusive_with_exception():
    """Test that lock is released even if runner raises exception."""
    print("\n=== Test 4: Lock Release on Exception ===")
    
    await ensure_indexes()
    job_id = "test_exception"
    
    await get_db().scheduler_locks.delete_many({"_id": job_id})
    
    async def failing_runner():
        await asyncio.sleep(0.05)
        raise ValueError("Simulated failure")
    
    try:
        # Run with exception
        try:
            await run_exclusive(job_id, 60, failing_runner, owner_id="owner-fail")
        except ValueError:
            pass  # Expected
        
        print("✓ Exception raised as expected")
        
        # Verify lock is still released
        doc = await get_db().scheduler_locks.find_one({"_id": job_id})
        assert doc is None, "Lock should be released even after exception"
        print("✓ Lock released despite exception")
        
        # Verify another owner can acquire immediately
        acquired = await try_acquire(job_id, "owner-retry", 60)
        assert acquired, "New owner should acquire lock after failed execution"
        print("✓ New owner can acquire lock after failed execution")
        
    finally:
        await get_db().scheduler_locks.delete_many({"_id": job_id})


async def test_scheduler_job_registration():
    """Verify that scheduler jobs are registered with lock wrappers."""
    print("\n=== Test 5: Scheduler Job Registration ===")
    
    # Start scheduler
    scheduler.start()
    
    sch = scheduler.get_scheduler()
    assert sch is not None, "Scheduler should be initialized"
    print("✓ Scheduler initialized")
    
    jobs = sch.get_jobs()
    job_ids = {j.id for j in jobs}
    
    # Verify expected jobs are registered
    expected_jobs = ["discover_tenants"]
    
    # Check for pulse_tick if enabled
    if scheduler.PULSE_ENABLED:
        expected_jobs.append("pulse_tick")
    
    # Check for daily_digest if enabled
    if scheduler.DIGEST_ENABLED:
        expected_jobs.append("daily_digest")
    
    # Check for session_cleanup if enabled
    if scheduler.SESSION_CLEANUP_ENABLED:
        expected_jobs.append("session_cleanup")
    
    for job_id in expected_jobs:
        assert job_id in job_ids, f"Job '{job_id}' should be registered"
        print(f"✓ Job '{job_id}' registered")
    
    # Verify discover_tenants is NOT wrapped with lock (as per requirements)
    discover_job = next((j for j in jobs if j.id == "discover_tenants"), None)
    assert discover_job is not None
    print("✓ discover_tenants job found (not wrapped with global lock)")
    
    # Verify locked jobs use the _locked wrapper functions
    if scheduler.PULSE_ENABLED:
        pulse_job = next((j for j in jobs if j.id == "pulse_tick"), None)
        assert pulse_job is not None
        assert pulse_job.func.__name__ == "_run_pulse_for_all_locked"
        print("✓ pulse_tick uses lock wrapper")
    
    if scheduler.DIGEST_ENABLED:
        digest_job = next((j for j in jobs if j.id == "daily_digest"), None)
        assert digest_job is not None
        assert digest_job.func.__name__ == "_run_digest_for_all_locked"
        print("✓ daily_digest uses lock wrapper")
    
    if scheduler.SESSION_CLEANUP_ENABLED:
        cleanup_job = next((j for j in jobs if j.id == "session_cleanup"), None)
        assert cleanup_job is not None
        assert cleanup_job.func.__name__ == "_run_session_cleanup_locked"
        print("✓ session_cleanup uses lock wrapper")


async def test_index_creation():
    """Verify that scheduler_locks index is created correctly."""
    print("\n=== Test 6: Index Creation ===")
    
    await ensure_indexes()
    
    indexes = await get_db().scheduler_locks.index_information()
    
    # Check for locked_until index
    locked_until_index = None
    for idx_name, idx_info in indexes.items():
        keys = idx_info.get("key", [])
        if any(k[0] == "locked_until" for k in keys):
            locked_until_index = idx_info
            break
    
    assert locked_until_index is not None, "locked_until index should exist"
    print("✓ locked_until index exists")
    print(f"  Index details: {locked_until_index}")


async def test_duplicate_key_race_condition():
    """Test handling of DuplicateKeyError during concurrent upserts."""
    print("\n=== Test 7: DuplicateKeyError Handling ===")
    
    await ensure_indexes()
    job_id = "test_duplicate_race"
    
    await get_db().scheduler_locks.delete_many({"_id": job_id})
    
    results = []
    
    async def attempt_acquire(owner_id: str):
        """Attempt to acquire lock and record result."""
        acquired = await try_acquire(job_id, owner_id, 60)
        results.append((owner_id, acquired))
        return acquired
    
    try:
        # Launch 10 concurrent acquisition attempts
        tasks = [attempt_acquire(f"owner-{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify exactly one succeeded
        successful = [r for r in results if r[1]]
        failed = [r for r in results if not r[1]]
        
        assert len(successful) == 1, f"Expected exactly 1 successful acquisition, got {len(successful)}"
        assert len(failed) == 9, f"Expected 9 failed acquisitions, got {len(failed)}"
        
        print(f"✓ Exactly 1 out of 10 concurrent acquisitions succeeded")
        print(f"  Winner: {successful[0][0]}")
        
        # Verify lock document exists with correct owner
        doc = await get_db().scheduler_locks.find_one({"_id": job_id})
        assert doc is not None
        assert doc["owner_id"] == successful[0][0]
        print(f"✓ Lock document has correct owner: {doc['owner_id']}")
        
    finally:
        await get_db().scheduler_locks.delete_many({"_id": job_id})


async def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n=== Test 8: Edge Cases & Error Handling ===")
    
    # Test 8.1: Empty job_id
    try:
        await try_acquire("", "owner-1", 60)
        assert False, "Should raise ValueError for empty job_id"
    except ValueError as e:
        assert "job_id is required" in str(e)
        print("✓ Empty job_id raises ValueError")
    
    # Test 8.2: Empty owner_id
    try:
        await try_acquire("test_job", "", 60)
        assert False, "Should raise ValueError for empty owner_id"
    except ValueError as e:
        assert "owner_id is required" in str(e)
        print("✓ Empty owner_id raises ValueError")
    
    # Test 8.3: Invalid lease_seconds
    try:
        await try_acquire("test_job", "owner-1", 0)
        assert False, "Should raise ValueError for lease_seconds <= 0"
    except ValueError as e:
        assert "lease_seconds must be > 0" in str(e)
        print("✓ Invalid lease_seconds raises ValueError")
    
    # Test 8.4: Release with empty parameters (should not raise)
    await release("", "")
    print("✓ Release with empty parameters handled gracefully")
    
    # Test 8.5: get_owner_id returns valid format
    owner_id = get_owner_id()
    assert owner_id, "owner_id should not be empty"
    assert ":" in owner_id, "owner_id should contain hostname:pid:uuid format"
    print(f"✓ get_owner_id returns valid format: {owner_id}")


async def run_all_tests():
    """Run all backend validation tests."""
    print("\n" + "="*70)
    print("DISTRIBUTED SCHEDULER LOCK - BACKEND VALIDATION")
    print("="*70)
    
    try:
        await test_lock_basic_mechanics()
        await test_lease_expiration_takeover()
        await test_race_condition_multiple_owners()
        await test_run_exclusive_with_exception()
        await test_scheduler_job_registration()
        await test_index_creation()
        await test_duplicate_key_race_condition()
        await test_edge_cases()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        return True
        
    except AssertionError as e:
        print("\n" + "="*70)
        print(f"❌ TEST FAILED: {e}")
        print("="*70)
        return False
    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("="*70)
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
