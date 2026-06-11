"""ODT to Markdown conversion using odfpy."""

import html
import io
import logging

from odf import opendocument, text  # type: ignore[import-untyped]
from odf.namespaces import TEXTNS  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def _escape_md_text(text: str) -> str:
    """Escape HTML entities in text to prevent XSS via raw HTML in Markdown.

    Args:
        text: Raw text extracted from an ODT element.

    Returns:
        Text with HTML-special characters escaped.
    """
    return html.escape(text, quote=False)


def convert_odt_to_md(file_bytes: bytes) -> str:
    """Pure Python ODT → MD conversion (odfpy)."""
    doc = opendocument.load(io.BytesIO(file_bytes))

    lines: list[str] = []
    current_list_items: list[str] = []

    def flush_list() -> None:
        """Flush accumulated list items as a Markdown list block."""
        if current_list_items:
            lines.extend(current_list_items)
            lines.append("")  # blank line after list
            current_list_items.clear()

    def get_element_text(element) -> str:
        """Extract text content from an ODT element child node."""
        if hasattr(element, "data"):
            # Text node
            return element.data or ""
        if hasattr(element, "localName"):
            local_name = element.localName
            if local_name == "h":
                # Heading inside paragraph (rare)
                level = min(int(element.getAttrNS(TEXTNS, "outline-level") or "1"), 6)
                return f"\n{'#' * level} {element._getText()}"
            elif local_name == "tab":
                return "\t"
            elif local_name == "br":
                return "\n"
            elif local_name == "span":
                return element._getText() if hasattr(element, "_getText") else ""
        return ""

    for paragraph in doc.body.getElementsByType(text.P):
        flush_list()

        parts: list[str] = []
        for element in paragraph.childNodes:
            parts.append(get_element_text(element))

        text_content = _escape_md_text("".join(parts)).strip()
        if not text_content:
            lines.append("")
            continue

        # Check if paragraph is a list item
        bullet_name = paragraph.getAttrNS(TEXTNS, "bullet-name")
        style_name = paragraph.getAttrNS(TEXTNS, "style-name") or ""

        is_list_item = (
            bullet_name is not None
            or "list" in style_name.lower()
            or "bullet" in style_name.lower()
        )

        if is_list_item:
            current_list_items.append(f"- {text_content}")
        else:
            lines.append("")  # blank line before paragraph
            lines.append(text_content)

    flush_list()

    return "\n".join(lines).strip()


def _extract_odt_content(file_bytes: bytes) -> list[tuple[int, str, list[str]]]:
    """Extract ODT content as pages (paragraphs).

    Args:
        file_bytes: Raw ODT file bytes.

    Returns:
        List of tuples (page_num, title, text_list).
    """
    doc = opendocument.load(io.BytesIO(file_bytes))

    lines: list[str] = []
    current_list_items: list[str] = []
    page_num = 0
    
    def flush_list() -> None:
        nonlocal page_num
        if current_list_items:
            lines.extend(current_list_items)
            lines.append("")
            page_num += 1
            current_list_items.clear()

    def get_element_text(element) -> str:
        if hasattr(element, "data"):
            return element.data or ""
        if hasattr(element, "localName"):
            local_name = element.localName
            if local_name == "h":
                level = min(int(element.getAttrNS(TEXTNS, "outline-level") or "1"), 6)
                return f"\n{'#' * level} {element._getText()}"
            elif local_name == "tab":
                return "\t"
            elif local_name == "br":
                return "\n"
            elif local_name == "span":
                return element._getText() if hasattr(element, "_getText") else ""
        return ""

    for paragraph in doc.body.getElementsByType(text.P):
        flush_list()

        parts: list[str] = []
        for element in paragraph.childNodes:
            parts.append(get_element_text(element))

        text_content = _escape_md_text("".join(parts)).strip()
        if not text_content:
            lines.append("")
            continue

        bullet_name = paragraph.getAttrNS(TEXTNS, "bullet-name")
        style_name = paragraph.getAttrNS(TEXTNS, "style-name") or ""

        is_list_item = (
            bullet_name is not None
            or "list" in style_name.lower()
            or "bullet" in style_name.lower()
        )

        if is_list_item:
            current_list_items.append(f"- {text_content}")
        else:
            lines.append("")
            lines.append(text_content)

    flush_list()
    
    # Group paragraphs into pages (simple heuristic: every 10 paragraphs = new page)
    results = []
    if lines:
        page_lines = []
        for line in lines:
            page_lines.append(line)
            if len(page_lines) >= 10 and not line.strip():
                results.append((page_num + 1, "", [l.strip() for l in page_lines if l.strip()]))
                page_lines = []
        
        if page_lines:
            results.append((len(results) + 1, "", [l.strip() for l in page_lines if l.strip()]))

    return results


def convert_odt_to_json(file_bytes: bytes) -> dict:
    """Convert ODT to JSON format.

    Args:
        file_bytes: Raw ODT file bytes.

    Returns:
        Dict with pages and metadata in JSON structure.
    """
    from app.models.response import PageJson
    
    results = _extract_odt_content(file_bytes)
    
    return {
        "format": "odt",
        "pages": [
            PageJson(
                page_num=page[0],
                title=page[1],
                text=[_escape_md_text(p) for p in page[2]]
            ).model_dump()
            for page in results
        ],
        "metadata": {
            "format": "odt",
            "size_bytes": len(file_bytes),
        },
    }


def convert_odt_to_jsonl(file_bytes: bytes) -> str:
    """Convert ODT to JSONL format with chunking.

    Args:
        file_bytes: Raw ODT file bytes.

    Returns:
        JSONL string with start, chunk, and end events.
    """
    from app.models.response import PageJson
    
    results = _extract_odt_content(file_bytes)
    
    return _to_jsonl(results)


def _to_jsonl(results: list[tuple[int, str, list[str]]]) -> str:
    """Convert extraction results to JSONL format with chunking.

    Args:
        results: List of (page_num, title, text_list) tuples.

    Returns:
        JSONL string with start, chunk, and end events.
    """
    import json
    
    lines = []
    
    # Start event
    lines.append(json.dumps({
        "type": "start",
        "format": "odt",
    }))
    
    # Convert to text representation for chunking
    all_text = []
    for page_num, title, page_lines in results:
        all_text.append(f"Page {page_num}: {title}")
        all_text.extend(page_lines)
    
    chunk_size = settings.CAAS_JSONL_CHUNK_SIZE
    
    if all_text:
        chunks = [all_text[i:i + chunk_size] for i in range(0, len(all_text), chunk_size)]
        
        for chunk in chunks:
            lines.append(json.dumps({
                "type": "chunk",
                "content": "\n".join(chunk),
            }))
    
    # End event
    lines.append(json.dumps({
        "type": "end",
        "format": "odt",
        "total_pages": len(results),
    }))
    
    return "\n".join(lines)
