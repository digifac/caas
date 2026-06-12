"""Health check route: /health."""

import importlib.metadata
import logging
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def get_version() -> str:
    """Retrieve the package version from metadata, falling back to 'unknown'."""
    try:
        return importlib.metadata.version("caas")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


async def check_redis(app: FastAPI) -> dict[str, Any]:
    """Check Redis connectivity and return its health status."""
    redis_manager = getattr(app.state, "redis_manager", None)

    if redis_manager is None:
        return {"enabled": False, "status": "not_configured"}

    try:
        client = redis_manager.client
        ping_ok = await client.ping()
        info = await client.info("server")
        return {
            "enabled": True,
            "status": "healthy" if ping_ok else "unhealthy",
            "redis_version": info.get("redis_version", "unknown"),
        }
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        return {
            "enabled": True,
            "status": "unhealthy",
            "error": f"Redis connection error: {exc}",
        }


async def check_task_manager(app: FastAPI) -> dict[str, Any]:
    """Check task manager status and return queue metrics."""
    task_manager = getattr(app.state, "task_manager", None)

    if task_manager is None:
        return {"status": "unavailable"}

    active = task_manager.get_active_count()
    pending = task_manager.get_pending_count()
    max_concurrent = task_manager.max_concurrent
    max_queue = task_manager.max_queue_size

    total = active + pending
    queue_ok = total < max_queue

    return {
        "status": "healthy" if queue_ok else "degraded",
        "active_tasks": active,
        "pending_tasks": pending,
        "max_concurrent": max_concurrent,
        "max_queue_size": max_queue,
        "queue_utilization": round(total / max_queue * 100, 1) if max_queue > 0 else 0,
    }


def register_health_routes(app: FastAPI) -> None:
    """Register health check routes on the FastAPI app instance."""

    @app.get("/health", response_model=dict[str, Any])
    async def health_check():
        """Health check endpoint with Redis and task manager diagnostics."""
        redis_health = await check_redis(app)
        tm_health = await check_task_manager(app)

        # Overall status is unhealthy if any critical component is unhealthy
        statuses = [
            redis_health.get("status", "healthy"),
            tm_health.get("status", "healthy"),
        ]
        overall = (
            "healthy"
            if all(
                s in ("healthy", "not_configured", "not_configured") for s in statuses
            )
            else "degraded"
        )

        return {
            "status": overall,
            "service": "caas",
            "version": get_version(),
            "redis": redis_health,
            "task_manager": tm_health,
        }
