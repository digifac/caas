"""Optional Redis client with lazy import and clear error messaging."""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is configured but the redis package is not installed."""


if TYPE_CHECKING:
    import redis.asyncio as aioredis


class RedisManager:
    """Manages the lifecycle of a Redis client instance.

    Replaces the previous module-level singleton with an explicit,
    injectable manager — safer for tests and hot-reload scenarios.
    """

    def __init__(self, url: str) -> None:
        """
        Args:
            url: Redis connection URL (e.g., 'redis://localhost:6379/0').
        """
        self._url = url
        self._client: aioredis.Redis | None = None

    @property
    def client(self) -> "aioredis.Redis":
        """Get or lazily create the Redis client.

        Returns:
            An async Redis client instance.

        Raises:
            RedisUnavailableError: If the redis package is not installed.
            RuntimeError: If Redis server is not accessible.
        """
        if self._client is not None:
            return self._client

        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise RedisUnavailableError(
                "Redis is configured (CAAS_REDIS_URL is set) but the 'redis' package "
                "is not installed. Install it with: pip install caas[redis]"
            ) from exc

        try:
            self._client = aioredis.from_url(
                self._url,
                decode_responses=True,
            )
            logger.info("Redis client initialized: %s", self._url)
            return self._client
        except ConnectionError as exc:
            raise RuntimeError(
                f"Redis is configured ({self._url}) but the server is not accessible: {exc}"
            ) from exc

    async def close(self) -> None:
        """Close the Redis client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis client closed")
