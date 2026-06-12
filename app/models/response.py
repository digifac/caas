"""Pydantic models for the conversion API's JSON/JSONL responses.

This module defines standardized data structures for all converters,
suring consistency across PDF, DOCX, XLSX and other formats.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class PageJson(BaseModel):
    """Represents a page or logical unit of the document.

    Used by PDF, DOCX, ODT, PPTX, HTML (textual content).
    For structured formats (XLSX/ODS), see SheetJson and CellJson.
    """

    model_config = ConfigDict(populate_by_name=True)

    page_idx: int | None = Field(None, description="Page/section index")
    markdown_text: str = Field(..., description="Raw content (Markdown or text)")
    links: list[str] = Field(default_factory=list, description="Extracted links")


class ConversionResponse(BaseModel):
    """Structured JSON response for the conversion API.

    Standardized format returned when `format=json` is specified in the request.
    Compatible with all converters (PDF, DOCX, XLSX, ODT, PPTX, HTML, ODP).
    """

    model_config = ConfigDict(populate_by_name=True)

    format: str = Field(..., description="Source document format (pdf, docx, xlsx, etc.)")
    pages: list[PageJson] = Field(default_factory=list, description="List of pages/sections with content")  # type: ignore[misc]
    raw_content: str | None = Field(None, alias="_content", description="Raw Markdown content (alternative to pages for simple formats)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Format-specific metadata")
    request_id: str | None = Field(None, description="Unique request ID for tracing")
    success: bool = Field(True, description="Success status")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp")


class SheetJson(BaseModel):
    """Represents a spreadsheet sheet (XLSX/ODS).

    Used for tabular formats with structured data.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Sheet name")
    data: list[list[Any]] = Field(default_factory=list, description="Raw data (list of lists)")  # type: ignore[misc]
    headers: list[str] | None = Field(None, description="Column headers if available")


class CellJson(BaseModel):
    """Represents an individual cell (XLSX/ODS).

    Used for tabular formats with cellular granularity.
    """

    model_config = ConfigDict(populate_by_name=True)

    row: int = Field(..., description="Row number")
    col: int = Field(..., description="Column number")
    value: Any = Field(None, description="Cell value (str, float, None)")


class SlideJson(BaseModel):
    """Represents a slide (PPTX/ODP).

    Used for presentations with textual content and tables.
    """

    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(..., description="Slide index")
    title: str | None = Field(None, description="Slide title")
    content: list[str] = Field(default_factory=list, description="List of paragraphs/text")
    tables: list[list[list[Any]]] = Field(default_factory=list, description="Extracted tables")  # type: ignore[misc]


class HtmlElementJson(BaseModel):
    """Represents an extracted HTML element.

    Used for the HTML converter with element structure.
    """

    model_config = ConfigDict(populate_by_name=True)

    tag: str = Field(..., description="Tag name (div, p, h1, etc.)")
    content: str = Field(..., description="Textual content of the element")


class OdtElementJson(BaseModel):
    """Represents an ODT element (paragraph, heading, list).

    Used for the ODT converter with element structure.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(..., description="Element type (paragraph, heading, list)")
    content: str = Field(..., description="Textual content")
    level: int = Field(0, description="Hierarchy level for headings/lists")


class OdpSlideJson(BaseModel):
    """Represents an ODP slide (OpenDocument Presentation).

    Used for the ODP converter with frames and lists.
    """

    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(..., description="Slide index")
    title: str | None = Field(None, description="Slide title")
    content: list[str] = Field(default_factory=list, description="Textual content of frames")
    lists: list[str] = Field(default_factory=list, description="Bulleted/numbered lists")  # type: ignore[misc]


# Standardized JSONL events (consistent across all converters)
class JsonlEvent(BaseModel):
    """JSONL event for granular streaming.

    Used when `format=jsonl` is specified in the request.
    Each event corresponds to a logical unit or content chunk.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(..., pattern="^(start|chunk|end)$", description="Event type")
    page_idx: int | None = Field(None, description="Page/section/slide index")
    markdown_text: str = Field("", description="Chunk content or raw data")
    links: list[str] = Field(default_factory=list, description="Extracted links")
    offset: int = Field(0, description="Offset in document (for chunking)")
    length: int = Field(0, description="Chunk length")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Specific metadata")


class BatchConversionResponse(BaseModel):
    """Structured JSON response for batch conversions.

    Standardized format returned when `format=json` is specified on the /convert/batch endpoint.
    Contains batch metadata and results of each converted file.
    
    Used by: app/routes/batch.py
    """

    model_config = ConfigDict(populate_by_name=True)

    batch_id: str | None = Field(None, description="Unique batch ID")
    total_files: int = Field(0, description="Total files submitted")
    succeeded: int = Field(0, description="Successful conversions count")
    failed: int = Field(0, description="Failed conversions count")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Results per file")  # type: ignore[misc]

    attributes: dict[str, Any] = Field(default_factory=dict, description="Extracted HTML attributes")
    children: list[dict[str, Any]] = Field(default_factory=list, description="Recursive children (if applicable)")  # type: ignore[misc]
