"""Exception handlers for the FastAPI application.

All exception handlers delegate to the unified ErrorHandler module
for consistent error response formatting across all modes.
"""

from fastapi import HTTPException, Request

from app.error_handler import ErrorHandler


async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return a secure response."""
    return await ErrorHandler.handle_global_exception(request, exc)


async def http_exception_handler(request: Request, exc: Exception):
    """Intercept HTTPException and normalize to standard error format."""
    if not isinstance(exc, HTTPException):
        return await global_exception_handler(request, exc)
    return await ErrorHandler.handle_http_exception(request, exc)
