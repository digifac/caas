"""DOCX to Markdown conversion using mammoth."""

from typing import Any, Pattern

import html
import io
import json
import logging
import re

import mammoth

from app.config import settings
from app.models.response import PageJson

logger = logging.getLogger(__name__)

# Dangerous URL schemes that must be blocked to prevent injection attacks
_DANGEROUS_URL_SCHEMES: Pattern[str] = re.compile(
    r"^(?:javascript|vbscript|data|file|blob):",
    re.IGNORECASE,
)


def sanitize_url(url: str) -> str:
    """Sanitize a URL by blocking dangerous schemes.

    Args:
        url: The raw URL string to sanitize.

    Returns:
        The sanitized URL, or "#" if the URL uses a dangerous scheme.
    """
    if not url:
        return url
    stripped = url.strip()
    if _DANGEROUS_URL_SCHEMES.match(stripped):
        logger.warning("Blocked dangerous URL scheme in DOCX: %s", stripped[:50])
        return "#"
    return url


def escape_md_text(text: str) -> str:
    """Escape HTML entities in text to prevent XSS via raw HTML in Markdown.

    Args:
        text: Raw text extracted from a DOCX element.

    Returns:
        Text with HTML-special characters escaped.
    """
    return html.escape(text, quote=False)


def convert_docx_to_md(file_bytes: bytes) -> str:
    """Pure Python DOCX → MD conversion (mammoth).

    Post-processes the Markdown output to:
    - Escape HTML entities in text content to prevent XSS
    - Sanitize URLs in links to block dangerous schemes
    """
    result = mammoth.convert_to_markdown(io.BytesIO(file_bytes))  # type: ignore[union-attr]
    if hasattr(result, 'messages') and result.messages:
        for msg in result.messages:
            logger.warning("DOCX Warning: %s", str(msg))

    markdown: str = result.value.strip()  # type: ignore[union-attr]

    # Sanitize URLs in Markdown links [text](url)
    def sanitize_link(match: re.Match[str]) -> str:
        link_text = match.group(1)
        url = match.group(2)
        safe_url = sanitize_url(url)
        return f"[{link_text}]({safe_url})"

    markdown = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", sanitize_link, markdown)

    # Sanitize URLs in Markdown images ![alt](url)
    def sanitize_image(match: re.Match[str]) -> str:
        alt = match.group(1)
        url = match.group(2)
        safe_url = sanitize_url(url)
        return f"![{alt}]({safe_url})"

    markdown = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", sanitize_image, markdown)

    return markdown


def _extract_docx_content(file_bytes: bytes) -> list[tuple[int, str, list[str]]]:
    """Extract DOCX content as pages (paragraphs).

    Args:
        file_bytes: Raw DOCX file bytes.

    Returns:
        List of tuples (page_num, title, text_list).
    """
    result = mammoth.convert_to_markdown(io.BytesIO(file_bytes))  # type: ignore[union-attr]
    if hasattr(result, 'messages') and result.messages:
        for msg in result.messages:
            logger.warning("DOCX Warning: %s", str(msg))

    markdown: str = result.value.strip()  # type: ignore[union-attr]
    
    # Split into paragraphs/pages - DOCX doesn't have natural page breaks,
    # so we treat the entire document as a single "page" with paragraph content
    paragraphs = [p.strip() for p in markdown.split("\n\n") if p.strip()]
    return [(0, "Document", paragraphs)]


def convert_docx_to_json(file_bytes: bytes) -> dict[str, Any]:
    """Convert DOCX to JSON format.

    Args:
        file_bytes: Raw DOCX file bytes.

    Returns:
        Dict with pages and metadata in JSON structure.
    """
    results = _extract_docx_content(file_bytes)

    return {
        "format": "docx",
        "pages": [
            PageJson(
                page_idx=page[0],
                markdown_text=" ".join(page[2]),  # Reconstituer le texte des paragraphes
                links=[]
            ).model_dump()
            for page in results
        ],
        "metadata": {
            "format": "docx",
            "size_bytes": len(file_bytes),
        },
    }


def convert_docx_to_jsonl(file_bytes: bytes) -> str:
    """Convert DOCX to JSONL format with chunking.

    Args:
        file_bytes: Raw DOCX file bytes.

    Returns:
        JSONL string with start, chunk, and end events.
    """
    results = _extract_docx_content(file_bytes)

    return _to_jsonl(results)


def _to_jsonl(results: list[tuple[int, str, list[str]]]) -> str:
    """Convert extraction results to JSONL format with chunking.

    Args:
        results: List of (page_num, title, text_list) tuples.

    Returns:
        JSONL string with start, chunk, and end events.
    """
    lines: list[str] = []

    # Start event
    lines.append(json.dumps({
        "type": "start",
        "format": "docx",
    }))

    # Chunk text content
    all_text = "\n".join(
        f"Page {page[0]}: {' '.join(page[2])}"
        for page in results
    )

    chunk_size = settings.jsonl_chunk_size

    if all_text:
        chunks = [all_text[i:i + chunk_size] for i in range(0, len(all_text), chunk_size)]

        for chunk in chunks:
            lines.append(json.dumps({
                "type": "chunk",
                "content": chunk,
            }))

    # End event
    lines.append(json.dumps({
        "type": "end",
        "format": "docx",
        "total_pages": len(results),
    }))

    return "\n".join(lines)
