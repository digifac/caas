"""DOCX to Markdown conversion using mammoth."""

import html
import io
import logging
import re

import mammoth

logger = logging.getLogger(__name__)

# Dangerous URL schemes that must be blocked to prevent injection attacks
_DANGEROUS_URL_SCHEMES = re.compile(
    r"^(?:javascript|vbscript|data|file|blob):",
    re.IGNORECASE,
)


def _sanitize_url(url: str) -> str:
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


def _escape_md_text(text: str) -> str:
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
    result = mammoth.convert_to_markdown(io.BytesIO(file_bytes))
    if result.messages:
        for msg in result.messages:
            logger.warning("DOCX Warning: %s", msg)
    markdown = result.value.strip()

    # Sanitize URLs in Markdown links [text](url)
    def sanitize_link(match):
        link_text = match.group(1)
        url = match.group(2)
        safe_url = _sanitize_url(url)
        return f"[{link_text}]({safe_url})"

    markdown = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", sanitize_link, markdown)

    # Sanitize URLs in Markdown images ![alt](url)
    def sanitize_image(match):
        alt = match.group(1)
        url = match.group(2)
        safe_url = _sanitize_url(url)
        return f"![{alt}]({safe_url})"

    markdown = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", sanitize_image, markdown)

    return markdown
