"""Tests for shared ZIP / Open XML utilities (zip_utils module)."""

import io
import zipfile

import pytest
from app.config import settings
from app.validation import _detect_mime_type, _validate_xlsx_structure
from app.zip_utils import _validate_openxml_structure, _validate_zip_bomb

# --- Helpers ---


def _make_zip(entries: dict, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Create an in-memory ZIP archive from a {name: content} dictionary."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_zip_stored(entries: dict) -> bytes:
    """Create an uncompressed (STORE) ZIP archive to test ratios."""
    return _make_zip(entries, zipfile.ZIP_STORED)


# --- Fixtures for common ZIP structures ---


@pytest.fixture
def valid_docx_bytes() -> bytes:
    """Minimal valid DOCX archive."""
    return _make_zip(
        {
            "[Content_Types].xml": "<?xml version='1.0'?><Types/>",
            "_rels/.rels": "<?xml version='1.0'?><Relationships/>",
            "word/document.xml": "<w:document><w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body></w:document>",
        }
    )


@pytest.fixture
def valid_odt_bytes() -> bytes:
    """Minimal valid ODT archive."""
    return _make_zip(
        {
            "mimetype": "application/vnd.oasis.opendocument.text",
            "content.xml": "<office:document-content><office:body><office:text><text:p>Hello</text:p></office:text></office:body></office:document-content>",
        }
    )


@pytest.fixture
def valid_xlsx_bytes() -> bytes:
    """Minimal valid XLSX archive."""
    return _make_zip(
        {
            "[Content_Types].xml": "<?xml version='1.0'?><Types/>",
            "_rels/.rels": "<?xml version='1.0'?><Relationships/>",
            "xl/workbook.xml": "<workbook><sheets><sheet name='Feuille1' sheetId='1'/></sheets></workbook>",
        }
    )


# --- Tests _validate_zip_bomb ---


class TestValidateZipBomb:
    """Tests for ZIP bomb detection from the shared zip_utils module."""

    def test_valid_zip_passes(self):
        """Normal ZIP archive passes validation."""
        data = _make_zip({"file.txt": "contenu normal"})
        assert _validate_zip_bomb(data) is None

    def test_valid_docx_passes(self, valid_docx_bytes):
        """Valid DOCX passes ZIP bomb detection."""
        assert _validate_zip_bomb(valid_docx_bytes) is None

    def test_valid_xlsx_passes(self, valid_xlsx_bytes):
        """Valid XLSX passes ZIP bomb detection."""
        assert _validate_zip_bomb(valid_xlsx_bytes) is None

    def test_high_compression_ratio_detected(self):
        """Compression ratio too high is detected."""
        large_content = "A" * (100 * 1024)
        data = _make_zip({"data.txt": large_content})
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "ratio" in result.lower() or "compression" in result.lower()

    def test_too_many_files_detected(self):
        """Too many files in the archive is detected."""
        entries = {f"file_{i}.txt": "x" for i in range(settings.zip_max_files + 1)}
        data = _make_zip(entries)
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "too many files" in result.lower()

    def test_filename_too_long_detected(self):
        """File name too long is detected."""
        long_name = "a" * (settings.zip_max_file_name_length + 1)
        data = _make_zip({long_name: "contenu"})
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "file name too long" in result.lower()

    def test_nested_zip_detected(self):
        """Nested ZIP archive is detected."""
        inner_zip = _make_zip({"inner.txt": "données"})
        data = _make_zip({"nested.zip": inner_zip})
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_nested_docx_detected(self):
        """DOCX nested inside another archive is detected."""
        inner_docx = _make_zip(
            {"[Content_Types].xml": "<?xml?>", "word/document.xml": "<doc/>"}
        )
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "attached.docx": inner_docx,
            }
        )
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_nested_xlsx_detected(self):
        """Nested XLSX is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "spreadsheet.xlsx": "fake xlsx",
            }
        )
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_nested_pptx_detected(self):
        """Nested PPTX is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "presentation.pptx": "fake pptx",
            }
        )
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_nested_jar_detected(self):
        """Nested JAR is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "malware.jar": "fake jar",
            }
        )
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_nested_apk_detected(self):
        """Nested APK is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "app.apk": "fake apk",
            }
        )
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_nested_odt_detected(self):
        """Nested ODT is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "document.odt": "fake odt",
            }
        )
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "nested" in result.lower()

    def test_bad_zip_file_detected(self):
        """Corrupted ZIP archive is detected."""
        data = b"PK\x03\x04" + b"not a real zip" * 50
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "invalid" in result.lower() or "corrupted" in result.lower()

    def test_total_decompressed_size_exceeded(self):
        """Total decompressed size too high is detected."""
        large_content = "A" * (
            settings.zip_max_total_decompressed_mb * 1024 * 1024 + 1024
        )
        data = _make_zip_stored({"large.txt": large_content})
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "decompressed" in result.lower() or "size" in result.lower()

    def test_boundary_compression_ratio_ok(self):
        """Acceptable compression ratio passes validation."""
        import os

        content = os.urandom(1024 * 1024)  # 1 MB of random data
        data = _make_zip({"data.bin": content})
        result = _validate_zip_bomb(data)
        assert result is None

    def test_global_compression_ratio_detected(self):
        """Global compression ratio too high is detected."""
        # Multiple files with high compression
        large_content = "B" * (500 * 1024)
        data = _make_zip({"data1.txt": large_content, "data2.txt": large_content})
        result = _validate_zip_bomb(data)
        assert result is not None
        assert "global" in result.lower() or "ratio" in result.lower()


# --- Tests _validate_openxml_structure ---


class TestValidateOpenXmlStructure:
    """Tests for the generic Open XML structure validation."""

    def test_valid_docx_structure(self, valid_docx_bytes):
        """Valid DOCX structure passes."""
        required = ["[Content_Types].xml", "word/document.xml"]
        assert _validate_openxml_structure(valid_docx_bytes, "docx", required) is None

    def test_valid_odt_structure(self, valid_odt_bytes):
        """Valid ODT structure passes."""
        required = ["mimetype", "content.xml"]
        assert _validate_openxml_structure(valid_odt_bytes, "odt", required) is None

    def test_valid_xlsx_structure(self, valid_xlsx_bytes):
        """Valid XLSX structure passes."""
        required = ["[Content_Types].xml", "xl/workbook.xml"]
        assert _validate_openxml_structure(valid_xlsx_bytes, "xlsx", required) is None

    def test_missing_required_file_single(self):
        """Missing one required file is detected."""
        data = _make_zip({"[Content_Types].xml": "<?xml?>"})
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is not None
        assert "document.xml" in result.lower()
        assert "missing" in result.lower()

    def test_missing_required_file_all(self):
        """Missing all required files is detected."""
        data = _make_zip({"random.txt": "pas un docx"})
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is not None
        assert "missing" in result.lower()

    def test_different_required_sets(self):
        """Different required file sets work correctly."""
        # Custom required files for a hypothetical format
        data = _make_zip({"custom/file1.xml": "a", "custom/file2.xml": "b"})
        result = _validate_openxml_structure(
            data, "custom", ["custom/file1.xml", "custom/file2.xml"]
        )
        assert result is None

    def test_extra_files_allowed(self):
        """Extra files beyond required ones are allowed."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "word/styles.xml": "<styles/>",
                "word/numbering.xml": "<numbering/>",
            }
        )
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is None

    def test_path_traversal_forward_slash(self):
        """Path traversal with /.. is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "word/../../etc/passwd": "malicious",
            }
        )
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is not None
        assert "traversal" in result.lower() or "suspicious" in result.lower()

    def test_path_traversal_backslash(self):
        r"""Path traversal with \.. is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "word\\..\\windows\\system32": "malicious",
            }
        )
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is not None
        assert "traversal" in result.lower() or "suspicious" in result.lower()

    def test_absolute_path_forward_slash(self):
        """Absolute path with / is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "/etc/passwd": "malicious",
            }
        )
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is not None
        assert "absolute" in result.lower()

    def test_absolute_path_backslash(self):
        """Absolute path with \\ is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "word/document.xml": "<doc/>",
                "\\windows\\system32\\config": "malicious",
            }
        )
        result = _validate_openxml_structure(
            data, "docx", ["[Content_Types].xml", "word/document.xml"]
        )
        assert result is not None
        assert "absolute" in result.lower()

    def test_bad_zip_file(self):
        """Corrupted ZIP returns error."""
        data = b"PK\x03\x04" + b"not a real zip" * 50
        result = _validate_openxml_structure(data, "docx", ["[Content_Types].xml"])
        assert result is not None
        assert "invalid" in result.lower() or "corrupted" in result.lower()

    def test_ext_in_error_message(self):
        """Error message contains the extension label."""
        data = _make_zip({"random.txt": "data"})
        result = _validate_openxml_structure(
            data, "xlsx", ["[Content_Types].xml", "xl/workbook.xml"]
        )
        assert result is not None
        assert "XLSX" in result  # ext is uppercased in error messages

    def test_empty_required_files_list(self):
        """Empty required files list passes validation (edge case)."""
        data = _make_zip({"any.txt": "data"})
        result = _validate_openxml_structure(data, "test", [])
        assert result is None


# --- Tests XLSX MIME detection ---


class TestXlsXMimeDetection:
    """Tests for XLSX MIME type detection via ZIP format markers."""

    def test_detect_xlsx_mime_with_xl_prefix(self):
        """XLSX detection via xl/ prefix in namelist."""
        data = _make_zip({"xl/workbook.xml": "<workbook/>"})
        assert (
            _detect_mime_type(data)
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_detect_xlsx_mime_content_types_and_xl(self):
        """XLSX detection with [Content_Types].xml and xl/ path."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "xl/worksheets/sheet1.xml": "<worksheet/>",
            }
        )
        assert (
            _detect_mime_type(data)
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_xlsx_not_confused_with_docx(self):
        """XLSX with xl/ should not be detected as DOCX."""
        data = _make_zip({"xl/workbook.xml": "<workbook/>"})
        mime = _detect_mime_type(data)
        assert "spreadsheetml" in mime
        assert "wordprocessingml" not in mime

    def test_docx_not_confused_with_xlsx(self):
        """DOCX with word/ should not be detected as XLSX."""
        data = _make_zip({"word/document.xml": "<doc/>"})
        mime = _detect_mime_type(data)
        assert "wordprocessingml" in mime
        assert "spreadsheetml" not in mime

    def test_content_types_only_no_prefix_is_plain_zip(self):
        """ZIP with only [Content_Types].xml but no word/ or xl/ is plain ZIP."""
        data = _make_zip({"[Content_Types].xml": "<?xml?>"})
        assert _detect_mime_type(data) == "application/zip"

    def test_plain_zip_no_false_xlsx(self):
        """Plain ZIP without xl/ or word/ should not be detected as XLSX."""
        data = _make_zip({"random.txt": "hello"})
        assert _detect_mime_type(data) == "application/zip"

    def test_odt_not_confused_with_xlsx(self):
        """ODT should not be detected as XLSX."""
        data = _make_zip(
            {
                "mimetype": "application/vnd.oasis.opendocument.text",
                "content.xml": "<content/>",
            }
        )
        mime = _detect_mime_type(data)
        assert "opendocument" in mime


# --- Tests XLSX structure validation ---


class TestValidateXlsxStructure:
    """Tests for XLSX structure validation (wrapper around _validate_openxml_structure)."""

    def test_valid_xlsx_structure_passes(self, valid_xlsx_bytes):
        """Valid XLSX passes structure validation."""
        assert _validate_xlsx_structure(valid_xlsx_bytes) is None

    def test_missing_content_types(self):
        """XLSX without [Content_Types].xml is rejected."""
        data = _make_zip({"xl/workbook.xml": "<workbook/>"})
        result = _validate_xlsx_structure(data)
        assert result is not None
        assert "content_types" in result.lower() or "missing" in result.lower()

    def test_missing_workbook_xml(self):
        """XLSX without xl/workbook.xml is rejected."""
        data = _make_zip({"[Content_Types].xml": "<?xml?>"})
        result = _validate_xlsx_structure(data)
        assert result is not None
        assert "workbook.xml" in result.lower() or "missing" in result.lower()

    def test_both_required_files_missing(self):
        """XLSX without any required files is rejected."""
        data = _make_zip({"random.txt": "pas un xlsx"})
        result = _validate_xlsx_structure(data)
        assert result is not None
        assert "missing" in result.lower()

    def test_path_traversal_detected(self):
        """Path traversal in XLSX is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "xl/workbook.xml": "<workbook/>",
                "xl/../../etc/passwd": "malicious",
            }
        )
        result = _validate_xlsx_structure(data)
        assert result is not None
        assert "traversal" in result.lower() or "suspicious" in result.lower()

    def test_absolute_path_detected(self):
        """Absolute path in XLSX is detected."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "xl/workbook.xml": "<workbook/>",
                "/etc/passwd": "malicious",
            }
        )
        result = _validate_xlsx_structure(data)
        assert result is not None
        assert "absolute" in result.lower()

    def test_extra_xl_files_allowed(self):
        """Extra xl/ files beyond required ones are allowed."""
        data = _make_zip(
            {
                "[Content_Types].xml": "<?xml?>",
                "xl/workbook.xml": "<workbook/>",
                "xl/worksheets/sheet1.xml": "<worksheet/>",
                "xl/styles.xml": "<styles/>",
                "xl/sharedStrings.xml": "<sst/>",
            }
        )
        result = _validate_xlsx_structure(data)
        assert result is None

    def test_bad_zip_file(self):
        """Corrupted ZIP returns error for XLSX."""
        data = b"PK\x03\x04" + b"not a real zip" * 50
        result = _validate_xlsx_structure(data)
        assert result is not None
        assert "invalid" in result.lower() or "corrupted" in result.lower()
