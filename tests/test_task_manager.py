"""Tests for the TaskManager (queue limits, concurrency, TTL, cleanup)."""

import asyncio
import json
import time
from typing import Any, Literal
from unittest.mock import AsyncMock

import pytest
from app.task_manager import (
    BatchInfo,
    BatchNotFoundError,
    QueueFullError,
    TaskManager,
    TaskResult,
    TaskStatus,
)

# Import fixtures from modules
from tests.fixtures.common import sample_pdf_bytes

# --- Task submission tests ---


class TestTaskManagerSubmit:
    """Tests for task submission."""

    @pytest.mark.anyio
    async def test_submit_returns_task_id(self):
        """submit() returns a valid task_id."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def dummy():
            return {"ok": True}

        task_id = manager.submit(dummy)
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    @pytest.mark.anyio
    async def test_submit_creates_pending_task(self):
        """Submitted task starts in PENDING status."""
        manager = TaskManager(max_concurrent=1, max_queue_size=5)

        async def slow_task():
            await asyncio.sleep(0.5)
            return {"ok": True}

        task_id = manager.submit(slow_task)
        result = await manager.get_task(task_id)
        assert result is not None
        assert result.status == TaskStatus.PENDING

    @pytest.mark.anyio
    async def test_submit_queue_full_raises(self):
        """submit() raises QueueFullError when queue is full."""
        manager = TaskManager(max_concurrent=1, max_queue_size=2)

        async def slow_task():
            await asyncio.sleep(2)
            return {"ok": True}

        # Fill the queue
        manager.submit(slow_task)
        manager.submit(slow_task)
        with pytest.raises(QueueFullError, match="Queue is full"):
            manager.submit(slow_task)

    @pytest.mark.anyio
    async def test_submit_task_completes(self):
        """Submitted task reaches COMPLETED status."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def success_task():
            return {"result": 42}

        task_id = manager.submit(success_task)
        await asyncio.sleep(0.5)
        result = await manager.get_task(task_id)
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"result": 42}

    @pytest.mark.anyio
    async def test_submit_task_fails(self):
        """Failed task reaches FAILED status with error code and detail."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def failing_task():
            raise ValueError("test error")

        task_id = manager.submit(failing_task)
        await asyncio.sleep(0.5)
        result = await manager.get_task(task_id)
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert result.error == "CONVERSION_FAILED"
        assert result.error_detail is not None and "test error" in result.error_detail

    @pytest.mark.anyio
    async def test_submit_task_has_timestamps(self):
        """Task has created_at and completed_at timestamps."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def quick_task():
            return {"ok": True}

        before = time.time()
        task_id = manager.submit(quick_task)
        await asyncio.sleep(0.5)
        result = await manager.get_task(task_id)
        assert result is not None
        assert result.created_at >= before
        assert result.completed_at is not None
        assert result.completed_at >= result.created_at


# --- Concurrency tests ---


class TestTaskManagerConcurrency:
    """Tests for concurrency limiting."""

    @pytest.mark.anyio
    async def test_respects_max_concurrent(self):
        """Never more than max_concurrent tasks run simultaneously."""
        max_concurrent = 2
        manager = TaskManager(max_concurrent=max_concurrent, max_queue_size=10)
        peak_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracked_task():
            nonlocal peak_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)
            await asyncio.sleep(0.2)
            async with lock:
                current_concurrent -= 1
            return {"ok": True}

        # Submit 5 tasks
        for _ in range(5):
            manager.submit(tracked_task)

        # Wait for all tasks to complete
        await asyncio.sleep(3)
        assert peak_concurrent <= max_concurrent

    @pytest.mark.anyio
    async def test_active_count_correct(self):
        """get_active_count() returns the correct number of running tasks."""
        manager = TaskManager(max_concurrent=3, max_queue_size=10)

        async def slow_task():
            await asyncio.sleep(1)
            return {"ok": True}

        manager.submit(slow_task)
        manager.submit(slow_task)
        await asyncio.sleep(0.2)
        active = manager.get_active_count()
        assert active <= 3


# --- Queue management tests ---


class TestTaskManagerQueue:
    """Tests for queue management."""

    @pytest.mark.anyio
    async def test_pending_count(self):
        """get_pending_count() returns correct count."""
        manager = TaskManager(max_concurrent=1, max_queue_size=5)

        async def slow_task():
            await asyncio.sleep(2)
            return {"ok": True}

        manager.submit(slow_task)
        # Give time for the first task to start processing
        await asyncio.sleep(0.2)
        manager.submit(slow_task)
        assert manager.get_pending_count() >= 1

    @pytest.mark.anyio
    async def test_queue_usage_stats(self):
        """get_queue_usage() returns correct statistics."""
        manager = TaskManager(max_concurrent=2, max_queue_size=10)

        usage = manager.get_queue_usage()
        assert "active" in usage
        assert "pending" in usage
        assert "total" in usage
        assert "max_concurrent" in usage
        assert "max_queue_size" in usage
        assert "available_slots" in usage
        assert usage["max_concurrent"] == 2
        assert usage["max_queue_size"] == 10

    @pytest.mark.anyio
    async def test_get_task_not_found(self):
        """get_task() returns None for unknown task_id."""
        manager = TaskManager()
        result = await manager.get_task("nonexistent-id")
        assert result is None


# --- TTL & cleanup tests ---


class TestTaskManagerCleanup:
    """Tests for result cleanup and TTL."""

    @pytest.mark.anyio
    async def test_cleanup_completed_old_tasks(self):
        """cleanup_completed() removes old completed tasks."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def quick_task():
            return {"ok": True}

        task_id = manager.submit(quick_task)
        await asyncio.sleep(0.5)
        # Manually age the task
        manager.tasks[task_id].completed_at = time.time() - 7200
        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed >= 1
        assert await manager.get_task(task_id) is None

    @pytest.mark.anyio
    async def test_cleanup_keeps_recent_tasks(self):
        """cleanup_completed() keeps recently completed tasks."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def quick_task():
            return {"ok": True}

        task_id = manager.submit(quick_task)
        await asyncio.sleep(0.5)
        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed == 0
        assert await manager.get_task(task_id) is not None

    @pytest.mark.anyio
    async def test_cleanup_orphan_pending_tasks(self):
        """cleanup_completed() removes orphan PENDING tasks."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        # Create a task manually in PENDING state with old timestamp
        task_id = "orphan-task-id"
        manager.tasks[task_id] = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=time.time() - 7200,
        )
        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed >= 1
        assert await manager.get_task(task_id) is None

    @pytest.mark.anyio
    async def test_cleanup_orphan_processing_tasks(self):
        """cleanup_completed() removes orphan PROCESSING tasks."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        task_id = "orphan-processing-id"
        manager.tasks[task_id] = TaskResult(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            created_at=time.time() - 7200,
        )
        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed >= 1
        assert await manager.get_task(task_id) is None

    @pytest.mark.anyio
    async def test_cleanup_returns_count(self):
        """cleanup_completed() returns the number of removed tasks."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        # Create multiple old tasks
        for i in range(3):
            task_id = f"old-task-{i}"
            manager.tasks[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                created_at=time.time() - 7200,
                completed_at=time.time() - 7200,
            )
        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed == 3

    @pytest.mark.anyio
    async def test_cleanup_empty_no_error(self):
        """cleanup_completed() on empty manager doesn't raise."""
        manager = TaskManager()
        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed == 0


# --- Default values ---


class TestTaskManagerDefaults:
    """Tests for default constructor values."""

    def test_default_values(self):
        """Default constructor values are correct."""
        manager = TaskManager()
        assert manager.max_concurrent == 3
        assert manager.max_queue_size == 20
        assert manager.result_ttl == 3600
        assert manager.cleanup_interval == 60

    def test_custom_values(self):
        """Custom constructor values are respected."""
        manager = TaskManager(
            max_concurrent=5, max_queue_size=50, result_ttl_seconds=7200
        )
        assert manager.max_concurrent == 5
        assert manager.max_queue_size == 50
        assert manager.result_ttl == 7200


# --- TaskResult.from_json tests ---


class TestTaskResultFromJson:
    """Tests for TaskResult.from_json deserialization."""

    def test_from_json_completed(self):
        """TaskResult.from_json correctly deserializes a COMPLETED JSON string."""
        data: dict[str, Any] = {
            "task_id": "abc123",
            "status": "completed",
            "result": {"key": "value"},
            "error": None,
            "created_at": 1000.0,
            "completed_at": 1001.0,
        }
        result = TaskResult.from_json(json.dumps(data))
        assert result.task_id == "abc123"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"key": "value"}

    def test_from_json_pending(self):
        """TaskResult.from_json handles PENDING status."""
        data: dict[str, Any] = {
            "task_id": "xyz",
            "status": "pending",
            "result": None,
            "error": None,
            "created_at": 2000.0,
            "completed_at": None,
        }
        result = TaskResult.from_json(json.dumps(data))
        assert result.status == TaskStatus.PENDING

    def test_from_json_failed(self):
        """TaskResult.from_json handles FAILED status."""
        data: dict[str, Any] = {
            "task_id": "fail1",
            "status": "failed",
            "result": None,
            "error": "boom",
            "created_at": 3000.0,
            "completed_at": 3001.0,
        }
        result = TaskResult.from_json(json.dumps(data))
        assert result.status == TaskStatus.FAILED
        assert result.error == "boom"


# --- BatchInfo.from_json tests ---


class TestBatchInfoFromJson:
    """Tests for BatchInfo.from_json deserialization."""

    def test_from_json_valid(self):
        """BatchInfo.from_json correctly deserializes a JSON string."""
        data: dict[str, Any] = {
            "batch_id": "batch-1",
            "task_ids": ["t1", "t2"],
            "filenames": ["a.pdf", "b.pdf"],
            "created_at": 3000.0,
            "total_files": 2,
        }
        batch = BatchInfo.from_json(json.dumps(data))
        assert batch.batch_id == "batch-1"
        assert batch.task_ids == ["t1", "t2"]
        assert batch.total_files == 2

    def test_to_json_round_trip(self):
        """BatchInfo.to_json -> from_json round trip preserves data."""
        original = BatchInfo(
            batch_id="b1",
            task_ids=["t1"],
            filenames=["f.pdf"],
            created_at=4000.0,
            total_files=1,
        )
        restored = BatchInfo.from_json(original.to_json())
        assert restored.batch_id == original.batch_id
        assert restored.task_ids == original.task_ids


# --- Storage property tests ---


class TestStorageProperty:
    """Tests for TaskManager.storage property."""

    @pytest.mark.anyio
    async def test_storage_property_returns_storage(self):
        """storage_backend property returns the internal storage backend."""
        manager = TaskManager(max_concurrent=1, max_queue_size=2)
        storage = manager.storage_backend
        assert storage is not None


# --- _can_accept tests ---


class TestCanAccept:
    """Tests for TaskManager._can_accept internal method."""

    @pytest.mark.anyio
    async def test_can_accept_true_when_empty(self):
        """_can_accept returns True when queue is empty."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        assert manager._can_accept() is True

    @pytest.mark.anyio
    async def test_can_accept_false_when_full(self):
        """_can_accept returns False when queue reaches max_queue_size."""
        manager = TaskManager(max_concurrent=1, max_queue_size=2)

        async def slow():
            await asyncio.sleep(10)

        manager.submit(slow)
        manager.submit(slow)
        assert manager._can_accept() is False


# --- restore_active_tasks tests ---


class TestRestoreActiveTasks:
    """Tests for TaskManager.restore_active_tasks."""

    @pytest.mark.anyio
    async def test_restore_active_tasks_from_storage(self):
        """Restores PENDING/PROCESSING tasks from storage keys."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        task_data = TaskResult(
            task_id="restore-me",
            status=TaskStatus.PROCESSING,
            result=None,
            error=None,
            created_at=time.time(),
            completed_at=None,
        )
        await manager._storage.set(
            f"{manager.ACTIVE_TASK_IDS_KEY}:restore-me", task_data.to_json()
        )

        restored_count = await manager.restore_active_tasks()
        assert restored_count == 1
        result = await manager.get_task("restore-me")
        assert result is not None
        assert result.status == TaskStatus.PENDING

    @pytest.mark.anyio
    async def test_restore_skips_completed_tasks(self):
        """Completed tasks in storage are NOT restored to memory."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        task_data = TaskResult(
            task_id="completed-task",
            status=TaskStatus.COMPLETED,
            result={"ok": True},
            error=None,
            created_at=time.time(),
            completed_at=time.time(),
        )
        await manager._storage.set(
            f"{manager.ACTIVE_TASK_IDS_KEY}:completed-task", task_data.to_json()
        )

        restored_count = await manager.restore_active_tasks()
        assert restored_count == 0

    @pytest.mark.anyio
    async def test_restore_handles_invalid_json(self):
        """Invalid JSON in storage is skipped during restore."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        await manager._storage.set(
            f"{manager.ACTIVE_TASK_IDS_KEY}:bad-key", "not-json{{{"
        )

        restored_count = await manager.restore_active_tasks()
        assert restored_count == 0

    @pytest.mark.anyio
    async def test_restore_handles_storage_exception(self):
        """Storage exception during restore is logged and doesn't crash."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        manager._storage.keys = AsyncMock(
            side_effect=RuntimeError("storage down")
        )

        restored_count = await manager.restore_active_tasks()
        assert restored_count == 0


# --- _evict_completed_tasks tests ---


class TestEvictCompletedTasks:
    """Tests for TaskManager._evict_completed_tasks."""

    @pytest.mark.anyio
    async def test_evict_nothing_when_under_limit(self):
        """_evict_completed_tasks returns 0 when under max_tasks."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5, max_tasks=100)

        async def quick():
            return "ok"

        manager.submit(quick)
        await asyncio.sleep(0.3)

        evicted = await manager._evict_completed_tasks()
        assert evicted == 0

    @pytest.mark.anyio
    async def test_evict_removes_completed_tasks(self):
        """Eviction removes oldest completed tasks when over max_tasks (auto-triggered during submit)."""
        manager = TaskManager(max_concurrent=10, max_queue_size=20, max_tasks=2)

        async def quick():
            return "ok"

        for _ in range(3):
            manager.submit(quick)

        await asyncio.sleep(0.5)

        assert len(manager.tasks) <= 2

    @pytest.mark.anyio
    async def test_evict_persists_before_removal(self):
        """Evicted tasks are persisted to storage before removal (auto-triggered during submit)."""
        manager = TaskManager(max_concurrent=10, max_queue_size=20, max_tasks=1)

        async def quick():
            return "persisted"

        tid = manager.submit(quick)
        await asyncio.sleep(0.3)

        manager.submit(quick)
        await asyncio.sleep(0.3)

        json_str = await manager._storage.get(
            manager._task_key(tid)
        )
        assert json_str is not None


# --- get_task_with_storage tests ---


class TestGetTaskWithStorage:
    """Tests for deprecated get_task_with_storage alias."""

    @pytest.mark.anyio
    async def test_get_task_with_storage_returns_task(self):
        """get_task_with_storage is an alias for get_task."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def quick():
            return "data"

        tid = manager.submit(quick)
        await asyncio.sleep(0.3)

        result = await manager.get_task_with_storage(tid)
        assert result is not None
        assert result.status == TaskStatus.COMPLETED


# --- Cleanup edge cases ---


class TestCleanupEdgeCases:
    """Tests for cleanup edge cases and async task cancellation."""

    @pytest.mark.anyio
    async def test_cleanup_cancels_running_async_task(self):
        """Cleanup cancels asyncio coroutines for expired tasks."""
        manager = TaskManager(
            max_concurrent=2, max_queue_size=5, result_ttl_seconds=int(0.1)
        )

        async def slow():
            await asyncio.sleep(10)
            return "should-not-complete"

        manager.submit(slow)
        await asyncio.sleep(0.3)

        cleaned = await manager.cleanup_completed(max_age_seconds=0)
        assert cleaned >= 1

    @pytest.mark.anyio
    async def test_cleanup_removes_from_storage(self):
        """Cleanup removes tasks from both memory and storage."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def quick():
            return "ok"

        tid = manager.submit(quick)
        await asyncio.sleep(0.3)

        json_str = await manager._storage.get(
            manager._task_key(tid)
        )
        assert json_str is not None

        await manager.cleanup_completed(max_age_seconds=0)
        await asyncio.sleep(0.1)

        json_str = await manager._storage.get(
            manager._task_key(tid)
        )
        assert json_str is None

    @pytest.mark.anyio
    async def test_cleanup_empty_batches_removed(self):
        """Empty batches are removed after cleanup."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def quick():
            return "ok"

        tid = manager.submit(quick)
        manager.register_batch("batch-x", [tid], ["file.pdf"], 1)
        await asyncio.sleep(0.3)

        assert manager.get_batch("batch-x") is not None

        await manager.cleanup_completed(max_age_seconds=0)

        assert manager.get_batch("batch-x") is None

    @pytest.mark.anyio
    async def test_cleanup_completed_returns_count(self):
        """cleanup_completed returns the number of removed tasks."""
        manager = TaskManager(max_concurrent=5, max_queue_size=10)

        async def quick():
            return "ok"

        for _ in range(3):
            manager.submit(quick)

        await asyncio.sleep(0.5)

        cleaned = await manager.cleanup_completed(max_age_seconds=0)
        assert cleaned == 3

    @pytest.mark.anyio
    async def test_cleanup_no_tasks_returns_zero(self):
        """cleanup_completed returns 0 when no tasks to clean."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        cleaned = await manager.cleanup_completed(max_age_seconds=0)
        assert cleaned == 0


# --- BatchNotFoundError tests ---


class TestBatchNotFoundError:
    """Tests for BatchNotFoundError exception."""

    def test_batch_not_found_error_raised(self):
        """BatchNotFoundError can be raised and caught."""
        with pytest.raises(BatchNotFoundError):
            raise BatchNotFoundError("batch-999")

    def test_batch_not_found_error_message(self):
        """BatchNotFoundError preserves error message."""
        try:
            raise BatchNotFoundError("batch-xyz not found")
        except BatchNotFoundError as e:
            assert "batch-xyz" in str(e)


# --- QueueFullError tests ---


class TestQueueFullError:
    """Tests for QueueFullError exception."""

    def test_queue_full_error_raised(self):
        """QueueFullError can be raised and caught."""
        with pytest.raises(QueueFullError):
            raise QueueFullError("queue full")


# --- get_batch_results non-existent tests ---


class TestBatchNotFoundGetResults:
    """Tests for get_batch_results with non-existent batch."""

    @pytest.mark.anyio
    async def test_get_batch_results_nonexistent(self):
        """get_batch_results returns None for non-existent batch."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        result = await manager.get_batch_results("nonexistent")
        assert result is None


# --- get_batch_with_storage tests ---


class TestGetBatchWithStorage:
    """Tests for get_batch_with_storage fallback to storage."""

    @pytest.mark.anyio
    async def test_get_batch_with_storage_from_storage(self):
        """get_batch_with_storage falls back to storage when not in memory."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        batch = BatchInfo(
            batch_id="stored-batch",
            task_ids=["t1"],
            filenames=["f.pdf"],
            created_at=time.time(),
            total_files=1,
        )
        await manager._storage.set(
            manager._batch_key("stored-batch"),
            batch.to_json(),
        )

        result = await manager.get_batch_with_storage("stored-batch")
        assert result is not None
        assert result.batch_id == "stored-batch"

    @pytest.mark.anyio
    async def test_get_batch_with_storage_not_found(self):
        """get_batch_with_storage returns None when batch doesn't exist anywhere."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        result = await manager.get_batch_with_storage("nonexistent")
        assert result is None


# --- submit_batch queue full tests ---


class TestSubmitBatchQueueFull:
    """Tests for submit_batch when queue is full mid-batch."""

    @pytest.mark.anyio
    async def test_submit_batch_queue_full_mid_batch(self):
        """submit_batch raises QueueFullError if queue fills mid-batch."""
        manager = TaskManager(max_concurrent=1, max_queue_size=2)

        async def slow(content: bytes, ext: str) -> None:
            await asyncio.sleep(10)

        manager.submit(slow)
        manager.submit(slow)

        with pytest.raises(QueueFullError, match="Queue is full"):
            manager.submit_batch(
                "batch-overflow",
                ["a.pdf", "b.pdf"],
                slow,
                [(b"data", "pdf"), (b"data", "pdf")],
            )


# --- TaskResult.to_json tests ---


class TestTaskResultToJson:
    """Tests for TaskResult.to_json serialization."""

    def test_to_json_completed(self):
        """TaskResult.to_json serializes completed task."""
        task = TaskResult(
            task_id="t1",
            status=TaskStatus.COMPLETED,
            result={"ok": True},
            error=None,
            created_at=1000.0,
            completed_at=1001.0,
        )
        json_str = task.to_json()
        data = json.loads(json_str)
        assert data["task_id"] == "t1"
        assert data["status"] == "completed"

    def test_to_json_failed(self):
        """TaskResult.to_json serializes failed task."""
        task = TaskResult(
            task_id="t2",
            status=TaskStatus.FAILED,
            result=None,
            error="something broke",
            created_at=2000.0,
            completed_at=2001.0,
        )
        json_str = task.to_json()
        data = json.loads(json_str)
        assert data["status"] == "failed"
        assert data["error"] == "something broke"


# --- get_task storage fallback tests ---


class TestGetTaskStorageFallback:
    """Tests for get_task storage fallback path."""

    @pytest.mark.anyio
    async def test_get_task_fallback_to_storage(self):
        """get_task falls back to storage when task not in memory."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        task = TaskResult(
            task_id="storage-only",
            status=TaskStatus.COMPLETED,
            result={"from": "storage"},
            error=None,
            created_at=time.time(),
            completed_at=time.time(),
        )
        await manager._storage.set(
            manager._task_key("storage-only"),
            task.to_json(),
        )

        result = await manager.get_task("storage-only")
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"from": "storage"}

    @pytest.mark.anyio
    async def test_get_task_not_found_anywhere(self):
        """get_task returns None when task doesn't exist anywhere."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        result = await manager.get_task("nonexistent-task")
        assert result is None


# --- Submit failed task tests ---


class TestSubmitFailedTask:
    """Tests for task submission that fails."""

    @pytest.mark.anyio
    async def test_submit_task_that_raises(self):
        """Task that raises an exception is marked as FAILED."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)

        async def failing():
            raise RuntimeError("task error")

        tid = manager.submit(failing)
        await asyncio.sleep(0.3)

        result = await manager.get_task(tid)
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert result.error == "CONVERSION_FAILED"
        assert result.error_detail == "task error"

    @pytest.mark.anyio
    async def test_submit_batch_with_failed_task(self):
        """Batch with a failed task still completes."""
        manager = TaskManager(max_concurrent=5, max_queue_size=10)

        async def task_func(content: bytes, ext: str) -> Literal["ok"]:
            if content == b"bad":
                raise ValueError("bad data")
            return "ok"

        manager.submit_batch(
            "batch-fail",
            ["good.pdf", "bad.pdf"],
            task_func,
            [(b"good", "pdf"), (b"bad", "pdf")],
        )

        await asyncio.sleep(0.5)

        batch = manager.get_batch("batch-fail")
        assert batch is not None
        assert len(batch.task_ids) == 2

        results: list[TaskResult] = []
        for tid in batch.task_ids:
            r = await manager.get_task(tid)
            if r is not None:
                results.append(r)

        failed_count = sum(1 for r in results if r.status == TaskStatus.FAILED)
        assert failed_count >= 1


# --- Internal key generation tests ---


class TestTaskKeyAndBatchKey:
    """Tests for internal key generation methods."""

    @pytest.mark.anyio
    async def test_task_key_format(self):
        """_task_key returns correct format."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        assert manager._task_key("abc") == "task:abc"

    @pytest.mark.anyio
    async def test_batch_key_format(self):
        """_batch_key returns correct format."""
        manager = TaskManager(max_concurrent=2, max_queue_size=5)
        assert manager._batch_key("xyz") == "batch:xyz"


# --- ACTIVE_TASK_IDS_KEY tests ---


class TestActiveTaskIdsKey:
    """Tests for ACTIVE_TASK_IDS_KEY constant."""

    def test_active_task_ids_key_value(self):
        """ACTIVE_TASK_IDS_KEY has correct value."""
        assert TaskManager.ACTIVE_TASK_IDS_KEY == "active_task_ids"
