"""Implémentation en mémoire du StorageProtocol (dict + TTL)."""

import asyncio
import time

from app.storage.base import StorageProtocol


class MemoryStorage(StorageProtocol):
    """Stockage clé/valeur en mémoire avec support TTL."""

    def __init__(self) -> None:
        # (key, value, expiry_timestamp ou None)
        self._store: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    async def _expired(self, key: str) -> bool:
        """Vérifier si une clé a expiré."""
        if key not in self._store:
            return True
        _, expiry = self._store[key]
        if expiry is not None and time.time() > expiry:
            self._store.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> str | None:
        """Récupérer la valeur associée à une clé."""
        async with self._lock:
            if await self._expired(key):
                return None
            value, _ = self._store[key]
            return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Stocker une valeur avec une clé optionnelle TTL (en secondes)."""
        async with self._lock:
            expiry = time.time() + ttl if ttl is not None else None
            self._store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Supprimer une clé du stockage."""
        async with self._lock:
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Vérifier si une clé existe (et n'a pas expiré)."""
        async with self._lock:
            return not await self._expired(key)

    async def incr(self, key: str, ttl: int | None = None) -> int:
        """Incrémenter une clé numérique de 1 et retourner la nouvelle valeur."""
        async with self._lock:
            if await self._expired(key):
                # Nouvelle clé : initialiser à 1 avec TTL si fourni
                expiry = time.time() + ttl if ttl is not None else None
                self._store[key] = ("1", expiry)
                return 1
            value, expiry = self._store[key]
            new_value = int(value) + 1
            self._store[key] = (str(new_value), expiry)
            return new_value

    async def keys(self, pattern: str) -> list:
        """Récupérer toutes les clés correspondant au pattern (glob-style: 'prefix:*')."""
        import fnmatch

        async with self._lock:
            # Filter out expired keys during scan
            active_keys = [
                k for k, v in self._store.items() if not await self._expired(k)
            ]
            return fnmatch.filter(active_keys, pattern)
