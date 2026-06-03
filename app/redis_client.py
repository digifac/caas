"""Optional Redis client with lazy import and clear error messaging."""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is configured but the redis package is not installed."""


if TYPE_CHECKING:
    import redis.asyncio as aioredis


def _mask_url(url: str) -> str:
    """Return a redacted version of a Redis URL, hiding credentials.

    'redis://user:mypassword@host:6379/0' → 'redis://user:****@host:6379/0'
    """
    try:
        from urllib.parse import ParseResult, urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.password is not None:
            masked = ParseResult(
                scheme=parsed.scheme,
                netloc=f"{parsed.username}:****@{parsed.hostname or ''}"
                + (f":{parsed.port}" if parsed.port else "")
                ,
                path=parsed.path,
                params=parsed.params,
                query=parsed.query,
                fragment=parsed.fragment,
            )
            return urlunparse(masked)
    except Exception:
        pass
    return url


def _inject_password(url: str, password: str) -> str:
    """Inject a password into a Redis URL if not already present.

    'redis://localhost:6379/0' + 'mypass' → 'redis://:mypass@localhost:6379/0'
    """
    if not password:
        return url

    from urllib.parse import ParseResult, urlparse, urlunparse

    parsed = urlparse(url)
    # Skip injection if credentials are already embedded in the URL
    if parsed.password is not None or (parsed.username and parsed.hostname):
        return url

    hostname = parsed.hostname or "localhost"
    port_str = f":{parsed.port}" if parsed.port else ""
    netloc = f":{password}@{hostname}{port_str}"
    injected = ParseResult(
        scheme=parsed.scheme,
        netloc=netloc,
        path=parsed.path,
        params=parsed.params,
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return urlunparse(injected)


class RedisManager:
    """Manages the lifecycle of a Redis client instance.

    Replaces the previous module-level singleton with an explicit,
    injectable manager — safer for tests and hot-reload scenarios.
    """

    def __init__(self, url: str, password: str = "") -> None:
        """
        Args:
            url: Redis connection URL (e.g., 'redis://localhost:6379/0').
            password: Optional Redis password for requirepass authentication.
                Injected into the URL automatically if not already present.
        """
        self._url = _inject_password(url, password)
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
            logger.info("Redis client initialized: %s", _mask_url(self._url))
            return self._client
        except ConnectionError as exc:
            raise RuntimeError(
                f"Redis is configured ({_mask_url(self._url)}) but the server is not accessible: {exc}"
            ) from exc

    async def close(self) -> None:
        """Close the Redis client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis client closed")
