"""Conversion orchestration: delegates to converter modules."""

import asyncio
import logging
import re

from app.config import settings
from app.converters.docx import convert_docx_to_md
from app.converters.html import convert_html_to_md
from app.converters.odp import convert_odp_to_md
from app.converters.ods import convert_ods_to_md
from app.converters.odt import convert_odt_to_md
from app.converters.pdf import convert_pdf_to_md
from app.converters.pptx import convert_pptx_to_md
from app.converters.xlsx import convert_xlsx_to_md

logger = logging.getLogger(__name__)


def _clean_lines(lines: list[str]) -> list[str]:
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


async def _convert_worker(file_bytes: bytes, ext: str) -> dict:
    """Worker that runs conversion in a thread (used by TaskManager)."""
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
    converter = converters.get(ext)
    if not converter:
        raise ValueError(f"Unsupported format: {ext}")
    markdown = await asyncio.to_thread(converter, file_bytes)
    return {
        "success": True,
        "markdown": markdown,
        "format": ext,
        "size_bytes": len(file_bytes),
    }
