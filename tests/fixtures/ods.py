"""Fixtures for ODS tests."""

__all__ = [
    "sample_ods_bytes",
    "sample_ods_multi_sheet_bytes",
    "sample_ods_empty_sheet_bytes",
    "sample_ods_special_chars_bytes",
]

import io
from typing import Any

import pytest


@pytest.fixture
def sample_ods_bytes() -> bytes:
    """Generate a minimal ODS spreadsheet file with one sheet and sample data using odfpy."""
    from odf import table, text  # type: ignore[attr-defined]
    from odf.opendocument import OpenDocumentSpreadsheet  # type: ignore[attr-defined]

    doc = OpenDocumentSpreadsheet()  # type: ignore[attr-defined]
    table_elem = table.Table(name="Feuille1")  # type: ignore[attr-defined]

    # Row 1: headers
    row1 = table.TableRow()  # type: ignore[attr-defined]
    c1 = table.TableCell()  # type: ignore[attr-defined]
    p1 = text.P()  # type: ignore[attr-defined]
    p1.addText("Nom")  # type: ignore[attr-defined]
    c1.addElement(p1)  # type: ignore[attr-defined]
    row1.addElement(c1)  # type: ignore[attr-defined]
    c2 = table.TableCell()  # type: ignore[attr-defined]
    p2 = text.P()  # type: ignore[attr-defined]
    p2.addText("Valeur")  # type: ignore[attr-defined]
    c2.addElement(p2)  # type: ignore[attr-defined]
    table_elem.addElement(row1)  # type: ignore[attr-defined]

    # Row 2: data
    row2 = table.TableRow()  # type: ignore[attr-defined]
    c3 = table.TableCell()  # type: ignore[attr-defined]
    p3 = text.P()  # type: ignore[attr-defined]
    p3.addText("A")  # type: ignore[attr-defined]
    c3.addElement(p3)  # type: ignore[attr-defined]
    row2.addElement(c3)  # type: ignore[attr-defined]
    c4 = table.TableCell()  # type: ignore[attr-defined]
    p4 = text.P()  # type: ignore[attr-defined]
    p4.addText("1")  # type: ignore[attr-defined]
    c4.addElement(p4)  # type: ignore[attr-defined]
    row2.addElement(c4)  # type: ignore[attr-defined]
    table_elem.addElement(row2)  # type: ignore[attr-defined]

    # Row 3: data
    row3 = table.TableRow()  # type: ignore[attr-defined]
    c5 = table.TableCell()  # type: ignore[attr-defined]
    p5 = text.P()  # type: ignore[attr-defined]
    p5.addText("B")  # type: ignore[attr-defined]
    c5.addElement(p5)  # type: ignore[attr-defined]
    row3.addElement(c5)  # type: ignore[attr-defined]
    c6 = table.TableCell()  # type: ignore[attr-defined]
    p6 = text.P()  # type: ignore[attr-defined]
    p6.addText("2")  # type: ignore[attr-defined]
    c6.addElement(p6)  # type: ignore[attr-defined]
    row3.addElement(c6)  # type: ignore[attr-defined]
    table_elem.addElement(row3)  # type: ignore[attr-defined]

    doc.spreadsheet.addElement(table_elem)  # type: ignore[attr-defined]

    buf = io.BytesIO()
    doc.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_multi_sheet_bytes() -> bytes:
    """Generate an ODS spreadsheet file containing multiple sheets using odfpy."""
    from odf import table, text  # type: ignore[attr-defined]
    from odf.opendocument import OpenDocumentSpreadsheet  # type: ignore[attr-defined]

    doc = OpenDocumentSpreadsheet()  # type: ignore[attr-defined]

    # Sheet 1: Données
    sheet1 = table.Table(name="Données")  # type: ignore[attr-defined]
    row1 = table.TableRow()  # type: ignore[attr-defined]
    c1 = table.TableCell()  # type: ignore[attr-defined]
    p1 = text.P()  # type: ignore[attr-defined]
    p1.addText("Produit")  # type: ignore[attr-defined]
    c1.addElement(p1)  # type: ignore[attr-defined]
    row1.addElement(c1)  # type: ignore[attr-defined]
    c2 = table.TableCell()  # type: ignore[attr-defined]
    p2 = text.P()  # type: ignore[attr-defined]
    p2.addText("Prix")  # type: ignore[attr-defined]
    c2.addElement(p2)  # type: ignore[attr-defined]
    sheet1.addElement(row1)  # type: ignore[attr-defined]

    row2 = table.TableRow()  # type: ignore[attr-defined]
    c3 = table.TableCell()  # type: ignore[attr-defined]
    p3 = text.P()  # type: ignore[attr-defined]
    p3.addText("Pomme")  # type: ignore[attr-defined]
    c3.addElement(p3)  # type: ignore[attr-defined]
    row2.addElement(c3)  # type: ignore[attr-defined]
    c4 = table.TableCell()  # type: ignore[attr-defined]
    p4 = text.P()  # type: ignore[attr-defined]
    p4.addText("1.5")  # type: ignore[attr-defined]
    c4.addElement(p4)  # type: ignore[attr-defined]
    sheet1.addElement(row2)  # type: ignore[attr-defined]

    row3 = table.TableRow()  # type: ignore[attr-defined]
    c5 = table.TableCell()  # type: ignore[attr-defined]
    p5 = text.P()  # type: ignore[attr-defined]
    p5.addText("Orange")  # type: ignore[attr-defined]
    c5.addElement(p5)  # type: ignore[attr-defined]
    row3.addElement(c5)  # type: ignore[attr-defined]
    c6 = table.TableCell()  # type: ignore[attr-defined]
    p6 = text.P()  # type: ignore[attr-defined]
    p6.addText("2.0")  # type: ignore[attr-defined]
    c6.addElement(p6)  # type: ignore[attr-defined]
    sheet1.addElement(row3)  # type: ignore[attr-defined]

    doc.spreadsheet.addElement(sheet1)  # type: ignore[attr-defined]

    # Sheet 2: Résumé
    sheet2 = table.Table(name="Résumé")  # type: ignore[attr-defined]
    row4 = table.TableRow()  # type: ignore[attr-defined]
    c7 = table.TableCell()  # type: ignore[attr-defined]
    p7 = text.P()  # type: ignore[attr-defined]
    p7.addText("Total")  # type: ignore[attr-defined]
    c7.addElement(p7)  # type: ignore[attr-defined]
    c8 = table.TableCell()  # type: ignore[attr-defined]
    p8 = text.P()  # type: ignore[attr-defined]
    p8.addText("3.5")  # type: ignore[attr-defined]
    c8.addElement(p8)  # type: ignore[attr-defined]
    sheet2.addElement(row4)  # type: ignore[attr-defined]

    doc.spreadsheet.addElement(sheet2)  # type: ignore[attr-defined]

    buf = io.BytesIO()
    doc.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_empty_sheet_bytes() -> bytes:
    """Generate an ODS file with an empty sheet using odfpy."""
    from odf import table  # type: ignore[attr-defined]
    from odf.opendocument import OpenDocumentSpreadsheet  # type: ignore[attr-defined]

    doc = OpenDocumentSpreadsheet()  # type: ignore[attr-defined]
    table_elem = table.Table(name="Vide")  # type: ignore[attr-defined]
    # No rows added — empty sheet
    doc.spreadsheet.addElement(table_elem)  # type: ignore[attr-defined]

    buf = io.BytesIO()
    doc.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_special_chars_bytes() -> bytes:
    """Generate an ODS file with special characters using odfpy."""
    from odf import table, text  # type: ignore[attr-defined]
    from odf.opendocument import OpenDocumentSpreadsheet  # type: ignore[attr-defined]

    doc = OpenDocumentSpreadsheet()  # type: ignore[attr-defined]
    table_elem = table.Table(name="Spécial")  # type: ignore[attr-defined]

    # Row 1: headers
    row1 = table.TableRow()  # type: ignore[attr-defined]
    c1 = table.TableCell()  # type: ignore[attr-defined]
    p1 = text.P()  # type: ignore[attr-defined]
    p1.addText("Colonne A")  # type: ignore[attr-defined]
    c1.addElement(p1)  # type: ignore[attr-defined]
    row1.addElement(c1)  # type: ignore[attr-defined]
    c2 = table.TableCell()  # type: ignore[attr-defined]
    p2 = text.P()  # type: ignore[attr-defined]
    p2.addText("Colonne B")  # type: ignore[attr-defined]
    c2.addElement(p2)  # type: ignore[attr-defined]
    row1.addElement(c2)  # type: ignore[attr-defined]
    table_elem.addElement(row1)  # type: ignore[attr-defined]

    # Row 2: pipe and backslash
    row2 = table.TableRow()  # type: ignore[attr-defined]
    c3 = table.TableCell()  # type: ignore[attr-defined]
    p3 = text.P()  # type: ignore[attr-defined]
    p3.addText("Texte avec | pipe")  # type: ignore[attr-defined]
    c3.addElement(p3)  # type: ignore[attr-defined]
    row2.addElement(c3)  # type: ignore[attr-defined]
    c4 = table.TableCell()  # type: ignore[attr-defined]
    p4 = text.P()  # type: ignore[attr-defined]
    p4.addText("Texte avec \\ backslash")  # type: ignore[attr-defined]
    c4.addElement(p4)  # type: ignore[attr-defined]
    row2.addElement(c4)  # type: ignore[attr-defined]
    table_elem.addElement(row2)  # type: ignore[attr-defined]

    # Row 3: accents
    row3 = table.TableRow()  # type: ignore[attr-defined]
    c5 = table.TableCell()  # type: ignore[attr-defined]
    p5 = text.P()  # type: ignore[attr-defined]
    p5.addText("Àéîôù")  # type: ignore[attr-defined]
    c5.addElement(p5)  # type: ignore[attr-defined]
    row3.addElement(c5)  # type: ignore[attr-defined]
    c6 = table.TableCell()  # type: ignore[attr-defined]
    p6 = text.P()  # type: ignore[attr-defined]
    p6.addText("Ñ ü ö ä")  # type: ignore[attr-defined]
    c6.addElement(p6)  # type: ignore[attr-defined]
    row3.addElement(c6)  # type: ignore[attr-defined]
    table_elem.addElement(row3)  # type: ignore[attr-defined]

    doc.spreadsheet.addElement(table_elem)  # type: ignore[attr-defined]

    buf = io.BytesIO()
    doc.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()
