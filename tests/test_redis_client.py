"""Tests for app/redis_client.py — RedisManager with mocked dependencies."""

import logging
import sys
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
# pylint: disable=protected-access
from app.redis_client import (
    RedisManager,
    RedisUnavailableError,
)

# Import private helpers for testing (intentional)
from app.redis_client import _inject_password
from app.redis_client import _mask_url


class TestMaskUrl:
    """Test the _mask_url helper function."""

    def test_masks_password_in_url(self):
        url = "redis://:mypassword@localhost:6379/0"
        assert _mask_url(url) == "redis://:****@localhost:6379/0"

    def test_masks_password_with_username(self):
        url = "redis://user:mypassword@host:1234/5"
        assert _mask_url(url) == "redis://user:****@host:1234/5"

    def test_returns_url_unchanged_without_credentials(self):
        url = "redis://localhost:6379/0"
        assert _mask_url(url) == url

    def test_returns_url_unchanged_for_invalid_url(self):
        url = "not-a-valid-url"
        assert _mask_url(url) == url


class TestInjectPassword:
    """Test the _inject_password helper function."""

    def test_injects_password_when_none_present(self):
        result = _inject_password("redis://localhost:6379/0", "secret")
        assert result == "redis://:secret@localhost:6379/0"

    def test_injects_password_with_custom_db(self):
        result = _inject_password("redis://myhost:6380/5", "pass123")
        assert result == "redis://:pass123@myhost:6380/5"

    def test_does_not_inject_when_empty_password(self):
        result = _inject_password("redis://localhost:6379/0", "")
        assert result == "redis://localhost:6379/0"

    def test_skips_injection_when_password_already_present(self):
        url = "redis://:existing@localhost:6379/0"
        result = _inject_password(url, "newpass")
        assert result == url

    def test_preserves_query_and_fragment(self):
        result = _inject_password("redis://localhost:6379/0?timeout=5", "pw")
        assert "://" in result and "@" in result


class TestRedisManagerPassword:
    """Test RedisManager with password parameter."""

    def _setup_mock_aioredis(
        self, mock_client: Optional[MagicMock] = None
    ) -> MagicMock:
        mock_aioredis = MagicMock()
        if mock_client is not None:
            mock_aioredis.from_url.return_value = mock_client
        mock_redis = MagicMock()
        mock_redis.asyncio = mock_aioredis
        sys.modules["redis"] = mock_redis
        sys.modules["redis.asyncio"] = mock_aioredis
        return mock_aioredis

    def _cleanup_sys_modules(self) -> None:
        for key in list(sys.modules):
            if key == "redis" or key.startswith("redis."):
                del sys.modules[key]

    def test_init_with_password_injects_into_url(self):
        manager = RedisManager("redis://localhost:6379/0", password="secret")
        assert manager._url == "redis://:secret@localhost:6379/0"

    def test_init_without_password_preserves_url(self):
        manager = RedisManager("redis://localhost:6379/0")
        assert manager._url == "redis://localhost:6379/0"

    def test_init_skips_injection_when_credentials_embedded(self):
        manager = RedisManager(
            "redis://:embedded@localhost:6379/0", password="ignored"
        )
        assert manager._url == "redis://:embedded@localhost:6379/0"

    def test_client_uses_injected_password_url(self):
        self._cleanup_sys_modules()
        mock_client = MagicMock()
        mock_aioredis = self._setup_mock_aioredis(mock_client=mock_client)

        try:
            manager = RedisManager("redis://localhost:6379/0", password="secret")
            _ = manager.client

            mock_aioredis.from_url.assert_called_once_with(
                "redis://:secret@localhost:6379/0",
                decode_responses=True,
            )
        finally:
            self._cleanup_sys_modules()

    def test_log_masks_password_on_init(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._cleanup_sys_modules()
        mock_client = MagicMock()
        self._setup_mock_aioredis(mock_client=mock_client)

        try:
            with caplog.at_level(logging.INFO):
                manager = RedisManager(
                    "redis://localhost:6379/0", password="secret"
                )
                _ = manager.client

                # Verify the log does NOT contain the raw password
                for record in caplog.records:
                    assert "secret" not in record.message
        finally:
            self._cleanup_sys_modules()



class TestRedisManagerInit:
    """Test RedisManager initialization."""

    def test_init_sets_url(self) -> None:
        manager = RedisManager("redis://localhost:6379/0")
        assert manager._url == "redis://localhost:6379/0"
        assert manager._client is None

    def test_init_with_custom_url(self) -> None:
        manager = RedisManager("redis://user:pass@host:1234/5")
        assert manager._url == "redis://user:pass@host:1234/5"


class TestRedisManagerClientProperty:
    """Test the lazy client creation via the .client property."""

    def _setup_mock_aioredis(
        self,
        mock_client: Optional[MagicMock] = None,
        connection_error: bool = False,
    ) -> MagicMock:
        """Helper: inject a fake redis.asyncio into sys.modules."""
        mock_aioredis = MagicMock()
        if connection_error:
            mock_aioredis.from_url.side_effect = ConnectionError(
                "Connection refused"
            )
        elif mock_client is not None:
            mock_aioredis.from_url.return_value = mock_client
        # Also mock parent module so `import redis.asyncio` resolves
        mock_redis = MagicMock()
        mock_redis.asyncio = mock_aioredis
        sys.modules["redis"] = mock_redis
        sys.modules["redis.asyncio"] = mock_aioredis
        return mock_aioredis

    def _cleanup_sys_modules(self) -> None:
        """Remove fake redis modules from sys.modules."""
        for key in list(sys.modules):
            if key == "redis" or key.startswith("redis."):
                del sys.modules[key]

    def test_client_creates_client_on_first_access(self) -> None:
        """First access to .client should create the Redis client."""
        self._cleanup_sys_modules()
        mock_client = MagicMock()
        mock_aioredis = self._setup_mock_aioredis(mock_client=mock_client)

        try:
            manager = RedisManager("redis://localhost:6379/0")
            client = manager.client

            assert client is mock_client
            mock_aioredis.from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                decode_responses=True,
            )
        finally:
            self._cleanup_sys_modules()

    def test_client_returns_cached_on_second_access(self) -> None:
        """Second access to .client should return the cached instance."""
        self._cleanup_sys_modules()
        mock_client = MagicMock()
        mock_aioredis = self._setup_mock_aioredis(mock_client=mock_client)

        try:
            manager = RedisManager("redis://localhost:6379/0")
            client1 = manager.client
            client2 = manager.client

            assert client1 is client2
            assert mock_aioredis.from_url.call_count == 1
        finally:
            self._cleanup_sys_modules()

    def test_client_raises_redis_unavailable_on_import_error(self) -> None:
        """If redis.asyncio import fails, raise RedisUnavailableError."""
        self._cleanup_sys_modules()

        # Custom import hook that blocks redis.asyncio imports
        class RedisImportBlocker:
            def find_spec(
                self,
                name: str,
                path: Optional[Any] = None,
                target: Any = None,
            ) -> Optional[Any]:
                if name == "redis.asyncio" or name == "redis":
                    raise ImportError(f"No module named '{name}'")
                return None

            def find_module(
                self, name: str, path: Optional[Any] = None
            ) -> Optional["RedisImportBlocker"]:
                if name == "redis.asyncio" or name == "redis":
                    return self
                return None

            def load_module(self, name: str) -> Any:
                raise ImportError(f"No module named '{name}'")

        blocker = RedisImportBlocker()

        # Remove redis modules and insert the blocker FIRST in meta_path
        for key in list(sys.modules):
            if key == "redis" or key.startswith("redis."):
                del sys.modules[key]

        sys.meta_path.insert(0, blocker)

        try:
            manager = RedisManager("redis://localhost:6379/0")
            with pytest.raises(
                RedisUnavailableError, match="pip install caas\\[redis\\]"
            ):
                _ = manager.client
        finally:
            sys.meta_path.remove(blocker)
            self._cleanup_sys_modules()

    def test_client_raises_runtime_error_on_connection_error(self) -> None:
        """If Redis server is unreachable, raise RuntimeError."""
        self._cleanup_sys_modules()
        self._setup_mock_aioredis(connection_error=True)

        try:
            manager = RedisManager("redis://localhost:6379/0")
            with pytest.raises(RuntimeError, match="server is not accessible"):
                _ = manager.client
        finally:
            self._cleanup_sys_modules()


class TestRedisManagerClose:
    """Test RedisManager.close() method."""

    def _setup_mock_aioredis(
        self,
        mock_client: Optional[AsyncMock] = None,
        connection_error: bool = False,
    ) -> MagicMock:
        """Helper: inject a fake redis.asyncio into sys.modules."""
        mock_aioredis = MagicMock()
        if connection_error:
            mock_aioredis.from_url.side_effect = ConnectionError(
                "Connection refused"
            )
        elif mock_client is not None:
            mock_aioredis.from_url.return_value = mock_client
        mock_redis = MagicMock()
        mock_redis.asyncio = mock_aioredis
        sys.modules["redis"] = mock_redis
        sys.modules["redis.asyncio"] = mock_aioredis
        return mock_aioredis

    def _cleanup_sys_modules(self) -> None:
        """Remove fake redis modules from sys.modules."""
        for key in list(sys.modules):
            if key == "redis" or key.startswith("redis."):
                del sys.modules[key]

    @pytest.mark.asyncio
    async def test_close_calls_client_aclose(self) -> None:
        """close() should call client.aclose() if a client exists."""
        self._cleanup_sys_modules()
        mock_client = AsyncMock()
        self._setup_mock_aioredis(mock_client=mock_client)

        try:
            manager = RedisManager("redis://localhost:6379/0")
            _ = manager.client  # Trigger client creation
            await manager.close()

            mock_client.aclose.assert_awaited_once()
            assert manager._client is None
        finally:
            self._cleanup_sys_modules()

    @pytest.mark.asyncio
    async def test_close_does_nothing_when_no_client(self) -> None:
        """close() should be a no-op if no client was created."""
        manager = RedisManager("redis://localhost:6379/0")
        await manager.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_resets_client_to_none(self) -> None:
        """close() should reset _client to None."""
        self._cleanup_sys_modules()
        mock_client = AsyncMock()
        self._setup_mock_aioredis(mock_client=mock_client)

        try:
            manager = RedisManager("redis://localhost:6379/0")
            _ = manager.client
            await manager.close()

            assert manager._client is None
        finally:
            self._cleanup_sys_modules()

    @pytest.mark.asyncio
    async def test_client_recreated_after_close(self) -> None:
        """After close(), accessing .client should create a new instance."""
        self._cleanup_sys_modules()
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        mock_aioredis = self._setup_mock_aioredis(mock_client=mock_client1)
        mock_aioredis.from_url.side_effect = [mock_client1, mock_client2]

        try:
            manager = RedisManager("redis://localhost:6379/0")
            c1 = manager.client
            await manager.close()
            c2 = manager.client

            assert c1 is not c2
            assert mock_aioredis.from_url.call_count == 2
        finally:
            self._cleanup_sys_modules()


class TestRedisUnavailableError:
    """Test RedisUnavailableError exception."""

    def test_is_runtime_error_subclass(self) -> None:
        assert issubclass(RedisUnavailableError, RuntimeError)

    def test_error_message_preserved(self) -> None:
        msg = "Custom error message"
        exc = RedisUnavailableError(msg)
        assert str(exc) == msg
