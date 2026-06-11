"""Fixtures for PPTX tests."""

__all__ = [
    "sample_pptx_bytes",
    "sample_pptx_with_table_bytes",
    "sample_pptx_empty_slide_bytes",
]

import io
from typing import Any

import pytest


@pytest.fixture
def sample_pptx_bytes() -> bytes:
    """Generate a minimal PPTX presentation in memory using python-pptx."""
    from pptx import Presentation  # type: ignore[misc]

    prs: Presentation = Presentation()  # type: ignore[misc]

    # Slide 1: title slide
    slide_layout = prs.slide_layouts[0]  # type: ignore[attr-defined]  # type: ignore[attr-defined]
    slide = prs.slides.add_slide(slide_layout)  # type: ignore[attr-defined]
    slide.shapes.title.text = "Présentation de Test"  # type: ignore[attr-defined]
    slide.placeholders[1].text = "Sous-titre de la présentation"  # type: ignore[attr-defined]

    # Slide 2: title + content with bullets
    slide_layout = prs.slide_layouts[1]  # type: ignore[attr-defined]
    slide = prs.slides.add_slide(slide_layout)  # type: ignore[attr-defined]
    slide.shapes.title.text = "Deuxième Slide"  # type: ignore[attr-defined]
    body_shape = slide.placeholders[1]  # type: ignore[attr-defined]
    tf = body_shape.text_frame  # type: ignore[attr-defined]
    tf.text = "Premier point"  # type: ignore[attr-defined]
    p = tf.add_paragraph()  # type: ignore[attr-defined]
    p.text = "Deuxième point"  # type: ignore[attr-defined]
    p.level = 0
    p = tf.add_paragraph()  # type: ignore[attr-defined]
    p.text = "Sous-point"  # type: ignore[attr-defined]
    p.level = 1

    buf = io.BytesIO()
    prs.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_with_table_bytes() -> bytes:
    """Generate a PPTX presentation containing a table in memory using python-pptx."""
    from pptx import Presentation  # type: ignore[misc]
    from pptx.util import Inches  # type: ignore[misc]

    prs = Presentation()  # type: ignore[misc]

    # Slide with table
    slide_layout = prs.slide_layouts[5]  # type: ignore[attr-defined]
    slide = prs.slides.add_slide(slide_layout)  # type: ignore[attr-defined]

    # Add title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.5))  # type: ignore[attr-defined]
    title_box.text = "Slide avec Tableau"  # type: ignore[attr-defined]

    # Add table
    rows = 3
    cols = 3
    left = Inches(1)
    top = Inches(1)
    width = Inches(6)
    height = Inches(2)
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)  # type: ignore[attr-defined]
    table = table_shape.table  # type: ignore[attr-defined]

    table.cell(0, 0).text = "En-tête 1"  # type: ignore[attr-defined]
    table.cell(0, 1).text = "En-tête 2"  # type: ignore[attr-defined]
    table.cell(0, 2).text = "En-tête 3"  # type: ignore[attr-defined]
    table.cell(1, 0).text = "A"  # type: ignore[attr-defined]
    table.cell(1, 1).text = "B"  # type: ignore[attr-defined]
    table.cell(1, 2).text = "C"  # type: ignore[attr-defined]
    table.cell(2, 0).text = "1"  # type: ignore[attr-defined]
    table.cell(2, 1).text = "2"  # type: ignore[attr-defined]
    table.cell(2, 2).text = "3"  # type: ignore[attr-defined]

    buf = io.BytesIO()
    prs.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_empty_slide_bytes() -> bytes:
    """Generate a PPTX presentation containing an empty slide in memory using python-pptx."""
    from pptx import Presentation  # type: ignore[misc]

    prs = Presentation()  # type: ignore[misc]
    slide_layout = prs.slide_layouts[6]  # type: ignore[attr-defined]
    prs.slides.add_slide(slide_layout)  # type: ignore[attr-defined]
    # No content added — empty slide

    buf = io.BytesIO()
    prs.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    return buf.getvalue()
