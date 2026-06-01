"""Validation of uploaded file content (magic bytes, MIME, minimum size, ZIP bomb, DOCX)."""

import io
import logging
import zipfile
from collections.abc import Callable

from app.config import settings
from app.zip_utils import _validate_openxml_structure, _validate_zip_bomb

logger = logging.getLogger(__name__)

# --- Magic bytes (headers) by format ---
MAGIC_BYTES: dict = {
    "pdf": (b"%PDF-", 5),  # PDF starts with "%PDF-"
    "docx": (b"PK\x03\x04", 4),  # DOCX is a ZIP (PK signature)
    "odt": (b"PK\x03\x04", 4),  # ODT is a ZIP (PK signature)
    "ods": (b"PK\x03\x04", 4),  # ODS is a ZIP (PK signature)
    "xlsx": (b"PK\x03\x04", 4),  # XLSX is a ZIP (PK signature)
    "pptx": (b"PK\x03\x04", 4),  # PPTX is a ZIP (PK signature)
    "odp": (b"PK\x03\x04", 4),  # ODP is a ZIP (PK signature)
    "html": (b"<", 1),  # HTML starts with "<"
}

# Minimum sizes in bytes for a valid file
MIN_FILE_SIZES: dict = {
    "pdf": 10,  # A minimal PDF is ~10 bytes
    "docx": 512,  # A minimal DOCX (ZIP) is ~512 bytes
    "odt": 512,  # A minimal ODT (ZIP) is ~512 bytes
    "ods": 512,  # A minimal ODS (ZIP) is ~512 bytes
    "xlsx": 512,  # A minimal XLSX (ZIP) is ~512 bytes
    "pptx": 512,  # A minimal PPTX (ZIP) is ~512 bytes
    "odp": 512,  # A minimal ODP (ZIP) is ~512 bytes
    "html": 10,  # A minimal HTML file is ~10 bytes
}

# --- Expected MIME types ---
MIME_TYPES: dict = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "html": "text/html",
}


# --- ZIP-based Open XML format detection markers ---
# Each entry: (marker_function, mime_type)
# marker_function takes a list of names from zipfile.namelist() and returns True if it matches.
# Order matters: first match wins, so more specific formats should come first.
ZIP_FORMAT_MARKERS: list[tuple[Callable[[list[str]], bool], str]] = [
    # DOCX: requires word/ prefix (specific to Word documents)
    (
        lambda names: any(name.startswith("word/") for name in names),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    # XLSX: requires xl/ prefix (specific to Excel spreadsheets)
    (
        lambda names: any(name.startswith("xl/") for name in names),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    # PPTX: requires ppt/ prefix (specific to PowerPoint presentations)
    (
        lambda names: any(name.startswith("ppt/") for name in names),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    # ODP: requires mimetype OR content.xml (OpenDocument Presentation format)
    (
        lambda names: any(
            name == "mimetype" or name.startswith("content.xml") for name in names
        ),
        "application/vnd.oasis.opendocument.presentation",
    ),
    # ODT: requires mimetype OR content.xml (OpenDocument Text format)
    (
        lambda names: any(
            name == "mimetype" or name.startswith("content.xml") for name in names
        ),
        "application/vnd.oasis.opendocument.text",
    ),
]


def _detect_mime_type(file_bytes: bytes) -> str:
    """Basic MIME type detection via magic bytes (no external dependency).

    For ZIP-based formats (DOCX, ODT, XLSX), inspects the archive's file names via
    zipfile.ZipFile.namelist() instead of searching raw compressed bytes,
    which avoids false positives when marker strings appear in content.

    For OpenDocument formats (ODT, ODS), reads the mimetype file inside the ZIP
    for reliable detection since both formats share the same structure.

    Uses a generic ZIP format markers table (ZIP_FORMAT_MARKERS) for extensibility.
    """
    if file_bytes[:5] == b"%PDF-":
        return "application/pdf"
    if file_bytes[:4] == b"PK\x03\x04":
        # ZIP-based formats: inspect extracted file names for reliable detection
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                names = zf.namelist()
                for marker_fn, mime_type in ZIP_FORMAT_MARKERS:
                    if marker_fn(names):
                        # For OpenDocument formats, check the mimetype file for precise detection
                        if "opendocument" in mime_type and "mimetype" in names:
                            try:
                                detected_mime = zf.read("mimetype").decode("utf-8", errors="ignore").strip()
                                if detected_mime:
                                    return detected_mime
                            except (KeyError, zipfile.BadZipFile):
                                pass
                        return mime_type
        except zipfile.BadZipFile:
            pass
        return "application/zip"
    # HTML detection: check for common HTML markers, or any file starting with "<"
    # (files starting with "<" are already validated by magic bytes for the .html extension)
    try:
        text_preview = file_bytes[:1024].decode("utf-8", errors="ignore")
        text_preview = text_preview.lower()
        if any(
            marker in text_preview
            for marker in [
                "<html",
                "<!doctype html",
                "<head",
                "<body",
                "<!DOCTYPE html",
            ]
        ):
            return "text/html"
        # Fallback: any file starting with "<" is likely HTML (even without standard containers)
        if file_bytes[:1] == b"<":
            return "text/html"
    except Exception:
        pass
    return "application/octet-stream"


def _validate_docx_structure(file_bytes: bytes) -> str | None:
    """
    Validate the internal structure of a DOCX file (Office Open XML).

    Wrapper around _validate_openxml_structure with DOCX-specific required files.
    """
    required_files = [
        f.strip() for f in settings.docx_required_files.split(",") if f.strip()
    ]
    return _validate_openxml_structure(file_bytes, "docx", required_files)


def _validate_odt_structure(file_bytes: bytes) -> str | None:
    """
    Validate the internal structure of an ODT file (OpenDocument Text).

    Wrapper around _validate_openxml_structure with ODT-specific required files.
    """
    return _validate_openxml_structure(file_bytes, "odt", ["mimetype", "content.xml"])


def _validate_xlsx_structure(file_bytes: bytes) -> str | None:
    """
    Validate the internal structure of an XLSX file (Office Open XML Spreadsheet).

    Wrapper around _validate_openxml_structure with XLSX-specific required files.
    """
    required_files = [
        f.strip() for f in settings.xlsx_required_files.split(",") if f.strip()
    ]
    return _validate_openxml_structure(file_bytes, "xlsx", required_files)


def _validate_pptx_structure(file_bytes: bytes) -> str | None:
    """
    Validate the internal structure of a PPTX file (Office Open XML Presentation).

    Wrapper around _validate_openxml_structure with PPTX-specific required files.
    """
    return _validate_openxml_structure(
        file_bytes, "pptx", ["ppt/presentation.xml", "ppt/slides/slide1.xml"]
    )


def _validate_ods_structure(file_bytes: bytes) -> str | None:
    """
    Validate the internal structure of an ODS file (OpenDocument Spreadsheet).

    Wrapper around _validate_openxml_structure with ODS-specific required files.
    """
    required_files = [
        f.strip() for f in settings.ods_required_files.split(",") if f.strip()
    ]
    return _validate_openxml_structure(file_bytes, "ods", required_files)


def _validate_odp_structure(file_bytes: bytes) -> str | None:
    """
    Validate the internal structure of an ODP file (OpenDocument Presentation).

    Wrapper around _validate_openxml_structure with ODP-specific required files.
    """
    return _validate_openxml_structure(file_bytes, "odp", ["mimetype", "content.xml"])


def validate_file_content(file_bytes: bytes, ext: str) -> str | None:
    """
    Validate the content of an uploaded file.

    Checks:
    - Minimum size (empty or truncated file)
    - Magic bytes (header matches extension)
    - Detected MIME type (consistent with expected format)
    - ZIP bomb detection (for DOCX and other ZIP archives)
    - Valid DOCX structure (required files, safe paths)

    Args:
        file_bytes: Raw file content.
        ext: File extension (e.g., "pdf", "docx").

    Returns:
        None if the file is valid, or a descriptive error message.
    """
    size = len(file_bytes)

    # --- 1. Minimum size ---
    min_size = MIN_FILE_SIZES.get(ext, 0)
    if size == 0:
        return "Empty file. Please upload a valid document."
    if size < min_size:
        return (
            f"File too short ({size} bytes). The file is likely corrupted or truncated."
        )

    # --- 2. Magic bytes ---
    magic_info = MAGIC_BYTES.get(ext)
    if magic_info:
        expected_header, header_len = magic_info
        if not file_bytes[:header_len].startswith(
            expected_header[: min(header_len, len(expected_header))]
        ):
            actual = _detect_mime_type(file_bytes)
            return (
                f"Invalid file header for {ext.upper()} format. "
                f"The file does not start with the expected bytes "
                f"(detected type: {actual})."
            )

    # --- 3. MIME type ---
    detected_mime = _detect_mime_type(file_bytes)
    expected_mime = MIME_TYPES.get(ext)
    if expected_mime and detected_mime != expected_mime:
        return (
            f"Unexpected MIME type: {detected_mime} detected instead of {expected_mime}. "
            f"The file may be corrupted or not match the {ext.upper()} format."
        )

    # --- 4. ZIP bomb protection (for ZIP-based formats: DOCX, ODT) ---
    if ext == "docx":
        zip_error = _validate_zip_bomb(file_bytes)
        if zip_error:
            return zip_error

        # --- 5. DOCX structure validation ---
        docx_error = _validate_docx_structure(file_bytes)
        if docx_error:
            return docx_error

    elif ext == "odt":
        zip_error = _validate_zip_bomb(file_bytes)
        if zip_error:
            return zip_error

        # --- 5. ODT structure validation ---
        odt_error = _validate_odt_structure(file_bytes)
        if odt_error:
            return odt_error

    elif ext == "xlsx":
        zip_error = _validate_zip_bomb(file_bytes)
        if zip_error:
            return zip_error

        # --- 5. XLSX structure validation ---
        xlsx_error = _validate_xlsx_structure(file_bytes)
        if xlsx_error:
            return xlsx_error

    elif ext == "pptx":
        zip_error = _validate_zip_bomb(file_bytes)
        if zip_error:
            return zip_error

        # --- 5. PPTX structure validation ---
        pptx_error = _validate_pptx_structure(file_bytes)
        if pptx_error:
            return pptx_error

    elif ext == "ods":
        zip_error = _validate_zip_bomb(file_bytes)
        if zip_error:
            return zip_error

        # --- 5. ODS structure validation ---
        ods_error = _validate_ods_structure(file_bytes)
        if ods_error:
            return ods_error

    elif ext == "odp":
        zip_error = _validate_zip_bomb(file_bytes)
        if zip_error:
            return zip_error

        # --- 5. ODP structure validation ---
        odp_error = _validate_odp_structure(file_bytes)
        if odp_error:
            return odp_error

    logger.debug("Validation OK: ext=%s, size=%d, mime=%s", ext, size, detected_mime)
    return None
