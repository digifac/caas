"""Common utilities shared by all converters."""

import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


def clean_lines(lines: list[str]) -> list[str]:
    """Clean lines and detect basic Markdown structure.

    Heading detection is controlled by settings.markdown_heading_detection.
    When enabled, only short ALL-CAPS lines without punctuation are treated
    as headings, reducing false positives on normal uppercase paragraphs.
    """
    cleaned = []
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
    """
    if len(line) < 3 or len(line) > 40:
        return False
    if line != line.upper():
        return False
    if not re.match(r"^[A-Z0-9\s\-]+$", line):
        return False
    # Exclude lines that are a single known acronym
    return line not in _KNOWN_ACRONYMS
