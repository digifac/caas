"""Independent OCR processing module.

Provides OCR capabilities that can be used by any converter.
Built on pypdfium2 (PDF rendering) + pytesseract (text recognition).
"""

import io
import logging

import pypdfium2 as pdfium
import pytesseract
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


def ocr_image(image: Image.Image, lang: str | None = None) -> str:
    """Run OCR on a PIL Image and return the extracted text.

    Args:
        image: A PIL Image object to process.
        lang: Optional language string for Tesseract (e.g., 'fra+eng').
              Defaults to settings.ocr_languages_resolved.

    Returns:
        The extracted text stripped of surrounding whitespace.
    """
    if lang is None:
        lang = settings.ocr_languages_resolved
    result: str = pytesseract.image_to_string(image, lang=lang)
    return result.strip()


def ocr_pdf_page(pdf_doc, page_number: int, lang: str | None = None) -> str:
    """Render a single PDF page to an image and run OCR on it (zero-disk I/O).

    Args:
        pdf_doc: An already-opened pypdfium2 PdfDocument object.
        page_number: Zero-based index of the page to OCR.
        lang: Optional language string for Tesseract.

    Returns:
        The extracted text stripped of surrounding whitespace.
    """
    page = pdf_doc[page_number]
    bitmap = page.render(scale=settings.ocr_scale)
    pil_image = bitmap.to_pil()

    try:
        text = ocr_image(pil_image, lang=lang)
    finally:
        pil_image.close()
    return text


def ocr_pdf_pages(
    file_bytes: bytes, page_numbers: list, lang: str | None = None
) -> dict:
    """Render multiple PDF pages to images and run OCR on all of them.

    Opens the PDF document only once, then processes all requested pages.

    Args:
        file_bytes: Raw bytes of the PDF document.
        page_numbers: List of zero-based page indices to OCR.
        lang: Optional language string for Tesseract.

    Returns:
        Dictionary mapping page_number -> extracted text.
    """
    pdf = pdfium.PdfDocument(file_bytes)
    results = {}
    try:
        for page_number in page_numbers:
            results[page_number] = ocr_pdf_page(pdf, page_number, lang=lang)
    finally:
        pdf.close()
    return results


def ocr_image_bytes(image_bytes: bytes, lang: str | None = None) -> str:
    """Run OCR on raw image bytes (any format supported by PIL).

    Args:
        image_bytes: Raw bytes of an image file (PNG, JPEG, etc.).
        lang: Optional language string for Tesseract.

    Returns:
        The extracted text stripped of surrounding whitespace.
    """
    img = None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return ocr_image(img, lang=lang)
    finally:
        if img:
            img.close()
