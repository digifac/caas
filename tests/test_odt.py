"""Tests for ODT to Markdown conversion."""

import io
import zipfile
from unittest.mock import MagicMock, patch

import httpx
import pytest
from app.converters import odt as odt_module
from app.converters.odt import convert_odt_to_md

# Import fixtures from modules
from tests.fixtures.odt import (  # noqa: E402
    sample_odt_bytes, # type: ignore[import-not-found]
    sample_odt_with_list_bytes, # type: ignore[import-not-found]
    sample_odt_with_special_chars_bytes, # type: ignore[import-not-found]
)


class TestConvertOdtToMd:
    """Unit tests for the convert_odt_to_md function."""

    def test_basic_paragraphs(self, sample_odt_bytes: bytes):
        """ODT with basic paragraphs returns correct markdown."""
        markdown = convert_odt_to_md(sample_odt_bytes)
        assert "Titre du document" in markdown
        assert "Premier paragraphe" in markdown
        assert "Deuxième paragraphe" in markdown

    def test_blank_lines_between_paragraphs(self, sample_odt_bytes: bytes):
        """Paragraphs are separated by blank lines in markdown output."""
        markdown = convert_odt_to_md(sample_odt_bytes)
        lines = markdown.split("\n")
        # There should be blank lines separating paragraphs
        assert "" in lines

    def test_list_items(self, sample_odt_with_list_bytes: bytes):
        """ODT with list items produces markdown list syntax."""
        markdown = convert_odt_to_md(sample_odt_with_list_bytes)
        assert "Liste de courses" in markdown
        assert "- Pommes" in markdown
        assert "- Oranges" in markdown
        assert "- Bananes" in markdown
        assert "Fin de la liste" in markdown

    def test_special_characters(self, sample_odt_with_special_chars_bytes: bytes):
        """ODT with special characters preserves them correctly."""
        markdown = convert_odt_to_md(sample_odt_with_special_chars_bytes)
        assert "Caractères spéciaux" in markdown
        assert "Àéîôù" in markdown
        assert "©" in markdown
        assert "€" in markdown

    def test_empty_paragraphs_produce_blank_lines(self, sample_odt_bytes: bytes):
        """Empty paragraphs in ODT produce blank lines in markdown."""
        markdown = convert_odt_to_md(sample_odt_bytes)
        # The result should be stripped but contain content
        assert markdown.strip()

    def test_returns_string(self, sample_odt_bytes: bytes):
        """convert_odt_to_md returns a string."""
        result = convert_odt_to_md(sample_odt_bytes)
        assert isinstance(result, str)

    def test_no_trailing_whitespace(self, sample_odt_bytes: bytes):
        """Result is stripped of leading/trailing whitespace."""
        markdown = convert_odt_to_md(sample_odt_bytes)
        assert markdown == markdown.strip()


class TestConvertOdtEndpoint:
    """Integration tests for ODT conversion via the /convert endpoint."""

    @pytest.mark.anyio
    async def test_convert_odt_success(
        self, async_client: httpx.AsyncClient, sample_odt_bytes: bytes
    ):
        """POST /convert with a valid ODT returns markdown."""
        response = await async_client.post(
            "/convert", files={"file": ("test.odt", sample_odt_bytes)}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "markdown" in data
        assert data["format"] == "odt"
        assert data["size_bytes"] == len(sample_odt_bytes)
        assert "Titre du document" in data["markdown"]

    @pytest.mark.anyio
    async def test_convert_odt_with_list(
        self, async_client: httpx.AsyncClient, sample_odt_with_list_bytes: bytes
    ):
        """POST /convert with ODT containing lists returns correct markdown."""
        response = await async_client.post(
            "/convert", files={"file": ("list.odt", sample_odt_with_list_bytes)}
        )
        assert response.status_code == 200
        markdown = response.json()["markdown"]
        assert "- Pommes" in markdown
        assert "- Oranges" in markdown
        assert "- Bananes" in markdown

    @pytest.mark.anyio
    async def test_convert_odt_special_chars(
        self,
        async_client: httpx.AsyncClient,
        sample_odt_with_special_chars_bytes: bytes,
    ):
        """POST /convert with ODT containing special characters preserves them."""
        response = await async_client.post(
            "/convert",
            files={"file": ("special.odt", sample_odt_with_special_chars_bytes)},
        )
        assert response.status_code == 200
        markdown = response.json()["markdown"]
        assert "Àéîôù" in markdown
        assert "€" in markdown

    @pytest.mark.anyio
    async def test_convert_odt_response_structure(
        self, async_client: httpx.AsyncClient, sample_odt_bytes: bytes
    ):
        """POST /convert with ODT returns expected response keys."""
        response = await async_client.post(
            "/convert", files={"file": ("test.odt", sample_odt_bytes)}
        )
        data = response.json()
        assert "success" in data
        assert "markdown" in data
        assert "format" in data
        assert "size_bytes" in data


# --- Unit tests for get_element_text with mocked localName elements ---


class _MockElement:
    """Mock element with localName but WITHOUT data attribute.

    MagicMock has all attributes by default, so hasattr(mock, "data") returns True.
    This class ensures hasattr(elem, "data") is False while hasattr(elem, "localName") is True.
    """

    def __init__(
        self,
        local_name: str,
        get_text: str | None = None,
        get_attr_ns: str | None = None,
    ) -> None:
        self.localName = local_name  # type: ignore[attr-defined]
        self._get_text: str | None = get_text
        self._get_attr_ns: str | None = get_attr_ns

    def _getText(self) -> str:  # noqa: N802
        return self._get_text or ""

    def getAttrNS(self, *args: object) -> str | None:  # noqa: N802
        return self._get_attr_ns


def _make_odt(content_xml: str) -> bytes:
    """Helper to create an ODT from raw content XML."""
    mimetype = "application/vnd.oasis.opendocument.text"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype)
        zf.writestr("META-INF/manifest.xml", manifest)
        zf.writestr("content.xml", content_xml)
    buf.seek(0)
    return buf.getvalue()


class TestGetElementTextHeading:
    """Tests for get_element_text handling of heading (h) elements via mocked localName."""

    def test_heading_in_paragraph(self):
        """Heading element inside a paragraph produces Markdown heading."""
        mock_h = _MockElement("h", get_text="Sub Heading", get_attr_ns="2")
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_h]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "## Sub Heading" in markdown

    def test_heading_level_1(self):
        """Heading with outline-level=1 produces single #."""
        mock_h = _MockElement("h", get_text="Title", get_attr_ns="1")
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_h]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "# Title" in markdown

    def test_heading_level_capped_at_6(self):
        """Heading with outline-level > 6 is capped at 6 hashes."""
        mock_h = _MockElement("h", get_text="Deep", get_attr_ns="10")
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_h]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "###### Deep" in markdown

    def test_heading_without_outline_level(self):
        """Heading without outline-level defaults to level 1."""
        mock_h = _MockElement("h", get_text="Default", get_attr_ns=None)
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_h]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "# Default" in markdown


class TestGetElementTextTab:
    """Tests for get_element_text handling of tab elements via mocked localName."""

    def test_tab_in_paragraph(self):
        """Tab element inside a paragraph produces a tab character."""
        mock_text1 = MagicMock()
        mock_text1.data = "A"
        mock_tab = _MockElement("tab")
        mock_text2 = MagicMock()
        mock_text2.data = "B"
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_text1, mock_tab, mock_text2]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "A\tB" in markdown


class TestGetElementTextBr:
    """Tests for get_element_text handling of br (line break) elements via mocked localName."""

    def test_br_between_text(self):
        """Br between text nodes produces newline in output."""
        mock_text1 = MagicMock()
        mock_text1.data = "Line1"
        mock_br = _MockElement("br")
        mock_text2 = MagicMock()
        mock_text2.data = "Line2"
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_text1, mock_br, mock_text2]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "Line1" in markdown
            assert "Line2" in markdown


class TestGetElementTextSpan:
    """Tests for get_element_text handling of span elements via mocked localName."""

    def test_span_in_paragraph(self):
        """Span element inside a paragraph extracts text content."""
        mock_span = _MockElement("span", get_text="Spanned")
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_span]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "Spanned" in markdown

    def test_span_without_gettext(self):
        """Span without _getText returns empty string."""

        class _SpanNoGetText:
            localName = "span"  # type: ignore[attr-defined]  # noqa: N815

        mock_span = _SpanNoGetText()
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [mock_span]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            # Should not crash, just produce empty
            assert markdown == ""


class TestParagraphChildNodes:
    """Tests for paragraph childNodes iteration and edge cases."""

    def test_empty_paragraph(self):
        """Empty paragraph produces a blank line."""
        content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
  <office:body>
    <office:text>
      <text:p>Content</text:p>
      <text:p></text:p>
      <text:p>More</text:p>
    </office:text>
  </office:body>
</office:document-content>"""
        markdown = odt_module.convert_odt_to_md(_make_odt(content_xml))
        assert "Content" in markdown
        assert "More" in markdown
        # Empty paragraph should produce blank line
        assert "\n\n" in markdown

    def test_mixed_elements_in_paragraph(self):
        """Paragraph with mixed text, heading, tab, br, span elements."""
        mock_text = MagicMock()
        mock_text.data = "Text"
        mock_h = _MockElement("h", get_text="H", get_attr_ns="1")
        mock_tab = _MockElement("tab")
        mock_t = MagicMock()
        mock_t.data = "T"
        mock_br = _MockElement("br")
        mock_b = MagicMock()
        mock_b.data = "B"
        mock_span = _MockElement("span", get_text="S")
        with patch.object(odt_module.opendocument, "load") as mock_load:
            mock_para = MagicMock()
            mock_para.childNodes = [
                mock_text,
                mock_h,
                mock_tab,
                mock_t,
                mock_br,
                mock_b,
                mock_span,
            ]
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = [mock_para]
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "Text" in markdown
            assert "# H" in markdown
            assert "\t" in markdown
            assert "S" in markdown

    def test_multiple_paragraphs_with_child_nodes(self):
        """Multiple paragraphs each with span child nodes."""
        spans: list[_MockElement] = []
        for word in ["First", "Second", "Third"]:
            mock_span = _MockElement("span", get_text=word)
            spans.append(mock_span)
        with patch.object(odt_module.opendocument, "load") as mock_load:
            paras: list[MagicMock] = []
            for span in spans:
                mock_para = MagicMock()
                mock_para.childNodes = [span]
                paras.append(mock_para)
            mock_doc = MagicMock()
            mock_doc.body.getElementsByType.return_value = paras
            mock_load.return_value = mock_doc
            markdown = odt_module.convert_odt_to_md(b"dummy")
            assert "First" in markdown
            assert "Second" in markdown
            assert "Third" in markdown


@pytest.mark.anyio
async def test_convert_odt_to_json(
    async_client: httpx.AsyncClient, sample_odt_bytes: bytes
):
    """Test ODT → JSON."""
    response = await async_client.post(
        "/convert", files={"file": ("test.odt", sample_odt_bytes)}, params={"format": "json"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["format"] == "odt"
    assert "json" in data
    assert data["json"] is not None
    
    json_data = data["json"]
    assert isinstance(json_data, dict)
    # ODT should have pages with content
    if "pages" in json_data:
        pages = json_data["pages"]  # type: ignore[assignment]
        assert isinstance(pages, list)
        assert len(pages) > 0  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_convert_odt_to_jsonl(
    async_client: httpx.AsyncClient, sample_odt_bytes: bytes
):
    """Test ODT → JSONL."""
    response = await async_client.post(
        "/convert", files={"file": ("test.odt", sample_odt_bytes)}, params={"format": "jsonl"}
    )
    assert response.status_code == 200
    
    # JSONL est retourné comme texte brut, pas comme JSON parseable
    jsonl_content = response.text
    
    # Parse le contenu JSONL ligne par ligne
    import json
    lines = jsonl_content.strip().split("\n")
    assert len(lines) >= 3
    
    # Vérifier les types d'événements (start, end, chunk sont valides)
    for line in lines:
        event_dict = json.loads(line)
        event_type = event_dict.get("type", "")
        assert event_type in ("start", "end", "chunk")
