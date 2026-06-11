"""Fixtures for expected outputs (JSON and JSONL) by input format."""

__all__ = [
    # PDF
    "expected_json_output_pdf",
    "expected_jsonl_output_pdf",
    # DOCX
    "expected_json_output_docx",
    "expected_jsonl_output_docx",
    # ODT
    "expected_json_output_odt",
    "expected_jsonl_output_odt",
    # XLSX
    "expected_json_output_xlsx",
    "expected_jsonl_output_xlsx",
    # PPTX
    "expected_json_output_pptx",
    "expected_jsonl_output_pptx",
    # HTML
    "expected_json_output_html",
    "expected_jsonl_output_html",
    # ODS
    "expected_json_output_ods",
    "expected_jsonl_output_ods",
    # ODP
    "expected_json_output_odp",
    "expected_jsonl_output_odp",
]

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# PDF - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_pdf() -> Dict[str, Any]:
    """Expected JSON output for PDF conversion (Hello World document)."""
    return {
        "format": "pdf",
        "pages": [
            {
                "page_idx": 0,
                "markdown_text": "# Hello World\n\nLigne deux",
                "links": []
            }
        ],
        "metadata": {"source_format": "pdf", "num_pages": 1},
        "success": True,
        "timestamp": None  # Will be set by actual conversion
    }


def expected_jsonl_output_pdf() -> List[str]:
    """Expected JSONL output for PDF conversion (one event per page)."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": "# Hello World\\n\\nLigne deux", "links": [], "offset": 0, "length": 28}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# DOCX - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_docx() -> Dict[str, Any]:
    """Expected JSON output for DOCX conversion."""
    return {
        "format": "docx",
        "pages": [
            {
                "page_idx": 0,
                "markdown_text": "# Bonjour le monde\n\n## Deuxième paragraphe",
                "links": []
            },
            {
                "page_idx": 1,
                "markdown_text": "# Deuxième paragraphe",
                "links": []
            }
        ],
        "metadata": {"source_format": "docx", "num_pages": 2},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_docx() -> List[str]:
    """Expected JSONL output for DOCX conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": "# Bonjour le monde\\n\\n## Deuxième paragraphe", "links": [], "offset": 0, "length": 42}',
        '{"type": "chunk", "page_idx": 1, "markdown_text": "# Deuxième paragraphe", "links": [], "offset": 42, "length": 23}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# ODT - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_odt() -> Dict[str, Any]:
    """Expected JSON output for ODT conversion."""
    return {
        "format": "odt",
        "pages": [
            {
                "page_idx": 0,
                "markdown_text": "# Titre du document\n\n## Premier paragraphe\n\n## Deuxième paragraphe",
                "links": []
            }
        ],
        "metadata": {"source_format": "odt", "num_pages": 1},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_odt() -> List[str]:
    """Expected JSONL output for ODT conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": "# Titre du document\\n\\n## Premier paragraphe\\n\\n## Deuxième paragraphe", "links": [], "offset": 0, "length": 72}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# XLSX - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_xlsx() -> Dict[str, Any]:
    """Expected JSON output for XLSX conversion."""
    return {
        "format": "xlsx",
        "sheets": [
            {
                "name": "Feuille1",
                "data": [
                    ["Nom", "Valeur"],
                    ["A", 1],
                    ["B", 2]
                ],
                "headers": ["Nom", "Valeur"]
            }
        ],
        "metadata": {"source_format": "xlsx", "num_sheets": 1},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_xlsx() -> List[str]:
    """Expected JSONL output for XLSX conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": [["Nom","Valeur"],["A",1.0],"[B",2.0]]", "links": [], "offset": 0, "length": 35}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# PPTX - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_pptx() -> Dict[str, Any]:
    """Expected JSON output for PPTX conversion."""
    return {
        "format": "pptx",
        "slides": [
            {
                "index": 0,
                "title": "Présentation de Test",
                "content": ["Sous-titre de la présentation"],
                "tables": []
            },
            {
                "index": 1,
                "title": "Deuxième Slide",
                "content": ["Premier point", "Deuxième point", "Sous-point"],
                "tables": []
            }
        ],
        "metadata": {"source_format": "pptx", "num_slides": 2},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_pptx() -> List[str]:
    """Expected JSONL output for PPTX conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": "Présentation de Test\\nSous-titre de la présentation", "links": [], "offset": 0, "length": 48}',
        '{"type": "chunk", "page_idx": 1, "markdown_text": "Deuxième Slide\\nPremier point\\nDeuxième point\\nSous-point", "links": [], "offset": 48, "length": 59}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# HTML - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_html() -> Dict[str, Any]:
    """Expected JSON output for HTML conversion."""
    return {
        "format": "html",
        "pages": [
            {
                "page_idx": 0,
                "markdown_text": "# Main Title\n\nThis is a **bold** and *italic* paragraph.\n\nVisit our website for more info.",
                "links": ["https://example.com"]
            }
        ],
        "metadata": {"source_format": "html", "num_pages": 1},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_html() -> List[str]:
    """Expected JSONL output for HTML conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": "# Main Title\\nThis is a **bold** and *italic* paragraph.\\nVisit our website for more info.", "links": ["https://example.com"], "offset": 0, "length": 95}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# ODS - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_ods() -> Dict[str, Any]:
    """Expected JSON output for ODS conversion."""
    return {
        "format": "ods",
        "sheets": [
            {
                "name": "Feuille1",
                "data": [
                    ["Nom", "Valeur"],
                    ["A", 1],
                    ["B", 2]
                ],
                "headers": ["Nom", "Valeur"]
            }
        ],
        "metadata": {"source_format": "ods", "num_sheets": 1},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_ods() -> List[str]:
    """Expected JSONL output for ODS conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": [["Nom","Valeur"],["A",1.0],"[B",2.0]]", "links": [], "offset": 0, "length": 35}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]


# ---------------------------------------------------------------------------
# ODP - Expected Outputs
# ---------------------------------------------------------------------------


def expected_json_output_odp() -> Dict[str, Any]:
    """Expected JSON output for ODP conversion."""
    return {
        "format": "odp",
        "slides": [
            {
                "index": 0,
                "title": "Présentation de Test",
                "content": ["Sous-titre de la présentation"],
                "lists": []
            },
            {
                "index": 1,
                "title": "Deuxième Slide",
                "content": ["Premier point", "Deuxième point", "Troisième point"],
                "lists": []
            }
        ],
        "metadata": {"source_format": "odp", "num_slides": 2},
        "success": True,
        "timestamp": None
    }


def expected_jsonl_output_odp() -> List[str]:
    """Expected JSONL output for ODP conversion."""
    return [
        '{"type": "start", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}',
        '{"type": "chunk", "page_idx": 0, "markdown_text": "Présentation de Test\\nSous-titre de la présentation", "links": [], "offset": 0, "length": 48}',
        '{"type": "chunk", "page_idx": 1, "markdown_text": "Deuxième Slide\\nPremier point\\nDeuxième point\\nTroisième point", "links": [], "offset": 48, "length": 62}',
        '{"type": "end", "page_idx": null, "markdown_text": "", "links": [], "offset": 0, "length": 0}'
    ]
