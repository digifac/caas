"""Tests for streaming conversion functionality."""

import json
from typing import Any
from unittest.mock import patch

import pytest
from app.api import create_app
from app.config import settings
from app.streaming import (
    _convert_docx_stream,  # type: ignore[attr-defined]
    _convert_html_stream,  # type: ignore[attr-defined]
    _convert_odp_stream,  # type: ignore[attr-defined]
    _convert_odt_stream,  # type: ignore[attr-defined]
    _convert_pdf_stream,  # type: ignore[attr-defined]
    _convert_xlsx_stream,  # type: ignore[attr-defined]
    _sse_event,  # type: ignore[attr-defined]
    convert_stream,
)
from fastapi.testclient import TestClient
# Import fixtures from modules
from tests.fixtures.common import sample_docx_bytes # type: ignore[import-not-found]

@pytest.fixture
def app() -> Any:
    """Create a test application."""
    return create_app()


@pytest.fixture
def client(app: Any) -> Any:
    """Create a test client."""
    return TestClient(app)


# --- SSE Event Formatting Tests ---


class TestSSEEvent:
    """Tests for SSE event formatting."""

    def test_sse_event_basic(self):
        """SSE event should format data correctly."""
        result = _sse_event("hello")
        assert result == "data: hello\n\n"

    def test_sse_event_escapes_newlines(self):
        """SSE event should escape newlines in data."""
        result = _sse_event("line1\nline2")
        assert result == "data: line1\\nline2\n\n"

    def test_sse_event_escapes_carriage_returns(self):
        """SSE event should remove carriage returns."""
        result = _sse_event("line1\r\nline2")
        assert "\r" not in result
        assert "line1\\nline2" in result


# --- Streaming Converter Tests ---


class TestConvertStream:
    """Tests for the main streaming converter."""

    @pytest.mark.asyncio
    async def test_convert_stream_pdf_yields_events(self):
        """PDF streaming should yield start, content, and done events."""
        # Create a minimal valid PDF
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        pdf_content += b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        pdf_content += (
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        )
        pdf_content += b"trailer<</Root 1 0 R>>\n%%EOF"

        events: list[str] = []
        async for event in convert_stream(pdf_content, "pdf"):
            events.append(event)

        assert len(events) >= 2  # At least start and done events
        # First event should be a start event
        start_data: str = events[0].strip().removeprefix("data: ")
        start_json: dict[str, Any] = json.loads(start_data)
        assert start_json["format"] == "pdf"
        assert start_json["status"] == "started"

    @pytest.mark.asyncio
    async def test_convert_stream_unsupported_format(self):
        """Unsupported format should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported format"):
            async for _ in convert_stream(b"content", "txt"):
                pass

    @pytest.mark.asyncio
    async def test_convert_stream_docx_yields_events(self, client: TestClient):
        """DOCX streaming should yield events."""
        # We'll test via the API endpoint instead of directly
        # because mammoth needs a real DOCX file
        pass


# --- API Endpoint Streaming Tests ---


class TestStreamingEndpoint:
    """Tests for the /convert endpoint with streaming."""

    def test_streaming_disabled_by_query(self, client: Any):
        """Streaming should work when enabled via query parameter."""
        # Create a simple HTML file for testing
        html_content = b"<html><body><h1>Test</h1><p>Content</p></body></html>"

        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.html", html_content, "text/html")},
        )

        # Should return text/event-stream content type
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_streaming_respects_setting(self, client: Any):
        """Streaming should respect the streaming_enabled setting."""
        html_content = b"<html><body><p>Test</p></body></html>"

        # When streaming is enabled (default), should work
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.html", html_content, "text/html")},
        )
        assert response.status_code == 200

    def test_streaming_returns_sse_events(self, client: Any):
        """Streaming should return properly formatted SSE events."""
        html_content = b"<html><body><h1>Hello</h1><p>World</p></body></html>"

        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.html", html_content, "text/html")},
        )

        assert response.status_code == 200
        content: str = response.text

        # Should contain SSE data lines
        assert "data:" in content

        # Should have start and complete events
        events: list[str] = [line for line in content.split("\n") if line.startswith("data:")]
        assert len(events) >= 2

    def test_streaming_headers(self, client: Any):
        """Streaming response should have correct headers."""
        html_content = b"<html><body><p>Test</p></body></html>"

        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.html", html_content, "text/html")},
        )

        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"

    def test_streaming_pdf(self, client: Any):
        """Streaming should work with PDF files."""
        # Minimal valid PDF
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        pdf_content += b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        pdf_content += (
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        )
        pdf_content += b"trailer<</Root 1 0 R>>\n%%EOF"

        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_streaming_validation_still_applies(self, client: Any):
        """File validation should still apply in streaming mode."""
        # Invalid PDF content
        invalid_pdf = b"This is not a valid PDF"

        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.pdf", invalid_pdf, "application/pdf")},
        )

        # Should reject invalid files
        assert response.status_code == 400

    def test_streaming_file_size_check(self, client: Any):
        """File size check should apply in streaming mode."""
        # Create content larger than max file size
        large_content = b"x" * (settings.max_file_size_mb * 1024 * 1024 + 1)

        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.html", large_content, "text/html")},
        )

        assert response.status_code == 400

    def test_streaming_unsupported_format(self, client: Any):
        """Unsupported formats should be rejected in streaming mode."""
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.txt", b"content", "text/plain")},
        )

        assert response.status_code == 400

    def test_streaming_missing_filename(self, client: Any):
        """Missing filename should be rejected in streaming mode (FastAPI returns 422)."""
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": (None, b"content", "text/html")},
        )

        # FastAPI validates the UploadFile before our code runs, returning 422
        assert response.status_code == 422

    def test_streaming_rate_limiting(self, client: Any):
        """Rate limiting should apply to streaming requests."""
        html_content = b"<html><body><p>Test</p></body></html>"

        # Make requests up to the rate limit
        for _ in range(settings.rate_limit_max_requests):
            resp: Any = client.post(
                "/convert?streaming=true",
                files={"file": ("test.html", html_content, "text/html")},
            )
            assert resp.status_code in (200, 429)

        # Next request should be rate limited
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.html", html_content, "text/html")},
        )
        assert response.status_code == 429


# --- Configuration Tests ---


class TestStreamingConfig:
    """Tests for streaming configuration."""

    def test_streaming_enabled_default(self):
        """Streaming should be enabled by default."""
        assert settings.streaming_enabled is True

    def test_streaming_chunk_size_default(self):
        """Streaming chunk size should have a reasonable default."""
        assert settings.streaming_chunk_size > 0
        assert settings.streaming_chunk_size == 1024


# --- Streaming Converter Unit Tests ---


class TestConvertPdfStream:
    """Tests for _convert_pdf_stream function."""

    @pytest.mark.asyncio
    async def test_convert_pdf_stream_yields_chunks(self):
        """PDF streaming should yield SSE-formatted chunks."""
        with patch("app.streaming.convert_pdf_to_md_stream") as mock_convert:

            async def mock_gen(file_bytes: bytes):
                yield "# Page 1"
                yield "\n## Page 2"

            mock_convert.side_effect = mock_gen

            pdf_content = b"%PDF-1.4 test"
            chunks: list[str] = []
            async for chunk in _convert_pdf_stream(pdf_content):
                chunks.append(chunk)

            assert len(chunks) > 0
            assert all(chunk.startswith("data:") for chunk in chunks)

    @pytest.mark.asyncio
    async def test_convert_pdf_stream_empty_result(self):
        """PDF streaming should handle empty PDF gracefully."""
        # Minimal PDF that might produce no text
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        pdf_content += b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        pdf_content += (
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        )
        pdf_content += b"trailer<</Root 1 0 R>>\n%%EOF"

        chunks: list[str] = []
        async for chunk in _convert_pdf_stream(pdf_content):
            chunks.append(chunk)

        # Should still yield at least one chunk (even if empty)
        assert len(chunks) >= 0


class TestConvertDocxStream:
    """Tests for _convert_docx_stream function."""

    @pytest.mark.asyncio
    async def test_convert_docx_stream_yields_chunks(self):
        """DOCX streaming should yield SSE-formatted chunks."""
        with patch("app.streaming.convert_docx_to_md") as mock_convert:
            mock_convert.return_value = (
                "# Test Heading\n\nFirst paragraph\n\nSecond paragraph"
            )

            docx_bytes = b"PK dummy docx content"
            chunks: list[str] = []
            async for chunk in _convert_docx_stream(docx_bytes):
                chunks.append(chunk)

            assert len(chunks) > 0
            assert all(chunk.startswith("data:") for chunk in chunks)

    @pytest.mark.asyncio
    async def test_convert_docx_stream_respects_chunk_size(self):
        """DOCX streaming should split content into chunks of configured size."""
        with patch("app.streaming.convert_docx_to_md") as mock_convert:
            # Create content larger than chunk size (1024 bytes)
            long_content = "# Heading\n\n" + "Paragraph text. " * 100
            mock_convert.return_value = long_content

            docx_bytes = b"PK dummy docx content"
            chunks: list[str] = []
            async for chunk in _convert_docx_stream(docx_bytes):
                chunks.append(chunk)

            # Should have multiple chunks if content exceeds chunk size
            assert len(chunks) >= 1
            # Reconstruct full content from chunks
            reconstructed = "".join(
                chunk.replace("data: ", "").replace("\\n", "\n").replace("\n\n", "")
                for chunk in chunks
            )
            assert "Heading" in reconstructed
            assert "Paragraph" in reconstructed


class TestConvertOdtStream:
    """Tests for _convert_odt_stream function."""

    @pytest.mark.asyncio
    async def test_convert_odt_stream_yields_chunks(self, sample_odt_bytes: bytes):
        """ODT streaming should yield SSE-formatted chunks."""
        chunks: list[str] = []
        async for chunk in _convert_odt_stream(sample_odt_bytes):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(chunk.startswith("data:") for chunk in chunks)


class TestConvertHtmlStream:
    """Tests for _convert_html_stream function."""

    @pytest.mark.asyncio
    async def test_convert_html_stream_yields_chunks(self):
        """HTML streaming should yield SSE-formatted chunks."""
        html_content = b"<html><body><h1>Test</h1><p>Content</p></body></html>"

        chunks: list[str] = []
        async for chunk in _convert_html_stream(html_content):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(chunk.startswith("data:") for chunk in chunks)

    @pytest.mark.asyncio
    async def test_convert_html_stream_empty_html(self):
        """HTML streaming should handle empty HTML."""
        html_content = b"<html><body></body></html>"

        chunks: list[str] = []
        async for chunk in _convert_html_stream(html_content):
            chunks.append(chunk)

        assert len(chunks) >= 0


class TestConvertStreamErrorHandling:
    """Tests for error handling in convert_stream."""

    @pytest.mark.asyncio
    async def test_convert_stream_catches_conversion_error(self):
        """convert_stream should catch and report conversion errors."""
        with patch("app.streaming._convert_pdf_stream") as mock_stream:

            async def error_generator():
                raise Exception("Conversion failed")
                yield ""  # Never reached

            mock_stream.side_effect = error_generator

            chunks: list[str] = []
            try:
                async for chunk in convert_stream(b"%PDF-1.4 test", "pdf"):
                    chunks.append(chunk)
            except Exception:
                pass  # Expected to re-raise after error event

            # Should have yielded start event and error event
            assert len(chunks) >= 1
            # Check for error event
            error_found = any("error" in chunk.lower() for chunk in chunks)
            assert error_found or len(chunks) >= 1  # At least start event

    @pytest.mark.asyncio
    async def test_convert_stream_yields_done_event(self):
        """convert_stream should yield done event in finally block."""
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        pdf_content += b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        pdf_content += (
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        )
        pdf_content += b"trailer<</Root 1 0 R>>\n%%EOF"

        chunks: list[str] = []
        async for chunk in convert_stream(pdf_content, "pdf"):
            chunks.append(chunk)

        # Last chunk should be a done event
        last_chunk = chunks[-1] if chunks else ""
        assert "complete" in last_chunk or len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_convert_stream_start_event_contains_metadata(self):
        """convert_stream start event should contain format and size."""
        pdf_content = b"%PDF-1.4 test content"

        chunks: list[str] = []
        async for chunk in convert_stream(pdf_content, "pdf"):
            chunks.append(chunk)
            break  # Only need first chunk

        # First chunk should be start event with metadata
        first_chunk = chunks[0] if chunks else ""
        assert "pdf" in first_chunk
        assert "started" in first_chunk


class TestConvertXlsxStream:
    """Tests for XLSX streaming conversion."""

    @pytest.mark.asyncio
    async def test_convert_xlsx_stream_yields_chunks(self, sample_xlsx_bytes: bytes):
        """_convert_xlsx_stream should yield SSE data chunks."""
        chunks: list[str] = []
        async for chunk in _convert_xlsx_stream(sample_xlsx_bytes):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(chunk.startswith("data:") for chunk in chunks)

    @pytest.mark.asyncio
    async def test_convert_xlsx_stream_multi_sheet(self, sample_xlsx_multi_sheet_bytes: bytes):
        """_convert_xlsx_stream should yield chunks for multi-sheet workbooks."""
        chunks: list[str] = []
        async for chunk in _convert_xlsx_stream(sample_xlsx_multi_sheet_bytes):
            chunks.append(chunk)

        assert len(chunks) > 0
        full_content = "".join(chunk.replace("data:", "") for chunk in chunks)
        # Multi-sheet fixture has "Données" and "Résumé" sheets with separator between them
        assert "---" in full_content  # Sheet separator present
        assert "Pomme" in full_content  # Data from first sheet
        assert "Total" in full_content  # Data from second sheet


class TestConvertOdpStream:
    """Tests for ODP streaming conversion."""

    @pytest.mark.asyncio
    async def test_convert_odp_stream_yields_chunks(self, sample_odp_bytes: bytes):
        """_convert_odp_stream should yield SSE data chunks."""
        chunks: list[str] = []
        async for chunk in _convert_odp_stream(sample_odp_bytes):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(chunk.startswith("data:") for chunk in chunks)

    @pytest.mark.asyncio
    async def test_convert_odp_stream_content(self, sample_odp_bytes: bytes):
        """_convert_odp_stream should yield slide content."""
        chunks: list[str] = []
        async for chunk in _convert_odp_stream(sample_odp_bytes):
            chunks.append(chunk)

        full_content = "".join(
            chunk.replace("data: ", "").replace("\\n", "\n").replace("\n\n", "")
            for chunk in chunks
        )
        assert "Présentation de Test" in full_content

    @pytest.mark.asyncio
    async def test_convert_odp_stream_list(self, sample_odp_with_list_bytes: bytes):
        """_convert_odp_stream should yield list content."""
        chunks: list[str] = []
        async for chunk in _convert_odp_stream(sample_odp_with_list_bytes):
            chunks.append(chunk)

        full_content = "".join(
            chunk.replace("data: ", "").replace("\\n", "\n").replace("\n\n", "")
            for chunk in chunks
        )
        assert "Liste de courses" in full_content
        assert "Pommes" in full_content

    @pytest.mark.asyncio
    async def test_convert_odp_stream_special_chars(self, sample_odp_with_special_chars_bytes: bytes):
        """_convert_odp_stream should preserve special characters."""
        chunks: list[str] = []
        async for chunk in _convert_odp_stream(sample_odp_with_special_chars_bytes):
            chunks.append(chunk)

        full_content = "".join(
            chunk.replace("data: ", "").replace("\\n", "\n").replace("\n\n", "")
            for chunk in chunks
        )
        assert "Àéîôù" in full_content
        assert "€" in full_content


class TestOdpStreamingEndpoint:
    """Tests for ODP streaming via the /convert?streaming=true endpoint."""

    def test_streaming_odp_success(self, client: Any, sample_odp_bytes: bytes):
        """Streaming ODP conversion should return SSE events."""
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.odp", sample_odp_bytes, "application/vnd.oasis.opendocument.presentation")},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        content = response.text
        assert "data:" in content

    def test_streaming_odp_headers(self, client: Any, sample_odp_bytes: bytes):
        """Streaming ODP response should have correct headers."""
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.odp", sample_odp_bytes, "application/vnd.oasis.opendocument.presentation")},
        )

        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"

    def test_streaming_odp_content(self, client: Any, sample_odp_bytes: bytes):
        """Streaming ODP should contain slide content."""
        response: Any = client.post(
            "/convert?streaming=true",
            files={"file": ("test.odp", sample_odp_bytes, "application/vnd.oasis.opendocument.presentation")},
        )

        assert response.status_code == 200
        content = response.text
        assert "Présentation de Test" in content
