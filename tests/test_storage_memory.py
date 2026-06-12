"""Unit tests for MemoryStorage (in-memory StorageProtocol implementation)."""

import asyncio

import pytest
from app.storage.memory import MemoryStorage


@pytest.fixture
def storage() -> MemoryStorage:
    """Fresh MemoryStorage instance for each test."""
    return MemoryStorage()


# -- get / set --


class TestMemoryStorageGetSet:
    """Tests for basic get/set operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage: MemoryStorage):
        """Setting a key should make it retrievable."""
        await storage.set("key", "value")
        result = await storage.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key_returns_none(self, storage: MemoryStorage):
        """Getting a key that was never set should return None."""
        result = await storage.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self, storage: MemoryStorage):
        """Setting a key twice should overwrite the previous value."""
        await storage.set("key", "v1")
        await storage.set("key", "v2")
        assert await storage.get("key") == "v2"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, storage: MemoryStorage):
        """Setting a key with TTL should store it normally until expiry."""
        await storage.set("key", "value", ttl=10)
        assert await storage.get("key") == "value"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, storage: MemoryStorage):
        """A key with TTL should become inaccessible after expiry."""
        await storage.set("key", "value", ttl=1)
        assert await storage.get("key") == "value"
        await asyncio.sleep(1.1)
        assert await storage.get("key") is None

    @pytest.mark.asyncio
    async def test_empty_string_value(self, storage: MemoryStorage):
        """An empty string should be stored and retrieved correctly."""
        await storage.set("key", "")
        assert await storage.get("key") == ""

    @pytest.mark.asyncio
    async def test_json_value(self, storage: MemoryStorage):
        """JSON-serialised values should round-trip correctly."""
        import json

        data = json.dumps({"task_id": "abc", "status": "done"})
        await storage.set("task:abc", data)
        result = await storage.get("task:abc")
        assert result is not None
        assert json.loads(result) == {"task_id": "abc", "status": "done"}


# -- delete --


class TestMemoryStorageDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, storage: MemoryStorage):
        """Deleting a key should make it inaccessible."""
        await storage.set("key", "value")
        await storage.delete("key")
        assert await storage.get("key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key_is_noop(self, storage: MemoryStorage):
        """Deleting a key that doesn't exist should not raise."""
        await storage.delete("missing")  # should not raise


# -- exists --


class TestMemoryStorageExists:
    """Tests for exists operations."""

    @pytest.mark.asyncio
    async def test_exists_true(self, storage: MemoryStorage):
        """exists() should return True for a stored key."""
        await storage.set("key", "value")
        assert await storage.exists("key") is True

    @pytest.mark.asyncio
    async def test_exists_false(self, storage: MemoryStorage):
        """exists() should return False for a missing key."""
        assert await storage.exists("missing") is False

    @pytest.mark.asyncio
    async def test_exists_after_delete(self, storage: MemoryStorage):
        """exists() should return False after deletion."""
        await storage.set("key", "value")
        await storage.delete("key")
        assert await storage.exists("key") is False

    @pytest.mark.asyncio
    async def test_exists_after_ttl_expiry(self, storage: MemoryStorage):
        """exists() should return False after TTL expiry."""
        await storage.set("key", "value", ttl=1)
        await asyncio.sleep(1.1)
        assert await storage.exists("key") is False


# -- incr --


class TestMemoryStorageIncr:
    """Tests for incr operations."""

    @pytest.mark.asyncio
    async def test_incr_new_key(self, storage: MemoryStorage):
        """Incrementing a new key should return 1."""
        result = await storage.incr("counter")
        assert result == 1

    @pytest.mark.asyncio
    async def test_incr_multiple_times(self, storage: MemoryStorage):
        """Repeated increments should return sequential integers."""
        assert await storage.incr("counter") == 1
        assert await storage.incr("counter") == 2
        assert await storage.incr("counter") == 3

    @pytest.mark.asyncio
    async def test_incr_with_ttl_first_call(self, storage: MemoryStorage):
        """Incrementing with TTL should apply TTL on first call."""
        await storage.incr("counter", ttl=1)
        assert await storage.exists("counter") is True
        await asyncio.sleep(1.1)
        assert await storage.exists("counter") is False

    @pytest.mark.asyncio
    async def test_incr_independent_keys(self, storage: MemoryStorage):
        """Different keys should have independent counters."""
        await storage.incr("a")
        await storage.incr("a")
        await storage.incr("b")
        assert await storage.incr("a") == 3
        assert await storage.incr("b") == 2


# -- concurrency --


class TestMemoryStorageConcurrency:
    """Tests for thread-safety under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_incr(self, storage: MemoryStorage):
        """Concurrent increments should all succeed without lost updates."""

        async def inc():
            for _ in range(100):
                await storage.incr("counter")

        await asyncio.gather(*(inc() for _ in range(10)))
        value = await storage.get("counter")
        assert value is not None
        assert int(value) == 1000

    @pytest.mark.asyncio
    async def test_concurrent_set_get(self, storage: MemoryStorage):
        """Concurrent writes and reads should not corrupt data."""

        async def writer(i: int):
            await storage.set(f"key-{i}", f"value-{i}")

        async def reader(i: int):
            await storage.get(f"key-{i}")

        await asyncio.gather(*(writer(i) for i in range(50)))
        await asyncio.gather(*(reader(i) for i in range(50)))
        for i in range(50):
            assert await storage.get(f"key-{i}") == f"value-{i}"
