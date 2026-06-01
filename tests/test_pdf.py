"""Tests for PDF to Markdown conversion."""

import asyncio
import io
import re
from urllib.parse import urlparse

import httpx
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@pytest.fixture
def multi_page_pdf_bytes(num_pages: int = 10) -> bytes:
    """Generate a PDF with multiple pages in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(num_pages):
        if i > 0:
            c.showPage()
        c.drawString(72, 750, f"Page {i + 1}")
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.mark.anyio
async def test_convert_pdf_success(
    async_client: httpx.AsyncClient, sample_pdf_bytes: bytes
):
    """POST /convert with a valid PDF returns markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.pdf", sample_pdf_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "markdown" in data
    assert data["format"] == "pdf"
    assert data["size_bytes"] == len(sample_pdf_bytes)
    assert "Hello World" in data["markdown"]


@pytest.mark.anyio
async def test_convert_pdf_uppercase_extension(
    async_client: httpx.AsyncClient, sample_pdf_bytes: bytes
):
    """POST /convert with .PDF extension (uppercase) works."""
    response = await async_client.post(
        "/convert", files={"file": ("test.PDF", sample_pdf_bytes)}
    )
    assert response.status_code == 200
    assert response.json()["format"] == "pdf"


@pytest.mark.anyio
async def test_convert_pdf_with_link(
    async_client: httpx.AsyncClient, sample_pdf_with_link_bytes: bytes
):
    """POST /convert extracts links from the PDF."""
    response = await async_client.post(
        "/convert", files={"file": ("linked.pdf", sample_pdf_with_link_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    # Extract URLs from markdown links and parse hostnames for strict host validation
    urls = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", markdown)
    parsed_hosts = {
        parsed.hostname
        for _, url in urls
        for parsed in [urlparse(url)]
        if parsed.hostname
    }
    assert any(host == "example.com" for host in parsed_hosts)


@pytest.mark.anyio
async def test_convert_scanned_pdf_ocr(
    async_client: httpx.AsyncClient, sample_scanned_pdf_bytes: bytes
):
    """POST /convert with a scanned PDF (no text) triggers OCR."""
    response = await async_client.post(
        "/convert", files={"file": ("scanned.pdf", sample_scanned_pdf_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["format"] == "pdf"
    assert "markdown" in data
    # Verify that OCR correctly extracted the French text from the scanned document.
    # Tesseract's French model (fra.traineddata) may or may not preserve diacritics
    # depending on the version installed, so we check for the word stems.
    markdown = data["markdown"]
    assert "Document" in markdown, (
        f"Word 'Document' was not detected by OCR. Markdown obtained: {markdown}"
    )
    assert "scanne" in markdown.lower(), (
        f"Word 'scanne' (scanné) was not detected by OCR. Markdown obtained: {markdown}"
    )
    assert "francais" in markdown.lower(), (
        f"Word 'francais' (français) was not detected by OCR. Markdown obtained: {markdown}"
    )


@pytest.mark.anyio
async def test_convert_async_pdf_completes(
    async_client: httpx.AsyncClient, sample_pdf_bytes: bytes
):
    """An async PDF task reaches completed status with the correct result."""
    # Submit the task
    response = await async_client.post(
        "/convert?async=true", files={"file": ("test.pdf", sample_pdf_bytes)}
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    # Poll until the task is complete (max 10s)
    status_data = {}
    for _ in range(40):
        await asyncio.sleep(0.25)
        status_res = await async_client.get(f"/task/{task_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        if status_data["status"] in ("completed", "failed"):
            break

    assert status_data["status"] == "completed", (
        f"Expected status 'completed', got '{status_data['status']}'"
    )
    assert "result" in status_data
    assert status_data["result"]["success"] is True
    assert "markdown" in status_data["result"]
    assert "Hello World" in status_data["result"]["markdown"]


@pytest.mark.anyio
async def test_convert_pdf_max_pages_exceeded(
    async_client: httpx.AsyncClient, monkeypatch
):
    """POST /convert with a PDF exceeding max pages returns 400."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    # Generate a PDF with more pages than the limit
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(600):  # Default limit is 500
        if i > 0:
            c.showPage()
        c.drawString(72, 750, f"Page {i + 1}")
    c.save()
    buf.seek(0)
    pdf_bytes = buf.getvalue()

    response = await async_client.post(
        "/convert", files={"file": ("large.pdf", pdf_bytes)}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "PDF_TOO_MANY_PAGES"


@pytest.mark.anyio
async def test_convert_pdf_max_pages_disabled(
    async_client: httpx.AsyncClient, monkeypatch
):
    """POST /convert with pdf_max_pages=0 allows unlimited pages."""
    from app.config import settings
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    # Disable page limit
    monkeypatch.setattr(settings, "pdf_max_pages", 0)

    # Generate a PDF with more pages than the default limit
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(600):
        if i > 0:
            c.showPage()
        c.drawString(72, 750, f"Page {i + 1}")
    c.save()
    buf.seek(0)
    pdf_bytes = buf.getvalue()

    response = await async_client.post(
        "/convert", files={"file": ("large.pdf", pdf_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.anyio
async def test_convert_pdf_within_pages_limit(async_client: httpx.AsyncClient):
    """POST /convert with a PDF within the pages limit succeeds."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    # Generate a PDF within the default limit (500 pages)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(10):
        if i > 0:
            c.showPage()
        c.drawString(72, 750, f"Page {i + 1}")
    c.save()
    buf.seek(0)
    pdf_bytes = buf.getvalue()

    response = await async_client.post(
        "/convert", files={"file": ("test.pdf", pdf_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Page 1" in data["markdown"]
    assert "Page 10" in data["markdown"]
