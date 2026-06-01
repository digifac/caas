"""Performance benchmarks for conversion operations.

Uses pytest-benchmark to measure conversion speed across all supported formats.
Run with: pytest tests/test_benchmarks.py -v --benchmark-only
"""

import io
import zipfile

import pytest
from app.converters.docx import convert_docx_to_md
from app.converters.html import convert_html_to_md
from app.converters.pdf import convert_pdf_to_md
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Fixtures – generate test documents of various sizes
# ---------------------------------------------------------------------------


@pytest.fixture
def small_pdf_bytes() -> bytes:
    """Minimal single-page PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, "Hello World")
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def medium_pdf_bytes() -> bytes:
    """PDF with 10 pages of text."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(10):
        if i > 0:
            c.showPage()
        y = 750
        for line in range(20):
            c.drawString(
                72, y, f"Page {i + 1} – Line {line + 1}: Lorem ipsum dolor sit amet"
            )
            y -= 18
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def large_pdf_bytes() -> bytes:
    """PDF with 50 pages of text."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(50):
        if i > 0:
            c.showPage()
        y = 750
        for line in range(50):
            c.drawString(
                72,
                y,
                f"Page {i + 1} – Line {line + 1}: Lorem ipsum dolor sit amet consectetur adipiscing elit",
            )
            y -= 18
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def small_docx_bytes() -> bytes:
    """Minimal DOCX with a few paragraphs."""
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    relationships = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    document_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Bonjour le monde</w:t></w:r></w:p><w:p><w:r><w:t>Deuxième paragraphe</w:t></w:r></w:p></w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", relationships)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


@pytest.fixture
def medium_docx_bytes() -> bytes:
    """DOCX with ~100 paragraphs."""
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    relationships = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    paragraphs = "".join(
        f"<w:p><w:r><w:t>Paragraph {i} of the document with some content.</w:t></w:r></w:p>"
        for i in range(100)
    )
    document_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", relationships)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


@pytest.fixture
def small_html_bytes() -> bytes:
    """Minimal HTML document."""
    return b"""<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <h1>Title</h1>
    <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
    <ul><li>Item 1</li><li>Item 2</li></ul>
</body>
</html>"""


@pytest.fixture
def medium_html_bytes() -> bytes:
    """HTML document with many elements."""
    paragraphs = "\n".join(
        f'<p>Paragraph {i} with some <a href="https://example.com/{i}">links</a> and <strong>formatting</strong>.</p>'
        for i in range(50)
    )
    html = f"""<!DOCTYPE html>
<html>
<head><title>Medium Test</title></head>
<body>
    <h1>Main Title</h1>
    {paragraphs}
    <table>
        <tr><th>Col A</th><th>Col B</th></tr>
        {"".join(f"<tr><td>Row {i} A</td><td>Row {i} B</td></tr>" for i in range(20))}
    </table>
</body>
</html>"""
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# Benchmarks – PDF conversion
# ---------------------------------------------------------------------------


class TestPdfConversionBenchmark:
    """Benchmark PDF → Markdown conversion speeds."""

    def test_bench_pdf_small(self, benchmark, small_pdf_bytes):
        """Benchmark single-page PDF conversion."""
        result = benchmark(convert_pdf_to_md, small_pdf_bytes)
        assert "Hello World" in result

    def test_bench_pdf_medium(self, benchmark, medium_pdf_bytes):
        """Benchmark 10-page PDF conversion."""
        result = benchmark(convert_pdf_to_md, medium_pdf_bytes)
        assert "Lorem ipsum" in result

    def test_bench_pdf_large(self, benchmark, large_pdf_bytes):
        """Benchmark 50-page PDF conversion."""
        result = benchmark(convert_pdf_to_md, large_pdf_bytes)
        assert "Lorem ipsum" in result


# ---------------------------------------------------------------------------
# Benchmarks – DOCX conversion
# ---------------------------------------------------------------------------


class TestDocxConversionBenchmark:
    """Benchmark DOCX → Markdown conversion speeds."""

    def test_bench_docx_small(self, benchmark, small_docx_bytes):
        """Benchmark minimal DOCX conversion."""
        result = benchmark(convert_docx_to_md, small_docx_bytes)
        assert "Bonjour" in result

    def test_bench_docx_medium(self, benchmark, medium_docx_bytes):
        """Benchmark DOCX with 100 paragraphs."""
        result = benchmark(convert_docx_to_md, medium_docx_bytes)
        assert "Paragraph" in result


# ---------------------------------------------------------------------------
# Benchmarks – HTML conversion
# ---------------------------------------------------------------------------


class TestHtmlConversionBenchmark:
    """Benchmark HTML → Markdown conversion speeds."""

    def test_bench_html_small(self, benchmark, small_html_bytes):
        """Benchmark minimal HTML conversion."""
        result = benchmark(convert_html_to_md, small_html_bytes)
        assert "Title" in result

    def test_bench_html_medium(self, benchmark, medium_html_bytes):
        """Benchmark HTML with 50 paragraphs and table."""
        result = benchmark(convert_html_to_md, medium_html_bytes)
        assert "Main Title" in result


# ---------------------------------------------------------------------------
# Benchmarks – Repeated / throughput
# ---------------------------------------------------------------------------


class TestThroughputBenchmark:
    """Benchmark throughput: how many conversions per second."""

    def test_bench_pdf_small_throughput(self, benchmark, small_pdf_bytes):
        """Measure small PDF conversion throughput."""
        benchmark(convert_pdf_to_md, small_pdf_bytes)

    def test_bench_docx_small_throughput(self, benchmark, small_docx_bytes):
        """Measure small DOCX conversion throughput."""
        benchmark(convert_docx_to_md, small_docx_bytes)

    def test_bench_html_small_throughput(self, benchmark, small_html_bytes):
        """Measure small HTML conversion throughput."""
        benchmark(convert_html_to_md, small_html_bytes)


# ---------------------------------------------------------------------------
# Benchmarks – API endpoints (async)
# ---------------------------------------------------------------------------


class TestAPIEndpointBenchmark:
    """Benchmark full API conversion endpoints via FastAPI."""

    @pytest.mark.asyncio
    async def test_bench_api_pdf(self, async_client, small_pdf_bytes):
        """Benchmark the /convert endpoint for PDF files."""
        files = {"file": ("document.pdf", small_pdf_bytes, "application/pdf")}
        response = await async_client.post("/convert", files=files)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bench_api_docx(self, async_client, small_docx_bytes):
        """Benchmark the /convert endpoint for DOCX files."""
        files = {
            "file": (
                "document.docx",
                small_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        response = await async_client.post("/convert", files=files)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bench_api_html(self, async_client, small_html_bytes):
        """Benchmark the /convert endpoint for HTML files."""
        files = {"file": ("document.html", small_html_bytes, "text/html")}
        response = await async_client.post("/convert", files=files)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Benchmarks – Concurrent API throughput (async)
# ---------------------------------------------------------------------------


class TestConcurrentAPIBenchmark:
    """Benchmark concurrent conversion throughput via API."""

    @pytest.mark.asyncio
    async def test_bench_concurrent_pdf(self, async_client, small_pdf_bytes):
        """Benchmark 5 concurrent PDF conversions via API."""
        import asyncio

        from app.api import app as fastapi_app

        fastapi_app.state.rate_limiter.enabled = False

        files = {"file": ("document.pdf", small_pdf_bytes, "application/pdf")}
        tasks = [async_client.post("/convert", files=files) for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in responses]
        assert all(s == 200 for s in statuses)

    @pytest.mark.asyncio
    async def test_bench_concurrent_html(self, async_client, small_html_bytes):
        """Benchmark 5 concurrent HTML conversions via API."""
        import asyncio

        from app.api import app as fastapi_app

        fastapi_app.state.rate_limiter.enabled = False

        files = {"file": ("document.html", small_html_bytes, "text/html")}
        tasks = [async_client.post("/convert", files=files) for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        statuses = [r.status_code for r in responses]
        assert all(s == 200 for s in statuses)
