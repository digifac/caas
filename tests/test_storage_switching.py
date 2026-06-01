"""Tests for storage backend switching (Memory ↔ Redis) — regression tests.

Ensures that TaskManager and RateLimiter behave identically regardless of
whether the storage backend is MemoryStorage or RedisStorage.

Uses fakeredis so no real Redis server is required.
"""

import asyncio
import json

import fakeredis.aioredis  # type: ignore[import-untyped]
import pytest
from app.rate_limiter import RateLimiter
from app.storage.base import StorageProtocol
from app.storage.memory import MemoryStorage
from app.storage.redis import RedisStorage
from app.task_manager import TaskManager, TaskStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_storage():
    """Fresh MemoryStorage instance."""
    return MemoryStorage()


@pytest.fixture
def fake_redis():
    """Create a fakeredis async client that mimics redis.asyncio.Redis."""
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def redis_storage(fake_redis):
    """RedisStorage backed by fakeredis."""
    return RedisStorage(fake_redis)


@pytest.fixture
def memory_task_manager(memory_storage):
    """TaskManager with MemoryStorage backend."""
    return TaskManager(
        max_concurrent=2,
        max_queue_size=10,
        result_ttl_seconds=60,
        storage=memory_storage,
    )


@pytest.fixture
def redis_task_manager(redis_storage):
    """TaskManager with RedisStorage backend."""
    return TaskManager(
        max_concurrent=2,
        max_queue_size=10,
        result_ttl_seconds=60,
        storage=redis_storage,
    )


@pytest.fixture
def memory_rate_limiter(memory_storage):
    """RateLimiter with MemoryStorage backend."""
    return RateLimiter(
        max_requests=5,
        window_seconds=60,
        enabled=True,
        storage=memory_storage,
    )


@pytest.fixture
def redis_rate_limiter(redis_storage):
    """RateLimiter with RedisStorage backend."""
    return RateLimiter(
        max_requests=5,
        window_seconds=60,
        enabled=True,
        storage=redis_storage,
    )


# ---------------------------------------------------------------------------
# Storage Protocol Parity — same operations, same results
# ---------------------------------------------------------------------------


class TestStorageParity:
    """Both backends should produce identical results for the same operations."""

    @pytest.mark.asyncio
    async def test_set_get_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """set/get should behave identically."""
        for storage in (memory_storage, redis_storage):
            await storage.set("key", "value")
            assert await storage.get("key") == "value"

    @pytest.mark.asyncio
    async def test_delete_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """delete should behave identically."""
        for storage in (memory_storage, redis_storage):
            await storage.set("key", "value")
            await storage.delete("key")
            assert await storage.get("key") is None

    @pytest.mark.asyncio
    async def test_exists_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """exists should behave identically."""
        for storage in (memory_storage, redis_storage):
            await storage.set("key", "value")
            assert await storage.exists("key") is True
            await storage.delete("key")
            assert await storage.exists("key") is False

    @pytest.mark.asyncio
    async def test_incr_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """incr should behave identically."""
        for storage in (memory_storage, redis_storage):
            v1 = await storage.incr("counter")
            v2 = await storage.incr("counter")
            v3 = await storage.incr("counter")
            assert v1 == 1
            assert v2 == 2
            assert v3 == 3

    @pytest.mark.asyncio
    async def test_json_roundtrip_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """JSON serialised values should round-trip identically."""
        data = json.dumps({"task_id": "abc123", "status": "completed"})
        for storage in (memory_storage, redis_storage):
            await storage.set("task:abc123", data)
            result = await storage.get("task:abc123")
            assert json.loads(result or "") == {
                "task_id": "abc123",
                "status": "completed",
            }

    @pytest.mark.asyncio
    async def test_empty_string_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """Empty strings should be stored and retrieved correctly."""
        for storage in (memory_storage, redis_storage):
            await storage.set("key", "")
            assert await storage.get("key") == ""

    @pytest.mark.asyncio
    async def test_large_value_parity(
        self, memory_storage: StorageProtocol, redis_storage: StorageProtocol
    ):
        """Large values should be handled identically."""
        large_value = "x" * 100_000  # ~100 KB
        for storage in (memory_storage, redis_storage):
            await storage.set("large", large_value)
            assert await storage.get("large") == large_value


# ---------------------------------------------------------------------------
# TaskManager Backend Switching
# ---------------------------------------------------------------------------


class TestTaskManagerSwitching:
    """TaskManager should work identically with MemoryStorage and RedisStorage."""

    @pytest.mark.asyncio
    async def test_task_lifecycle_memory(self, memory_task_manager: TaskManager):
        """Full task lifecycle with MemoryStorage."""

        async def success_task():
            return {"output": "done"}

        task_id = memory_task_manager.submit(success_task)
        # Wait for task to complete
        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await memory_task_manager.get_task_with_storage(task_id)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"output": "done"}

    @pytest.mark.asyncio
    async def test_task_lifecycle_redis(self, redis_task_manager: TaskManager):
        """Full task lifecycle with RedisStorage."""

        async def success_task():
            return {"output": "done"}

        task_id = redis_task_manager.submit(success_task)
        # Wait for task to complete
        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await redis_task_manager.get_task_with_storage(task_id)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"output": "done"}

    @pytest.mark.asyncio
    async def test_task_failure_memory(self, memory_task_manager: TaskManager):
        """Task failure should be handled identically."""

        async def failing_task():
            raise RuntimeError("conversion failed")

        task_id = memory_task_manager.submit(failing_task)
        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await memory_task_manager.get_task_with_storage(task_id)
            if result and result.status == TaskStatus.FAILED:
                break
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert result.error == "CONVERSION_FAILED"
        assert "conversion failed" in (result.error_detail or "")

    @pytest.mark.asyncio
    async def test_task_failure_redis(self, redis_task_manager: TaskManager):
        """Task failure should be handled identically with Redis."""

        async def failing_task():
            raise RuntimeError("conversion failed")

        task_id = redis_task_manager.submit(failing_task)
        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await redis_task_manager.get_task_with_storage(task_id)
            if result and result.status == TaskStatus.FAILED:
                break
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert result.error == "CONVERSION_FAILED"
        assert "conversion failed" in (result.error_detail or "")

    @pytest.mark.asyncio
    async def test_batch_memory(self, memory_task_manager: TaskManager):
        """Batch submission should work with MemoryStorage."""

        async def convert_task(content, ext):
            return {"output": f"converted {ext}"}

        batch_id = "test-batch-mem"
        filenames = ["file0.pdf", "file1.pdf", "file2.pdf"]
        contents_and_exts = [(b"fake-content", "pdf") for _ in range(3)]

        task_ids = memory_task_manager.submit_batch(
            batch_id, filenames, convert_task, contents_and_exts
        )
        assert len(task_ids) == 3

        # Wait for tasks to complete
        for _ in range(20):
            await asyncio.sleep(0.1)
            batch = memory_task_manager.get_batch(batch_id)
            if batch is None:
                continue
            all_done = True
            for tid in task_ids:
                task = await memory_task_manager.get_task(tid)
                if task is None or task.status != TaskStatus.COMPLETED:
                    all_done = False
                    break
            if all_done:
                break

        batch = memory_task_manager.get_batch(batch_id)
        assert batch is not None
        assert len(batch.task_ids) == 3

    @pytest.mark.asyncio
    async def test_batch_redis(self, redis_task_manager: TaskManager):
        """Batch submission should work with RedisStorage."""

        async def convert_task(content, ext):
            return {"output": f"converted {ext}"}

        batch_id = "test-batch-redis"
        filenames = ["file0.pdf", "file1.pdf", "file2.pdf"]
        contents_and_exts = [(b"fake-content", "pdf") for _ in range(3)]

        task_ids = redis_task_manager.submit_batch(
            batch_id, filenames, convert_task, contents_and_exts
        )
        assert len(task_ids) == 3

        # Wait for tasks to complete
        for _ in range(20):
            await asyncio.sleep(0.1)
            all_done = True
            for tid in task_ids:
                result = await redis_task_manager.get_task_with_storage(tid)
                if result is None or result.status != TaskStatus.COMPLETED:
                    all_done = False
                    break
            if all_done:
                break

        batch = await redis_task_manager.get_batch_with_storage(batch_id)
        assert batch is not None
        assert len(batch.task_ids) == 3

    @pytest.mark.asyncio
    async def test_task_result_ttl_memory(self):
        """Task results should expire with MemoryStorage after in-memory cache is cleared.

        Simulates a restart scenario where the in-memory cache is lost but storage
        should have expired the key via TTL.
        """

        async def success_task():
            return {"output": "done"}

        mem_store = MemoryStorage()
        short_tm = TaskManager(
            max_concurrent=2,
            max_queue_size=10,
            result_ttl_seconds=1,
            storage=mem_store,
        )

        task_id = short_tm.submit(success_task)
        # Wait for completion
        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await short_tm.get_task_with_storage(task_id)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None

        # Simulate restart: clear in-memory cache (tasks dict)
        short_tm._tasks.clear()

        # Wait for TTL expiry in storage
        await asyncio.sleep(1.5)
        expired_result = await short_tm.get_task_with_storage(task_id)
        assert expired_result is None

    @pytest.mark.asyncio
    async def test_task_result_ttl_redis(self, fake_redis):
        """Task results should expire with RedisStorage after in-memory cache is cleared.

        Simulates a restart scenario where the in-memory cache is lost but Redis
        should have expired the key via EXPIRE.
        """

        async def success_task():
            return {"output": "done"}

        redis_store = RedisStorage(fake_redis)
        short_tm = TaskManager(
            max_concurrent=2,
            max_queue_size=10,
            result_ttl_seconds=1,
            storage=redis_store,
        )

        task_id = short_tm.submit(success_task)
        # Wait for completion
        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await short_tm.get_task_with_storage(task_id)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None

        # Simulate restart: clear in-memory cache (tasks dict)
        short_tm._tasks.clear()

        # Wait for TTL expiry in Redis
        await asyncio.sleep(1.5)
        expired_result = await short_tm.get_task_with_storage(task_id)
        assert expired_result is None


# ---------------------------------------------------------------------------
# RateLimiter Backend Switching
# ---------------------------------------------------------------------------


class TestRateLimiterSwitching:
    """RateLimiter should work identically with MemoryStorage and RedisStorage."""

    @pytest.mark.asyncio
    async def test_allow_within_limit_memory(self, memory_rate_limiter: RateLimiter):
        """Requests within limit should be allowed."""
        for _ in range(5):
            assert await memory_rate_limiter.is_allowed("192.168.1.1") is True

    @pytest.mark.asyncio
    async def test_allow_within_limit_redis(self, redis_rate_limiter: RateLimiter):
        """Requests within limit should be allowed with Redis."""
        for _ in range(5):
            assert await redis_rate_limiter.is_allowed("192.168.1.1") is True

    @pytest.mark.asyncio
    async def test_deny_over_limit_memory(self, memory_rate_limiter: RateLimiter):
        """Requests over limit should be denied."""
        for _ in range(5):
            await memory_rate_limiter.is_allowed("192.168.1.1")
        assert await memory_rate_limiter.is_allowed("192.168.1.1") is False

    @pytest.mark.asyncio
    async def test_deny_over_limit_redis(self, redis_rate_limiter: RateLimiter):
        """Requests over limit should be denied with Redis."""
        for _ in range(5):
            await redis_rate_limiter.is_allowed("192.168.1.1")
        assert await redis_rate_limiter.is_allowed("192.168.1.1") is False

    @pytest.mark.asyncio
    async def test_independent_keys_memory(self, memory_rate_limiter: RateLimiter):
        """Different IPs should have independent limits."""
        for _ in range(5):
            await memory_rate_limiter.is_allowed("10.0.0.1")
        # 10.0.0.1 is exhausted, but 10.0.0.2 should still be allowed
        assert await memory_rate_limiter.is_allowed("10.0.0.2") is True

    @pytest.mark.asyncio
    async def test_independent_keys_redis(self, redis_rate_limiter: RateLimiter):
        """Different IPs should have independent limits with Redis."""
        for _ in range(5):
            await redis_rate_limiter.is_allowed("10.0.0.1")
        # 10.0.0.1 is exhausted, but 10.0.0.2 should still be allowed
        assert await redis_rate_limiter.is_allowed("10.0.0.2") is True

    @pytest.mark.asyncio
    async def test_disabled_memory(self, memory_storage: StorageProtocol):
        """Disabled rate limiter should always allow."""
        rl = RateLimiter(
            max_requests=1, window_seconds=60, enabled=False, storage=memory_storage
        )
        for _ in range(10):
            assert await rl.is_allowed("any") is True

    @pytest.mark.asyncio
    async def test_disabled_redis(self, redis_storage: StorageProtocol):
        """Disabled rate limiter should always allow with Redis."""
        rl = RateLimiter(
            max_requests=1, window_seconds=60, enabled=False, storage=redis_storage
        )
        for _ in range(10):
            assert await rl.is_allowed("any") is True


# ---------------------------------------------------------------------------
# Full Switching Regression — Memory → Redis → Memory
# ---------------------------------------------------------------------------


class TestFullSwitchingRegression:
    """Verify no regression when switching between backends."""

    @pytest.mark.asyncio
    async def test_memory_to_redis_to_memory_task_manager(self, fake_redis):
        """Submit tasks with MemoryStorage, then RedisStorage, then MemoryStorage again.

        Each backend should work independently without interference.
        """

        async def mem_task():
            return {"backend": "memory"}

        async def redis_task():
            return {"backend": "redis"}

        async def mem2_task():
            return {"backend": "memory-again"}

        # Phase 1: MemoryStorage
        mem_store = MemoryStorage()
        mem_tm = TaskManager(
            max_concurrent=2,
            max_queue_size=10,
            result_ttl_seconds=60,
            storage=mem_store,
        )

        task_id_mem = mem_tm.submit(mem_task)

        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await mem_tm.get_task_with_storage(task_id_mem)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"backend": "memory"}

        # Phase 2: RedisStorage
        redis_store = RedisStorage(fake_redis)
        redis_tm = TaskManager(
            max_concurrent=2,
            max_queue_size=10,
            result_ttl_seconds=60,
            storage=redis_store,
        )

        task_id_redis = redis_tm.submit(redis_task)

        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await redis_tm.get_task_with_storage(task_id_redis)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"backend": "redis"}

        # Phase 3: Back to MemoryStorage (fresh instance)
        mem_store2 = MemoryStorage()
        mem_tm2 = TaskManager(
            max_concurrent=2,
            max_queue_size=10,
            result_ttl_seconds=60,
            storage=mem_store2,
        )

        task_id_mem2 = mem_tm2.submit(mem2_task)

        for _ in range(20):
            await asyncio.sleep(0.1)
            result = await mem_tm2.get_task_with_storage(task_id_mem2)
            if result and result.status == TaskStatus.COMPLETED:
                break
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"backend": "memory-again"}

        # Verify no cross-contamination: memory task IDs shouldn't exist in Redis
        redis_result = await redis_tm.get_task_with_storage(task_id_mem)
        assert redis_result is None

        mem_result = await mem_tm.get_task_with_storage(task_id_redis)
        assert mem_result is None

    @pytest.mark.asyncio
    async def test_memory_to_redis_to_memory_rate_limiter(self, fake_redis):
        """Rate limiting should work correctly across backend switches."""
        # Phase 1: MemoryStorage
        mem_store = MemoryStorage()
        mem_rl = RateLimiter(
            max_requests=3, window_seconds=60, enabled=True, storage=mem_store
        )

        for _ in range(3):
            assert await mem_rl.is_allowed("ip1") is True
        assert await mem_rl.is_allowed("ip1") is False  # Should be denied

        # Phase 2: RedisStorage — independent counters
        redis_store = RedisStorage(fake_redis)
        redis_rl = RateLimiter(
            max_requests=3, window_seconds=60, enabled=True, storage=redis_store
        )

        for _ in range(3):
            assert await redis_rl.is_allowed("ip1") is True
        assert await redis_rl.is_allowed("ip1") is False  # Should be denied

        # Phase 3: Back to MemoryStorage — fresh counters
        mem_store2 = MemoryStorage()
        mem_rl2 = RateLimiter(
            max_requests=3, window_seconds=60, enabled=True, storage=mem_store2
        )

        for _ in range(3):
            assert await mem_rl2.is_allowed("ip1") is True
        assert await mem_rl2.is_allowed("ip1") is False  # Should be denied
