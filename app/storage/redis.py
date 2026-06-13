"""Implémentation Redis du StorageProtocol (redis.asyncio)."""

from typing import TYPE_CHECKING

from app.storage.base import StorageProtocol

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class RedisStorage(StorageProtocol):
    """Stockage clé/valeur via Redis avec support TTL natif."""

    def __init__(self, redis_client: "aioredis.Redis") -> None:
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        """Récupérer la valeur associée à une clé."""
        result = await self._redis.get(key)
        if result is None:
            return None
        if isinstance(result, bytes):
            return result.decode("utf-8")
        value: str = result
        return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Stocker une valeur avec une clé optionnelle TTL (en secondes)."""
        if ttl is not None:
            await self._redis.setex(key, ttl, value)
        else:
            await self._redis.set(key, value)

    async def delete(self, key: str) -> None:
        """Supprimer une clé du stockage."""
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Vérifier si une clé existe."""
        return bool(await self._redis.exists(key))

    async def incr(self, key: str, ttl: int | None = None) -> int:
        """Incrémenter une clé numérique de 1 et retourner la nouvelle valeur.
        Si `ttl` est fourni et que la clé est créée, appliquer le TTL.

        INCR est atomique côté Redis. On utilise sa valeur de retour (1 = nouvelle clé)
        pour appliquer le TTL uniquement au premier appel, évitant la course
        exists → incr → expire du code précédent.
        """
        new_value = await self._redis.incr(key)
        if new_value == 1 and ttl is not None:
            await self._redis.expire(key, ttl)
        count: int = new_value
        return count

    async def keys(self, pattern: str) -> list:
        """Récupérer toutes les clés correspondant au pattern (glob-style: 'prefix:*')."""
        results = await self._redis.keys(pattern)
        # Redis returns bytes, decode to strings
        return [k.decode("utf-8") if isinstance(k, bytes) else k for k in results]
