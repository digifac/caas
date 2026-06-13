"""Tests for the RateLimiter (sliding window, cleanup, edge cases, storage-backed)."""

import asyncio

import pytest
from app.rate_limiter import RateLimiter
from app.storage.memory import MemoryStorage

# Import fixtures from modules
from tests.fixtures.common import sample_pdf_bytes

# --- Basic allow/deny tests (in-memory mode) ---


class TestRateLimiterBasic:
    """Tests for core rate limiting behavior."""

    @pytest.mark.anyio
    async def test_allows_when_under_limit(self):
        """Requests under the limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_denies_when_limit_reached(self):
        """Requests exceeding the limit are denied."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is False

    @pytest.mark.anyio
    async def test_different_keys_independent(self):
        """Each key has its own counter."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        await limiter.is_allowed("ip1")
        await limiter.is_allowed("ip1")
        assert await limiter.is_allowed("ip1") is False
        # ip2 should still be allowed
        assert await limiter.is_allowed("ip2") is True

    @pytest.mark.anyio
    async def test_sliding_window_allows_after_expiry(self):
        """Requests are allowed again after the window expires."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        await limiter.is_allowed("127.0.0.1")
        await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is False
        # Wait for the window to expire
        await asyncio.sleep(1.1)
        assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_disabled_always_allows(self):
        """When disabled, all requests are allowed."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, enabled=False)
        await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_toggle_enabled(self):
        """Enabling/disabling rate limiter works dynamically."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, enabled=True)
        await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is False
        limiter.enabled = False
        assert await limiter.is_allowed("127.0.0.1") is True
        limiter.enabled = True
        assert await limiter.is_allowed("127.0.0.1") is False


# --- Cleanup tests (in-memory mode) ---


class TestRateLimiterCleanup:
    """Tests for cleanup mechanisms."""

    @pytest.mark.anyio
    async def test_cleanup_removes_expired_timestamps(self):
        """_cleanup removes timestamps outside the window."""
        limiter = RateLimiter(max_requests=10, window_seconds=1)
        await limiter.is_allowed("127.0.0.1")
        await limiter.is_allowed("127.0.0.1")
        assert len(limiter._requests["127.0.0.1"]) == 2
        await asyncio.sleep(1.1)
        limiter._cleanup("127.0.0.1")
        assert "127.0.0.1" not in limiter._requests

    @pytest.mark.anyio
    async def test_cleanup_all_removes_empty_keys(self):
        """_cleanup_all removes keys with no remaining timestamps."""
        limiter = RateLimiter(max_requests=10, window_seconds=1)
        await limiter.is_allowed("ip1")
        await limiter.is_allowed("ip2")
        await asyncio.sleep(1.1)
        removed = limiter._cleanup_all()
        assert removed == 2
        assert len(limiter._requests) == 0

    @pytest.mark.anyio
    async def test_cleanup_all_returns_count(self):
        """_cleanup_all returns the number of removed keys."""
        limiter = RateLimiter(max_requests=10, window_seconds=1)
        await limiter.is_allowed("ip1")
        await limiter.is_allowed("ip2")
        await limiter.is_allowed("ip3")
        await asyncio.sleep(1.1)
        removed = limiter._cleanup_all()
        assert removed == 3

    @pytest.mark.anyio
    async def test_cleanup_all_keeps_active_keys(self):
        """_cleanup_all keeps keys with recent timestamps."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        await limiter.is_allowed("ip1")
        await limiter.is_allowed("ip2")
        removed = limiter._cleanup_all()
        assert removed == 0
        assert "ip1" in limiter._requests
        assert "ip2" in limiter._requests

    @pytest.mark.anyio
    async def test_reset_clears_all(self):
        """reset() clears all stored requests."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        await limiter.is_allowed("ip1")
        await limiter.is_allowed("ip2")
        await limiter.reset()
        assert len(limiter._requests) == 0

    @pytest.mark.anyio
    async def test_periodic_cleanup_runs(self):
        """Periodic cleanup task starts and runs in the background."""
        limiter = RateLimiter(
            max_requests=10, window_seconds=1, cleanup_interval_seconds=1
        )
        await limiter.is_allowed("ip1")
        await asyncio.sleep(1.1)
        # Wait for periodic cleanup to run (cleanup_interval + buffer)
        await asyncio.sleep(1.5)
        # The key should have been cleaned up
        assert "ip1" not in limiter._requests


# --- Edge cases (in-memory mode) ---


class TestRateLimiterEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_single_request_limit(self):
        """Limit of 1 request works correctly."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert await limiter.is_allowed("127.0.0.1") is True
        assert await limiter.is_allowed("127.0.0.1") is False

    @pytest.mark.anyio
    async def test_zero_window(self):
        """Window of 0 seconds means every request is denied after the first batch expires immediately."""
        limiter = RateLimiter(max_requests=5, window_seconds=0)
        # With 0 window, timestamps are immediately expired
        for _ in range(10):
            assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_large_number_of_keys(self):
        """Many unique keys don't cause issues."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        for i in range(100):
            await limiter.is_allowed(f"ip_{i}")
        assert len(limiter._requests) == 100

    def test_cleanup_empty_dict(self):
        """_cleanup_all on empty dict doesn't raise."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        removed = limiter._cleanup_all()
        assert removed == 0

    def test_cleanup_nonexistent_key(self):
        """_cleanup on a key that doesn't exist doesn't raise."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        limiter._cleanup("nonexistent")
        assert len(limiter._requests) == 0

    def test_enabled_property_getter_setter(self):
        """enabled property getter/setter works correctly."""
        limiter = RateLimiter(enabled=True)
        assert limiter.enabled is True
        limiter.enabled = False
        assert limiter.enabled is False
        limiter.enabled = True
        assert limiter.enabled is True

    def test_default_values(self):
        """Default constructor values are correct."""
        limiter = RateLimiter()
        assert limiter.max_requests == 30
        assert limiter.window_seconds == 60
        assert limiter.enabled is True
        assert limiter.cleanup_interval == 120


# --- Storage-backed tests ---


class TestRateLimiterStorage:
    """Tests for RateLimiter with StorageProtocol backend."""

    @pytest.mark.anyio
    async def test_storage_mode_allows_under_limit(self):
        """Storage-backed mode allows requests under the limit."""
        storage = MemoryStorage()
        limiter = RateLimiter(max_requests=5, window_seconds=60, storage=storage)
        for _ in range(5):
            assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_storage_mode_denies_when_limit_reached(self):
        """Storage-backed mode denies requests exceeding the limit."""
        storage = MemoryStorage()
        limiter = RateLimiter(max_requests=3, window_seconds=60, storage=storage)
        for _ in range(3):
            await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is False

    @pytest.mark.anyio
    async def test_storage_mode_different_keys_independent(self):
        """Each key has its own counter in storage mode."""
        storage = MemoryStorage()
        limiter = RateLimiter(max_requests=2, window_seconds=60, storage=storage)
        await limiter.is_allowed("ip1")
        await limiter.is_allowed("ip1")
        assert await limiter.is_allowed("ip1") is False
        assert await limiter.is_allowed("ip2") is True

    @pytest.mark.anyio
    async def test_storage_mode_disabled_always_allows(self):
        """When disabled, storage mode also allows all requests."""
        storage = MemoryStorage()
        limiter = RateLimiter(
            max_requests=1, window_seconds=60, enabled=False, storage=storage
        )
        await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_storage_mode_expiry(self):
        """Storage-backed mode respects TTL expiry."""
        storage = MemoryStorage()
        limiter = RateLimiter(max_requests=2, window_seconds=1, storage=storage)
        await limiter.is_allowed("127.0.0.1")
        await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is False
        # Wait for TTL to expire
        await asyncio.sleep(1.1)
        assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.anyio
    async def test_storage_mode_no_periodic_cleanup_needed(self):
        """Storage-backed mode doesn't start periodic cleanup task."""
        storage = MemoryStorage()
        limiter = RateLimiter(max_requests=10, window_seconds=60, storage=storage)
        await limiter.is_allowed("ip1")
        # No cleanup task should be created
        assert limiter._cleanup_task is None
