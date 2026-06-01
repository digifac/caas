"""HTML to Markdown conversion using beautifulsoup4 and html2text."""

import html
import logging
import re

from bs4 import BeautifulSoup

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


def _sanitize_url(url: str) -> str:
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
            element["href"] = _sanitize_url(href_val)

        # Sanitize src on tags that load external resources
        if (
            element.name in ("img", "video", "audio", "source")
            and "src" in element.attrs
        ):
            src_val = element["src"]
            if isinstance(src_val, list):
                src_val = " ".join(src_val)
            element["src"] = _sanitize_url(src_val)


def _convert_element(element) -> list[str]:
    """Recursively convert a BeautifulSoup element to Markdown lines."""
    from bs4 import Comment, NavigableString, Tag

    if isinstance(element, Comment):
        return []

    if isinstance(element, NavigableString):
        text = str(element)
        # Preserve meaningful whitespace
        parent = element.parent
        if parent and parent.name in _RAW_TEXT_TAGS:
            return [text]
        # Escape HTML entities to prevent XSS via raw HTML in Markdown
        escaped = _escape_md_text(text)
        # Collapse whitespace for normal text
        return [escaped] if escaped.strip() else []

    if not isinstance(element, Tag):
        return []

    tag = element.name

    # Headings
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        text = _get_text(element)
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        content = "".join(lines).strip()
        return [f"{'#' * level} {content}"]

    # Paragraphs
    if tag == "p":
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        content = "".join(lines).strip()
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
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        text = "".join(lines).strip()
        if text:
            return [f"[{text}]({href})"]
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
        code = code_tag.string if code_tag else element.get_text()
        return [f"```\n{code}\n```", ""]

    if tag == "code":
        # Inline code (not inside <pre>)
        if element.parent and element.parent.name == "pre":
            return []  # Already handled by <pre>
        text = element.get_text()
        return [f"`{text}`"]

    # Blockquotes
    if tag == "blockquote":
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        quoted = []
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
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        text = "".join(lines)
        return [f"**{text}**"]

    # Italic
    if tag in ("em", "i"):
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        text = "".join(lines)
        return [f"*{text}*"]

    # Strikethrough
    if tag in ("del", "s", "strike"):
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        text = "".join(lines)
        return [f"~~{text}~~"]

    # Divs and sections (block-level containers)
    if tag in ("div", "section", "article", "main", "header", "footer", "body", "html"):
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        return lines

    # Span (inline container)
    if tag == "span":
        lines = []
        for child in element.children:
            lines.extend(_convert_element(child))
        return lines

    # For other tags, just process children
    lines = []
    for child in element.children:
        lines.extend(_convert_element(child))
    return lines


def _get_text(element) -> str:
    """Get stripped text content from an element."""
    text: str = element.get_text()
    return text.strip()


def _convert_list(element, ordered: bool) -> list[str]:
    """Convert a <ul> or <ol> to Markdown list."""
    lines = []
    index = 1
    for li in element.find_all("li", recursive=False):
        li_lines = []
        for child in li.children:
            li_lines.extend(_convert_element(child))

        # Flatten the list item content
        content_parts = []
        for line in li_lines:
            stripped = line.strip()
            if stripped:
                content_parts.append(stripped)

        content = " ".join(content_parts) if content_parts else ""

        if ordered:
            lines.append(f"{index}. {content}")
            index += 1
        else:
            lines.append(f"- {content}")

    if lines:
        lines.append("")
    return lines


def _convert_table(element) -> list[str]:
    """Convert a <table> to Markdown table."""
    rows = []

    # Get all rows (from <thead>, <tbody>, <tfoot>, or direct <tr>)
    for tr in element.find_all("tr"):
        cells = []
        for cell in tr.find_all(["td", "th"], recursive=False):
            lines = []
            for child in cell.children:
                lines.extend(_convert_element(child))
            content = "".join(lines).strip().replace("\n", " ")
            cells.append(content)
        if cells:
            rows.append(cells)

    if not rows:
        return []

    # Find max columns
    max_cols = max(len(row) for row in rows)

    # Normalize row lengths
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    # Build Markdown table
    md_lines = []
    md_lines.append("| " + " | ".join(rows[0]) + " |")
    md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for row in rows[1:]:
        md_lines.append("| " + " | ".join(row) + " |")

    md_lines.append("")
    return md_lines
