"""Fixtures for ODT tests."""

__all__ = [
    "sample_odt_bytes",
    "sample_odt_with_list_bytes",
    "sample_odt_with_special_chars_bytes",
]

import io
import pytest


@pytest.fixture
def sample_odt_bytes() -> bytes:
    """Generate a minimal ODT document in memory using raw XML (zip-based format)."""
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
    """Generate an ODT document containing a bulleted list using raw XML (zip-based format)."""
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
    """Generate an ODT document containing special characters using raw XML (zip-based format)."""
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
