"""Shared fixtures for all tests."""

import asyncio
import io
import os

import httpx
import pytest
from app.api import app
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@pytest.fixture
def clean_caas_env(monkeypatch):
    """Remove all CAAS_ environment variables for testing defaults."""
    keys_to_remove = [k for k in os.environ if k.startswith("CAAS_")]
    for key in keys_to_remove:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting during all tests."""
    app.state.rate_limiter.enabled = False
    yield


@pytest.fixture(autouse=True)
def reset_task_manager():
    """Reset the TaskManager between each test to avoid task accumulation.
    Also restores the original task_manager if a test replaced app.state.task_manager.
    """
    from app.api import app as main_app

    original_tm = main_app.state.task_manager
    original_tm._tasks.clear()
    original_tm._async_tasks.clear()
    original_tm._batches.clear()
    # Reset the semaphore so it's available again
    original_tm._semaphore = asyncio.Semaphore(original_tm._max_concurrent)
    yield
    # Restore original task_manager in case a test replaced it
    main_app.state.task_manager = original_tm
    original_tm._tasks.clear()
    original_tm._async_tasks.clear()
    original_tm._batches.clear()
    original_tm._semaphore = asyncio.Semaphore(original_tm._max_concurrent)


@pytest.fixture
async def async_client():
    """Client HTTP asynchrone pour tester l'API FastAPI."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Generate a minimal PDF with text in memory (zero-disk)."""
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
    """Generate a PDF with a hyperlink in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, "Visitez notre site")
    # Add an URI link with reportlab
    c.linkURL("https://example.com", (72, 740, 200, 760), thickness=0)
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_scanned_pdf_bytes() -> bytes:
    """Generate a 'scanned' PDF (image with French text, no text layer)."""
    import io as _io
    import os

    from PIL import Image, ImageDraw, ImageFont

    # Create a larger image with a TrueType font for reliable OCR
    img = Image.new("RGB", (1200, 300), color="white")
    draw = ImageDraw.Draw(img)

    # Use the arial.ttf font provided in the tests folder
    font_path = os.path.join(os.path.dirname(__file__), "arial.ttf")
    font = ImageFont.truetype(font_path, 36)

    # Draw black text on white background (simulates a scanned document)
    draw.text((40, 100), "Document scanné en français", fill="black", font=font)
    img_bytes = _io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Create a PDF with the image using reportlab (no text layer)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    from reportlab.lib.utils import ImageReader

    c.drawImage(ImageReader(img_bytes), 50, 50, width=495, height=200)
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_docx_bytes() -> bytes:
    """
    Generate a minimal DOCX in memory.
    Uses the raw XML structure of a .docx (zip) without external dependencies.
    """
    import zipfile

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
def sample_html_bytes() -> bytes:
    """
    Generate a minimal HTML document in memory with various elements.
    Includes headings, paragraphs, links, lists, bold/italic, and a table.
    """
    html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Main Title</h1>
    <p>This is a <strong>bold</strong> and <em>italic</em> paragraph.</p>
    <p>Visit <a href="https://example.com">our website</a> for more info.</p>
    <ul>
        <li>First item</li>
        <li>Second item</li>
    </ul>
    <ol>
        <li>Step one</li>
        <li>Step two</li>
    </ol>
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>A</td><td>1</td></tr>
        <tr><td>B</td><td>2</td></tr>
    </table>
    <blockquote>
        <p>A quoted paragraph</p>
    </blockquote>
    <pre><code>def hello():\n    print("world")</code></pre>
    <hr>
    <p>Final paragraph with an <img src="image.png" alt="test image"> inline.</p>
</body>
</html>"""
    return html.encode("utf-8")


@pytest.fixture
def sample_html_minimal_bytes() -> bytes:
    """Generate a minimal HTML document with just a heading and paragraph."""
    html = """<!DOCTYPE html>
<html>
<body>
    <h1>Hello World</h1>
    <p>This is a simple paragraph.</p>
</body>
</html>"""
    return html.encode("utf-8")


@pytest.fixture
def sample_html_latin1_bytes() -> bytes:
    """Generate an HTML document encoded in Latin-1."""
    html = """<!DOCTYPE html>
<html>
<body>
    <h1>Document en français</h1>
    <p>Des caractères spéciaux : àéîôù</p>
</body>
</html>"""
    return html.encode("latin-1")


@pytest.fixture
def sample_odt_bytes() -> bytes:
    """Generate a minimal ODT document in memory using raw XML (zip-based)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.text"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
  <office:body>
    <office:text>
      <text:p>Titre du document</text:p>
      <text:p>Premier paragraphe</text:p>
      <text:p>Deuxième paragraphe</text:p>
    </office:text>
  </office:body>
</office:document-content>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype)
        zf.writestr("META-INF/manifest.xml", manifest)
        zf.writestr("content.xml", content_xml)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odt_with_list_bytes() -> bytes:
    """Generate an ODT document with list items using raw XML (zip-based)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.text"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" office:version="1.2">
  <office:body>
    <office:text>
      <text:p>Liste de courses</text:p>
      <text:p text:bullet-name="•">Pommes</text:p>
      <text:p text:bullet-name="•">Oranges</text:p>
      <text:p text:bullet-name="•">Bananes</text:p>
      <text:p>Fin de la liste</text:p>
    </office:text>
  </office:body>
</office:document-content>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype)
        zf.writestr("META-INF/manifest.xml", manifest)
        zf.writestr("content.xml", content_xml)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odt_with_special_chars_bytes() -> bytes:
    """Generate an ODT document with special characters using raw XML (zip-based)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.text"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
  <office:body>
    <office:text>
      <text:p>Caractères spéciaux</text:p>
      <text:p>Àéîôù Ñ ü ö ä</text:p>
      <text:p>Symboles: © ® ™ € £ ¥</text:p>
    </office:text>
  </office:body>
</office:document-content>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype)
        zf.writestr("META-INF/manifest.xml", manifest)
        zf.writestr("content.xml", content_xml)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_bytes() -> bytes:
    """Generate a minimal XLSX in memory with 1 sheet and a few cells."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Feuille1"
    ws["A1"] = "Nom"
    ws["B1"] = "Valeur"
    ws["A2"] = "A"
    ws["B2"] = 1
    ws["A3"] = "B"
    ws["B3"] = 2

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_multi_sheet_bytes() -> bytes:
    """Generate an XLSX with multiple sheets."""
    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Données"
    ws1["A1"] = "Produit"
    ws1["B1"] = "Prix"
    ws1["A2"] = "Pomme"
    ws1["B2"] = 1.5
    ws1["A3"] = "Orange"
    ws1["B3"] = 2.0

    ws2 = wb.create_sheet(title="Résumé")
    ws2["A1"] = "Total"
    ws2["B1"] = 3.5

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_merged_cells_bytes() -> bytes:
    """Generate an XLSX with merged cells."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Fusionné"
    ws["A1"] = "En-tête fusionné"
    ws.merge_cells("A1:C1")
    ws["A2"] = "Col1"
    ws["B2"] = "Col2"
    ws["C2"] = "Col3"
    ws["A3"] = "v1"
    ws["B3"] = "v2"
    ws["C3"] = "v3"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_dates_numbers_bytes() -> bytes:
    """Generate an XLSX with dates and numbers."""
    from datetime import date, datetime

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Types"
    ws["A1"] = "Texte"
    ws["B1"] = "Nombre"
    ws["C1"] = "Date"
    ws["D1"] = "Booléen"
    ws["A2"] = "hello"
    ws["B2"] = 42.5
    ws["C2"] = date(2024, 1, 15)
    ws["D2"] = True
    ws["A3"] = "world"
    ws["B3"] = -10
    ws["C3"] = datetime(2024, 6, 30, 12, 0, 0)
    ws["D3"] = False

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_special_chars_bytes() -> bytes:
    """Generate an XLSX with Markdown special characters."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Spécial"
    ws["A1"] = "Colonne A"
    ws["B1"] = "Colonne B"
    ws["A2"] = "Texte avec | pipe"
    ws["B2"] = "Texte avec \\ backslash"
    ws["A3"] = "Ligne 1\nLigne 2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_empty_sheet_bytes() -> bytes:
    """Generate an XLSX with an empty sheet."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Vide"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_bytes() -> bytes:
    """Generate a minimal PPTX in memory using python-pptx."""
    from pptx import Presentation

    prs = Presentation()

    # Slide 1: title slide
    slide_layout = prs.slide_layouts[0]  # Title slide
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Présentation de Test"
    slide.placeholders[1].text = "Sous-titre de la présentation"

    # Slide 2: title + content with bullets
    slide_layout = prs.slide_layouts[1]  # Title and Content
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Deuxième Slide"
    body_shape = slide.placeholders[1]
    tf = body_shape.text_frame
    tf.text = "Premier point"
    p = tf.add_paragraph()
    p.text = "Deuxième point"
    p.level = 0
    p = tf.add_paragraph()
    p.text = "Sous-point"
    p.level = 1

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_with_table_bytes() -> bytes:
    """Generate a PPTX with a table in memory using python-pptx."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()

    # Slide with table
    slide_layout = prs.slide_layouts[5]  # Blank
    slide = prs.slides.add_slide(slide_layout)

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.5))
    title_box.text = "Slide avec Tableau"

    # Add table
    rows = 3
    cols = 3
    left = Inches(1)
    top = Inches(1)
    width = Inches(6)
    height = Inches(2)
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    table.cell(0, 0).text = "En-tête 1"
    table.cell(0, 1).text = "En-tête 2"
    table.cell(0, 2).text = "En-tête 3"
    table.cell(1, 0).text = "A"
    table.cell(1, 1).text = "B"
    table.cell(1, 2).text = "C"
    table.cell(2, 0).text = "1"
    table.cell(2, 1).text = "2"
    table.cell(2, 2).text = "3"

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_empty_slide_bytes() -> bytes:
    """Generate a PPTX with an empty slide in memory using python-pptx."""
    from pptx import Presentation

    prs = Presentation()
    slide_layout = prs.slide_layouts[6]  # Blank layout
    prs.slides.add_slide(slide_layout)
    # No content added — empty slide

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# ODS Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ods_bytes() -> bytes:
    """Generate a minimal ODS file with one sheet and some data using odfpy."""
    from odf import table, text
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table_elem = table.Table(name="Feuille1")

    # Row 1: headers
    row1 = table.TableRow()
    c1 = table.TableCell()
    p1 = text.P()
    p1.addText("Nom")
    c1.addElement(p1)
    row1.addElement(c1)
    c2 = table.TableCell()
    p2 = text.P()
    p2.addText("Valeur")
    c2.addElement(p2)
    row1.addElement(c2)
    table_elem.addElement(row1)

    # Row 2: data
    row2 = table.TableRow()
    c3 = table.TableCell()
    p3 = text.P()
    p3.addText("A")
    c3.addElement(p3)
    row2.addElement(c3)
    c4 = table.TableCell()
    p4 = text.P()
    p4.addText("1")
    c4.addElement(p4)
    row2.addElement(c4)
    table_elem.addElement(row2)

    # Row 3: data
    row3 = table.TableRow()
    c5 = table.TableCell()
    p5 = text.P()
    p5.addText("B")
    c5.addElement(p5)
    row3.addElement(c5)
    c6 = table.TableCell()
    p6 = text.P()
    p6.addText("2")
    c6.addElement(p6)
    row3.addElement(c6)
    table_elem.addElement(row3)

    doc.spreadsheet.addElement(table_elem)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_multi_sheet_bytes() -> bytes:
    """Generate an ODS file with multiple sheets using odfpy."""
    from odf import table, text
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()

    # Sheet 1: Données
    sheet1 = table.Table(name="Données")
    row1 = table.TableRow()
    c1 = table.TableCell()
    p1 = text.P()
    p1.addText("Produit")
    c1.addElement(p1)
    row1.addElement(c1)
    c2 = table.TableCell()
    p2 = text.P()
    p2.addText("Prix")
    c2.addElement(p2)
    row1.addElement(c2)
    sheet1.addElement(row1)

    row2 = table.TableRow()
    c3 = table.TableCell()
    p3 = text.P()
    p3.addText("Pomme")
    c3.addElement(p3)
    row2.addElement(c3)
    c4 = table.TableCell()
    p4 = text.P()
    p4.addText("1.5")
    c4.addElement(p4)
    row2.addElement(c4)
    sheet1.addElement(row2)

    row3 = table.TableRow()
    c5 = table.TableCell()
    p5 = text.P()
    p5.addText("Orange")
    c5.addElement(p5)
    row3.addElement(c5)
    c6 = table.TableCell()
    p6 = text.P()
    p6.addText("2.0")
    c6.addElement(p6)
    row3.addElement(c6)
    sheet1.addElement(row3)

    doc.spreadsheet.addElement(sheet1)

    # Sheet 2: Résumé
    sheet2 = table.Table(name="Résumé")
    row4 = table.TableRow()
    c7 = table.TableCell()
    p7 = text.P()
    p7.addText("Total")
    c7.addElement(p7)
    row4.addElement(c7)
    c8 = table.TableCell()
    p8 = text.P()
    p8.addText("3.5")
    c8.addElement(p8)
    row4.addElement(c8)
    sheet2.addElement(row4)

    doc.spreadsheet.addElement(sheet2)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_empty_sheet_bytes() -> bytes:
    """Generate an ODS file with an empty sheet using odfpy."""
    from odf import table
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table_elem = table.Table(name="Vide")
    # No rows added — empty sheet
    doc.spreadsheet.addElement(table_elem)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_special_chars_bytes() -> bytes:
    """Generate an ODS file with special characters using odfpy."""
    from odf import table, text
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table_elem = table.Table(name="Spécial")

    # Row 1: headers
    row1 = table.TableRow()
    c1 = table.TableCell()
    p1 = text.P()
    p1.addText("Colonne A")
    c1.addElement(p1)
    row1.addElement(c1)
    c2 = table.TableCell()
    p2 = text.P()
    p2.addText("Colonne B")
    c2.addElement(p2)
    row1.addElement(c2)
    table_elem.addElement(row1)

    # Row 2: pipe and backslash
    row2 = table.TableRow()
    c3 = table.TableCell()
    p3 = text.P()
    p3.addText("Texte avec | pipe")
    c3.addElement(p3)
    row2.addElement(c3)
    c4 = table.TableCell()
    p4 = text.P()
    p4.addText("Texte avec \\ backslash")
    c4.addElement(p4)
    row2.addElement(c4)
    table_elem.addElement(row2)

    # Row 3: accents
    row3 = table.TableRow()
    c5 = table.TableCell()
    p5 = text.P()
    p5.addText("Àéîôù")
    c5.addElement(p5)
    row3.addElement(c5)
    c6 = table.TableCell()
    p6 = text.P()
    p6.addText("Ñ ü ö ä")
    c6.addElement(p6)
    row3.addElement(c6)
    table_elem.addElement(row3)

    doc.spreadsheet.addElement(table_elem)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# ODP Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_odp_bytes() -> bytes:
    """Generate a minimal ODP file with slides and text using odfpy."""
    from odf import draw, opendocument, text

    doc = opendocument.OpenDocumentPresentation()

    # Slide 1: title slide
    page1 = draw.Page(name="Slide 1", masterpagename="Default")
    title_frame = draw.Frame(name="TitleFrame")
    title_text_box = draw.TextBox()
    title_para = text.P()
    title_para.addText("Présentation de Test")
    title_text_box.addElement(title_para)
    title_frame.addElement(title_text_box)
    page1.addElement(title_frame)

    # Subtitle frame
    subtitle_frame = draw.Frame(name="SubtitleFrame")
    subtitle_text_box = draw.TextBox()
    subtitle_para = text.P()
    subtitle_para.addText("Sous-titre de la présentation")
    subtitle_text_box.addElement(subtitle_para)
    subtitle_frame.addElement(subtitle_text_box)
    page1.addElement(subtitle_frame)

    doc.presentation.addElement(page1)

    # Slide 2: content slide
    page2 = draw.Page(name="Slide 2", masterpagename="Default")
    title_frame2 = draw.Frame(name="TitleFrame2")
    title_text_box2 = draw.TextBox()
    title_para2 = text.P()
    title_para2.addText("Deuxième Slide")
    title_text_box2.addElement(title_para2)
    title_frame2.addElement(title_text_box2)
    page2.addElement(title_frame2)

    # Content frame with list items
    content_frame = draw.Frame(name="ContentFrame")
    content_text_box = draw.TextBox()
    para1 = text.P()
    para1.addText("Premier point")
    content_text_box.addElement(para1)
    para2 = text.P()
    para2.addText("Deuxième point")
    content_text_box.addElement(para2)
    para3 = text.P()
    para3.addText("Troisième point")
    content_text_box.addElement(para3)
    content_frame.addElement(content_text_box)
    page2.addElement(content_frame)

    doc.presentation.addElement(page2)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odp_with_list_bytes() -> bytes:
    """Generate an ODP file with bullet list items using odfpy."""
    from odf import draw, opendocument, text

    doc = opendocument.OpenDocumentPresentation()

    page = draw.Page(name="Slide 1", masterpagename="Default")
    title_frame = draw.Frame(name="TitleFrame")
    title_text_box = draw.TextBox()
    title_para = text.P()
    title_para.addText("Liste de courses")
    title_text_box.addElement(title_para)
    title_frame.addElement(title_text_box)
    page.addElement(title_frame)

    content_frame = draw.Frame(name="ContentFrame")
    content_text_box = draw.TextBox()
    para1 = text.P()
    para1.addText("Pommes")
    content_text_box.addElement(para1)
    para2 = text.P()
    para2.addText("Oranges")
    content_text_box.addElement(para2)
    para3 = text.P()
    para3.addText("Bananes")
    content_text_box.addElement(para3)
    content_frame.addElement(content_text_box)
    page.addElement(content_frame)

    doc.presentation.addElement(page)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odp_with_special_chars_bytes() -> bytes:
    """Generate an ODP file with special characters using odfpy."""
    from odf import draw, opendocument, text

    doc = opendocument.OpenDocumentPresentation()

    page = draw.Page(name="Slide 1", masterpagename="Default")
    title_frame = draw.Frame(name="TitleFrame")
    title_text_box = draw.TextBox()
    title_para = text.P()
    title_para.addText("Caractères spéciaux")
    title_text_box.addElement(title_para)
    title_frame.addElement(title_text_box)
    page.addElement(title_frame)

    content_frame = draw.Frame(name="ContentFrame")
    content_text_box = draw.TextBox()
    para1 = text.P()
    para1.addText("Àéîôù Ñ ü ö ä")
    content_text_box.addElement(para1)
    para2 = text.P()
    para2.addText("Symboles: © ® ™ € £ ¥")
    content_text_box.addElement(para2)
    content_frame.addElement(content_text_box)
    page.addElement(content_frame)

    doc.presentation.addElement(page)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odp_with_groups_bytes() -> bytes:
    """Generate an ODP file with draw:g groups (LibreOffice-style structure).

    LibreOffice wraps frames in draw:g (group) elements, which was previously
    not handled by the ODP converter.
    """
    import zipfile

    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
        ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
        ' xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"'
        ' xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
        ' office:version="1.3">'
        '  <office:body>'
        '    <office:presentation>'
        '      <draw:page draw:name="Page1" draw:master-page-name="Default">'
        '        <draw:g draw:style-name="dp1">'
        '          <draw:frame draw:name="pm-title" draw:style-name="Title">'
        '            <draw:text-frame>'
        '              <text:p>Titre dans un groupe</text:p>'
        '            </draw:text-frame>'
        '          </draw:frame>'
        '        </draw:g>'
        '        <draw:g draw:style-name="dp1">'
        '          <draw:frame draw:name="pm-subtitle">'
        '            <draw:text-frame>'
        '              <text:p>Sous-titre dans un groupe</text:p>'
        '            </draw:text-frame>'
        '          </draw:frame>'
        '        </draw:g>'
        '        <draw:frame draw:name="ContentFrame">'
        '          <draw:text-frame>'
        '            <text:p>Contenu direct</text:p>'
        '          </draw:text-frame>'
        '        </draw:frame>'
        '      </draw:page>'
        '    </office:presentation>'
        '  </office:body>'
        '</office:document-content>'
    )

    manifest_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
        '  <manifest:file-entry manifest:full-path="/"'
        '    manifest:media-type="application/vnd.oasis.opendocument.presentation"/>'
        '  <manifest:file-entry manifest:full-path="content.xml"'
        '    manifest:media-type="text/xml"/>'
        "</manifest:manifest>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", content_xml)
        zf.writestr("META-INF/manifest.xml", manifest_xml)
    buf.seek(0)
    return buf.getvalue()
