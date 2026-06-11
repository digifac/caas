"""ODP to Markdown conversion using odfpy."""

import html
import io
import logging

from odf import opendocument  # type: ignore[import-untyped]
from odf.namespaces import DRAWNS, STYLENS  # type: ignore[import-untyped]

from app.converters.base import clean_lines
from app.models.response import SlideJson

logger = logging.getLogger(__name__)


def _get_attr_ns(element, namespace_local: str, attr_name: str) -> str | None:
    """Get an attribute value using namespace and local name.

    Args:
        element: An ODF element.
        namespace_local: Namespace URI (e.g., STYNS, DRAWNS).
        attr_name: Local attribute name.

    Returns:
        The attribute value or None if not found.
    """
    if hasattr(element, "getAttrNS"):
        return element.getAttrNS(namespace_local, attr_name)  # type: ignore[no-any-return]
    return None


def _escape_md_text(text: str) -> str:
    """Escape HTML entities in text to prevent XSS via raw HTML in Markdown.

    Args:
        text: Raw text extracted from an ODP element.

    Returns:
        Text with HTML-special characters escaped.
    """
    return html.escape(text, quote=False)


def _get_local_name(element) -> str | None:
    """Get the local name of an ODF element.

    Args:
        element: An ODF element.

    Returns:
        The local name (without namespace) or None if not available.
    """
    if hasattr(element, "qname") and element.qname:
        return element.qname[1]  # type: ignore[no-any-return]
    return None


def _extract_text_frame(element) -> str:
    """Extract text content from a draw:text-frame element.

    Recursively walks child nodes to collect all text paragraphs.

    Args:
        element: An ODF element that may contain text paragraphs.

    Returns:
        Concatenated text from all child paragraphs.
    """
    parts: list[str] = []
    if hasattr(element, "childNodes"):
        for child in element.childNodes:
            local_name = _get_local_name(child)
            if local_name == "p":
                # text:p — paragraph inside a text frame
                paragraph_text = _get_paragraph_text(child)
                if paragraph_text:
                    parts.append(paragraph_text)
            elif local_name == "span":
                if hasattr(child, "_getText"):
                    parts.append(child._getText())
                else:
                    parts.append(_extract_text_frame(child))
            elif local_name is not None:
                parts.append(_extract_text_frame(child))
            elif hasattr(child, "data") and child.data:
                parts.append(child.data)
    return "".join(parts)


def _get_text_recursive(element) -> str:
    """Recursively extract all text content from an ODF element and its children.

    Args:
        element: An ODF element.

    Returns:
        Concatenated text from all text nodes in the subtree.
    """
    parts: list[str] = []
    if hasattr(element, "data") and element.data:
        parts.append(element.data)
    elif hasattr(element, "childNodes"):
        for child in element.childNodes:
            parts.append(_get_text_recursive(child))
    return "".join(parts)


def _get_paragraph_text(paragraph) -> str:
    """Extract text content from a text:p element.

    Args:
        paragraph: A text:p ODF element.

    Returns:
        The text content of the paragraph.
    """
    parts: list[str] = []
    if hasattr(paragraph, "childNodes"):
        for element in paragraph.childNodes:
            if hasattr(element, "data"):
                text_val = element.data or ""
                if text_val:
                    parts.append(text_val)
            else:
                local_name = _get_local_name(element)
                if local_name == "tab":
                    parts.append("\t")
                elif local_name == "br":
                    parts.append("\n")
                elif local_name == "span":
                    if hasattr(element, "_getText"):
                        parts.append(element._getText())
                    else:
                        # Recursively extract text from span children
                        parts.append(_get_text_recursive(element))
    return "".join(parts)


def _collect_frames(element) -> list:
    """Recursively collect all draw:frame elements from an element and its children.

    Handles both direct frames and frames nested inside draw:g (group) elements,
    which is common in LibreOffice-generated ODP files.

    Args:
        element: An ODF element (typically a draw:page or draw:g).

    Returns:
        A list of draw:frame elements found in the subtree.
    """
    frames: list = []
    if not hasattr(element, "childNodes"):
        return frames

    for child in element.childNodes:
        local_name = _get_local_name(child)
        if local_name == "frame":
            frames.append(child)
        elif local_name == "g":
            # Recurse into groups (draw:g) to find nested frames
            frames.extend(_collect_frames(child))
    return frames


def _extract_slide_text(page, slide_number: int) -> list[str]:
    """Extract text content from a single ODP slide (draw:page).

    Walks all draw:frame elements looking for text frames and shapes.
    Handles frames both directly on the page and nested inside draw:g groups.

    Args:
        page: A draw:page ODF element representing one slide.
        slide_number: The 1-based slide number.

    Returns:
        A list of Markdown lines representing the slide content.
    """
    lines: list[str] = []
    title_found = False

    # Collect all frames, including those nested in draw:g groups
    frames = _collect_frames(page)

    for frame in frames:
        # Check for title shape via style name or frame name
        style_name = (_get_attr_ns(frame, STYLENS, "name") or "").lower()
        page_master = (_get_attr_ns(frame, DRAWNS, "style-name") or "").lower()
        frame_name = (_get_attr_ns(frame, DRAWNS, "name") or "").lower()

        is_title = "title" in style_name or "title" in page_master or "title" in frame_name

        # Get text content from the frame
        frame_text = ""
        if hasattr(frame, "childNodes"):
            for child in frame.childNodes:
                child_name = _get_local_name(child)
                if child_name in ("text-frame", "text-box"):
                    frame_text = _extract_text_frame(child)
                elif child_name == "table":
                    # ODP tables — extract cell text
                    frame_text = _extract_odp_table(child)
                elif child_name == "custom-shape":
                    frame_text = _extract_text_frame(child)

        frame_text = frame_text.strip()
        if not frame_text:
            continue

        if is_title and not title_found:
            lines.append(f"## {_escape_md_text(frame_text)}")
            title_found = True
        else:
            # Process paragraphs within the text frame
            paragraphs = frame_text.split("\n")
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                lines.append(_escape_md_text(para))

    # If no title was found, add a generic slide header
    if not title_found:
        lines.insert(0, f"## Slide {slide_number}")

    return lines


def _extract_odp_table(table_element) -> str:
    """Extract text from an ODP table and convert to Markdown table.

    Args:
        table_element: A draw:table ODF element.

    Returns:
        A Markdown string representing the table.
    """
    rows: list[list[str]] = []

    if hasattr(table_element, "childNodes"):
        for row_elem in table_element.childNodes:
            row_name = _get_local_name(row_elem)
            if row_name != "table-row":
                continue

            row_values: list[str] = []
            if hasattr(row_elem, "childNodes"):
                for cell_elem in row_elem.childNodes:
                    cell_name = _get_local_name(cell_elem)
                    if cell_name != "table-cell":
                        continue
                    cell_text = _extract_text_frame(cell_elem).strip().replace("|", "\\|")
                    row_values.append(cell_text)
            if row_values:
                rows.append(row_values)

    if not rows:
        return ""

    md_lines = []
    # Header row
    header = "| " + " | ".join(rows[0]) + " |"
    md_lines.append(header)

    # Separator row
    separator = "| " + " | ".join("---" for _ in rows[0]) + " |"
    md_lines.append(separator)

    # Data rows
    for row in rows[1:]:
        line = "| " + " | ".join(row) + " |"
        md_lines.append(line)

    return "\n".join(md_lines)


def convert_odp_to_md(file_bytes: bytes) -> str:
    """Pure Python ODP → MD conversion (odfpy).

    Converts all slides to Markdown, handling:
    - Slide titles
    - Text frames with paragraphs
    - Bullet points
    - Tables within slides
    - Empty slides

    Args:
        file_bytes: The raw bytes of the ODP file.

    Returns:
        A Markdown string representing the entire presentation.

    Raises:
        Exception: If the file is not a valid ODP.
    """
    try:
        doc = opendocument.load(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error("Invalid ODP file: %s", e)
        raise

    all_lines: list[str] = []
    slide_count = 0
    slides: list = []

    # Collect all draw:page elements (slides) from the presentation body
    if hasattr(doc, "body"):
        for child in doc.body.childNodes:
            if _get_local_name(child) == "presentation":
                for page in child.childNodes:
                    if _get_local_name(page) == "page":
                        slides.append(page)

    slide_count = len(slides)
    logger.debug("ODP properties: slides=%d", slide_count)

    for idx, page in enumerate(slides, start=1):
        try:
            slide_lines = _extract_slide_text(page, idx)
            all_lines.extend(slide_lines)

            # Add separator between slides (but not after the last one)
            if idx < slide_count:
                all_lines.append("")
                all_lines.append("---")
                all_lines.append("")
        except Exception as e:
            logger.warning("Error converting slide %d: %s", idx, e)
            all_lines.append(f"## Slide {idx}")
            all_lines.append(f"_(error converting slide: {e})_")

            if idx < slide_count:
                all_lines.append("")
                all_lines.append("---")
                all_lines.append("")

    # Log warnings for unsupported elements
    for idx, page in enumerate(slides, start=1):
        if hasattr(page, "childNodes"):
            for frame in page.childNodes:
                if hasattr(frame, "localName"):
                    if frame.localName == "image":
                        logger.warning(
                            "Slide %d contains an image which is not supported in Markdown conversion",
                            idx,
                        )
                    elif frame.localName == "graphic-frame":
                        logger.warning(
                            "Slide %d contains a graphic which is not supported in Markdown conversion",
                            idx,
                        )

    # Post-process with clean_lines from base module
    result_lines = clean_lines(all_lines)

    return "\n".join(result_lines)


def _extract_odp_content(file_bytes: bytes) -> list[tuple[int, str, list[str]]]:
    """Extract ODP content as slides.

    Args:
        file_bytes: Raw ODP file bytes.

    Returns:
        List of tuples (slide_num, title, text_lines).
    """
    try:
        doc = opendocument.load(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error("Invalid ODP file: %s", e)
        raise

    slides: list = []

    if hasattr(doc, "body"):
        for child in doc.body.childNodes:
            if _get_local_name(child) == "presentation":
                for page in child.childNodes:
                    if _get_local_name(page) == "page":
                        slides.append(page)

    results = []
    
    for idx, page in enumerate(slides, start=1):
        try:
            lines = _extract_slide_text(page, idx)
            
            # Get title or default to slide number
            frames = _collect_frames(page)
            has_title = False
            
            for frame in frames:
                style_name = (_get_attr_ns(frame, STYLENS, "name") or "").lower()
                page_master = (_get_attr_ns(frame, DRAWNS, "style-name") or "").lower()
                frame_name = (_get_attr_ns(frame, DRAWNS, "name") or "").lower()
                
                is_title = "title" in style_name or "title" in page_master or "title" in frame_name
                
                if is_title:
                    has_title = True
                    break
            
            title = f"Slide {idx}" if not has_title else ""
            
            results.append((idx, title, lines))
        except Exception as e:
            logger.warning("Error extracting slide %d: %s", idx, e)
            results.append((idx, f"Slide {idx}", [f"_(error converting slide: {e})_"]))

    return results


def convert_odp_to_json(file_bytes: bytes) -> dict:
    """Convert ODP to JSON format.

    Args:
        file_bytes: Raw ODP file bytes.

    Returns:
        Dict with slides and metadata in JSON structure.
    """
    results = _extract_odp_content(file_bytes)
    
    return {
        "format": "odp",
        "slides": [
            SlideJson(
                slide_num=slide[0],
                title=slide[1],
                text=[line for line in slide[2] if line.strip()]
            ).model_dump()
            for slide in results
        ],
        "metadata": {
            "format": "odp",
            "size_bytes": len(file_bytes),
            "slide_count": len(results),
        },
    }


def convert_odp_to_jsonl(file_bytes: bytes) -> str:
    """Convert ODP to JSONL format with chunking.

    Args:
        file_bytes: Raw ODP file bytes.

    Returns:
        JSONL string with start, chunk, and end events.
    """
    results = _extract_odp_content(file_bytes)
    
    return _to_jsonl(results)


def _to_jsonl(results: list[tuple[int, str, list[str]]]) -> str:
    """Convert extraction results to JSONL format with chunking.

    Args:
        results: List of (slide_num, title, text_lines) tuples.

    Returns:
        JSONL string with start, chunk, and end events.
    """
    import json
    
    lines = []
    
    # Start event
    lines.append(json.dumps({
        "type": "start",
        "format": "odp",
    }))
    
    # Convert to text representation for chunking
    all_text = []
    for slide_num, title, slide_lines in results:
        all_text.append(f"Slide {slide_num}: {title}")
        all_text.extend(slide_lines)
    
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
        "format": "odp",
        "total_slides": len(results),
    }))
    
    return "\n".join(lines)
