"""XLSX to Markdown conversion using openpyxl."""

import html
import io
import json
import logging
import re
from datetime import date, datetime
from typing import Optional

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.config import settings

logger = logging.getLogger(__name__)

# Dangerous URL schemes that must be blocked to prevent injection attacks
_DANGEROUS_URL_SCHEMES = re.compile(
    r"^(?:javascript|vbscript|data|file|blob):",
    re.IGNORECASE,
)


def _sanitize_url(url: Optional[str]) -> Optional[str]:
    """Sanitize a URL by blocking dangerous schemes.

    Args:
        url: The raw URL string to sanitize, or None.

    Returns:
        The sanitized URL, "#" if the URL uses a dangerous scheme, or None.
    """
    if url is None:
        return None
    if not url:
        return url
    stripped = url.strip()
    if _DANGEROUS_URL_SCHEMES.match(stripped):
        logger.warning("Blocked dangerous URL scheme in XLSX: %s", stripped[:50])
        return "#"
    return url


def _escape_md_table(text: Optional[str]) -> Optional[str]:
    r"""Escape characters that have special meaning in Markdown tables.

    Escapes `|` and `\` to prevent table structure corruption.

    Args:
        text: Raw cell text, or None.

    Returns:
        Text with Markdown table special characters escaped, or None.
    """
    if text is None:
        return None
    if not text:
        return text
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    return text


def _cell_to_string(cell) -> str:
    """Convert an openpyxl cell value to its string representation.

    Handles different cell types: text, number, date, boolean, formula, None.

    Args:
        cell: An openpyxl cell object.

    Returns:
        The string representation of the cell value.
    """
    value = cell.value

    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    # String value (including formula results that are strings)
    return str(value)


def _get_merged_cell_value(ws, row: int, col: int) -> str:
    """Get the value of a cell, checking merged ranges first.

    If the cell is part of a merged range, returns the value of the
    top-left cell of that range.

    Note: In read_only mode, merged_cells is not available, so we
    just return the cell value directly.

    Args:
        ws: The openpyxl worksheet.
        row: Row number (1-based).
        col: Column number (1-based).

    Returns:
        The string representation of the cell value.
    """
    # In read_only mode, merged_cells is not available
    # We skip merged cell handling for better performance
    if hasattr(ws, "merged_cells") and ws.merged_cells:
        for merged_range in ws.merged_cells.ranges:
            if (row, col) in merged_range:
                top_cell = ws.cell(
                    row=merged_range.min_row, column=merged_range.min_col
                )
                return _cell_to_string(top_cell)
    return _cell_to_string(ws.cell(row=row, column=col))


def _build_sheet_md(ws) -> str:
    """Convert a single worksheet to a Markdown table.

    Args:
        ws: An openpyxl worksheet object.

    Returns:
        A Markdown string with a heading and table representation of the sheet.
    """
    if ws.max_row == 0 or ws.max_column == 0:
        return f"# {html.escape(ws.title)}\n\n_(empty sheet)_"

    # Collect all values into a 2D array
    rows = []
    for row_idx in range(1, ws.max_row + 1):
        row_values = []
        for col_idx in range(1, ws.max_column + 1):
            value = _get_merged_cell_value(ws, row_idx, col_idx)
            row_values.append(value)
        rows.append(row_values)

    # Build Markdown table
    lines = []

    # Header row
    header = "| " + " | ".join(_escape_md_table(v) for v in rows[0]) + " |"
    lines.append(header)

    # Separator row
    separator = "| " + " | ".join("---" for _ in rows[0]) + " |"
    lines.append(separator)

    # Data rows
    for row in rows[1:]:
        line = "| " + " | ".join(_escape_md_table(v) for v in row) + " |"
        lines.append(line)

    return f"# {html.escape(ws.title)}\n\n" + "\n".join(lines)


def convert_xlsx_to_md(file_bytes: bytes) -> str:
    """Pure Python XLSX → MD conversion (openpyxl).

    Converts all worksheets to Markdown tables, handling:
    - Multiple sheets
    - Merged cells
    - Different cell types (text, number, date, boolean, formula)
    - Empty cells
    - Special Markdown character escaping

    Args:
        file_bytes: The raw bytes of the XLSX file.

    Returns:
        A Markdown string representing the entire workbook.

    Raises:
        InvalidFileException: If the file is not a valid XLSX.
    """
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except InvalidFileException as e:
        logger.error("Invalid XLSX file: %s", e)
        raise

    # Log openpyxl warnings
    if hasattr(wb, "properties"):
        logger.debug(
            "XLSX properties: title=%s, creator=%s",
            wb.properties.title,
            wb.properties.creator,
        )

    sheets_md = []
    for ws in wb.worksheets:
        try:
            sheet_md = _build_sheet_md(ws)
            sheets_md.append(sheet_md)
        except Exception as e:
            logger.warning("Error converting sheet '%s': %s", ws.title, e)
            sheets_md.append(
                f"# {html.escape(ws.title)}\n\n"
                f"_(error converting sheet: {html.escape(str(e))})_"
            )

    wb.close()

    return "\n\n---\n\n".join(sheets_md)


def _extract_xlsx_content(file_bytes: bytes) -> list[tuple[int, str, list[list[str]]]]:
    """Extract XLSX content as sheets (tables).

    Args:
        file_bytes: Raw XLSX file bytes.

    Returns:
        List of tuples (sheet_num, title, cell_values_list_of_lists).
    """
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except InvalidFileException as e:
        logger.error("Invalid XLSX file: %s", e)
        raise

    results: list[tuple[int, str, list[list[str]]]] = []
    sheet_num = 0

    for ws in wb.worksheets:
        try:
            # Collect all values into a 2D array
            rows = []
            for row_idx in range(1, ws.max_row + 1):
                row_values = []
                for col_idx in range(1, ws.max_column + 1):
                    value = _get_merged_cell_value(ws, row_idx, col_idx)
                    row_values.append(value)
                rows.append(row_values)

            sheet_num += 1
            _results: list[tuple[int, str, list[list[str]]]] = []
            _results.append((sheet_num, html.escape(ws.title), rows))

        except Exception as e:
            logger.warning("Error extracting sheet '%s': %s", ws.title, e)

    wb.close()
    return results  # type: ignore[return-value]


def convert_xlsx_to_json(file_bytes: bytes) -> dict:
    """Convert XLSX to JSON format.

    Args:
        file_bytes: Raw XLSX file bytes.

    Returns:
        Dict with sheets and metadata in JSON structure.
    """
    from app.models.response import CellJson, SheetJson

    results = _extract_xlsx_content(file_bytes)

    return {
        "format": "xlsx",
        "sheets": [
            SheetJson(
                name=sheet[1],
                data=[[_escape_md_table(str(cell_val)) if cell_val else "" for cell_val in row] for row in sheet[2]],
                headers=None
            ).model_dump()
            for sheet in results
        ],
        "metadata": {
            "format": "xlsx",
            "size_bytes": len(file_bytes),
            "sheet_count": len(results),
        },
    }


def convert_xlsx_to_jsonl(file_bytes: bytes) -> str:
    """Convert XLSX to JSONL format with chunking.

    Args:
        file_bytes: Raw XLSX file bytes.

    Returns:
        JSONL string with start, chunk, and end events.
    """

    results = _extract_xlsx_content(file_bytes)

    return _to_jsonl(results)


def _to_jsonl(results: list[tuple[int, str, list[list[str]]]]) -> str:
    """Convert extraction results to JSONL format with chunking.

    Args:
        results: List of (sheet_num, title, cell_values_list_of_lists) tuples.

    Returns:
        JSONL string with start, chunk, and end events.
    """

    lines = []

    # Start event
    lines.append(json.dumps({
        "type": "start",
        "format": "xlsx",
    }))

    # Convert to tabular text representation for chunking
    all_text: list[str] = []
    for sheet_num, title, rows in results:
        all_text.append(f"Sheet {sheet_num}: {title}")
        for row_idx, row_values in enumerate(rows, 1):
            row_str = "| " + " | ".join(str(v) if v else "" for v in row_values) + " |"
            all_text.append(f"Row {row_idx}:\n{row_str}")

    chunk_size = settings.jsonl_chunk_size

    if all_text:
        chunks: list[list[str]] = [all_text[i:i + chunk_size] for i in range(0, len(all_text), chunk_size)]

        for chunk in chunks:
            lines.append(json.dumps({
                "type": "chunk",
                "content": "\n".join(chunk),
            }))

    # End event
    lines.append(json.dumps({
        "type": "end",
        "format": "xlsx",
        "total_sheets": len(results),
    }))

    return "\n".join(lines)
