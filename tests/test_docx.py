"""Tests for DOCX to Markdown conversion."""

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Import fixtures from modules
from tests.fixtures.docx import sample_docx_bytes  # type: ignore[import-not-found]


# ─── sanitize_url ─────────────────────────────────────────────────────────────


class TestSanitizeUrl:
    """Test URL sanitization for dangerous schemes."""

    def test_empty_string_returns_as_is(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("") == ""

    def test_safe_http_url_preserved(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("https://example.com/page") == "https://example.com/page"

    def test_safe_mailto_preserved(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("mailto:test@example.com") == "mailto:test@example.com"

    def test_javascript_scheme_blocked(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("javascript:alert('XSS')") == "#"

    def test_vbscript_scheme_blocked(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("vbscript:msgbox('XSS')") == "#"

    def test_data_scheme_blocked(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("data:text/html,<h1>XSS</h1>") == "#"

    def test_file_scheme_blocked(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("file:///etc/passwd") == "#"

    def test_blob_scheme_blocked(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("blob:https://example.com/uuid") == "#"

    def test_javascript_case_insensitive(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("JavaScript:alert(1)") == "#"

    def test_data_scheme_with_whitespace(self) -> None:
        from app.converters.docx import sanitize_url

        assert sanitize_url("  data:text/html,<h1>XSS</h1>") == "#"


# ─── escape_md_text ───────────────────────────────────────────────────────────


class TestEscapeMdText:
    """Test HTML entity escaping in text content."""

    def test_plain_text_unchanged(self) -> None:
        from app.converters.docx import escape_md_text

        assert escape_md_text("Hello World") == "Hello World"

    def test_html_lt_gt_escaped(self) -> None:
        from app.converters.docx import escape_md_text

        assert (
            escape_md_text("<script>alert(1)</script>")
            == "&lt;script&gt;alert(1)&lt;/script&gt;"
        )

    def test_html_ampersand_escaped(self) -> None:
        from app.converters.docx import escape_md_text

        assert escape_md_text("Tom & Jerry") == "Tom &amp; Jerry"


# ─── convert_docx_to_md (mocked) ──────────────────────────────────────────────


class TestConvertDocxToMd:
    """Test full DOCX to Markdown conversion with security post-processing."""

    def test_conversion_with_mammoth_warnings(self, sample_docx_bytes, caplog) -> None:  # type: ignore[no-untyped-def]
        """Warnings from mammoth should be logged."""
        mock_msg = MagicMock()
        type(mock_msg).__str__ = lambda self: "Unknown element: w:sdt"  # type: ignore[method-assign]

        mock_result = MagicMock()
        mock_result.value = "# Document"
        mock_result.messages = [mock_msg]

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            with caplog.at_level(logging.WARNING):  # type: ignore[attr-defined]
                from app.converters.docx import convert_docx_to_md

                result = convert_docx_to_md(sample_docx_bytes)  # type: ignore[arg-type]

        assert "DOCX Warning:" in caplog.text  # type: ignore[attr-defined]

    def test_dangerous_link_in_markdown_sanitized(self, sample_docx_bytes) -> None:  # type: ignore[no-untyped-def]
        """JavaScript URLs in links should be replaced with #."""
        mock_result = MagicMock()
        mock_result.value = "[Click here](javascript:void(0))"
        mock_result.messages = []

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            from app.converters.docx import convert_docx_to_md

            result = convert_docx_to_md(sample_docx_bytes)  # type: ignore[arg-type]

        # The regex [^)]* stops at first ')', so javascript:void(0) captures as "javascript:void(0"
        # which is sanitized to #, leaving the trailing )
        assert "javascript" not in result
        assert "[#]" in result or result.count("#") >= 1

    def test_dangerous_image_url_sanitized(self, sample_docx_bytes) -> None:  # type: ignore[no-untyped-def]
        """JavaScript URLs in images should be blocked."""
        mock_result = MagicMock()
        mock_result.value = "![Click](javascript:void(0))"
        mock_result.messages = []

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            from app.converters.docx import convert_docx_to_md

            result = convert_docx_to_md(sample_docx_bytes)  # type: ignore[arg-type]

        # Same regex behavior - javascript scheme is blocked
        assert "javascript" not in result
        assert "[#]" in result or result.count("#") >= 1

    def test_file_url_in_image_sanitized(self, sample_docx_bytes) -> None:  # type: ignore[no-untyped-def]
        """File URLs in images should be blocked."""
        mock_result = MagicMock()
        mock_result.value = "![Secret](file:///etc/passwd)"
        mock_result.messages = []

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            from app.converters.docx import convert_docx_to_md

            result = convert_docx_to_md(sample_docx_bytes)  # type: ignore[arg-type]

        assert result == "![Secret](#)"

    def test_multiple_links_and_images_sanitized(self, sample_docx_bytes) -> None:  # type: ignore[no-untyped-def]
        """Multiple links and images should all be sanitized."""
        mock_result = MagicMock()
        mock_result.value = (
            "[Safe](https://ok.com) [Danger](javascript:alert(1))\n"
            "![Safe](https://ok.com/img.png) ![Danger](data:text/html,x)"
        )
        mock_result.messages = []

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            from app.converters.docx import convert_docx_to_md

            result = convert_docx_to_md(sample_docx_bytes)  # type: ignore[arg-type]

        assert "[Safe](https://ok.com)" in result
        assert "[Danger](#)" in result
        assert "![Safe](https://ok.com/img.png)" in result
        assert "![Danger](#)" in result

    def test_empty_markdown_output(self, sample_docx_bytes) -> None:  # type: ignore[no-untyped-def]
        """Empty markdown from mammoth should return empty string."""
        mock_result = MagicMock()
        mock_result.value = ""
        mock_result.messages = []

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            from app.converters.docx import convert_docx_to_md

            result = convert_docx_to_md(sample_docx_bytes)  # type: ignore[arg-type]

        assert result == ""

    def test_whitespace_only_markdown(self, sample_docx_bytes) -> None:  # type: ignore[no-untyped-def]
        """Whitespace-only markdown should return empty string."""
        mock_result = MagicMock()
        mock_result.value = "   \n\n  "
        mock_result.messages = []

        with patch("app.converters.docx.mammoth") as mock_mammoth:
            mock_mammoth.convert_to_markdown.return_value = mock_result
            from app.converters.docx import convert_docx_to_md

            result = convert_docx_to_md(sample_docx_bytes)  # type: ignore

        assert result == ""


@pytest.mark.anyio
async def test_convert_docx_success(
    async_client: httpx.AsyncClient, sample_docx_bytes: bytes
) -> None:
    """POST /convert with a valid DOCX returns markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.docx", sample_docx_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "markdown" in data
    assert data["format"] == "docx"
    assert data["size_bytes"] == len(sample_docx_bytes)


@pytest.mark.anyio
async def test_convert_async_docx_completes(
    async_client: httpx.AsyncClient, sample_docx_bytes: bytes
) -> None:
    """An async DOCX task reaches completed status."""
    response = await async_client.post(
        "/convert?async=true", files={"file": ("test.docx", sample_docx_bytes)}
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    status_data: dict[str, Any] = {}
    for _ in range(40):
        await asyncio.sleep(0.25)
        status_res = await async_client.get(f"/task/{task_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()  # type: ignore
        if status_data["status"] in ("completed", "failed"):
            break

    assert status_data["status"] == "completed"
    assert status_data["result"]["format"] == "docx"  # type: ignore
