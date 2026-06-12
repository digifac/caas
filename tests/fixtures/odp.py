# type: ignore

"""Fixtures for ODP tests using odfpy."""

__all__ = [
    "sample_odp_bytes",
    "sample_odp_multi_sheet_bytes",
    "sample_odp_empty_slide_bytes",
    "sample_odp_with_list_bytes",
    "sample_odp_with_special_chars_bytes",
    "sample_odp_with_groups_bytes",
]

import io
from odf import opendocument, office  # type: ignore[import-untyped]
from odf.text import P, List, ListItem  # type: ignore[import-untyped]
from odf import draw  # type: ignore[import-untyped]

import pytest


def _create_odp_with_content(texts: list[str]) -> bytes:
    """Create a minimal ODP with text frames containing paragraphs.
    
    Args:
        texts: List of paragraph texts to add as separate slides.
        
    Returns:
        ODP document as bytes.
    """
    doc = opendocument.OpenDocumentPresentation()
    pres_el = office.Presentation()
    
    for idx, text_content in enumerate(texts):
        page = draw.Page(masterpagename='dp0')
        frame = draw.Frame(name=f'frame_{idx}', width='10cm', height='5cm')
        txt_frame = draw.TextBox()
        para = P(text=text_content)
        txt_frame.addElement(para)
        frame.addElement(txt_frame)
        page.addElement(frame)
        pres_el.addElement(page)
    
    doc.body.appendChild(pres_el)
    
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odp_bytes() -> bytes:
    """Generate a minimal ODP presentation document with two slides in memory using odfpy."""
    return _create_odp_with_content([
        "Présentation de Test",
        "Sous-titre de la présentation",
        "Deuxième Slide"
    ])


@pytest.fixture
def sample_odp_multi_sheet_bytes() -> bytes:
    """Generate an ODP with multiple paragraphs representing slides."""
    return _create_odp_with_content([
        "Titre de la présentation",
        "Contenu principal", 
        "Conclusion"
    ])


@pytest.fixture
def sample_odp_empty_slide_bytes() -> bytes:
    """Generate an ODP presentation document containing an empty slide using odfpy."""
    doc = opendocument.OpenDocumentPresentation()
    
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odp_with_list_bytes() -> bytes:
    """Generate an ODP document with list items using odfpy."""
    doc = opendocument.OpenDocumentPresentation()
    pres_el = office.Presentation()
    
    page = draw.Page(masterpagename='dp0')
    frame = draw.Frame(name='frame_list', width='10cm', height='5cm')
    txt_frame = draw.TextBox()
    
    # Add title paragraph
    title = P(text="Liste de courses")
    txt_frame.addElement(title)
    
    # Add list items
    liste = List()
    for item_text in ["Pommes", "Bananes", "Oranges"]:
        list_item = ListItem()
        para = P(text=item_text)
        list_item.addElement(para)
        liste.addElement(list_item)
    
    txt_frame.addElement(liste)
    frame.addElement(txt_frame)
    page.addElement(frame)
    pres_el.addElement(page)
    doc.body.appendChild(pres_el)
    
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_odp_with_special_chars_bytes() -> bytes:
    """Generate an ODP document with special characters using odfpy."""
    texts = ["Caractères spéciaux", "Àéîôù © € £ ¥", "Accents et symboles"]
    return _create_odp_with_content(texts)


@pytest.fixture  
def sample_odp_with_groups_bytes() -> bytes:
    """Generate an ODP document with grouped content using odfpy."""
    texts = ["Groupe de contenu", "Plusieurs éléments", "Titre dans un groupe"]
    return _create_odp_with_content(texts)
