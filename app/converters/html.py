"""HTML to Markdown conversion using beautifulsoup4 and html2text."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

from bs4 import BeautifulSoup  # type: ignore[import-not-found]
from bs4 import Tag as _bs4_Tag
from bs4.element import NavigableString as _bs4_NavigableString

from app.config import settings
from app.models.response import JsonlEvent

# Alias for type annotations
bs4 = type('bs4', (), {'Tag': _bs4_Tag, 'NavigableString': _bs4_NavigableString})()  # type: ignore[misc]

logger = logging.getLogger(__name__)

# Dangerous URL schemes that must be blocked to prevent injection attacks
_DANGEROUS_URL_SCHEMES = re.compile(
    r"^(?:javascript|vbscript|data|file|blob):",
    re.IGNORECASE,
)

# HTML event handler attributes (onclick, onload, onerror, etc.)
_EVENT_ATTRS = re.compile(r"^on\w+$", re.IGNORECASE)

# Tags whose text content should NOT be escaped (code blocks preserve raw content)
_RAW_TEXT_TAGS = frozenset(("pre", "code"))

# Tags that are explicitly removed for security reasons.
# Includes tags that can execute JavaScript (math mscript, template, details)
# or load external resources without sanitisation (video, audio).
_DANGEROUS_TAGS = frozenset(
    (
        "script",
        "style",
        "meta",
        "head",
        "iframe",
        "object",
        "embed",
        "form",
        "link",
        "base",
        "applet",
        "frame",
        "frameset",
        "svg",
        "math",
        "template",
        "details",
        "marquee",
        "video",
        "audio",
    )
)


def _escape_md_text(text: str) -> str:
    """Escape HTML entities in text to prevent XSS via raw HTML in Markdown.

    When BeautifulSoup decodes HTML entities in text nodes (e.g., &lt;img ...&gt;),
    the resulting raw HTML tags can be interpreted by Markdown renderers,
    leading to XSS. This function re-escapes dangerous characters so they
    appear as literal text in the rendered Markdown.

    Args:
        text: Raw text extracted from an HTML text node.

    Returns:
        Text with HTML-special characters escaped.
    """
    return html.escape(text, quote=False)


def convert_html_to_md(file_bytes: bytes) -> str:
    """Convert HTML content to Markdown.

    Uses BeautifulSoup for parsing and a custom converter for Markdown output.
    Handles common HTML elements: headings, paragraphs, lists, links, images,
    tables, code blocks, blockquotes, and inline formatting.
    """
    try:
        html_content = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            html_content = file_bytes.decode("latin-1")
        except UnicodeDecodeError as e:
            logger.error("Failed to decode HTML file: %s", e)
            raise ValueError("Unable to decode HTML file content") from e

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove all dangerous elements explicitly
    for tag in soup(_DANGEROUS_TAGS):
        tag.decompose()

    # Sanitize all elements: remove event handlers and dangerous URLs
    _sanitize_soup(soup)

    # Convert the body content to Markdown
    md_lines = _convert_element(soup)

    # Clean up extra blank lines
    markdown = "\n".join(md_lines)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def sanitize_url(url: str) -> str:
    """Sanitize a URL by blocking dangerous schemes.

    Blocks javascript:, vbscript:, data:, file:, and blob: URLs
    which can be used for XSS or local file access attacks.

    Args:
        url: The raw URL string to sanitize.

    Returns:
        The sanitized URL, or "#" if the URL uses a dangerous scheme.
    """
    if not url:
        return url
    stripped = url.strip()
    if _DANGEROUS_URL_SCHEMES.match(stripped):
        logger.warning("Blocked dangerous URL scheme: %s", stripped[:50])
        return "#"
    return url


def _sanitize_soup(soup: BeautifulSoup) -> None:
    """Sanitize a BeautifulSoup tree by removing event handlers and dangerous URLs.

    Modifies the soup in-place:
    - Removes all event handler attributes (onclick, onerror, onload, etc.)
    - Sanitizes href attributes on <a> tags
    - Sanitizes src attributes on <img>, <video>, <audio>, <source> tags
    - Removes <svg> tags containing embedded scripts or event handlers

    Args:
        soup: The BeautifulSoup object to sanitize.
    """
    for element in soup.find_all(True):
        # Remove all event handler attributes
        attrs_to_remove = [attr for attr in element.attrs if _EVENT_ATTRS.match(attr)]
        for attr in attrs_to_remove:
            del element[attr]

        # Sanitize href on <a> tags
        if element.name == "a" and "href" in element.attrs:
            href_val = element["href"]
            if isinstance(href_val, list):
                href_val = " ".join(href_val)
            element["href"] = sanitize_url(href_val)

        # Sanitize src on tags that load external resources
        if (
            element.name in ("img", "video", "audio", "source")
            and "src" in element.attrs
        ):
            src_val = element["src"]
            if isinstance(src_val, list):
                src_val = " ".join(src_val)  # type: ignore
            element["src"] = sanitize_url(src_val)


def _convert_element(element: _bs4_Tag | _bs4_NavigableString) -> list[str]:  # type: ignore[misc]
    """Recursively convert a BeautifulSoup element to Markdown lines."""
    from bs4 import Comment

    if isinstance(element, Comment):
        return []  # type: ignore

    if isinstance(element, _bs4_NavigableString):
        text = str(element)
        # Preserve meaningful whitespace
        parent = element.parent
        if parent and parent.name in _RAW_TEXT_TAGS:
            return [text]
        # Escape HTML entities to prevent XSS via raw HTML in Markdown
        escaped = _escape_md_text(text)
        # Collapse whitespace for normal text
        return [escaped] if escaped.strip() else []

    # This check is redundant since we already handle Tag in the Union type
    # Keeping it for clarity but mypy will complain

    tag = element.name  # type: ignore[union-attr]

    # Headings - process children to preserve inline formatting
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        parts: list[str] = []
        for child in element.children:
            child_lines = _convert_element(child)
            for line in child_lines:
                stripped = line.strip()  # type: ignore
                if stripped:
                    parts.append(stripped)

        content = "".join(parts).strip()
        return [f"{'#' * level} {content}"]

    # Paragraphs - process children to preserve inline formatting (links, bold, italic, images)
    if tag == "p":
        parts: list[str] = []
        for child in element.children:
            child_lines = _convert_element(child)
            for line in child_lines:
                stripped = line.strip()  # type: ignore
                if stripped:
                    parts.append(stripped)

        content = "".join(parts).strip()
        if content:
            return [content, ""]

    # Line breaks
    if tag == "br":
        return ["\n"]

    # Horizontal rules
    if tag == "hr":
        return ["---", ""]

    # Lists
    if tag == "ul":
        return _convert_list(element, ordered=False)
    if tag == "ol":
        return _convert_list(element, ordered=True)

    # Links
    if tag == "a":
        href = element.get("href", "")
        text = _get_text(element)
        if text.strip():
            return [f"[{text.strip()}]({href})"]
        return []

    # Images
    if tag == "img":
        src = element.get("src", "")
        alt_raw = element.get("alt", "")
        alt = _escape_md_text(alt_raw if isinstance(alt_raw, str) else str(alt_raw))
        # src is already sanitized by _sanitize_soup
        return [f"![{alt}]({src})"]

    # Code blocks
    if tag == "pre":
        code_tag = element.find("code")
        code = code_tag.string if code_tag else element.get_text()  # type: ignore
        return [f"```\n{code}\n```", ""]

    if tag == "code":
        # Inline code (not inside <pre>)
        if element.parent and element.parent.name == "pre":
            return []  # Already handled by <pre>
        text = element.get_text()  # type: ignore
        return [f"`{text}`"]

    # Blockquotes
    if tag == "blockquote":
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))  # type: ignore
        quoted: list[str] = []
        for line in lines:
            if line.strip():
                quoted.append(f"> {line.strip()}")
            else:
                quoted.append(">")
        quoted.append("")
        return quoted

    # Tables
    if tag == "table":
        return _convert_table(element)

    # Bold
    if tag in ("strong", "b"):
        text = _get_text(element)
        return [f"**{text.strip()}**"]

    # Italic
    if tag in ("em", "i"):
        text = _get_text(element)
        return [f"*{text.strip()}*"]

    # Strikethrough
    if tag in ("del", "s", "strike"):
        text = _get_text(element)
        return [f"~~{text.strip()}~~"]

    # Divs and sections (block-level containers)
    if tag in ("div", "section", "article", "main", "header", "footer", "body", "html"):
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))  # type: ignore
        return lines

    # Span (inline container)
    if tag == "span":
        text = _get_text(element)
        return [text.strip()]

    # For other tags, just process children
    lines = []
    for child in element.children:
        lines.extend(_convert_element(child))  # type: ignore
    return lines


def _get_text(element: _bs4_Tag | _bs4_NavigableString) -> str:  # type: ignore[misc]
    """Get stripped text content from an element."""
    text: str = element.get_text()  # type: ignore
    return text.strip()  # type: ignore


def _convert_list(element: _bs4_Tag, ordered: bool) -> list[str]:  # type: ignore[misc]
    """Convert a <ul> or <ol> to Markdown list."""
    lines: list[str] = []
    index = 1
    for li in element.find_all("li", recursive=False):  # type: ignore[union-attr]
        li_lines: list[str] = []
        for child in li.children:  # type: ignore[attr-defined]
            li_lines.extend(_convert_element(child))  # type: ignore

        # Flatten the list item content
        content_parts: list[str] = []
        for line in li_lines:
            stripped = line.strip()  # type: ignore
            if stripped:
                content_parts.append(stripped)

        content = " ".join(content_parts) if content_parts else ""  # type: ignore

        if ordered:
            lines.append(f"{index}. {content}")
            index += 1
        else:
            lines.append(f"- {content}")

    if lines:
        lines.append("")
    return lines


def _convert_table(element: _bs4_Tag) -> list[str]:
    """Convert a <table> to Markdown table."""
    rows: list[list[str]] = []

    # Get all rows (from <thead>, <tbody>, <tfoot>, or direct <tr>)
    for tr in element.find_all("tr"):  # type: ignore[union-attr]
        cells: list[str] = []
        for cell in tr.find_all(["td", "th"], recursive=False):  # type: ignore[union-attr]
            lines: list[str] = []
            for child in cell.children:  # type: ignore[attr-defined]
                lines.extend(_convert_element(child))  # type: ignore
            content = "".join(lines).strip().replace("\n", " ")  # type: ignore
            cells.append(content)
        if cells:
            rows.append(cells)

    if not rows:
        return []

    # Find max columns
    max_cols = max(len(row) for row in rows)  # type: ignore

    # Normalize row lengths
    for row in rows:
        while len(row) < max_cols:
            row.append("")  # type: ignore

    # Build Markdown table
    md_lines: list[str] = []
    md_lines.append("| " + " | ".join(rows[0]) + " |")
    md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for row in rows[1:]:
        md_lines.append("| " + " | ".join(row) + " |")  # type: ignore[list-item]

    md_lines.append("")
    return md_lines


def _extract_html_content(file_bytes: bytes) -> list[tuple[int, str, list[str]]]:  # type: ignore[misc]
    """Extract HTML content as sections.

    Args:
        file_bytes: Raw HTML file bytes.

    Returns:
        List of tuples (section_num, title, text_lines).
    """
    try:
        html_content = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            html_content = file_bytes.decode("latin-1")
        except UnicodeDecodeError as e:
            logger.error("Failed to decode HTML file: %s", e)
            raise ValueError("Unable to decode HTML file content") from e

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove dangerous elements and sanitize
    for tag in soup.find_all(_DANGEROUS_TAGS):  # type: ignore[union-attr]
        tag.decompose()

    _sanitize_soup(soup)

    sections: list[tuple[int, str, list[str]]] = []
    section_num = 0

    # Extract content from body or html if no body
    container = soup.body if soup.body is not None else soup.html

    if container is None:
        return []

    for element in container.find_all(True):  # type: ignore[union-attr]
        tag_name = str(element.name)

        # Headings as section titles
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _get_text(element)

            if text.strip():
                section_num += 1
                title = f"Section {section_num}: {text}"

                # Extract content after heading
                lines: list[str] = []
                for child in element.children:
                    lines.extend(_convert_element(child))  # type: ignore[arg-type]

                sections.append((section_num, title, lines))

    return sections


def convert_html_to_json(file_bytes: bytes) -> dict[str, Any]:  # type: ignore[misc]
    """Convert HTML to JSON format.

    Args:
        file_bytes: Raw HTML file bytes.

    Returns:
        Dict with sections and metadata in JSON structure.
    """
    from app.models.response import HtmlElementJson

    results = _extract_html_content(file_bytes)  # type: ignore[list-item]

    return {  # type: ignore[dict-item]
        "format": "html",
        "sections": [
            HtmlElementJson(
                tag="section",
                content=section[1]
            ).model_dump()
            for section in results  # type: ignore[tuple, list-item]
        ],
        "metadata": {
            "format": "html",
            "size_bytes": len(file_bytes),
            "section_count": len(results),
        },
    }


def convert_html_to_jsonl(file_bytes: bytes) -> list[JsonlEvent]:
    """Convert HTML to JSONL format with chunking.

    Args:
        file_bytes: Raw HTML file bytes.

    Returns:
        List of JsonlEvent objects with start, chunk, and end events.
    """

    results = _extract_html_content(file_bytes)

    return _to_jsonl(results)


def _to_jsonl(results: list[tuple[int, str, list[str]]]) -> list[JsonlEvent]:
    """Convert extraction results to JSONL format with chunking.

    Args:
        results: List of (section_num, title, text_lines) tuples.

    Returns:
        List of JsonlEvent objects with start, chunk, and end events.
    """
    from app.models.response import JsonlEvent

    # Start event
    events: list[JsonlEvent] = [JsonlEvent(
        type="start",
        metadata={"format": "html"}
    )]

    # Convert to text representation for chunking
    all_text: list[str] = []
    for section_num, title, section_lines in results:  # type: ignore[tuple]
        all_text.append(f"Section {section_num}: {title}")
        all_text.extend(section_lines)

    chunk_size = settings.jsonl_chunk_size

    if all_text:
        chunks: list[str] = [all_text[i:i + chunk_size] for i in range(0, len(all_text), chunk_size)]

        for chunk in chunks:
            events.append(JsonlEvent(type="chunk", markdown_text=chunk))

    # End event
    events.append(JsonlEvent(
        type="end",
        metadata={"format": "html", "total_sections": len(results)}
    ))

    return events
