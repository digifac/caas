"""Converter modules: PDF, DOCX, ODT, ODS, ODP, HTML, XLSX, and PPTX to Markdown."""

from app.converters.docx import convert_docx_to_md
from app.converters.html import convert_html_to_md
from app.converters.odp import convert_odp_to_md
from app.converters.ods import convert_ods_to_md
from app.converters.odt import convert_odt_to_md
from app.converters.pdf import convert_pdf_to_md
from app.converters.pptx import convert_pptx_to_md
from app.converters.xlsx import convert_xlsx_to_md

__all__ = [
    "convert_pdf_to_md",
    "convert_docx_to_md",
    "convert_odt_to_md",
    "convert_ods_to_md",
    "convert_odp_to_md",
    "convert_html_to_md",
    "convert_xlsx_to_md",
    "convert_pptx_to_md",
]
