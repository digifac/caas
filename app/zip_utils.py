"""Shared ZIP / Open XML utilities for DOCX, ODT, and XLSX validation."""

import io
import logging
import zipfile

from app.config import settings

logger = logging.getLogger(__name__)


def _validate_zip_bomb(file_bytes: bytes) -> str | None:
    """
    ZIP bomb detection: analyzes the ZIP archive without decompressing it.

    Checks:
    - Compression ratio (decompressed size / compressed size)
    - Total decompressed size
    - Number of files in the archive
    - File name lengths
    - Nested files (ZIP in ZIP)

    Args:
        file_bytes: Raw ZIP file content.

    Returns:
        None if the archive is safe, or a descriptive error message.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            info_list = zf.infolist()

            # 1. Number of files
            if len(info_list) > settings.zip_max_files:
                return (
                    f"ZIP archive contains too many files "
                    f"({len(info_list)} > {settings.zip_max_files}). "
                    f"Possible ZIP bomb detected."
                )

            total_decompressed = 0
            compressed_size = len(file_bytes)

            for info in info_list:
                # 2. File name length
                if len(info.filename) > settings.zip_max_file_name_length:
                    return (
                        f"File name too long in ZIP archive "
                        f"({len(info.filename)} characters). "
                        f"Possible ZIP bomb detected."
                    )

                # 3. Decompressed size of each file
                decompressed_size = info.file_size
                total_decompressed += decompressed_size

                # 4. Compression ratio per file
                if info.compress_size > 0:
                    ratio = decompressed_size / info.compress_size
                    if ratio > settings.zip_max_compression_ratio:
                        return (
                            f"Compression ratio too high for '{info.filename}' "
                            f"({ratio:.1f}x > {settings.zip_max_compression_ratio}x). "
                            f"Possible ZIP bomb detected."
                        )

                # 5. Nested file detection (ZIP in ZIP)
                nested_exts = (
                    ".zip",
                    ".docx",
                    ".xlsx",
                    ".pptx",
                    ".odt",
                    ".ods",
                    ".jar",
                    ".apk",
                )
                if info.filename.lower().endswith(nested_exts):
                    return (
                        f"Nested ZIP archive detected: '{info.filename}'. "
                        f"Nested archives are not allowed for security reasons."
                    )

            # 6. Total decompressed size
            max_decompressed_bytes = (
                settings.zip_max_total_decompressed_mb * 1024 * 1024
            )
            if total_decompressed > max_decompressed_bytes:
                mb = total_decompressed / 1024 / 1024
                limit = settings.zip_max_total_decompressed_mb
                return (
                    f"Total decompressed size too large "
                    f"({mb:.1f} MB > {limit} MB). "
                    f"Possible ZIP bomb detected."
                )

            # 7. Global compression ratio
            if compressed_size > 0:
                global_ratio = total_decompressed / compressed_size
                if global_ratio > settings.zip_max_compression_ratio * 2:
                    return (
                        f"Global compression ratio too high "
                        f"({global_ratio:.1f}x). Possible ZIP bomb detected."
                    )

    except zipfile.BadZipFile:
        return "Invalid or corrupted ZIP archive."
    except Exception as e:
        logger.warning("Error during ZIP analysis: %s", e)
        return "Error analyzing the ZIP archive."

    return None


def _validate_openxml_structure(
    file_bytes: bytes, ext: str, required_files: list[str]
) -> str | None:
    """
    Validate the internal structure of an Open XML ZIP-based file.

    Checks:
    - The ZIP archive is valid
    - Required files are present
    - No suspicious paths (path traversal)

    Args:
        file_bytes: Raw file content.
        ext: File extension label (e.g., "DOCX", "ODT", "XLSX") for error messages.
        required_files: List of required file paths inside the archive.

    Returns:
        None if the structure is valid, or a descriptive error message.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            namelist = zf.namelist()

            # 1. Check required files
            missing = [f for f in required_files if f not in namelist]
            if missing:
                return (
                    f"Invalid {ext.upper()} file: "
                    f"missing required files ({', '.join(missing)}). "
                    f"The document is likely corrupted."
                )

            # 2. Check suspicious paths (path traversal)
            for name in namelist:
                if "/.." in name or "\\.." in name:
                    return (
                        f"Suspicious path detected in {ext.upper()}: '{name}'. "
                        f"Possible path traversal attempt."
                    )
                if name.startswith("/") or name.startswith("\\"):
                    return (
                        f"Absolute path detected in {ext.upper()}: '{name}'. "
                        f"Relative paths are expected."
                    )

    except zipfile.BadZipFile:
        return f"Invalid or corrupted {ext.upper()} archive."
    except Exception as e:
        logger.warning("Error during %s validation: %s", ext.upper(), e)
        return f"Error validating {ext.upper()} structure."

    return None
