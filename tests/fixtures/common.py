"""Common fixtures for all tests."""

from .docx import sample_docx_bytes  # noqa: E402
from .pdf import sample_pdf_bytes  # noqa: E402
from .pptx import sample_pptx_bytes  # noqa: E402

__all__ = [
    "async_client",
    "clean_caas_env",
    "disable_rate_limiting",
    "reset_task_manager",
    "sample_scanned_pdf_bytes",
    "sample_docx_bytes",
    "sample_pdf_bytes",
    "sample_pptx_bytes",
]

import asyncio
import io
import os
from typing import Any
import httpx
import pytest
from app.api import app


@pytest.fixture
def clean_caas_env(monkeypatch: Any) -> None:
    """Remove all CAAS_ environment variables to test default behavior."""
    keys_to_remove = [k for k in os.environ if k.startswith("CAAS_")]
    for key in keys_to_remove:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests."""
    app.state.rate_limiter.enabled = False
    yield


@pytest.fixture(autouse=True)
def reset_task_manager():
    """Reset the TaskManager between tests to prevent task accumulation.
    Also restores the original task_manager if a test replaced app.state.task_manager.
    """
    from app.api import app as main_app

    original_tm = main_app.state.task_manager
    original_tm.tasks.clear()
    original_tm.async_tasks.clear()
    original_tm.batches.clear()
    # Reset the semaphore so it's available again
    original_tm._semaphore = asyncio.Semaphore(original_tm.max_concurrent)
    yield
    # Restore original task_manager in case a test replaced it
    main_app.state.task_manager = original_tm
    original_tm.tasks.clear()
    original_tm.async_tasks.clear()
    original_tm.batches.clear()
    original_tm._semaphore = asyncio.Semaphore(original_tm.max_concurrent)


@pytest.fixture
async def async_client():
    """Async HTTP client for testing the FastAPI application."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Global fixtures (not specific to a format)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_scanned_pdf_bytes() -> bytes:
    """Generate a 'scanned' PDF (image with OCR-friendly text, no text layer)."""
    import io as _io

    from PIL import Image, ImageDraw, ImageFont

    # Create a larger image with a TrueType font for reliable OCR
    img = Image.new("RGB", (1200, 300), color="white")
    draw = ImageDraw.Draw(img)

    # Use the arial.ttf font provided in the tests folder
    font_path = os.path.join(os.path.dirname(__file__), "arial.ttf")
    font = ImageFont.truetype(font_path, 36)

    # Draw black text on white background (simulates a scanned document)
    draw.text((40, 100), "Document scanné en français", fill="black", font=font)
    img_bytes = _io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Create a PDF with the image using reportlab (no text layer)
    buf = io.BytesIO()
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader

    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img_bytes), 50, 50, width=495, height=200)  # type: ignore[attr-defined]
    c.save()
    buf.seek(0)
    return buf.getvalue()
