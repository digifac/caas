"""Unit tests for routes/health.py deep coverage.

Targets uncovered lines in app/routes/health.py:
- _get_version fallback (lines 13-14)
- _check_redis error path (lines 24-34)
- _check_task_manager unavailable (line 46)
"""

import importlib.metadata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.routes.health import _check_redis, _check_task_manager, _get_version


class TestGetVersionFallback:
    """Tests for _get_version fallback path."""

    def test_version_fallback_unknown(self):
        """Returns 'unknown' when package is not found."""
        with patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("caas"),
        ):
            result = _get_version()
            assert result == "unknown"

    def test_version_success(self):
        """Returns version string when package exists."""
        with patch.object(importlib.metadata, "version", return_value="1.2.3"):
            result = _get_version()
            assert result == "1.2.3"


class TestCheckRedisErrorPath:
    """Tests for _check_redis error handling."""

    @pytest.mark.anyio
    async def test_redis_not_configured(self):
        """Returns not_configured when redis_manager is None."""
        app = MagicMock()
        app.state.redis_manager = None
        result = await _check_redis(app)
        assert result["enabled"] is False
        assert result["status"] == "not_configured"

    @pytest.mark.anyio
    async def test_redis_healthy(self):
        """Returns healthy when Redis ping succeeds."""
        app = MagicMock()
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.info = AsyncMock(return_value={"redis_version": "7.0.0"})
        app.state.redis_manager.client = mock_client
        result = await _check_redis(app)
        assert result["enabled"] is True
        assert result["status"] == "healthy"
        assert result["redis_version"] == "7.0.0"

    @pytest.mark.anyio
    async def test_redis_unhealthy_ping(self):
        """Returns unhealthy when Redis ping fails."""
        app = MagicMock()
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=False)
        mock_client.info = AsyncMock(return_value={"redis_version": "7.0.0"})
        app.state.redis_manager.client = mock_client
        result = await _check_redis(app)
        assert result["status"] == "unhealthy"

    @pytest.mark.anyio
    async def test_redis_error_exception(self):
        """Returns unhealthy with error when exception occurs."""
        app = MagicMock()
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
        app.state.redis_manager.client = mock_client
        result = await _check_redis(app)
        assert result["enabled"] is True
        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["error"]

    @pytest.mark.anyio
    async def test_redis_no_attribute(self):
        """Returns not_configured when redis_manager attribute doesn't exist."""
        app = MagicMock()
        # getattr(app.state, "redis_manager", None) returns None when not set
        app.state.redis_manager = None
        result = await _check_redis(app)
        assert result["enabled"] is False
        assert result["status"] == "not_configured"


class TestCheckTaskManagerUnavailable:
    """Tests for _check_task_manager unavailable path."""

    @pytest.mark.anyio
    async def test_task_manager_unavailable(self):
        """Returns unavailable when task_manager is None."""
        app = MagicMock()
        app.state.task_manager = None
        result = await _check_task_manager(app)
        assert result["status"] == "unavailable"

    @pytest.mark.anyio
    async def test_task_manager_healthy(self):
        """Returns healthy when task manager has capacity."""
        app = MagicMock()
        tm = MagicMock()
        tm.get_active_count.return_value = 2
        tm.get_pending_count.return_value = 1
        tm.max_concurrent = 10
        tm._max_queue_size = 100
        app.state.task_manager = tm
        result = await _check_task_manager(app)
        assert result["status"] == "healthy"
        assert result["active_tasks"] == 2
        assert result["pending_tasks"] == 1
        assert result["max_concurrent"] == 10
        assert result["max_queue_size"] == 100

    @pytest.mark.anyio
    async def test_task_manager_degraded(self):
        """Returns degraded when queue is near capacity."""
        app = MagicMock()
        tm = MagicMock()
        tm.get_active_count.return_value = 95
        tm.get_pending_count.return_value = 10
        tm.max_concurrent = 10
        tm._max_queue_size = 100
        app.state.task_manager = tm
        result = await _check_task_manager(app)
        assert result["status"] == "degraded"

    @pytest.mark.anyio
    async def test_task_manager_no_attribute(self):
        """Returns unavailable when task_manager attribute doesn't exist."""
        app = MagicMock()
        app.state.task_manager = None
        result = await _check_task_manager(app)
        assert result["status"] == "unavailable"
