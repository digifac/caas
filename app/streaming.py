"""Streaming conversion: yields Markdown chunks via async generators.

Each converter streams content in chunks (per-page for PDF, per-block for others)
so the client receives data progressively instead of waiting for the full result.

Events are emitted as SSE (Server-Sent Events) compatible strings:
    data: <chunk>\n\n
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from app.config import settings
from app.converters.docx import convert_docx_to_md
from app.converters.html import convert_html_to_md
from app.converters.odp import convert_odp_to_md
from app.converters.ods import convert_ods_to_md
from app.converters.odt import convert_odt_to_md
from app.converters.pdf import convert_pdf_to_md_stream
from app.converters.pptx import convert_pptx_to_md
from app.converters.xlsx import convert_xlsx_to_md

logger = logging.getLogger(__name__)


def _sse_event(data: str) -> str:
    """Format a string as an SSE data event."""
    # Escape newlines for SSE data field
    escaped = data.replace("\n", "\\n").replace("\r", "")
    return f"data: {escaped}\n\n"


async def _convert_pdf_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream PDF → Markdown conversion, yielding one page per event.

    Delegates to the shared extraction core in converters/pdf.py and wraps
    each chunk as an SSE event.
    
    Args:
        file_bytes: Raw PDF content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    async for chunk in convert_pdf_to_md_stream(file_bytes):
        yield _sse_event(chunk)


async def _convert_docx_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream DOCX → Markdown conversion.

    Mammoth converts the entire document at once, so we split the result
    into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw DOCX content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_docx_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_docx_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_docx_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


async def _convert_odt_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream ODT → Markdown conversion.

    The ODT converter processes the entire document at once, so we split
    into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw ODT content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_odt_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_odt_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_odt_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


async def _convert_html_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream HTML → Markdown conversion.

    The HTML converter processes the entire document at once, so we split
    the result into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw HTML content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_html_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_html_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_html_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


async def _convert_xlsx_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream XLSX → Markdown conversion.

    The XLSX converter processes the entire document at once, so we split
    into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw XLSX content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_xlsx_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_xlsx_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_xlsx_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


async def _convert_pptx_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream PPTX → Markdown conversion.

    The PPTX converter processes the entire document at once, so we split
    into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw PPTX content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_pptx_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_pptx_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_pptx_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


async def convert_stream(file_bytes: bytes, ext: str, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream ODS → Markdown conversion.

    The ODS converter processes the entire spreadsheet at once, so we split
    into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw ODS content.
        ext: File extension (ods).
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_ods_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_ods_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_ods_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


async def _convert_odp_stream(file_bytes: bytes, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream ODP → Markdown conversion.

    The ODP converter processes the entire presentation at once, so we split
    into chunks of approximately `streaming_chunk_size` bytes.
    
    Args:
        file_bytes: Raw ODP content.
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".
    """
    if format == "json":
        result = await asyncio.to_thread(convert_odp_to_json, file_bytes)
        for i in range(0, len(result), settings.streaming_chunk_size):
            chunk = result[i : i + settings.streaming_chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)
    elif format == "jsonl":
        result = await asyncio.to_thread(convert_odp_to_jsonl, file_bytes)
        for line in result:
            yield _sse_event(line)
    else:
        markdown = await asyncio.to_thread(convert_odp_to_md, file_bytes)
        chunk_size = settings.streaming_chunk_size
        for i in range(0, len(markdown), chunk_size):
            chunk = markdown[i : i + chunk_size]
            yield _sse_event(chunk)
            await asyncio.sleep(0)


# Mapping of extensions to streaming converter functions
_STREAMING_CONVERTERS = {
    "pdf": _convert_pdf_stream,
    "docx": _convert_docx_stream,
    "odt": _convert_odt_stream,
    "ods": _convert_ods_stream,
    "html": _convert_html_stream,
    "xlsx": _convert_xlsx_stream,
    "pptx": _convert_pptx_stream,
    "odp": _convert_odp_stream,
}


async def convert_stream(file_bytes: bytes, ext: str, format: str = "markdown") -> AsyncGenerator[str, None]:
    """Stream a document conversion, yielding SSE-formatted chunks.

    Args:
        file_bytes: Raw file content.
        ext: File extension (pdf, docx, odt, html).
        format: Output format ("markdown", "json", or "jsonl"). Defaults to "markdown".

    Yields:
        SSE-formatted strings containing conversion chunks in the requested format.

    Raises:
        ValueError: If the format is unsupported.
    """
    converter = _STREAMING_CONVERTERS.get(ext)
    if not converter:
        raise ValueError(f"Unsupported format: {ext}")

    # Yield a start event with metadata
    start_event = json.dumps(
        {"format": ext, "output_format": format, "size_bytes": len(file_bytes), "status": "started"}
    )
    yield _sse_event(start_event)

    try:
        async for chunk in converter(
            file_bytes,
            format=format,
        ):
            yield chunk
    except Exception:
        logger.exception("Streaming conversion failed for format %s", ext)
        error_event = json.dumps(
            {"status": "error", "message": "Conversion failed during streaming."}
        )
        yield _sse_event(error_event)
        raise
    finally:
        # Yield a done event
        done_event = json.dumps({"status": "complete"})
        yield _sse_event(done_event)
