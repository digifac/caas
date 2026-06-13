"""Conversion orchestration: delegates to converter modules."""

import asyncio
import logging
import re
from typing import Any, Coroutine

from app.config import settings
from app.converters.docx import (
    convert_docx_to_json,
    convert_docx_to_jsonl,
    convert_docx_to_md,
)
from app.converters.html import (
    convert_html_to_json,
    convert_html_to_jsonl,
    convert_html_to_md,
)
from app.converters.odp import (
    convert_odp_to_json,
    convert_odp_to_jsonl,
    convert_odp_to_md,
)
from app.converters.ods import (
    convert_ods_to_json,
    convert_ods_to_jsonl,
    convert_ods_to_md,
)
from app.converters.odt import (
    convert_odt_to_json,
    convert_odt_to_jsonl,
    convert_odt_to_md,
)
from app.converters.pdf import (
    convert_pdf_to_json,
    convert_pdf_to_jsonl,
    convert_pdf_to_md,
)
from app.converters.pptx import (
    convert_pptx_to_json,
    convert_pptx_to_jsonl,
    convert_pptx_to_md,
)
from app.converters.xlsx import (
    convert_xlsx_to_json,
    convert_xlsx_to_jsonl,
    convert_xlsx_to_md,
)

logger = logging.getLogger(__name__)


def clean_lines(lines: list[str]) -> list[str]:
    """Clean and enhance lines of text for better Markdown output.

    - Removes empty/whitespace-only lines.
    - Strips leading/trailing whitespace.
    - Detects numbered headings (e.g., "1. Introduction").
    - Detects Markdown headings (e.g., "## Titre").
    - Detects all-caps headings when enabled (short lines without punctuation/digits).
    - Preserves bullet lists and normal text.

    Args:
        lines: List of text lines to clean.

    Returns:
        List of cleaned lines with detected headings prefixed with "# ".
    """
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect numbered headings: "1. Title" or "1) Title"
        if re.match(r"^\d+[\.\)]\s+", stripped) or stripped.startswith("#") or (
            settings.markdown_heading_detection
            and stripped.isupper()
            and len(stripped) <= 40
            and not re.search(r"[0-9]", stripped)
            and not re.search(r"[:;\-]", stripped)
        ):
            stripped = f"# {stripped}"

        result.append(stripped)
    return result


async def convert_worker(file_bytes: bytes, ext: str, output_format: str = "markdown") -> dict[str, Any]:
    """Worker that runs conversion in a thread (used by TaskManager).

    Args:
        file_bytes: Raw file bytes.
        ext: File extension (pdf, docx, xlsx, etc.).
        output_format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".

    Returns:
        Dict with conversion result in the requested format.
    """
    converters = {
        "pdf": convert_pdf_to_md,
        "docx": convert_docx_to_md,
        "odt": convert_odt_to_md,
        "ods": convert_ods_to_md,
        "odp": convert_odp_to_md,
        "html": convert_html_to_md,
        "xlsx": convert_xlsx_to_md,
        "pptx": convert_pptx_to_md,
    }

    json_converters = {
        "pdf": convert_pdf_to_json,
        "docx": convert_docx_to_json,
        "odt": convert_odt_to_json,
        "ods": convert_ods_to_json,
        "odp": convert_odp_to_json,
        "html": convert_html_to_json,
        "xlsx": convert_xlsx_to_json,
        "pptx": convert_pptx_to_json,
    }

    jsonl_converters = {
        "pdf": convert_pdf_to_jsonl,
        "docx": convert_docx_to_jsonl,
        "odt": convert_odt_to_jsonl,
        "ods": convert_ods_to_jsonl,
        "odp": convert_odp_to_jsonl,
        "html": convert_html_to_jsonl,
        "xlsx": convert_xlsx_to_jsonl,
        "pptx": convert_pptx_to_jsonl,
    }

    converter = converters.get(ext)
    json_converter = json_converters.get(ext)
    jsonl_converter = jsonl_converters.get(ext)

    if not converter:
        raise ValueError(f"Unsupported format: {ext}")

    if output_format == "json":
        assert json_converter is not None, f"No JSON converter for {ext}"
        result = await asyncio.to_thread(json_converter, file_bytes)
    elif output_format == "jsonl":
        assert jsonl_converter is not None, f"No JSONL converter for {ext}"
        result = await asyncio.to_thread(jsonl_converter, file_bytes)
    else:  # markdown (default)
        result = await asyncio.to_thread(converter, file_bytes)

    return {
        "success": True,
        "markdown": result if output_format == "markdown" else None,
        "json": result if output_format == "json" else None,
        "jsonl": result if output_format == "jsonl" else None,
        "format": ext,
        "size_bytes": len(file_bytes),
    }
