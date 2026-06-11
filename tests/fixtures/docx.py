"""Fixtures for DOCX tests."""

__all__ = [
    "sample_docx_bytes",
]

import io
from typing import Any

import pytest


@pytest.fixture
def sample_docx_bytes() -> bytes:
    """
    Generate a minimal DOCX document in memory.
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
