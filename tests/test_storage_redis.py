"""Tests for RedisStorage using fakeredis (no real Redis required).

Marked with @pytest.mark.redis so they can be selected/deselected with -m redis.
"""

import asyncio

import fakeredis.aioredis  # type: ignore[import-untyped]
import pytest
from app.storage.redis import RedisStorage


@pytest.fixture
def fake_redis():
    """Create a fakeredis async client that mimics redis.asyncio.Redis."""
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def storage(fake_redis):
    """RedisStorage backed by fakeredis."""
    return RedisStorage(fake_redis)


# -- get / set --


class TestRedisStorageGetSet:
    """Tests for basic get/set operations with RedisStorage."""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_set_and_get(self, storage):
        """Setting a key should make it retrievable."""
        await storage.set("key", "value")
        result = await storage.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_get_nonexistent_key_returns_none(self, storage):
        """Getting a key that was never set should return None."""
        result = await storage.get("missing")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_overwrite_existing_key(self, storage):
        """Setting a key twice should overwrite the previous value."""
        await storage.set("key", "v1")
        await storage.set("key", "v2")
        assert await storage.get("key") == "v2"

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_set_with_ttl(self, storage):
        """Setting a key with TTL should store it normally until expiry."""
        await storage.set("key", "value", ttl=10)
        assert await storage.get("key") == "value"

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_ttl_expiry(self, storage):
        """A key with TTL should become inaccessible after expiry."""
        await storage.set("key", "value", ttl=1)
        assert await storage.get("key") == "value"
        await asyncio.sleep(1.1)
        assert await storage.get("key") is None

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_empty_string_value(self, storage):
        """An empty string should be stored and retrieved correctly."""
        await storage.set("key", "")
        assert await storage.get("key") == ""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_json_value(self, storage):
        """JSON-serialised values should round-trip correctly."""
        import json

        data = json.dumps({"task_id": "abc", "status": "done"})
        await storage.set("task:abc", data)
        result = await storage.get("task:abc")
        assert json.loads(result) == {"task_id": "abc", "status": "done"}


# -- delete --


class TestRedisStorageDelete:
    """Tests for delete operations with RedisStorage."""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_delete_existing_key(self, storage):
        """Deleting a key should make it inaccessible."""
        await storage.set("key", "value")
        await storage.delete("key")
        assert await storage.get("key") is None

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_delete_nonexistent_key_is_noop(self, storage):
        """Deleting a key that doesn't exist should not raise."""
        await storage.delete("missing")  # should not raise


# -- exists --


class TestRedisStorageExists:
    """Tests for exists operations with RedisStorage."""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_exists_true(self, storage):
        """exists() should return True for a stored key."""
        await storage.set("key", "value")
        assert await storage.exists("key") is True

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_exists_false(self, storage):
        """exists() should return False for a missing key."""
        assert await storage.exists("missing") is False

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_exists_after_delete(self, storage):
        """exists() should return False after deletion."""
        await storage.set("key", "value")
        await storage.delete("key")
        assert await storage.exists("key") is False

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_exists_after_ttl_expiry(self, storage):
        """exists() should return False after TTL expiry."""
        await storage.set("key", "value", ttl=1)
        await asyncio.sleep(1.1)
        assert await storage.exists("key") is False


# -- incr --


class TestRedisStorageIncr:
    """Tests for incr operations with RedisStorage."""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_incr_new_key(self, storage):
        """Incrementing a new key should return 1."""
        result = await storage.incr("counter")
        assert result == 1

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_incr_multiple_times(self, storage):
        """Repeated increments should return sequential integers."""
        assert await storage.incr("counter") == 1
        assert await storage.incr("counter") == 2
        assert await storage.incr("counter") == 3

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_incr_with_ttl_first_call(self, storage):
        """Incrementing with TTL should apply TTL on first call."""
        await storage.incr("counter", ttl=1)
        assert await storage.exists("counter") is True
        await asyncio.sleep(1.1)
        assert await storage.exists("counter") is False

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_incr_independent_keys(self, storage):
        """Different keys should have independent counters."""
        await storage.incr("a")
        await storage.incr("a")
        await storage.incr("b")
        assert await storage.incr("a") == 3
        assert await storage.incr("b") == 2


# -- protocol conformance --


class TestRedisStorageProtocolConformance:
    """Verify RedisStorage implements StorageProtocol correctly."""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_all_protocol_methods_exist(self, storage):
        """All StorageProtocol methods should be callable."""
        assert callable(storage.get)
        assert callable(storage.set)
        assert callable(storage.delete)
        assert callable(storage.exists)
        assert callable(storage.incr)

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_storage_protocol_interface(self, storage):
        """RedisStorage should be an instance of StorageProtocol."""
        from app.storage.base import StorageProtocol

        assert isinstance(storage, StorageProtocol)


# -- parity with MemoryStorage --


class TestRedisStorageParity:
    """Ensure RedisStorage behaves the same as MemoryStorage for shared workflows."""

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_task_manager_workflow(self, storage):
        """Simulate a TaskManager-like workflow: set JSON, get, delete."""
        import json

        task_data = json.dumps({"id": "t1", "status": "completed", "output": "ok"})
        await storage.set("task:t1", task_data, ttl=300)
        assert await storage.exists("task:t1") is True
        result = json.loads(await storage.get("task:t1"))
        assert result["status"] == "completed"
        await storage.delete("task:t1")
        assert await storage.exists("task:t1") is False

    @pytest.mark.asyncio
    @pytest.mark.redis
    async def test_rate_limiter_workflow(self, storage):
        """Simulate a RateLimiter-like workflow: incr with TTL."""
        window = 60
        for _ in range(5):
            count = await storage.incr("rate:127.0.0.1", ttl=window)
        assert count == 5
        # Key should exist and have the right value
        assert await storage.exists("rate:127.0.0.1") is True
