"""Tests for PPTX to Markdown conversion."""

from typing import Any, Dict, Optional

import httpx
import pytest
from app.api import create_app
from app.converters.pptx import convert_pptx_to_md
from app.validation import validate_file_content
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

# Import PPTX-specific fixtures directly from fixture modules
from tests.fixtures.pptx import (
    sample_pptx_bytes,
    sample_pptx_empty_slide_bytes,
    sample_pptx_with_table_bytes,
)


@pytest.fixture
def app():
    """Create a test application."""
    return create_app()


@pytest.fixture
def client(app: Any) -> StarletteTestClient:
    """Create a sync test client for streaming tests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app: Any) -> Any:
    """Async HTTP client for testing the FastAPI application."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# =============================================================================
# Tests unitaires — convert_pptx_to_md
# =============================================================================


class TestConvertPptxToMdBasic:
    """Tests for basic PPTX to Markdown conversion."""

    def test_convert_pptx_to_md_basic(self, sample_pptx_bytes: bytes) -> None:
        """Conversion d'une présentation simple."""
        result = convert_pptx_to_md(sample_pptx_bytes)
        assert "## Présentation de Test" in result
        assert "Sous-titre de la présentation" in result

    def test_convert_pptx_to_md_multiple_slides(self, sample_pptx_bytes: bytes) -> None:
        """Plusieurs slides."""
        result = convert_pptx_to_md(sample_pptx_bytes)
        assert "## Présentation de Test" in result
        assert "## Deuxième Slide" in result
        # Slides should be separated by ---
        assert "---" in result

    def test_convert_pptx_to_md_with_title(self, sample_pptx_bytes: bytes) -> None:
        """Slide avec titre."""
        result = convert_pptx_to_md(sample_pptx_bytes)
        assert "## Présentation de Test" in result
        assert "## Deuxième Slide" in result

    def test_convert_pptx_to_md_with_bullets(self, sample_pptx_bytes: bytes) -> None:
        """Listes à puces."""
        result = convert_pptx_to_md(sample_pptx_bytes)
        assert "Premier point" in result
        assert "Deuxième point" in result
        assert "Sous-point" in result

    def test_convert_pptx_to_md_with_table(
        self, sample_pptx_with_table_bytes: bytes
    ) -> None:
        """Tableau dans une slide."""
        result = convert_pptx_to_md(sample_pptx_with_table_bytes)
        assert "Slide avec Tableau" in result
        assert "En-tête 1" in result
        assert "En-tête 2" in result
        assert "En-tête 3" in result
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "1" in result
        assert "2" in result
        assert "3" in result
        # Markdown table format
        assert "| En-tête 1 |" in result
        assert "| --- |" in result

    def test_convert_pptx_to_md_empty_slide(
        self, sample_pptx_empty_slide_bytes: bytes
    ) -> None:
        """Slide vide."""
        result = convert_pptx_to_md(sample_pptx_empty_slide_bytes)
        # Even an empty slide should have a slide header
        assert "## Slide 1" in result

    def test_convert_pptx_to_md_mocked(self, sample_pptx_bytes: bytes) -> None:
        """Test avec python-pptx mocké (vérifie que le résultat est une chaîne)."""
        result = convert_pptx_to_md(sample_pptx_bytes)
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# Tests d'intégration — API endpoints
# =============================================================================


class TestConvertPptxIntegration:
    """Tests for PPTX conversion via API endpoints."""

    @pytest.mark.anyio
    async def test_convert_pptx_success(
        self, async_client: httpx.AsyncClient, sample_pptx_bytes: bytes
    ):
        """POST /convert avec fichier valide."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.pptx",
                    sample_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "markdown" in data
        assert "## Présentation de Test" in data["markdown"]

    @pytest.mark.anyio
    async def test_convert_pptx_uppercase_ext(
        self, async_client: httpx.AsyncClient, sample_pptx_bytes: bytes
    ):
        """Extension .PPTX en majuscules."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.PPTX",
                    sample_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "markdown" in data

    @pytest.mark.anyio
    async def test_convert_async_pptx_completes(
        self, async_client: httpx.AsyncClient, sample_pptx_bytes: bytes
    ):
        """Tâche asynchrone PPTX."""
        response = await async_client.post(
            "/convert?async=true",
            files={
                "file": (
                    "test.pptx",
                    sample_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data
        assert data["status"] == "pending"

        # Wait for task to complete
        import asyncio

        task_id = data["task_id"]
        task_data: Optional[Dict[str, Any]] = None
        last_task_data: Dict[str, Any] = {}
        for _ in range(30):  # Max 30 seconds
            await asyncio.sleep(0.5)
            task_response = await async_client.get(f"/task/{task_id}")
            last_task_data = task_response.json()
            if last_task_data["status"] == "completed":
                task_data = last_task_data
                break
        if task_data is None:
            task_data = last_task_data
        assert task_data is not None
        assert task_data["status"] == "completed"
        assert "markdown" in task_data["result"]
        assert "## Présentation de Test" in task_data["result"]["markdown"]

    def test_convert_pptx_streaming(
        self, client: StarletteTestClient, sample_pptx_bytes: bytes
    ) -> None:
        """Streaming SSE pour PPTX (TestClient sync — StreamingResponse non supporté par httpx.AsyncClient)."""
        response = client.post(
            "/convert?streaming=true",
            files={
                "file": (
                    "test.pptx",
                    sample_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        # The response should contain SSE data
        text = response.text
        assert "data:" in text
        # Should have start and complete events
        events: list[str] = [line for line in text.split("\n") if line.startswith("data:")]
        assert len(events) >= 2


# =============================================================================
# Tests de validation
# =============================================================================


class TestValidatePptx:
    """Tests for PPTX file validation."""

    def test_validate_pptx_magic_bytes(
        self, sample_pptx_bytes: bytes
    ) -> None:
        """Détection par magic bytes."""
        error = validate_file_content(sample_pptx_bytes, "pptx")
        assert error is None

    def test_validate_pptx_mime_type(
        self, sample_pptx_bytes: bytes
    ) -> None:
        """Validation MIME."""
        error = validate_file_content(sample_pptx_bytes, "pptx")
        assert error is None

    def test_validate_pptx_zip_structure(
        self, sample_pptx_bytes: bytes
    ) -> None:
        """Validation structure ZIP."""
        error = validate_file_content(sample_pptx_bytes, "pptx")
        assert error is None

    def test_validate_pptx_min_size(self) -> None:
        """Taille minimale."""
        # A minimal PPTX should be at least 512 bytes
        small_bytes = b"PK\x03\x04" + b"\x00" * 100  # Too small
        error = validate_file_content(small_bytes, "pptx")
        assert error is not None
        assert "too short" in error.lower() or "corrupted" in error.lower()

    def test_validate_pptx_invalid_header(self) -> None:
        """En-tête invalide."""
        invalid_bytes = b"This is not a PPTX file" + b"\x00" * 600
        error = validate_file_content(invalid_bytes, "pptx")
        assert error is not None
        assert "header" in error.lower() or "invalid" in error.lower()

    def test_validate_pptx_empty_file(self) -> None:
        """Fichier vide."""
        error = validate_file_content(b"", "pptx")
        assert error is not None
        assert "empty" in error.lower()


@pytest.mark.asyncio
async def test_convert_pptx_to_json(
    async_client: Any, sample_pptx_bytes: bytes
) -> None:
    """Upload valid PPTX → JSON with slides."""
    response = await async_client.post(
        "/convert",
        files={
            "file": (
                "test.pptx",
                sample_pptx_bytes,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
        params={"format": "json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["format"] == "pptx"
    assert "json" in data
    
    json_data = data["json"]
    # PPTX should have slides with content
    if "slides" in json_data:
        assert isinstance(json_data["slides"], list)
        assert len(json_data["slides"]) > 0


@pytest.mark.asyncio
async def test_convert_pptx_to_jsonl(
    async_client: Any, sample_pptx_bytes: bytes
) -> None:
    """Upload valid PPTX → JSONL with events."""
    response = await async_client.post(
        "/convert",
        files={
            "file": (
                "test.pptx",
                sample_pptx_bytes,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
        params={"format": "jsonl"},
    )
    assert response.status_code == 200
    data = response.json()
    
    jsonl_data: list[dict[str, Any]] = data["jsonl"]
    assert len(jsonl_data) >= 3
    
    # Verify event types (each item is now a dict with "type" field)
    event_types: list[str] = [e.get("type", "") for e in jsonl_data]
    assert "start" in event_types
    assert "end" in event_types
    
    # Verify that events have proper structure (not JSON strings)
    start_event = next((e for e in jsonl_data if e.get("type") == "start"), None)
    end_event = next((e for e in jsonl_data if e.get("type") == "end"), None)
    
    assert start_event is not None, "Missing start event"
    assert end_event is not None, "Missing end event"
    assert isinstance(start_event["metadata"], dict), "Start event metadata should be a dict"
    assert isinstance(end_event["metadata"], dict), "End event metadata should be a dict"
