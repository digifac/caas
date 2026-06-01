"""Unit tests for converter.py error paths and edge cases.

Targets uncovered lines in app/converter.py:
- get_html_form FileNotFoundError (line 27-28)
- get_html_form IOError (line 30-32)
- _convert_worker unsupported format (line 45)
"""

from unittest.mock import patch

import pytest
from app.converter import _convert_worker, get_html_form


class TestGetHtmlFormErrors:
    """Tests for get_html_form error handling paths."""

    def test_file_not_found(self):
        """get_html_form raises FileNotFoundError when template is missing."""
        with patch("os.path.join", return_value="/nonexistent/path/form.html"), \
             pytest.raises(FileNotFoundError):
                get_html_form()

    def test_io_error(self):
        """get_html_form raises IOError when template cannot be read."""
        with patch("builtins.open", side_effect=OSError("permission denied")), \
             pytest.raises(IOError):
                get_html_form()

    def test_returns_string_on_success(self):
        """get_html_form returns a string on success."""
        result = get_html_form()
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result or "<html" in result.lower()


class TestConvertWorkerUnsupportedFormat:
    """Tests for _convert_worker with unsupported format."""

    @pytest.mark.anyio
    async def test_unsupported_format_raises(self):
        """_convert_worker raises ValueError for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            await _convert_worker(b"dummy", "xyz")

    @pytest.mark.anyio
    async def test_unsupported_format_message(self):
        """Error message includes the unsupported extension."""
        with pytest.raises(ValueError, match="txt"):
            await _convert_worker(b"dummy", "txt")

    @pytest.mark.anyio
    async def test_supported_format_pdf(self):
        """_convert_worker returns correct structure for PDF."""
        with patch("app.converter.convert_pdf_to_md", return_value="# PDF Content"):
            result = await _convert_worker(b"pdf-data", "pdf")
            assert result["success"] is True
            assert result["markdown"] == "# PDF Content"
            assert result["format"] == "pdf"
            assert result["size_bytes"] == len(b"pdf-data")

    @pytest.mark.anyio
    async def test_supported_format_docx(self):
        """_convert_worker returns correct structure for DOCX."""
        with patch("app.converter.convert_docx_to_md", return_value="# DOCX Content"):
            result = await _convert_worker(b"docx-data", "docx")
            assert result["success"] is True
            assert result["markdown"] == "# DOCX Content"
            assert result["format"] == "docx"

    @pytest.mark.anyio
    async def test_supported_format_odt(self):
        """_convert_worker returns correct structure for ODT."""
        with patch("app.converter.convert_odt_to_md", return_value="# ODT Content"):
            result = await _convert_worker(b"odt-data", "odt")
            assert result["success"] is True
            assert result["format"] == "odt"

    @pytest.mark.anyio
    async def test_supported_format_html(self):
        """_convert_worker returns correct structure for HTML."""
        with patch("app.converter.convert_html_to_md", return_value="# HTML Content"):
            result = await _convert_worker(b"<html></html>", "html")
            assert result["success"] is True
            assert result["format"] == "html"

    @pytest.mark.anyio
    async def test_supported_format_xlsx(self):
        """_convert_worker returns correct structure for XLSX."""
        with patch("app.converter.convert_xlsx_to_md", return_value="# XLSX Content"):
            result = await _convert_worker(b"xlsx-data", "xlsx")
            assert result["success"] is True
            assert result["markdown"] == "# XLSX Content"
            assert result["format"] == "xlsx"
            assert result["size_bytes"] == len(b"xlsx-data")
