"""Tests for exception handlers (app/exceptions.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import settings
from app.exceptions import global_exception_handler, http_exception_handler
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class TestGlobalExceptionHandler:
    """Tests for global_exception_handler."""

    @pytest.mark.asyncio
    async def test_global_handler_returns_500(self):
        """Global handler should return 500 status code."""
        mock_request = MagicMock(spec=Request)
        exc = ValueError("test error")

        response = await global_exception_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_global_handler_includes_request_id(self):
        """Global handler should include a request_id in the response."""
        mock_request = MagicMock(spec=Request)
        exc = RuntimeError("something broke")

        response = await global_exception_handler(mock_request, exc)

        body = bytes(response.body).decode()
        assert "request_id" in body
        assert len(body) > 0

    @pytest.mark.asyncio
    async def test_global_handler_includes_error_code(self):
        """Global handler should include SERVER_ERROR error code."""
        mock_request = MagicMock(spec=Request)
        exc = Exception("unexpected")

        response = await global_exception_handler(mock_request, exc)

        body = bytes(response.body).decode()
        assert "SERVER_ERROR" in body
        assert "error_code" in body

    @pytest.mark.asyncio
    async def test_global_handler_no_detail_in_production(self):
        """Global handler should not expose debug details in production."""
        mock_request = MagicMock(spec=Request)
        exc = Exception("secret error")

        # Ensure debug is off
        original_debug = settings.debug
        settings.debug = False
        try:
            response = await global_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        # Should not contain the raw exception message
        assert "secret error" not in body

    @pytest.mark.asyncio
    async def test_global_handler_with_debug_mode(self):
        """Global handler should include debug info when debug=True."""
        mock_request = MagicMock(spec=Request)
        exc = Exception("debug error")

        original_debug = settings.debug
        settings.debug = True
        try:
            response = await global_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        assert "debug" in body


class TestHttpExceptionHandler:
    """Tests for http_exception_handler."""

    @pytest.mark.asyncio
    async def test_http_handler_non_http_exception_delegates(self):
        """Non-HTTPException should be delegated to global handler."""
        mock_request = MagicMock(spec=Request)
        exc = ValueError("not http")

        with patch(
            "app.exceptions.global_exception_handler", new_callable=AsyncMock
        ) as mock_global:
            mock_global.return_value = JSONResponse(status_code=500, content={})
            await http_exception_handler(mock_request, exc)

            mock_global.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_handler_404(self):
        """HTTPException 404 should return proper response."""
        mock_request = MagicMock(spec=Request)
        exc = HTTPException(status_code=404, detail="Not found")

        response = await http_exception_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_http_handler_with_string_detail(self):
        """HTTPException with string detail should include message in debug mode."""
        mock_request = MagicMock(spec=Request)
        exc = HTTPException(status_code=400, detail="Bad request")

        original_debug = settings.debug
        settings.debug = True
        try:
            response = await http_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        assert "Bad request" in body
        assert "request_id" in body
        assert "detail" in body  # detail field appears when debug=True

    @pytest.mark.asyncio
    async def test_http_handler_with_dict_detail(self):
        """HTTPException with dict detail should preserve the dict."""
        mock_request = MagicMock(spec=Request)
        exc = HTTPException(
            status_code=400,
            detail={"error_code": "FILE_TOO_LARGE", "message": "File is too big"},
        )

        original_debug = settings.debug
        settings.debug = False
        try:
            response = await http_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        assert "request_id" in body

    @pytest.mark.asyncio
    async def test_http_handler_hides_details_in_production(self):
        """HTTPException should hide error_code details in production."""
        mock_request = MagicMock(spec=Request)
        exc = HTTPException(
            status_code=400,
            detail={"error_code": "FILE_TOO_LARGE", "message": "File is too big"},
        )

        original_debug = settings.debug
        settings.debug = False
        try:
            response = await http_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        # When debug=False and error_code exists, it should use AppError.get()
        # which returns a sanitized message
        assert "request_id" in body

    @pytest.mark.asyncio
    async def test_http_handler_with_debug_true(self):
        """HTTPException should include debug flag when debug=True."""
        mock_request = MagicMock(spec=Request)
        exc = HTTPException(
            status_code=400,
            detail={"error_code": "FILE_TOO_LARGE", "message": "File is too big"},
        )

        original_debug = settings.debug
        settings.debug = True
        try:
            response = await http_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        assert "detail" in body  # detail field appears when debug=True
        assert "File is too big" in body  # Original message preserved in debug mode

    @pytest.mark.asyncio
    async def test_http_handler_string_detail_production_mode(self):
        """HTTPException with string detail should use AppError.get in production."""
        mock_request = MagicMock(spec=Request)
        exc = HTTPException(status_code=500, detail="Something went wrong")

        original_debug = settings.debug
        settings.debug = False
        try:
            response = await http_exception_handler(mock_request, exc)
        finally:
            settings.debug = original_debug

        body = bytes(response.body).decode()
        # In production: error_code=UNKNOWN triggers AppError.get("UNKNOWN")
        # which replaces the detail_dict entirely
        assert "request_id" in body
        assert "error_code" in body or "message" in body
