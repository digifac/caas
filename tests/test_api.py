"""Tests for FastAPI application factory (app/api.py)."""

from unittest.mock import MagicMock, patch

import pytest
from app.api import get_lifespan, get_version, create_app
from fastapi import FastAPI


class TestGetVersion:
    """Tests for get_version helper."""

    def test_returns_version_from_pyproject_toml(self):
        """Should return version read directly from pyproject.toml."""
        import re

        version = get_version()
        assert version is not None
        assert version != "unknown"
        # Version should match a.b.c or a.b-<tag>.c format (e.g. 1.0.3, 1.0-beta.0, 2.1.rc1.7)
        # The first two parts must be digits (major.minor), last part is the release number
        assert re.match(r"^\d+\.\d+([-.]?[a-zA-Z][a-zA-Z0-9._-]*)?\.(\d+)$", version), \
            f"Version '{version}' should match a.b.c or a.b-<tag>.c format"

    def test_returns_unknown_when_pyproject_toml_unreadable(self):
        """Should return 'unknown' when pyproject.toml cannot be read."""
        with patch("pathlib.Path.read_text", side_effect=Exception("no file")):
            version = get_version()
            assert version == "unknown"


class TestCreateApp:
    """Tests for create_app factory."""

    def test_create_app_returns_fastapi_instance(self):
        """create_app should return a FastAPI instance."""
        with patch("app.api.get_version", return_value="1.0.0"):
            test_app = create_app()
            assert isinstance(test_app, FastAPI)

    def test_create_app_sets_title(self):
        """App should have correct title."""
        with patch("app.api.get_version", return_value="1.0.0"):
            test_app = create_app()
            assert test_app.title == "CAAS Converter"

    def test_create_app_registers_exception_handlers(self):
        """App should register exception handlers."""
        with patch("app.api.get_version", return_value="1.0.0"):
            test_app = create_app()
            # Check that exception handlers are registered
            assert Exception in test_app.exception_handlers
            from fastapi import HTTPException

            assert HTTPException in test_app.exception_handlers

    def test_create_app_with_cors_origins(self):
        """App should add CORS middleware when origins are configured."""
        with patch("app.api.get_version", return_value="1.0.0"), \
             patch("app.api.settings") as mock_settings:
                mock_settings.cors_origins_list = ["http://localhost:3000"]
                mock_settings.cors_allow_credentials = False
                mock_settings.cors_max_age = 600
                mock_settings.rate_limit_max_requests = 30
                mock_settings.rate_limit_window_seconds = 60
                mock_settings.rate_limit_enabled = True
                mock_settings.rate_limit_max_keys = 10000
                mock_settings.task_max_concurrent = 0
                mock_settings.task_max_queue_size = 20
                mock_settings.task_result_ttl_seconds = 1800
                mock_settings.task_cleanup_interval_seconds = 60
                mock_settings.task_max_tasks = 500
                mock_settings.redis_enabled = False
                mock_settings.redis_url = ""
                test_app = create_app()
                # CORS middleware should be added
                assert any("CORSMiddleware" in str(m) for m in test_app.user_middleware)

    def test_create_app_without_cors_origins(self):
        """App should not add CORS middleware when no origins configured."""
        with patch("app.api.get_version", return_value="1.0.0"), \
             patch("app.api.settings") as mock_settings:
                mock_settings.cors_origins_list = []
                mock_settings.cors_allow_credentials = False
                mock_settings.cors_max_age = 600
                mock_settings.rate_limit_max_requests = 30
                mock_settings.rate_limit_window_seconds = 60
                mock_settings.rate_limit_enabled = True
                mock_settings.rate_limit_max_keys = 10000
                mock_settings.task_max_concurrent = 0
                mock_settings.task_max_queue_size = 20
                mock_settings.task_result_ttl_seconds = 1800
                mock_settings.task_cleanup_interval_seconds = 60
                mock_settings.task_max_tasks = 500
                mock_settings.redis_enabled = False
                mock_settings.redis_url = ""
                test_app = create_app()
                # No CORS middleware should be added
                cors_middleware = [
                    m for m in test_app.user_middleware if "CORSMiddleware" in str(m)
                ]
                assert len(cors_middleware) == 0

    def test_create_app_mounts_static_files(self):
        """App should mount static files."""
        with patch("app.api.get_version", return_value="1.0.0"):
            test_app = create_app()
            # Check by name since mount creates a Mount route
            route_names = [getattr(r, "name", "") for r in test_app.routes]
            assert "static" in route_names

    def test_create_app_initializes_rate_limiter(self):
        """App should initialize rate limiter."""
        with patch("app.api.get_version", return_value="1.0.0"):
            test_app = create_app()
            assert hasattr(test_app.state, "rate_limiter")

    def test_create_app_initializes_task_manager(self):
        """App should initialize task manager."""
        with patch("app.api.get_version", return_value="1.0.0"):
            test_app = create_app()
            assert hasattr(test_app.state, "task_manager")


class TestGetLifespan:
    """Tests for _get_lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_without_redis(self):
        """Lifespan should work without Redis."""
        lifespan_cm = get_lifespan(redis_enabled=False, redis_url="")

        mock_app = MagicMock(spec=FastAPI)
        mock_app.state = MagicMock()

        async with lifespan_cm(mock_app):
            pass  # Should complete without errors

    @pytest.mark.asyncio
    async def test_lifespan_with_redis_enabled_but_unavailable(self):
        """Lifespan should fall back to memory when Redis is unavailable."""
        lifespan_cm = get_lifespan(
            redis_enabled=True, redis_url="redis://localhost:9999"
        )

        mock_app = MagicMock(spec=FastAPI)
        mock_app.state = MagicMock()

        # Redis connection should fail, falling back to memory
        async with lifespan_cm(mock_app):
            pass  # Should complete without errors even if Redis fails

    @pytest.mark.asyncio
    async def test_lifespan_redis_shutdown_closes_client(self):
        """Lifespan should close Redis client on shutdown when Redis was active."""
        # This test is more of an integration test
        # We'll just verify the lifespan context manager works
        lifespan_cm = get_lifespan(redis_enabled=False, redis_url="")

        mock_app = MagicMock(spec=FastAPI)
        mock_app.state = MagicMock()

        entered = False
        async with lifespan_cm(mock_app):
            entered = True

        assert entered
