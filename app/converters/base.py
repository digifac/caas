"""Common utilities shared by all converters."""

import json
import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def clean_lines(lines: list[str]) -> list[str]:
    """Clean lines and detect basic Markdown structure.

    Heading detection is controlled by settings.markdown_heading_detection.
    When enabled, only short ALL-CAPS lines without punctuation are treated
    as headings, reducing false positives on normal uppercase paragraphs.
    """
    cleaned: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Headings (numbered or already Markdown)
        if re.match(r"^#{1,6}\s", line):
            # Already a Markdown heading — keep as-is
            cleaned.append(line)
        elif (
            re.match(r"^\d+[.)]\s", line)
            or settings.markdown_heading_detection
            and is_uppercase_heading(line)
        ):
            cleaned.append(f"# {line}")
        # Lists
        elif re.match(r"^[\*\-•]\s", line):
            cleaned.append(line)
        else:
            cleaned.append(line)
    return cleaned


# Common acronyms that should not be treated as headings
_KNOWN_ACRONYMS = frozenset(
    {
        "API",
        "URL",
        "HTTP",
        "HTTPS",
        "FTP",
        "SSH",
        "TCP",
        "UDP",
        "IP",
        "DNS",
        "HTML",
        "CSS",
        "JS",
        "JSON",
        "XML",
        "YAML",
        "SQL",
        "DB",
        "CPU",
        "GPU",
        "RAM",
        "ROM",
        "SSD",
        "HDD",
        "ID",
        "UUID",
        "URI",
        "URN",
        "EOF",
        "FAQ",
        "GUI",
        "CLI",
        "UI",
        "UX",
        "IO",
        "OS",
        "PC",
        "MAC",
    }
)


def is_uppercase_heading(line: str) -> bool:
    """Return True if the line looks like an ALL-CAPS heading.

    Criteria:
    - 3–40 characters long (reduced false positives on short acronyms)
    - contains only uppercase letters, digits, whitespace, and hyphens
    - is actually uppercase (line == line.upper())
    - contains no punctuation (excludes sentences/paragraphs)
    - is not a known acronym (e.g., API, URL, HTTP)
    - is not a Markdown separator (--- or similar)
    """
    if len(line) < 3 or len(line) > 40:
        return False
    # Exclude Markdown horizontal rules (lines that are only hyphens/underscores/spaces)
    if re.match(r"^[\-\_ ]+$", line):
        return False
    if line != line.upper():
        return False
    if not re.match(r"^[A-Z0-9\s\-]+$", line):
        return False
    # Exclude lines that are a single known acronym
    return line not in _KNOWN_ACRONYMS


def _to_json_format(data: dict[str, Any]) -> str:
    """Convert unstructured data to JSON format.

    Args:
        data: Dictionary containing the conversion result with keys like 'format',
              'pages' or 'content', and 'metadata'.

    Returns:
        JSON string representation of the data, properly encoded with UTF-8.
    """
    return json.dumps(data, ensure_ascii=False, indent=2)


def _to_jsonl_format(pages: list[dict[str, Any]]) -> str:
    """Convert a list of pages/sections to JSONL format (one JSON object per line).

    Args:
        pages: List of dictionaries representing pages or sections. Each dict should
               contain keys like 'index', 'content', and optionally 'urls'.

    Returns:
        JSONL string with one JSON object per line, suitable for streaming.
    """
    return "\n".join(json.dumps(page, ensure_ascii=False) for page in pages)
