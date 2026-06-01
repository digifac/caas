"""FastAPI application factory: app instance, middleware, and exception handlers."""

import logging
import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.exceptions import global_exception_handler, http_exception_handler
from app.metrics import AppMetrics
from app.middleware import add_security_headers
from app.rate_limiter import RateLimiter
from app.redis_client import RedisManager
from app.routes import _register_routes
from app.storage.base import StorageProtocol
from app.storage.memory import MemoryStorage
from app.task_manager import TaskManager

logger = logging.getLogger(__name__)

_VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _get_version() -> str:
    """Retrieve the package version directly from pyproject.toml.

    This ensures the version shown in Swagger UI is always synchronized
    with pyproject.toml, even after an automatic bump by the pre-commit hook.
    """
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        match = _VERSION_PATTERN.search(content)
        if match:
            return match.group(1)
    except Exception as exc:
        logger.warning("Could not read version from pyproject.toml: %s", exc)
    return "unknown"


def _get_lifespan(redis_enabled: bool, redis_url: str):
    """Create a lifespan context manager for startup/shutdown events."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Manage application lifecycle: startup and shutdown."""
        redis_active = False

        # Startup logic — attempt Redis swap if configured
        if redis_enabled:
            try:
                from app.storage.redis import RedisStorage

                redis_manager = RedisManager(redis_url)
                redis_storage = RedisStorage(redis_manager.client)
                app.state.redis_manager = redis_manager
                logger.info("Storage: Redis mode active (%s)", redis_url)

                # Replace rate limiter with Redis-backed instance
                app.state.rate_limiter = RateLimiter(
                    max_requests=settings.rate_limit_max_requests,
                    window_seconds=settings.rate_limit_window_seconds,
                    enabled=settings.rate_limit_enabled,
                    max_keys=settings.rate_limit_max_keys,
                    storage=redis_storage,
                )

                # Replace task manager with Redis-backed instance
                cpu_count = os.cpu_count() or 1
                app.state.task_manager = TaskManager(
                    max_concurrent=settings.task_max_concurrent or cpu_count,
                    max_queue_size=settings.task_max_queue_size,
                    result_ttl_seconds=settings.task_result_ttl_seconds,
                    cleanup_interval_seconds=settings.task_cleanup_interval_seconds,
                    max_tasks=settings.task_max_tasks,
                    storage=redis_storage,
                )

                # Restore any active tasks from storage (resilience on restart)
                restored = await app.state.task_manager.restore_active_tasks()
                if restored:
                    logger.info(
                        "TaskManager: restored %d active tasks from Redis on startup",
                        restored,
                    )

                redis_active = True

            except Exception as exc:
                logger.error(
                    "Redis unavailable (%s) — falling back to in-memory storage", exc
                )
                logger.info("Storage: in-memory mode (fallback)")

        yield

        # Shutdown logic
        if redis_active:
            redis_mgr: RedisManager = app.state.redis_manager
            await redis_mgr.close()

    return lifespan


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="CAAS Converter",
        description="PDF/DOCX/ODT/ODS/ODP/HTML/XLSX/PPTX → Markdown conversion, 100% in-memory (zero-disk I/O)",
        version=_get_version(),
        lifespan=_get_lifespan(settings.redis_enabled, settings.redis_url),
    )

    # CORS middleware (only if origins are configured)
    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization"],
            max_age=settings.cors_max_age,
        )

    # Security headers middleware (imported from app.middleware)
    app.middleware("http")(add_security_headers)

    # Metrics middleware and collector
    app.state.metrics = AppMetrics()
    app.middleware("http")(app.state.metrics.middleware(app))

    # Static files (CSS, JS)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Register exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # --- Storage initialization (synchronous — in-memory by default) ---
    # Redis swap happens in the startup event below if configured.
    storage: StorageProtocol = MemoryStorage()
    logger.info("Storage: in-memory mode (default)")

    # Rate limiting
    rate_limiter = RateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
        enabled=settings.rate_limit_enabled,
        max_keys=settings.rate_limit_max_keys,
        storage=storage,
    )
    app.state.rate_limiter = rate_limiter

    # Task manager
    cpu_count = os.cpu_count() or 1
    task_manager = TaskManager(
        max_concurrent=settings.task_max_concurrent or cpu_count,
        max_queue_size=settings.task_max_queue_size,
        result_ttl_seconds=settings.task_result_ttl_seconds,
        cleanup_interval_seconds=settings.task_cleanup_interval_seconds,
        max_tasks=settings.task_max_tasks,
        storage=storage,
    )
    app.state.task_manager = task_manager

    # Register routes
    _register_routes(app)

    return app


# Module-level instances (backward-compatible imports for tests and app/main.py)
app = create_app()
task_manager = app.state.task_manager
