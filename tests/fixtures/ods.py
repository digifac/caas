"""Fixtures for ODS tests."""

__all__ = [
    "sample_ods_bytes",
    "sample_ods_multi_sheet_bytes",
    "sample_ods_empty_sheet_bytes",
    "sample_ods_special_chars_bytes",
]

import io
import pytest


@pytest.fixture
def sample_ods_bytes() -> bytes:
    """Generate a minimal ODS spreadsheet file with one sheet and sample data using odfpy."""
    from odf import table, text
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table_elem = table.Table(name="Feuille1")

    # Row 1: headers - plusieurs colonnes pour générer plus de texte
    headers = ["ID", "Nom", "Description_détaillée", "Prix_unitaire", "Quantité_disponible", "Catégorie_produit"]
    for _col, header in enumerate(headers, 1):
        c = table.TableCell()
        p = text.P()
        p.addText(header)
        c.addElement(p)
        row1 = table.TableRow()
        row1.addElement(c)
        table_elem.addElement(row1)

    # Descriptions variées pour générer du texte long
    descriptions = [
        "Ceci est une description très détaillée pour le produit numéro {i}. Ce texte est suffisamment long pour dépasser la taille de chunk par défaut de 1024 caractères lors de la conversion JSONL.",
        "Description complète du produit avec beaucoup d'informations techniques et des spécifications détaillées pour tester correctement le chunking.",
        "Ceci est une description très longue et détaillée pour le produit numéro {i}. Le texte doit être assez long pour générer plusieurs chunks lors de la conversion en format JSONL.",
    ]

    # Multiple rows of data to generate chunks
    for i in range(2, 51):  # Lignes 2 à 50 (49 lignes de données)
        row = table.TableRow()
        
        c_id = table.TableCell()
        p_id = text.P()
        p_id.addText(str(i))
        c_id.addElement(p_id)
        row.addElement(c_id)

        c_nom = table.TableCell()
        p_nom = text.P()
        p_nom.addText(f"Produit {i}")
        c_nom.addElement(p_nom)
        row.addElement(c_nom)

        desc_idx = (i - 2) % len(descriptions)
        c_desc = table.TableCell()
        p_desc = text.P()
        p_desc.addText(descriptions[desc_idx].format(i=i))
        c_desc.addElement(p_desc)
        row.addElement(c_desc)

        c_price = table.TableCell()
        p_price = text.P()
        p_price.addText(str(float(i * 1.5)))
        c_price.addElement(p_price)
        row.addElement(c_price)

        c_qty = table.TableCell()
        p_qty = text.P()
        p_qty.addText(str(i * 10))
        c_qty.addElement(p_qty)
        row.addElement(c_qty)

        c_cat = table.TableCell()
        p_cat = text.P()
        p_cat.addText(f"Catégorie_{i % 5}")
        c_cat.addElement(p_cat)
        row.addElement(c_cat)

        table_elem.addElement(row)

    doc.spreadsheet.addElement(table_elem)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_multi_sheet_bytes() -> bytes:
    """Generate an ODS spreadsheet file containing multiple sheets using odfpy."""
    from odf import table, text
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()

    # Sheet 1: Données
    sheet1 = table.Table(name="Données")
    row1 = table.TableRow()
    c1 = table.TableCell()
    p1 = text.P()
    p1.addText("Produit")
    c1.addElement(p1)
    row1.addElement(c1)
    c2 = table.TableCell()
    p2 = text.P()
    p2.addText("Prix")
    c2.addElement(p2)
    row1.addElement(c2)
    sheet1.addElement(row1)

    row2 = table.TableRow()
    c3 = table.TableCell()
    p3 = text.P()
    p3.addText("Pomme")
    c3.addElement(p3)
    row2.addElement(c3)
    c4 = table.TableCell()
    p4 = text.P()
    p4.addText("1.5")
    c4.addElement(p4)
    row2.addElement(c4)
    sheet1.addElement(row2)

    row3 = table.TableRow()
    c5 = table.TableCell()
    p5 = text.P()
    p5.addText("Orange")
    c5.addElement(p5)
    row3.addElement(c5)
    c6 = table.TableCell()
    p6 = text.P()
    p6.addText("2.0")
    c6.addElement(p6)
    row3.addElement(c6)
    sheet1.addElement(row3)

    doc.spreadsheet.addElement(sheet1)

    # Sheet 2: Résumé
    sheet2 = table.Table(name="Résumé")
    row4 = table.TableRow()
    c7 = table.TableCell()
    p7 = text.P()
    p7.addText("Total")
    c7.addElement(p7)
    row4.addElement(c7)
    c8 = table.TableCell()
    p8 = text.P()
    p8.addText("3.5")
    c8.addElement(p8)
    row4.addElement(c8)
    sheet2.addElement(row4)

    doc.spreadsheet.addElement(sheet2)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_empty_sheet_bytes() -> bytes:
    """Generate an ODS file with an empty sheet using odfpy."""
    from odf import table
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table_elem = table.Table(name="Vide")
    # No rows added — empty sheet
    doc.spreadsheet.addElement(table_elem)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_ods_special_chars_bytes() -> bytes:
    """Generate an ODS file with special characters using odfpy."""
    from odf import table, text
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table_elem = table.Table(name="Spécial")

    # Row 1: headers
    row1 = table.TableRow()
    c1 = table.TableCell()
    p1 = text.P()
    p1.addText("Colonne A")
    c1.addElement(p1)
    row1.addElement(c1)
    c2 = table.TableCell()
    p2 = text.P()
    p2.addText("Colonne B")
    c2.addElement(p2)
    row1.addElement(c2)
    table_elem.addElement(row1)

    # Row 2: pipe and backslash
    row2 = table.TableRow()
    c3 = table.TableCell()
    p3 = text.P()
    p3.addText("Texte avec | pipe")
    c3.addElement(p3)
    row2.addElement(c3)
    c4 = table.TableCell()
    p4 = text.P()
    p4.addText("Texte avec \\ backslash")
    c4.addElement(p4)
    row2.addElement(c4)
    table_elem.addElement(row2)

    # Row 3: accents
    row3 = table.TableRow()
    c5 = table.TableCell()
    p5 = text.P()
    p5.addText("Àéîôù")
    c5.addElement(p5)
    row3.addElement(c5)
    c6 = table.TableCell()
    p6 = text.P()
    p6.addText("Ñ ü ö ä")
    c6.addElement(p6)
    row3.addElement(c6)
    table_elem.addElement(row3)

    doc.spreadsheet.addElement(table_elem)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
