"""PDF to Markdown conversion with OCR fallback.

Provides both synchronous and async streaming conversion, sharing a common
extraction core to avoid code duplication.
"""

import asyncio
import io
import logging
import re
from collections.abc import AsyncGenerator

import pdfplumber

from app.config import settings
from app.converters.base import clean_lines
from app.ocr import ocr_pdf_pages

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
        logger.warning("Blocked dangerous URL scheme in PDF: %s", stripped[:50])
        return "#"
    return url


def _extract_pdf_content(file_bytes: bytes) -> list[tuple[int, str, list[str]]]:
    """Core PDF extraction: two passes with OCR fallback and link extraction.

    Returns a list of (page_idx, markdown_text, [urls]) for each page.
    Pages with empty markdown_text are still included.

    Args:
        file_bytes: Raw PDF bytes.

    Returns:
        List of tuples (page_idx, page_md, link_list).

    Raises:
        ValueError: If page count exceeds the configured limit.
    """
    ocr_page_indices = []
    text_cache = {}  # page_idx -> extracted text (single extraction per page)

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        # Enforce page limit (0 = unlimited)
        if settings.pdf_max_pages > 0 and len(pdf.pages) > settings.pdf_max_pages:
            raise ValueError(
                f"PDF has {len(pdf.pages)} pages, exceeding the limit of {settings.pdf_max_pages}."
            )

        # 1. First pass: extract text once, cache it, identify pages needing OCR
        for page_idx, page in enumerate(pdf.pages):
            extracted_text = page.extract_text() or ""
            text_cache[page_idx] = extracted_text
            if not extracted_text.strip():
                ocr_page_indices.append(page_idx)

        # 2. Batch OCR all scanned pages at once (pypdfium2 opened only once)
        ocr_results = {}
        if ocr_page_indices:
            ocr_results = ocr_pdf_pages(file_bytes, ocr_page_indices)

        # 3. Second pass: build results from cached text + OCR results
        results: list[tuple[int, str, list[str]]] = []
        for page_idx, page in enumerate(pdf.pages):
            page_text = ocr_results[page_idx] if page_idx in ocr_results else text_cache[page_idx]

            # Clean text
            page_md = ""
            if page_text:
                cleaned = clean_lines(page_text.split("\n"))
                page_md = "\n".join(cleaned)

            # Extract hyperlinks
            links: list[str] = []
            hyperlinks = getattr(page, "hyperlinks", [])
            if hyperlinks:
                seen_uris = set()
                for link in hyperlinks:
                    uri = link.get("uri")
                    if uri and uri not in seen_uris:
                        seen_uris.add(uri)
                        safe_uri = _sanitize_url(uri)
                        links.append(safe_uri)

            results.append((page_idx, page_md, links))

    return results


def convert_pdf_to_md(file_bytes: bytes) -> str:
    """Extract text in memory via pdfplumber, with OCR for scanned pages and link extraction.

    Single-pass design: text is extracted once per page and cached, so the PDF is never
    re-parsed by pdfplumber.  pypdfium2 is opened only for pages that need OCR.
    """
    md_blocks = []
    results = _extract_pdf_content(file_bytes)

    for _page_idx, page_md, links in results:
        if page_md:
            md_blocks.append(page_md)
        if links:
            link_lines = [f"\n[{uri}]({uri})" for uri in links]
            md_blocks.append("".join(link_lines))

    return "\n\n".join(md_blocks).replace("\n\n\n", "\n\n").strip()


async def convert_pdf_to_md_stream(
    file_bytes: bytes,
) -> AsyncGenerator[str, None]:
    """Stream PDF -> Markdown conversion, yielding accumulated markdown per page.

    Shares the same extraction core as convert_pdf_to_md() but yields chunks
    progressively so clients receive data via SSE without waiting for the full result.

    Args:
        file_bytes: Raw PDF bytes.

    Yields:
        Markdown chunks (plain strings, NOT SSE-formatted).

    Raises:
        ValueError: If page count exceeds the configured limit.
    """
    md_blocks = []
    results = _extract_pdf_content(file_bytes)

    for _page_idx, page_md, links in results:
        if page_md:
            md_blocks.append(page_md)
        if links:
            link_lines = [f"\n[{uri}]({uri})" for uri in links]
            md_blocks.append("".join(link_lines))

        # Yield accumulated markdown for this page
        chunk = "\n\n".join(md_blocks).replace("\n\n\n", "\n\n").strip()
        if chunk:
            yield chunk
            # Allow other tasks to run between pages
            await asyncio.sleep(0)
