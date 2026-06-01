"""ODS to Markdown converter using odfpy.

Converts OpenDocument Spreadsheet (.ods) files to Markdown format.
Extracts all sheets, cells, and formats them as Markdown tables.
"""

import html
import io
import logging

from odf import opendocument, table, text

logger = logging.getLogger(__name__)


def convert_ods_to_md(file_bytes: bytes) -> str:
    """
    Convert an ODS file to Markdown format.

    Args:
        file_bytes: Raw ODS file content.

    Returns:
        Markdown string representation of the spreadsheet.

    Raises:
        ValueError: If the ODS file is invalid or cannot be parsed.
    """
    try:
        doc = opendocument.load(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Invalid ODS file: {e}") from e

    sheets = doc.getElementsByType(table.Table)
    markdown_parts: list[str] = []

    if not sheets:
        return "*Spreadsheet is empty or contains no sheets.*"

    for sheet_idx, sheet in enumerate(sheets):
        sheet_name = sheet.getAttribute("name") or f"Sheet {sheet_idx + 1}"
        markdown_parts.append(f"## {html.escape(str(sheet_name))}\n")

        rows = list(sheet.getElementsByType(table.TableRow))

        if not rows:
            markdown_parts.append("*Empty sheet*\n")
            continue

        # Extract data into a 2D grid
        grid: list[list[str]] = []

        for row in rows:
            cells = list(row.getElementsByType(table.TableCell))
            row_data: list[str] = []

            for cell in cells:
                cell_text = _extract_cell_text(cell)
                row_data.append(cell_text)

            # Skip completely empty rows
            if any(cell.strip() for cell in row_data):
                grid.append(row_data)

        if not grid:
            markdown_parts.append("*Empty sheet*\n")
            continue

        # Determine number of columns (max width across all rows)
        num_cols = max(len(row) for row in grid)

        # Convert to Markdown table
        markdown_parts.append(_grid_to_markdown_table(grid, num_cols))

    return "\n".join(markdown_parts)


def _extract_cell_text(cell: table.TableCell) -> str:
    """
    Extract text content from a table cell.

    Args:
        cell: ODF TableCell element.

    Returns:
        Cell text content as a string.
    """
    texts = cell.getElementsByType(text.P)
    if not texts:
        return ""

    # Concatenate all paragraph text in the cell (escape to prevent XSS)
    parts: list[str] = []
    for p in texts:
        cell_text = html.escape(str(p).strip())
        if cell_text:
            parts.append(cell_text)

    return "\n".join(parts) if parts else ""


def _grid_to_markdown_table(grid: list[list[str]], num_cols: int) -> str:
    """
    Convert a 2D grid to a Markdown table.

    Args:
        grid: 2D list of cell values.
        num_cols: Number of columns in the table.

    Returns:
        Markdown table string.
    """
    if not grid:
        return ""

    # Pad rows to have consistent column count
    padded_grid = []
    for row in grid:
        padded_row = row + [""] * (num_cols - len(row))
        padded_grid.append(padded_row)

    # Create header separator
    separator = "| " + " | ".join(["---"] * num_cols) + " |"

    # Build table rows
    def format_row(row_data: list[str]) -> str:
        formatted_cells = [" " if cell == "" else cell.replace("|", "\\|") for cell in row_data]
        return "| " + " | ".join(formatted_cells) + " |"

    table_lines = [format_row(padded_grid[0]), separator]

    # Add data rows (skip first row as it's the header)
    for row in padded_grid[1:]:
        table_lines.append(format_row(row))

    return "\n".join(table_lines)
