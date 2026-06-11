"""Fixtures for ODP tests."""

__all__ = [
    "sample_odp_bytes",
    "sample_odp_multi_sheet_bytes",
    "sample_odp_empty_slide_bytes",
    "sample_odp_with_list_bytes",
    "sample_odp_with_special_chars_bytes",
    "sample_odp_with_groups_bytes",
]

import io
from typing import Any

import pytest


@pytest.fixture
def sample_odp_bytes() -> bytes:
    """Generate a minimal ODP presentation document in memory using raw XML (zip-based format)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.presentation"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:drawing="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.2">
  <office:body>
    <office:presentation>
      <draw:page draw:name="Slide1" draw:master-page-name="Default">
        <text:p>Bienvenue</text:p>
      </draw:page>
    </office:presentation>
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
def sample_odp_multi_sheet_bytes() -> bytes:
    """Generate an ODP presentation document containing multiple slides using raw XML (zip-based format)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.presentation"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:drawing="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.2">
  <office:body>
    <office:presentation>
      <draw:page draw:name="Slide1" draw:master-page-name="Default">
        <text:p>Titre de la présentation</text:p>
      </draw:page>
      <draw:page draw:name="Slide2" draw:master-page-name="Default">
        <text:p>Contenu principal</text:p>
      </draw:page>
      <draw:page draw:name="Slide3" draw:master-page-name="Default">
        <text:p>Conclusion</text:p>
      </draw:page>
    </office:presentation>
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
def sample_odp_empty_slide_bytes() -> bytes:
    """Generate an ODP presentation document containing an empty slide using raw XML (zip-based format)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.presentation"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:drawing="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.2">
  <office:body>
    <office:presentation>
      <draw:page draw:name="Slide1" draw:master-page-name="Default"/>
    </office:presentation>
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
def sample_odp_with_list_bytes() -> bytes:
    """Generate an ODP document with list items using raw XML (zip-based)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.presentation"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:drawing="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.2">
  <office:body>
    <office:presentation>
      <draw:page draw:name="Slide1" draw:master-page-name="Default">
        <text:p>Liste d'objectifs</text:p>
        <text:list><list-item>Premier objectif</list-item></text:list>
        <text:list><list-item>Deuxième objectif</list-item></text:list>
        <text:list><list-item>Troisième objectif</list-item></text:list>
      </draw:page>
    </office:presentation>
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
def sample_odp_with_special_chars_bytes() -> bytes:
    """Generate an ODP document with special characters using raw XML (zip-based)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.presentation"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
  <office:body>
    <office:presentation>
      <draw:page draw:name="Slide1" draw:master-page-name="Default">
        <text:p>Présentation multilingue</text:p>
        <text:p>Français • Español • Deutsch</text:p>
        <text:p>Àéîôù Ñ ü ö ä</text:p>
      </draw:page>
    </office:presentation>
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
def sample_odp_with_groups_bytes() -> bytes:
    """Generate an ODP document with grouped objects using raw XML (zip-based)."""
    import zipfile

    mimetype = "application/vnd.oasis.opendocument.presentation"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:drawing="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.2">
  <office:body>
    <office:presentation>
      <draw:page draw:name="Slide1" draw:master-page-name="Default">
        <text:p>Titre</text:p>
        <draw:g draw:name="Group1">
          <draw:text-box>Objet 1</draw:text-box>
          <draw:text-box>Objet 2</draw:text-box>
        </draw:g>
      </draw:page>
    </office:presentation>
  </office:body>
</office:document-content>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype)
        zf.writestr("META-INF/manifest.xml", manifest)
        zf.writestr("content.xml", content_xml)
    buf.seek(0)
    return buf.getvalue()
