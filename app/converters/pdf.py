"""PDF to Markdown conversion with OCR fallback.

Provides both synchronous and async streaming conversion, sharing a common
extraction core to avoid code duplication.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import pdfplumber

from app.config import settings
from app.converters.base import clean_lines
from app.models.response import JsonlEvent, PageJson
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
        ocr_results: dict[int, str] = {}
        if ocr_page_indices:
            ocr_results = ocr_pdf_pages(file_bytes, ocr_page_indices)

        # 3. Second pass: build results from cached text + OCR results
        results: list[tuple[int, str, list[str]]] = []
        for page_idx, page in enumerate(pdf.pages):
            page_text = ocr_results[page_idx] if page_idx in ocr_results else text_cache[page_idx]

            # Clean text
            page_md = ""
            if page_text:
                cleaned_lines = clean_lines(page_text.split("\n"))
                page_md = "\n".join(cleaned_lines)

            # Extract hyperlinks
            links: list[str] = []
            hyperlinks = getattr(page, "hyperlinks", [])
            if hyperlinks:
                seen_uris: set[str] = set()
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
    md_blocks: list[str] = []
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
    md_blocks: list[str] = []
    results = _extract_pdf_content(file_bytes)

    for _page_idx, page_md, links in results:
        if page_md:
            md_blocks.append(page_md)
        if links:
            link_lines = [f"\n[{uri}]({uri})" for uri in links]
            md_blocks.append("".join(link_lines))

        # Yield accumulated markdown for this page
        chunk: str = "\n\n".join(md_blocks).replace("\n\n\n", "\n\n").strip()
        if chunk:
            yield chunk
            # Allow other tasks to run between pages
            await asyncio.sleep(0)


def _to_json(results: list[tuple[int, str, list[str]]]) -> dict[str, Any]:
    """Convert PDF results to structured JSON format.

    Args:
        results: List of tuples (page_idx, page_md, [urls]) returned by _extract_pdf_content().

    Returns:
        JSON Dict with pages and metadata.
    """
    pages = [PageJson(page_idx=p[0], markdown_text=p[1], links=p[2]) for p in results]

    return {
        "format": "pdf",
        "pages": pages,
        "metadata": {"total_pages": len(pages)},
    }


def _to_jsonl(results: list[tuple[int, str, list[str]]]) -> str:
    """Convert PDF results to JSONL format with textual chunking.

    Each page is chunked into blocks of CAAS_JSONL_CHUNK_SIZE characters (default: 1024).
    Returns a string with one JSON line per event (start, chunk×N, end).

    Args:
        results: List of tuples (page_idx, page_md, [urls]) returned by _extract_pdf_content().

    Returns:
        JSONL string ready to be streamed.
    """
    chunks: list[Any] = []

    for page_idx, page_md, _links in results:
        # Événement start pour la page
        chunks.append(JsonlEvent(
            type="start",
            page_idx=page_idx,
            markdown_text="",
            offset=0,
            length=0
        ))

        # Chunker le contenu textuel (Markdown) par blocs de CAAS_JSONL_CHUNK_SIZE
        content = page_md  # Markdown text
        chunk_size = settings.jsonl_chunk_size or 1024

        for i in range(0, len(content), chunk_size):
            chunk_content = content[i:i+chunk_size]
            chunks.append(JsonlEvent(
                type="chunk",
                page_idx=None,
                markdown_text=chunk_content,
                offset=i,
                length=len(chunk_content)
            ))

        # Événement end pour la page
        chunks.append(JsonlEvent(
            type="end",
            page_idx=None,
            markdown_text="",
            offset=0,
            length=0
        ))

    import json

    return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)


def convert_pdf_to_json(file_bytes: bytes) -> dict[str, Any]:
    """Extract text in memory via pdfplumber, with OCR for scanned pages and link extraction.

    Single-pass design: text is extracted once per page and cached, so the PDF is never
    re-parsed by pdfplumber.  pypdfium2 is opened only for pages that need OCR.
    
    Returns:
        Structured JSON dict with pages and metadata, ready for serialization.
    """
    results = _extract_pdf_content(file_bytes)
    json_result = _to_json(results)
    # Convert PageJson objects to dicts for JSON serialization (by_alias for 'index')
    return {
        "format": json_result["format"],
        "pages": [page.model_dump(by_alias=True) for page in json_result["pages"]],
        "metadata": json_result["metadata"],
    }


def convert_pdf_to_jsonl(file_bytes: bytes) -> list[JsonlEvent]:
    """Extract text in memory via pdfplumber, with OCR for scanned pages and link extraction.

    Single-pass design: text is extracted once per page and cached, so the PDF is never
    re-parsed by pdfplumber.  pypdfium2 is opened only for pages that need OCR.
    
    Returns:
        List of JsonlEvent objects with start, chunk(s), and end events per page.
    """
    from app.config import settings
    
    results = _extract_pdf_content(file_bytes)
    jsonl_results: list[JsonlEvent] = []
    
    for page_idx, page_md, links in results:
        # Start event for the page
        jsonl_results.append(JsonlEvent(
            type="start",
            page_idx=page_idx,
            markdown_text="",
            links=[],
            offset=0,
            length=0
        ))
        
        # Chunk events (split by chunk_size)
        chunk_size = settings.jsonl_chunk_size or 1024
        for i in range(0, max(len(page_md), 1), chunk_size):
            chunk_content = page_md[i:i + chunk_size]
            jsonl_results.append(JsonlEvent(
                type="chunk",
                page_idx=None,
                markdown_text=chunk_content,
                links=links if i == 0 else [],
                offset=i,
                length=len(chunk_content)
            ))
        
        # End event for the page
        jsonl_results.append(JsonlEvent(
            type="end",
            page_idx=None,
            markdown_text="",
            links=[],
            offset=0,
            length=0
        ))
    
    return jsonl_results
