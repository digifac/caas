"""Fixtures for XLSX tests."""

__all__ = [
    "sample_xlsx_bytes",
    "sample_xlsx_simple_bytes",  # Nouveau fixture pour les tests Markdown simples
    "sample_xlsx_multi_sheet_bytes",
    "sample_xlsx_merged_cells_bytes",
    "sample_xlsx_dates_numbers_bytes",
    "sample_xlsx_special_chars_bytes",
    "sample_xlsx_empty_sheet_bytes",
]

import io
from datetime import date, datetime
import pytest
from openpyxl import Workbook


@pytest.fixture
def sample_xlsx_bytes() -> bytes:
    """Generate a minimal XLSX file in memory with one sheet and several cells."""
    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Feuille1"
    
    # En-têtes - plusieurs colonnes pour générer plus de texte
    headers = ["ID", "Nom", "Description_détaillée", "Prix_unitaire", "Quantité_disponible", "Catégorie_produit"]
    for col, header in enumerate(headers, 1):
        ws[f"A{col}"] = header
    
    # Données - beaucoup de lignes avec du texte long pour générer des chunks
    descriptions = [
        "Ceci est une description très détaillée pour le produit numéro {i}. Ce texte est suffisamment long pour dépasser la taille de chunk par défaut de 1024 caractères lors de la conversion JSONL.",
        "Description complète du produit avec beaucoup d'informations techniques et des spécifications détaillées pour tester correctement le chunking.",
        "Ceci est une description très longue et détaillée pour le produit numéro {i}. Le texte doit être assez long pour générer plusieurs chunks lors de la conversion en format JSONL.",
    ]
    
    for i in range(2, 51):  # Lignes 2 à 50 (49 lignes de données)
        ws[f"A{i}"] = i
        ws[f"B{i}"] = f"Produit {i}"
        desc_idx = (i - 2) % len(descriptions)
        ws[f"C{i}"] = descriptions[desc_idx].format(i=i)
        ws[f"D{i}"] = float(i * 1.5)
        ws[f"E{i}"] = i * 10
        ws[f"F{i}"] = f"Catégorie_{i % 5}"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_simple_bytes() -> bytes:
    """Generate a minimal XLSX file with simple data for Markdown tests."""
    from openpyxl import Workbook

    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Feuille1"
    
    # En-têtes simples pour les tests Markdown (ligne 1)
    ws["A1"] = "Nom"
    ws["B1"] = "Valeur"
    
    # Données simples (lignes 2 à 6)
    for i in range(1, 6):
        ws[f"A{i+1}"] = f"Produit {i}"
        ws[f"B{i+1}"] = i

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_multi_sheet_bytes() -> bytes:
    """Generate an XLSX file containing multiple sheets."""
    from openpyxl import Workbook

    wb: Workbook = Workbook()
    ws1 = wb.active
    ws1.title = "Données"
    ws1["A1"] = "Produit"
    ws1["B1"] = "Prix"
    ws1["A2"] = "Pomme"
    ws1["B2"] = 1.5
    ws1["A3"] = "Orange"
    ws1["B3"] = 2.0

    ws2 = wb.create_sheet(title="Résumé")
    ws2["A1"] = "Total"
    ws2["B1"] = 3.5

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_merged_cells_bytes() -> bytes:
    """Generate an XLSX file containing merged cells."""
    from openpyxl import Workbook

    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Fusionné"
    ws["A1"] = "En-tête fusionné"
    ws.merge_cells("A1:C1")
    ws["A2"] = "Col1"
    ws["B2"] = "Col2"
    ws["C2"] = "Col3"
    ws["A3"] = "v1"
    ws["B3"] = "v2"
    ws["C3"] = "v3"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_dates_numbers_bytes() -> bytes:
    """Generate an XLSX file containing dates and numeric values."""
    from openpyxl import Workbook

    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Types"
    ws["A1"] = "Texte"
    ws["B1"] = "Nombre"
    ws["C1"] = "Date"
    ws["D1"] = "Booléen"
    ws["A2"] = "hello"
    ws["B2"] = 42.5
    ws["C2"] = date(2024, 1, 15)
    ws["D2"] = True
    ws["A3"] = "world"
    ws["B3"] = -10
    ws["C3"] = datetime(2024, 6, 30, 12, 0, 0)
    ws["D3"] = False

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_special_chars_bytes() -> bytes:
    """Generate an XLSX file containing Markdown special characters."""
    from openpyxl import Workbook

    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Spécial"
    ws["A1"] = "Colonne A"
    ws["B1"] = "Colonne B"
    ws["A2"] = "Texte avec | pipe"
    ws["B2"] = "Texte avec \\ backslash"
    ws["A3"] = "Ligne 1\nLigne 2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_empty_sheet_bytes() -> bytes:
    """Generate an XLSX file containing an empty sheet."""
    from openpyxl import Workbook

    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Vide"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
