"""Fixtures for PDF tests."""

__all__ = [
    "sample_pdf_bytes",
    "sample_pdf_with_link_bytes",
]

import io
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Generate a minimal PDF with text in memory without using disk."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, "Hello World")
    c.drawString(72, 730, "Ligne deux")
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_pdf_with_link_bytes() -> bytes:
    """Generate a PDF containing a hyperlink in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, "Visitez notre site")
    # Add an URI link with reportlab
    c.linkURL("https://example.com", (72, 740, 200, 760), thickness=0)  # type: ignore[attr-defined]
    c.save()
    buf.seek(0)
    return buf.getvalue()
