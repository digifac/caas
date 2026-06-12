"""Unit tests for converter.py error paths and edge cases.

Targets uncovered lines in app/converter.py:
- convert_worker unsupported format (line 45)
"""

from unittest.mock import patch

import pytest
from app.converter import convert_worker


class TestConvertWorkerUnsupportedFormat:
    """Tests for convert_worker with unsupported format."""

    @pytest.mark.anyio
    async def test_unsupported_format_raises(self):
        """_convert_worker raises ValueError for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            await convert_worker(b"dummy", "xyz")

    @pytest.mark.anyio
    async def test_unsupported_format_message(self):
        """Error message includes the unsupported extension."""
        with pytest.raises(ValueError, match=r"Unsupported format: txt"):
            await convert_worker(b"dummy", "txt")

    @pytest.mark.anyio
    async def test_supported_format_pdf(self):
        """_convert_worker returns correct structure for PDF."""
        with patch("app.converter.convert_pdf_to_md", return_value="# PDF Content"):
            result = await convert_worker(b"pdf-data", "pdf")
            assert result["success"] is True
            assert result["markdown"] == "# PDF Content"
            assert result["format"] == "pdf"
            assert result["size_bytes"] == len(b"pdf-data")

    @pytest.mark.anyio
    async def test_supported_format_docx(self):
        """_convert_worker returns correct structure for DOCX."""
        with patch("app.converter.convert_docx_to_md", return_value="# DOCX Content"):
            result = await convert_worker(b"docx-data", "docx")
            assert result["success"] is True
            assert result["markdown"] == "# DOCX Content"
            assert result["format"] == "docx"
            assert result["size_bytes"] == len(b"docx-data")

    @pytest.mark.anyio
    async def test_supported_format_odt(self):
        """_convert_worker returns correct structure for ODT."""
        with patch("app.converter.convert_odt_to_md", return_value="# ODT Content"):
            result = await convert_worker(b"odt-data", "odt")
            assert result["success"] is True
            assert result["markdown"] == "# ODT Content"
            assert result["format"] == "odt"
            assert result["size_bytes"] == len(b"odt-data")

    @pytest.mark.anyio
    async def test_supported_format_html(self):
        """_convert_worker returns correct structure for HTML."""
        with patch("app.converter.convert_html_to_md", return_value="# HTML Content"):
            result = await convert_worker(b"<html></html>", "html")
            assert result["success"] is True
            assert result["markdown"] == "# HTML Content"
            assert result["format"] == "html"
            assert result["size_bytes"] == len(b"<html></html>")

    @pytest.mark.anyio
    async def test_supported_format_xlsx(self):
        """_convert_worker returns correct structure for XLSX."""
        with patch("app.converter.convert_xlsx_to_md", return_value="# XLSX Content"):
            result = await convert_worker(b"xlsx-data", "xlsx")
            assert result["success"] is True
            assert result["markdown"] == "# XLSX Content"
            assert result["format"] == "xlsx"
            assert result["size_bytes"] == len(b"xlsx-data")
