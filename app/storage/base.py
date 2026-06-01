"""Storage abstraction — common protocol for memory and Redis."""

from abc import ABC, abstractmethod


class StorageProtocol(ABC):
    """Asynchronous abstraction protocol for key/value storage."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Retrieve the value associated with a key."""
        ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Store a value with an optional TTL (in seconds)."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from storage."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        ...

    @abstractmethod
    async def incr(self, key: str, ttl: int | None = None) -> int:
        """Increment a numeric key by 1 and return the new value.
        If `ttl` is provided and the key is newly created, apply the TTL."""
        ...

    @abstractmethod
    async def keys(self, pattern: str) -> list:
        """Retrieve all keys matching the pattern (glob-style: 'prefix:*')."""
        ...
