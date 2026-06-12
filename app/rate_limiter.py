"""Native rate limiter (replaces slowapi) — sliding window by IP, zero dependency."""

import asyncio
import logging
import time
from collections import defaultdict

from app.storage.base import StorageProtocol

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter with interchangeable storage backend.

    - In-memory mode (default): sliding window using timestamp lists, periodic cleanup.
    - Redis mode: atomic INCR + EXPIRE, no cleanup needed (handled by Redis TTL).

    Accepts an optional StorageProtocol; if None, falls back to in-memory behavior.
    """

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
        enabled: bool = True,
        cleanup_interval_seconds: int = 120,
        max_keys: int = 10000,
        storage: StorageProtocol | None = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.enabled = enabled
        self.cleanup_interval = cleanup_interval_seconds
        self.max_keys = max_keys
        self._storage = storage
        # In-memory fallback: key -> list of timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    @property
    def _use_storage(self) -> bool:
        """Whether an external storage backend is configured."""
        return self._storage is not None

    # --- In-memory helpers (only used when storage is None) ---

    def _cleanup(self, key: str) -> None:
        """Remove timestamps outside the sliding window and empty keys. Must be called with lock held."""
        now = time.time()
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        if not self._requests[key]:
            del self._requests[key]

    def _cleanup_all(self) -> int:
        """Global cleanup: remove all expired keys (memory leak prevention). Must be called with lock held."""
        now = time.time()
        cutoff = now - self.window_seconds
        keys_to_remove = []
        for key in self._requests:
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            if not self._requests[key]:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._requests[key]
        if keys_to_remove:
            logger.debug(
                "RateLimiter cleanup: %d expired keys removed", len(keys_to_remove)
            )
        return len(keys_to_remove)

    def _evict_oldest_if_over_limit(self) -> None:
        """Evict oldest keys when total key count exceeds max_keys. Must be called with lock held.

        This provides a strict upper bound on memory usage: even under extreme load
        where periodic cleanup hasn't run yet, we never exceed max_keys entries.
        """
        if len(self._requests) <= self.max_keys:
            return
        # Sort keys by their oldest timestamp (ascending) and remove the oldest first
        keys_by_oldest = sorted(
            self._requests.keys(),
            key=lambda k: self._requests[k][0] if self._requests[k] else float("inf"),
        )
        num_to_evict = len(self._requests) - self.max_keys
        evicted = 0
        for key in keys_by_oldest:
            if evicted >= num_to_evict:
                break
            del self._requests[key]
            evicted += 1
        if evicted:
            logger.warning(
                "RateLimiter eviction: %d keys removed (limit %d reached)",
                evicted,
                self.max_keys,
            )

    async def _periodic_cleanup(self):
        """Background periodic cleanup to prevent memory leaks (in-memory mode only)."""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            async with self._lock:
                removed = self._cleanup_all()
            if removed > 0:
                logger.info("RateLimiter: %d expired entries cleaned", removed)

    async def _ensure_cleanup_started(self):
        """Start periodic cleanup on first call (lazy start, in-memory mode only)."""
        async with self._lock:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.ensure_future(self._periodic_cleanup())

    # --- Public API ---

    async def is_allowed(self, key: str) -> bool:
        """
        Check if a request is allowed for the given key.

        Returns:
            True if the request is allowed, False if the limit is exceeded.
        """
        if not self.enabled:
            return True

        if self._use_storage:
            return await self._is_allowed_storage(key)
        else:
            await self._ensure_cleanup_started()
            return await self._is_allowed_memory(key)

    async def _is_allowed_memory(self, key: str) -> bool:
        """In-memory rate limiting using sliding window of timestamps.

        Proactively evicts oldest keys when max_keys is exceeded, guaranteeing
        a strict upper bound on memory consumption regardless of load.
        """
        async with self._lock:
            self._cleanup(key)
            # Evict oldest keys if we've exceeded the hard limit
            self._evict_oldest_if_over_limit()
            if len(self._requests[key]) >= self.max_requests:
                logger.warning(
                    "Rate limit exceeded for %s (%d/%d requests)",
                    key,
                    len(self._requests[key]),
                    self.max_requests,
                )
                return False

            self._requests[key].append(time.time())
            return True

    async def _is_allowed_storage(self, key: str) -> bool:
        """Storage-backed rate limiting using atomic INCR + EXPIRE."""
        assert self._storage is not None, (
            "storage backend required for _is_allowed_storage"
        )
        storage_key = f"ratelimit:{key}"
        count = await self._storage.incr(storage_key, ttl=self.window_seconds)
        if count > self.max_requests:
            logger.warning(
                "Rate limit exceeded for %s (%d/%d requests)",
                key,
                count,
                self.max_requests,
            )
            return False
        return True

    async def reset(self) -> None:
        """Reset all entries (useful for testing)."""
        if self._use_storage:
            # For storage-backed mode, we can't easily enumerate keys,
            # so reset is a no-op in production; tests should use fresh storage.
            logger.info("RateLimiter reset: storage-backed mode — skipping full reset")
        else:
            async with self._lock:
                self._requests.clear()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
