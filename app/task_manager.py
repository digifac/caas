"""Asynchronous task manager with queue and concurrency limiting."""

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from app.config import settings
from app.errors import AppError
from app.storage.base import StorageProtocol
from app.storage.memory import MemoryStorage

logger = logging.getLogger(__name__)


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    error_detail: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_json(self) -> str:
        """Serialize TaskResult to JSON string for storage."""
        data = asdict(self)
        # Convert TaskStatus enum to string for JSON serialization
        data["status"] = self.status.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskResult":
        """Deserialize TaskResult from JSON string."""
        data = json.loads(json_str)
        # Convert string back to TaskStatus enum
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


class QueueFullError(Exception):
    """Raised when the queue has reached its maximum capacity."""

    pass


@dataclass
class BatchInfo:
    """Metadata for a batch of tasks."""

    batch_id: str
    task_ids: list
    filenames: list
    created_at: float
    total_files: int

    def to_json(self) -> str:
        """Serialize BatchInfo to JSON string for storage."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "BatchInfo":
        """Deserialize BatchInfo from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


class BatchNotFoundError(Exception):
    """Raised when a batch_id is not found or has expired."""

    pass


class TaskManager:
    """
    Manages conversion tasks in the background with concurrency limiting.

    - Requests are accepted immediately and return a task_id.
    - Tasks are processed in an asynchronous queue.
    - The number of concurrently executed tasks is limited by a semaphore.
    - The queue is capped to prevent memory overload.
    - Old results are automatically cleaned up.
    - Batches group multiple tasks under a single batch_id for tracking.
    - Uses StorageProtocol for interchangeable backends (memory or Redis).
    """

    # Key prefixes for storage
    TASK_KEY_PREFIX = "task:"
    BATCH_KEY_PREFIX = "batch:"
    ACTIVE_TASK_IDS_KEY = "active_task_ids"

    def __init__(
        self,
        max_concurrent: int = 3,
        max_queue_size: int = 20,
        result_ttl_seconds: int = 3600,
        cleanup_interval_seconds: int = 60,
        max_tasks: int = 500,
        storage: StorageProtocol | None = None,
    ):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        # In-memory cache for active tasks (PENDING/PROCESSING) — always fast access
        self._tasks: dict[str, TaskResult] = {}
        self._async_tasks: dict[str, asyncio.Task] = {}
        self._batches: dict[str, BatchInfo] = {}
        self._max_concurrent = max_concurrent
        self._max_queue_size = max_queue_size
        self._result_ttl = result_ttl_seconds
        self._cleanup_interval = cleanup_interval_seconds
        self._max_tasks = max_tasks
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_lock = asyncio.Lock()
        # Storage backend — defaults to MemoryStorage for backward compatibility
        self._storage: StorageProtocol = (
            storage if storage is not None else MemoryStorage()
        )
        # Background cleanup will be started on the first submit() call
        # Short TTL for active tasks (longer than a typical task duration, shorter than result TTL)
        self._active_task_ttl = max(300, result_ttl_seconds // 2)

    @property
    def max_concurrent(self) -> int:
        """Maximum number of concurrently executed tasks."""
        return self._max_concurrent

    @property
    def storage(self) -> StorageProtocol:
        """The storage backend in use."""
        return self._storage

    def _task_key(self, task_id: str) -> str:
        """Build storage key for a task."""
        return f"{self.TASK_KEY_PREFIX}{task_id}"

    def _batch_key(self, batch_id: str) -> str:
        """Build storage key for a batch."""
        return f"{self.BATCH_KEY_PREFIX}{batch_id}"

    def _can_accept(self) -> bool:
        """Check if the queue can accept a new task."""
        pending = self.get_pending_count()
        processing = self.get_active_count()
        return (pending + processing) < self._max_queue_size

    async def _periodic_cleanup(self):
        """Periodic cleanup of expired results to prevent memory leaks."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self.cleanup_completed(max_age_seconds=self._result_ttl)

    async def _ensure_cleanup_started(self):
        """Start periodic cleanup on first call (lazy start). Async-safe via lock."""
        async with self._cleanup_lock:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.ensure_future(self._periodic_cleanup())

    async def _persist_task(self, task: TaskResult) -> None:
        """Persist a completed/failed task to storage with TTL."""
        await self._storage.set(
            self._task_key(task.task_id),
            task.to_json(),
            ttl=self._result_ttl,
        )

    async def _persist_active_task(self, task: TaskResult) -> None:
        """Persist an active (PENDING/PROCESSING) task to storage with shorter TTL.

        The TTL is shorter than result TTL because active tasks should expire
        if the service crashes (preventing stale state). On restart,
        restore_active_tasks() will find tasks still within their TTL.
        """
        await self._storage.set(
            self._task_key(task.task_id),
            task.to_json(),
            ttl=self._active_task_ttl,
        )
        # Also track this task_id in the active set for batch restoration
        await self._storage.set(
            f"{self.ACTIVE_TASK_IDS_KEY}:{task.task_id}",
            task.to_json(),
            ttl=self._active_task_ttl,
        )

    async def _persist_batch(self, batch: BatchInfo) -> None:
        """Persist a batch to storage with TTL."""
        await self._storage.set(
            self._batch_key(batch.batch_id),
            batch.to_json(),
            ttl=self._result_ttl,
        )

    async def restore_active_tasks(self) -> int:
        """Restore active tasks from storage on startup.

        Scans storage for tasks that are still within their TTL and have
        PENDING or PROCESSING status. These are tasks that were being processed
        when the service last stopped.

        Returns:
            Number of tasks restored.
        """
        restored = 0
        try:
            # Get all keys matching the active task pattern
            keys = await self._storage.keys(f"{self.ACTIVE_TASK_IDS_KEY}:*")
            for key in keys:
                try:
                    json_str = await self._storage.get(key)
                    if json_str is not None:
                        task = TaskResult.from_json(json_str)
                        # Only restore PENDING/PROCESSING tasks
                        if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                            # Mark as PENDING since we can't resume PROCESSING without the original coroutine
                            task.status = TaskStatus.PENDING
                            self._tasks[task.task_id] = task
                            restored += 1
                            logger.info(
                                "Restored active task: %s (was %s, now PENDING)",
                                task.task_id,
                                task.status.value,
                            )
                except Exception as e:
                    logger.warning("Failed to restore task from key %s: %s", key, e)
                    continue
        except Exception as e:
            logger.warning("Failed to restore active tasks: %s", e)

        if restored:
            logger.info("Restored %d active tasks from storage", restored)
        return restored

    async def _evict_completed_tasks(self) -> int:
        """Evict old completed/failed tasks when _tasks exceeds max_tasks.

        Provides a strict upper bound on memory: even between periodic cleanups,
        the in-memory task dict never grows beyond max_tasks entries.

        Returns:
            Number of tasks evicted.
        """
        if len(self._tasks) <= self._max_tasks:
            return 0
        # Collect completed/failed tasks sorted by completion time (oldest first)
        finished = [
            (tid, t)
            for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ]
        finished.sort(key=lambda x: x[1].completed_at or x[1].created_at)

        num_to_evict = len(self._tasks) - self._max_tasks
        evicted = 0
        for task_id, task in finished:
            if evicted >= num_to_evict:
                break
            # Persist before evicting from memory so storage still has the result
            await self._persist_task(task)
            del self._tasks[task_id]
            evicted += 1
        if evicted:
            logger.warning(
                "TaskManager eviction: %d completed tasks removed from memory (limit %d reached)",
                evicted,
                self._max_tasks,
            )
        return evicted

    def submit(self, task_func: Callable, *args: Any, **kwargs: Any) -> str:
        """
        Submit a task to the queue and immediately return a task_id.

        Args:
            task_func: Async function to execute.
            *args, **kwargs: Arguments passed to the function.

        Returns:
            task_id: Unique identifier to track the task.

        Raises:
            QueueFullError: If the queue is full.
        """
        asyncio.ensure_future(self._ensure_cleanup_started())
        if not self._can_accept():
            raise QueueFullError(
                f"Queue is full ({self._max_queue_size} tasks max). "
                f"Please try again in a moment."
            )
        task_id = secrets.token_hex(16)
        task = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )
        self._tasks[task_id] = task
        # Persist active task to storage for resilience on restart
        asyncio.ensure_future(self._persist_active_task(task))
        # Proactively evict old completed tasks if we're over the memory limit
        asyncio.ensure_future(self._evict_completed_tasks())
        async_task = asyncio.create_task(
            self._run_task(task_id, task_func, *args, **kwargs)
        )
        self._async_tasks[task_id] = async_task
        async_task.add_done_callback(lambda _: self._async_tasks.pop(task_id, None))
        logger.info(
            "Task submitted: %s (queue: %d pending, %d processing)",
            task_id,
            self.get_pending_count(),
            self.get_active_count(),
        )
        return task_id

    def submit_failed_task(
        self, error: str, error_detail: str | None = None
    ) -> str:
        """
        Create a task that is immediately marked as FAILED.

        Used for files that fail validation before they can be queued
        (e.g., corrupted, too large). The task is persisted to storage
        so it appears in batch results during polling.

        Args:
            error: Error code or message describing why the task failed.
            error_detail: Optional raw error detail (exposed in debug mode).

        Returns:
            task_id: Unique identifier for the failed task.
        """
        task_id = secrets.token_hex(16)
        now = time.time()
        task = TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=error,
            error_detail=error_detail,
            created_at=now,
            completed_at=now,
        )
        self._tasks[task_id] = task
        # Persist failed task to storage backend
        asyncio.ensure_future(self._persist_task(task))
        # Proactively evict old completed tasks if we're over the memory limit
        asyncio.ensure_future(self._evict_completed_tasks())
        logger.info("Failed task created: %s — %s", task_id, error)
        return task_id

    def register_batch(
        self, batch_id: str, task_ids: list[str], filenames: list[str], total_files: int
    ) -> None:
        """
        Register a batch with the given task IDs and filenames.

        This allows the caller to construct the batch externally
        (e.g., mixing valid tasks with pre-failed tasks).
        """
        batch = BatchInfo(
            batch_id=batch_id,
            task_ids=task_ids,
            filenames=filenames,
            created_at=time.time(),
            total_files=total_files,
        )
        self._batches[batch_id] = batch
        asyncio.ensure_future(self._persist_batch(batch))
        logger.info("Batch %s registered with %d tasks", batch_id, len(task_ids))

    async def _run_task(
        self, task_id: str, task_func: Callable, *args: Any, **kwargs: Any
    ):
        """Execute a task with concurrency limiting."""
        async with self._semaphore:
            self._tasks[task_id].status = TaskStatus.PROCESSING
            # Persist the PROCESSING state to storage for resilience
            await self._persist_active_task(self._tasks[task_id])
            logger.info("Task processing: %s", task_id)
            try:
                result = await task_func(*args, **kwargs)
                self._tasks[task_id] = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    created_at=self._tasks[task_id].created_at,
                    completed_at=time.time(),
                )
                # Persist completed task to storage backend
                await self._persist_task(self._tasks[task_id])
                # Remove from active task tracking since it's now completed
                await self._storage.delete(f"{self.ACTIVE_TASK_IDS_KEY}:{task_id}")
                logger.info("Task completed: %s", task_id)
            except Exception as e:
                self._tasks[task_id] = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error="CONVERSION_FAILED",
                    error_detail=str(e),
                    created_at=self._tasks[task_id].created_at,
                    completed_at=time.time(),
                )
                # Persist failed task to storage backend
                await self._persist_task(self._tasks[task_id])
                # Remove from active task tracking since it's now failed
                await self._storage.delete(f"{self.ACTIVE_TASK_IDS_KEY}:{task_id}")
                logger.error("Task failed: %s — %s", task_id, e)
            finally:
                # Clean up asyncio.Task reference once the coroutine is done
                self._async_tasks.pop(task_id, None)

    async def get_task(self, task_id: str) -> TaskResult | None:
        """
        Retrieve a task, checking in-memory first, then falling back to storage.
        This ensures completed tasks that have been evicted from RAM are still
        retrievable via the storage backend.
        """
        # Check in-memory cache first (fast path for active tasks)
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        # Fall back to storage for completed/evicted tasks
        json_str = await self._storage.get(self._task_key(task_id))
        if json_str is not None:
            return TaskResult.from_json(json_str)
        return None

    async def get_task_with_storage(self, task_id: str) -> TaskResult | None:
        """
        Deprecated alias for get_task(). Kept for backward compatibility.
        """
        return await self.get_task(task_id)

    def get_active_count(self) -> int:
        """Number of tasks currently running (processing)."""
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PROCESSING)

    def get_pending_count(self) -> int:
        """Number of tasks waiting in queue."""
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)

    def get_queue_usage(self) -> dict[str, Any]:
        """Return queue usage statistics."""
        return {
            "active": self.get_active_count(),
            "pending": self.get_pending_count(),
            "total": len(self._tasks),
            "max_concurrent": self._max_concurrent,
            "max_queue_size": self._max_queue_size,
            "async_tasks_tracked": len(self._async_tasks),
            "available_slots": max(
                0,
                self._max_queue_size
                - self.get_pending_count()
                - self.get_active_count(),
            ),
        }

    async def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up tasks older than max_age_seconds from both memory and storage.

        Covers all statuses:
        - COMPLETED / FAILED → based on completed_at (or created_at if missing).
        - PENDING / PROCESSING → based on created_at (protection against orphans/zombies).

        Returns:
            Number of tasks removed.
        """
        now = time.time()
        keys_to_remove = []
        for task_id, task in self._tasks.items():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                age = now - (task.completed_at or task.created_at)
                if age > max_age_seconds:
                    keys_to_remove.append(task_id)
            elif task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                age = now - task.created_at
                if age > max_age_seconds:
                    logger.warning(
                        "Orphan task removed: %s (status=%s, age=%.0fs)",
                        task_id,
                        task.status.value,
                        age,
                    )
                    keys_to_remove.append(task_id)
        for key in keys_to_remove:
            # Cancel the asyncio coroutine if it's still running
            async_task = self._async_tasks.pop(key, None)
            if async_task is not None and not async_task.done():
                async_task.cancel()
                logger.info("Asyncio coroutine cancelled for expired task: %s", key)
            del self._tasks[key]
            # Also remove from storage backend
            await self._storage.delete(self._task_key(key))
            # Remove from active task tracking if it was an active task
            await self._storage.delete(f"{self.ACTIVE_TASK_IDS_KEY}:{key}")
        if keys_to_remove:
            logger.debug("Cleanup: %d expired tasks removed", len(keys_to_remove))
        # Clean up batches that no longer have any valid tasks
        self._cleanup_empty_batches()
        return len(keys_to_remove)

    def _cleanup_empty_batches(self):
        """Remove batches whose tasks have all been cleaned up."""
        empty_batches = [
            batch_id
            for batch_id, info in self._batches.items()
            if not any(tid in self._tasks for tid in info.task_ids)
        ]
        for batch_id in empty_batches:
            del self._batches[batch_id]
            logger.debug("Removed empty batch: %s", batch_id)

    def submit_batch(
        self,
        batch_id: str,
        filenames: list[str],
        task_func: Callable,
        contents_and_exts: list,
    ) -> list[str]:
        """
        Submit multiple files as individual tasks grouped under a batch_id.

        Args:
            batch_id: Unique batch identifier.
            filenames: List of filenames for each file.
            task_func: Async function to execute for each file.
            contents_and_exts: List of (content_bytes, ext_str) tuples.

        Returns:
            List of task_ids, one per file.
        """
        asyncio.ensure_future(self._ensure_cleanup_started())
        task_ids: list[str] = []
        for content, ext in contents_and_exts:
            if not self._can_accept():
                raise QueueFullError(
                    f"Queue is full ({self._max_queue_size} tasks max). "
                    f"Some files in the batch could not be submitted."
                )
            task_id = self.submit(task_func, content, ext)
            task_ids.append(task_id)

        self.register_batch(batch_id, task_ids, filenames, len(filenames))
        return task_ids

    def get_batch(self, batch_id: str) -> BatchInfo | None:
        """Retrieve batch metadata by batch_id (in-memory only)."""
        return self._batches.get(batch_id)

    async def get_batch_with_storage(self, batch_id: str) -> BatchInfo | None:
        """
        Retrieve a batch, checking in-memory first, then falling back to storage.
        """
        batch = self._batches.get(batch_id)
        if batch is not None:
            return batch
        json_str = await self._storage.get(self._batch_key(batch_id))
        if json_str is not None:
            return BatchInfo.from_json(json_str)
        return None

    async def get_batch_results(self, batch_id: str) -> dict[str, Any] | None:
        """
        Retrieve full batch results: metadata + per-task status/result.

        Checks in-memory first, then falls back to storage for both the batch
        and individual tasks. This ensures completed/failed tasks that have been
        evicted from memory are still retrievable via the storage backend.

        Returns None if the batch doesn't exist (in either memory or storage).
        """
        # Check in-memory first, then fall back to storage for the batch itself
        batch_info = self._batches.get(batch_id)
        if batch_info is None:
            batch_info = await self.get_batch_with_storage(batch_id)
        if batch_info is None:
            return None

        results = []
        succeeded = 0
        failed = 0
        pending = 0
        processing = 0

        for index, task_id in enumerate(batch_info.task_ids):
            # Use get_task which checks in-memory first, then falls back to storage
            task = await self.get_task(task_id)
            entry: dict[str, Any] = {
                "index": index,
                "filename": batch_info.filenames[index]
                if index < len(batch_info.filenames)
                else "unknown",
                "task_id": task_id,
            }
            if task is None:
                entry["status"] = "expired"
                error_info = AppError.get("TASK_NOT_FOUND")
                entry["error_code"] = error_info["error_code"]
                entry["message"] = error_info["message"]
                if settings.debug:
                    entry["detail"] = "Task expired or was cleaned up."
                failed += 1
            elif task.status == TaskStatus.COMPLETED:
                entry["status"] = task.status.value
                entry["result"] = task.result
                succeeded += 1
            elif task.status == TaskStatus.FAILED:
                entry["status"] = task.status.value
                error_code = task.error if task.error else "CONVERSION_FAILED"
                error_info = AppError.get(error_code)
                entry["error_code"] = error_info["error_code"]
                entry["message"] = error_info["message"]
                if settings.debug and task.error_detail:
                    entry["detail"] = task.error_detail
                failed += 1
            elif task.status == TaskStatus.PROCESSING:
                entry["status"] = task.status.value
                processing += 1
            else:
                entry["status"] = task.status.value
                pending += 1

            results.append(entry)

        all_done = pending == 0 and processing == 0

        return {
            "batch_id": batch_id,
            "total_files": batch_info.total_files,
            "succeeded": succeeded,
            "failed": failed,
            "pending": pending,
            "processing": processing,
            "all_done": all_done,
            "results": results,
        }
