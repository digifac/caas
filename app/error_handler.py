"""Unified error handling for the CAAS application.

Provides a single, consistent error response format across all modes
(sync, sync file, sync batch, async, streaming).

Error Response Format
---------------------
All error responses follow this structure:

    {
        "request_id": "<8-char UUID>",       // Always present
        "error_code": "<ERROR_CODE>",         // Always present
        "message": "<user-friendly message>"  // Always present
    }

When DEBUG mode is enabled, an additional field is added:

    {
        "request_id": "<8-char UUID>",
        "error_code": "<ERROR_CODE>",
        "message": "<user-friendly message>",
        "detail": "<raw error detail>"        // Only in debug mode
    }

Batch Per-File Error Format
---------------------------
For batch operations, each file result follows this structure:

    {
        "index": 0,
        "filename": "doc.pdf",
        "success": false,
        "error_code": "FILE_TOO_LARGE",
        "message": "File exceeds the maximum allowed size."
    }

When DEBUG mode is enabled:

    {
        "index": 0,
        "filename": "doc.pdf",
        "success": false,
        "error_code": "FILE_TOO_LARGE",
        "message": "File exceeds the maximum allowed size.",
        "detail": "<raw error detail>"        // Only in debug mode
    }
"""

import logging
import traceback
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.errors import AppError

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling with consistent response format.

    All error responses include:
    - request_id: for tracing
    - error_code: machine-readable error identifier
    - message: user-friendly message

    In debug mode, an additional "detail" field is included with the raw error.
    """

    @staticmethod
    def make_error_response(
        error_code: str,
        request_id: str | None = None,
        detail: str | None = None,
    ) -> dict[str, Any]:
        """Build a standardized error response dictionary.

        Args:
            error_code: The AppError code (e.g., "CONVERSION_FAILED").
            request_id: Optional request ID for tracing.
            detail: Raw error detail (only included when debug mode is enabled).

        Returns:
            A dictionary with the standardized error response format.
        """
        if request_id is None:
            request_id = ErrorHandler.generate_request_id()

        response: dict[str, Any] = {
            "request_id": request_id,
            **AppError.get(error_code),
        }

        if settings.debug and detail is not None:
            response["detail"] = detail

        return response

    @staticmethod
    def make_batch_error_result(
        index: int,
        filename: str,
        error_code: str,
        detail: str | None = None,
    ) -> dict[str, Any]:
        """Build a standardized per-file error result for batch operations.

        Args:
            index: Original index of the file in the batch.
            filename: Original filename.
            error_code: The AppError code.
            detail: Raw error detail (only included when debug mode is enabled).

        Returns:
            A dictionary with the standardized batch error result format.
        """
        result: dict[str, Any] = {
            "index": index,
            "filename": filename,
            "success": False,
            "error_code": error_code,
            "message": AppError.get(error_code)["message"],
        }

        if settings.debug and detail is not None:
            result["detail"] = detail

        return result

    @staticmethod
    def generate_request_id() -> str:
        """Generate a short request ID for tracing."""
        return str(uuid.uuid4())[:8]

    @classmethod
    async def handle_global_exception(
        cls, request: Request, exc: Exception
    ) -> JSONResponse:
        """Global exception handler for unhandled exceptions.

        Logs the full traceback and returns a secure error response.
        """
        # Don't handle HTTPException here - let it be handled by handle_http_exception
        if isinstance(exc, HTTPException):
            return await cls.handle_http_exception(request, exc)

        request_id = cls.generate_request_id()
        logger.exception(
            "[%s] Unhandled error: %s\n%s",
            request_id,
            exc,
            traceback.format_exc(),
        )

        return JSONResponse(
            status_code=500,
            content=cls.make_error_response(
                "SERVER_ERROR",
                request_id=request_id,
                detail=str(exc) if settings.debug else None,
            ),
        )

    @classmethod
    async def handle_http_exception(
        cls, request: Request, exc: HTTPException
    ) -> JSONResponse:
        """HTTPException handler that normalizes all error responses.

        Ensures all HTTPException responses follow the standard format
        with request_id, error_code, and message.
        """
        request_id = cls.generate_request_id()
        logger.warning("[%s] HTTP %d: %s", request_id, exc.status_code, exc.detail)

        if isinstance(exc.detail, dict):
            # Already a structured error dict (from AppError.get() or similar)
            detail_dict = dict(exc.detail)
            error_code = detail_dict.get("error_code", "UNKNOWN")

            # Extract any detail that was added before raising
            raw_detail = detail_dict.get("detail")

            # In debug mode, include the original message as detail if no raw_detail
            if settings.debug and not raw_detail:
                original_message = detail_dict.get("message", "")
                if original_message:
                    raw_detail = original_message

            response = cls.make_error_response(
                error_code,
                request_id=request_id,
                detail=raw_detail,
            )
        else:
            # Plain string detail - wrap in standard format
            response = cls.make_error_response(
                "UNKNOWN",
                request_id=request_id,
                detail=str(exc.detail) if settings.debug else None,
            )
            response["message"] = str(exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content=response,
        )

    @classmethod
    def raise_error(
        cls,
        status_code: int,
        error_code: str,
        detail: str | None = None,
    ) -> None:
        """Raise an HTTPException with a standardized error response.

        This is the preferred way to raise errors in route handlers.

        Args:
            status_code: HTTP status code.
            error_code: The AppError code.
            detail: Raw error detail (will be included in response if debug mode is enabled).
        """
        error_response = cls.make_error_response(error_code, detail=detail)
        raise HTTPException(status_code=status_code, detail=error_response)


# Module-level convenience function for quick error raising
def error(
    status_code: int,
    error_code: str,
    detail: str | None = None,
) -> None:
    """Raise an HTTPException with a standardized error response.

    Args:
        status_code: HTTP status code.
        error_code: The AppError code.
        detail: Raw error detail (included in response only when debug mode is enabled).
    """
    ErrorHandler.raise_error(status_code, error_code, detail)
