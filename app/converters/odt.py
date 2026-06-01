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
