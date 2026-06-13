"""Tests for ODS to Markdown conversion."""

import io
from typing import Any

import pytest
from app.converters.ods import convert_ods_to_md

# Import fixtures from modules
from tests.fixtures.ods import (  # noqa: E402
    sample_ods_bytes,# type: ignore[import-not-found]
    sample_ods_multi_sheet_bytes,# type: ignore[import-not-found]
    sample_ods_empty_sheet_bytes,# type: ignore[import-not-found]
    sample_ods_special_chars_bytes,# type: ignore[import-not-found]
)


# --- Tests unitaires du convertisseur ---


class TestConvertOdsToMd:
    """Unit tests for the ODS converter."""

    def test_simple_sheet_conversion(self, sample_ods_bytes: bytes) -> None:
        """Test conversion of a simple single-sheet ODS."""
        result = convert_ods_to_md(sample_ods_bytes)
        assert "## Feuille1" in result
        assert "| Nom | Valeur |" in result
        assert "| --- | --- |" in result
        assert "| A | 1 |" in result
        assert "| B | 2 |" in result

    def test_multi_sheet_conversion(
        self, sample_ods_multi_sheet_bytes: bytes
    ) -> None:
        """Test conversion of an ODS with multiple sheets."""
        result = convert_ods_to_md(sample_ods_multi_sheet_bytes)
        assert "## Données" in result
        assert "## Résumé" in result
        assert "| Produit | Prix |" in result
        assert "| Pomme | 1.5 |" in result
        assert "| Orange | 2.0 |" in result
        assert "| Total | 3.5 |" in result

    def test_empty_sheet(self, sample_ods_empty_sheet_bytes: bytes) -> None:
        """Test handling of an empty sheet."""
        result = convert_ods_to_md(sample_ods_empty_sheet_bytes)
        assert "## Vide" in result
        assert "*Empty sheet*" in result

    def test_special_chars(self, sample_ods_special_chars_bytes: bytes) -> None:
        """Test handling of special characters (pipe, backslash, accents)."""
        result = convert_ods_to_md(sample_ods_special_chars_bytes)
        assert "## Spécial" in result
        assert "Colonne A" in result
        assert "Colonne B" in result
        # Pipe characters should be escaped in Markdown tables
        assert "\\|" in result
        # Accented characters should be preserved
        assert "Àéîôù" in result
        assert "Ñ ü ö ä" in result

    def test_invalid_ods_raises_error(self) -> None:
        """Test that an invalid ODS file raises a ValueError."""
        with pytest.raises(ValueError, match="Invalid ODS file"):
            convert_ods_to_md(b"not a valid ods file")

    def test_empty_cells(self) -> None:
        """Test that empty cells are handled correctly."""
        from odf import table, text  # type: ignore[import-not-found]
        from odf.opendocument import OpenDocumentSpreadsheet  # type: ignore[import-not-found]

        doc = OpenDocumentSpreadsheet()  # type: ignore[arg-type]
        table_elem = table.Table(name="Test")  # type: ignore[attr-defined]

        # Row 1: headers
        row1 = table.TableRow()  # type: ignore[attr-defined]
        c1 = table.TableCell()  # type: ignore[attr-defined]
        p1 = text.P()  # type: ignore[attr-defined]
        p1.addText("Header")  # type: ignore[attr-defined]
        c1.addElement(p1)  # type: ignore[attr-defined]
        row1.addElement(c1)  # type: ignore[attr-defined]
        c2 = table.TableCell()  # type: ignore[attr-defined]
        p2 = text.P()  # type: ignore[attr-defined]
        p2.addText("Data")  # type: ignore[attr-defined]
        c2.addElement(p2)  # type: ignore[attr-defined]
        row1.addElement(c2)  # type: ignore[attr-defined]
        table_elem.addElement(row1)  # type: ignore[attr-defined]

        # Row 2: one value, one empty cell
        row2 = table.TableRow()  # type: ignore[attr-defined]
        c3 = table.TableCell()  # type: ignore[attr-defined]
        p3 = text.P()  # type: ignore[attr-defined]
        p3.addText("value")  # type: ignore[attr-defined]
        c3.addElement(p3)  # type: ignore[attr-defined]
        row2.addElement(c3)  # type: ignore[attr-defined]
        c4 = table.TableCell()  # Empty cell  # type: ignore[attr-defined]
        row2.addElement(c4)  # type: ignore[attr-defined]
        table_elem.addElement(row2)  # type: ignore[attr-defined]

        doc.spreadsheet.addElement(table_elem)  # type: ignore[union-attr]

        buf = io.BytesIO()
        doc.save(buf)  # type: ignore[arg-type]
        buf.seek(0)

        result = convert_ods_to_md(buf.getvalue())
        assert "## Test" in result
        assert "| Header | Data |" in result
        # The row with an empty cell should still appear
        assert "| value |" in result


# --- Tests API synchrones ---


class TestOdsApiSync:
    """Synchronous API tests for ODS conversion."""

    @pytest.mark.asyncio
    async def test_convert_ods_sync_success(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """POST /convert with a valid ODS file returns 200 with Markdown."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.ods",
                    sample_ods_bytes,
                    "application/vnd.oasis.opendocument.spreadsheet",
                )
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "markdown" in data
        assert "## Feuille1" in data["markdown"]

    @pytest.mark.asyncio
    async def test_convert_ods_sync_invalid_file(
        self, async_client: Any
    ) -> None:
        """POST /convert with an invalid ODS file returns 400."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.ods",
                    b"not a valid ods file",
                    "application/octet-stream",
                )
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_convert_ods_sync_too_large(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """POST /convert with an ODS file that is too large returns an error."""
        # Create a file larger than the max allowed size
        from app.config import settings

        # Pad the file to exceed the limit
        large_ods = sample_ods_bytes + b"\x00" * (
            settings.max_file_size_mb * 1024 * 1024 + 1
        )

        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "large.ods",
                    large_ods,
                    "application/vnd.oasis.opendocument.spreadsheet",
                )
            },
        )
        # Should return 400 or 413 for file too large
        assert response.status_code in (400, 413)


# --- Tests API asynchrones (batch) ---


class TestOdsApiAsync:
    """Asynchronous / batch API tests for ODS conversion."""

    @pytest.mark.asyncio
    async def test_convert_ods_async_success(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """POST /convert with ?async=true returns a task ID."""
        response = await async_client.post(
            "/convert?async=true",
            files={
                "file": (
                    "test.ods",
                    sample_ods_bytes,
                    "application/vnd.oasis.opendocument.spreadsheet",
                )
            },
        )
        assert response.status_code in (200, 202)
        data = response.json()
        assert "task_id" in data or "markdown" in data

    @pytest.mark.asyncio
    async def test_batch_convert_ods_sync(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """POST /convert/batch with an ODS file returns success."""
        response = await async_client.post(
            "/convert/batch",
            files=[("files", ("test.ods", sample_ods_bytes))],
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["total_files"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["success"] is True
        assert "## Feuille1" in result["markdown"]

    @pytest.mark.asyncio
    async def test_batch_convert_ods_async(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """POST /convert/batch?async=true with an ODS file returns a batch ID."""
        response = await async_client.post(
            "/convert/batch?async=true",
            files=[("files", ("test.ods", sample_ods_bytes))],
        )
        assert response.status_code in (200, 202)
        data = response.json()
        assert "batch_id" in data or "results" in data

    @pytest.mark.asyncio
    async def test_batch_convert_mixed_formats(
        self, async_client: Any, sample_ods_bytes: bytes, sample_pdf_bytes: bytes
    ) -> None:
        """POST /convert/batch with ODS + PDF returns success for both."""
        response = await async_client.post(
            "/convert/batch",
            files=[
                ("files", ("test.ods", sample_ods_bytes)),
                ("files", ("test.pdf", sample_pdf_bytes)),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2

        # Check that both results are present
        filenames = {r["filename"] for r in data["results"]}
        assert "test.ods" in filenames
        assert "test.pdf" in filenames

        # Check ODS result
        ods_result = next(r for r in data["results"] if r["filename"] == "test.ods")
        assert ods_result["success"] is True
        assert "## Feuille1" in ods_result["markdown"]

        # Check PDF result
        pdf_result = next(r for r in data["results"] if r["filename"] == "test.pdf")
        assert pdf_result["success"] is True
        assert "Hello World" in pdf_result["markdown"]


class TestOdsApiAsyncFormat:
    """Asynchronous API tests for ODS conversion with different formats."""

    @pytest.mark.asyncio
    async def test_convert_ods_to_json(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """Upload valid ODS → JSON with sheets."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.ods",
                    sample_ods_bytes,
                    "application/vnd.oasis.opendocument.spreadsheet",
                )
            },
            params={"format": "json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["format"] == "ods"
        assert "json" in data

        json_data = data["json"]
        # ODS should have sheets with tables
        if "sheets" in json_data:
            assert isinstance(json_data["sheets"], list)
            assert len(json_data["sheets"]) > 0

    @pytest.mark.asyncio
    async def test_convert_ods_to_jsonl(
        self, async_client: Any, sample_ods_bytes: bytes
    ) -> None:
        """Upload valid ODS → JSONL with events."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.ods",
                    sample_ods_bytes,
                    "application/vnd.oasis.opendocument.spreadsheet",
                )
            },
            params={"format": "jsonl"},
        )
        assert response.status_code == 200
        data = response.json()

        jsonl_data: list[str] = data["jsonl"]
        assert len(jsonl_data) >= 3

        # Verify event types
        event_types: list[str] = [e.split('{"type": ')[1].split('}')[0] for e in jsonl_data]
        assert "start" in event_types
        assert "end" in event_types
