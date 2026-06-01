"""Routes package: modular route registration for the CAAS application.

Each sub-module registers its routes on the FastAPI app instance.
Import `_register_routes` here to register everything in one call.
"""

from fastapi import FastAPI

from app.routes.batch import register_batch_routes
from app.routes.convert import register_convert_routes
from app.routes.health import register_health_routes


def _register_routes(app: FastAPI) -> None:
    """Register all API routes on the FastAPI app instance."""
    register_convert_routes(app)
    register_batch_routes(app)
    register_health_routes(app)


__all__ = [
    "_register_routes",
    "register_convert_routes",
    "register_batch_routes",
    "register_health_routes",
]
