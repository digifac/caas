"""Tests for ODP to Markdown conversion."""

import httpx
import pytest
from app.converters.odp import convert_odp_to_md

# Import fixtures from modules
from tests.fixtures.odp import (
    sample_odp_bytes, # type: ignore[import-not-found]
    sample_odp_with_list_bytes, # type: ignore[import-not-found]
    sample_odp_with_special_chars_bytes, # type: ignore[import-not-found]
    sample_odp_with_groups_bytes, # type: ignore[import-not-found]
  )

# =============================================================================
# Unit tests — convert_odp_to_md
# =============================================================================


class TestConvertOdpToMd:
    """Unit tests for the convert_odp_to_md function."""

    def test_basic_slides(self, sample_odp_bytes: bytes):
        """ODP with basic slides returns correct markdown."""
        markdown = convert_odp_to_md(sample_odp_bytes)
        assert "Présentation de Test" in markdown
        assert "Sous-titre de la présentation" in markdown
        assert "Deuxième Slide" in markdown

    def test_slide_separators(self, sample_odp_bytes: bytes):
        """Slides are separated by --- in markdown output."""
        markdown = convert_odp_to_md(sample_odp_bytes)
        assert "---" in markdown

    def test_slide_headers(self, sample_odp_bytes: bytes):
        """Slide titles appear as ## headers (generic slide headers when no title style)."""
        markdown = convert_odp_to_md(sample_odp_bytes)
        assert "## Slide 1" in markdown
        assert "Présentation de Test" in markdown
        assert "## Slide 3" in markdown
        assert "Deuxième Slide" in markdown

    def test_list_items(self, sample_odp_with_list_bytes: bytes):
        """ODP with list items produces markdown content."""
        markdown = convert_odp_to_md(sample_odp_with_list_bytes)
        assert "Liste de courses" in markdown
        assert "Pommes" in markdown
        assert "Oranges" in markdown
        assert "Bananes" in markdown

    def test_special_characters(self, sample_odp_with_special_chars_bytes: bytes):
        """ODP with special characters preserves them correctly."""
        markdown = convert_odp_to_md(sample_odp_with_special_chars_bytes)
        assert "Caractères spéciaux" in markdown
        assert "Àéîôù" in markdown
        assert "©" in markdown
        assert "€" in markdown

    def test_groups_in_odp(self, sample_odp_with_groups_bytes: bytes):
        """ODP with grouped content extracts all slide texts."""
        markdown = convert_odp_to_md(sample_odp_with_groups_bytes)
        assert "Groupe de contenu" in markdown
        assert "Plusieurs éléments" in markdown
        assert "Titre dans un groupe" in markdown

    def test_returns_string(self, sample_odp_bytes: bytes):
        """convert_odp_to_md returns a string."""
        result = convert_odp_to_md(sample_odp_bytes)
        assert isinstance(result, str)

    def test_no_trailing_whitespace(self, sample_odp_bytes: bytes):
        """Result is stripped of leading/trailing whitespace."""
        markdown = convert_odp_to_md(sample_odp_bytes)
        assert markdown == markdown.strip()

    def test_empty_odp(self, sample_odp_bytes: bytes):
        """ODP conversion produces non-empty result for valid input."""
        markdown = convert_odp_to_md(sample_odp_bytes)
        assert len(markdown) > 0


# =============================================================================
# Integration tests — /convert endpoint (sync)
# =============================================================================


class TestConvertOdpEndpoint:
    """Integration tests for ODP conversion via the /convert endpoint."""

    @pytest.mark.anyio
    async def test_convert_odp_success(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert with a valid ODP returns markdown."""
        response = await async_client.post(
            "/convert", files={"file": ("test.odp", sample_odp_bytes)}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "markdown" in data
        assert data["format"] == "odp"
        assert data["size_bytes"] == len(sample_odp_bytes)
        assert "Présentation de Test" in data["markdown"]

    @pytest.mark.anyio
    async def test_convert_odp_with_list(
        self, async_client: httpx.AsyncClient, sample_odp_with_list_bytes: bytes
    ):
        """POST /convert with ODP containing lists returns correct markdown."""
        response = await async_client.post(
            "/convert", files={"file": ("list.odp", sample_odp_with_list_bytes)}
        )
        assert response.status_code == 200
        markdown = response.json()["markdown"]
        assert "Liste de courses" in markdown
        assert "Pommes" in markdown
        assert "Oranges" in markdown
        assert "Bananes" in markdown

    @pytest.mark.anyio
    async def test_convert_odp_special_chars(
        self,
        async_client: httpx.AsyncClient,
        sample_odp_with_special_chars_bytes: bytes,
    ):
        """POST /convert with ODP containing special characters preserves them."""
        response = await async_client.post(
            "/convert",
            files={"file": ("special.odp", sample_odp_with_special_chars_bytes)},
        )
        assert response.status_code == 200
        markdown = response.json()["markdown"]
        assert "Àéîôù" in markdown
        assert "€" in markdown

    @pytest.mark.anyio
    async def test_convert_odp_response_structure(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert with ODP returns expected response keys."""
        response = await async_client.post(
            "/convert", files={"file": ("test.odp", sample_odp_bytes)}
        )
        data = response.json()
        assert "success" in data
        assert "markdown" in data
        assert "format" in data
        assert "size_bytes" in data

    @pytest.mark.anyio
    async def test_convert_odp_uppercase_ext(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert with .ODP extension works."""
        response = await async_client.post(
            "/convert", files={"file": ("test.ODP", sample_odp_bytes)}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["format"] == "odp"


# =============================================================================
# Integration tests — /convert endpoint (async)
# =============================================================================


class TestConvertOdpAsyncEndpoint:
    """Integration tests for ODP conversion via the /convert?async=true endpoint."""

    @pytest.mark.anyio
    async def test_convert_odp_async_success(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert?async=true with a valid ODP returns task id."""
        response = await async_client.post(
            "/convert?async=true",
            files={"file": ("test.odp", sample_odp_bytes)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_convert_odp_async_and_retrieve(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert?async=true then GET /task/<task_id> returns markdown."""
        post_response = await async_client.post(
            "/convert?async=true",
            files={"file": ("test.odp", sample_odp_bytes)},
        )
        assert post_response.status_code == 200
        task_id = post_response.json()["task_id"]

        # Poll for result
        import asyncio

        for _ in range(20):
            await asyncio.sleep(0.1)
            get_response = await async_client.get(f"/task/{task_id}")
            if get_response.status_code == 200:
                data = get_response.json()
                if data.get("status") == "completed":
                    assert "result" in data
                    assert "markdown" in data["result"]
                    assert "Présentation de Test" in data["result"]["markdown"]
                    return

        # If we get here, the task didn't complete in time
        raise AssertionError("Task did not complete within timeout")


# =============================================================================
# Integration tests — /convert/batch (sync)
# =============================================================================


class TestConvertOdpBatchSync:
    """Integration tests for ODP batch conversion via /convert/batch (sync)."""

    @pytest.mark.anyio
    async def test_batch_convert_odp_success(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert/batch with valid ODP files returns markdown."""
        response = await async_client.post(
            "/convert/batch",
            files=[
                ("files", ("slide1.odp", sample_odp_bytes)),
                ("files", ("slide2.odp", sample_odp_bytes)),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["total_files"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2
        for result in data["results"]:
            assert result["success"] is True
            assert "Présentation de Test" in result["markdown"]

    @pytest.mark.anyio
    async def test_batch_convert_odp_mixed_formats(
        self,
        async_client: httpx.AsyncClient,
        sample_odp_bytes: bytes,
        sample_odt_bytes: bytes,
    ):
        """POST /convert/batch with ODP + ODT mixed formats."""
        response = await async_client.post(
            "/convert/batch",
            files=[
                ("files", ("slide.odp", sample_odp_bytes)),
                ("files", ("doc.odt", sample_odt_bytes)),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["total_files"] == 2
        assert data["succeeded"] == 2
        assert len(data["results"]) == 2


# =============================================================================
# Integration tests — /convert/batch (async)
# =============================================================================


class TestConvertOdpBatchAsync:
    """Integration tests for ODP batch conversion via /convert/batch?async=true."""

    @pytest.mark.anyio
    async def test_batch_convert_odp_async_success(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert/batch?async=true with valid ODP returns batch id."""
        response = await async_client.post(
            "/convert/batch?async=true",
            files=[
                ("files", ("slide1.odp", sample_odp_bytes)),
                ("files", ("slide2.odp", sample_odp_bytes)),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["total_files"] == 2


# =============================================================================
# Validation tests
# =============================================================================


class TestOdpValidation:
    """Validation tests for ODP files."""

    @pytest.mark.anyio
    async def test_convert_odp_invalid_extension(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert with wrong extension returns 400."""
        response = await async_client.post(
            "/convert", files={"file": ("test.txt", sample_odp_bytes)}
        )
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_convert_odp_empty_file(
        self, async_client: httpx.AsyncClient
    ):
        """POST /convert with empty file returns 400."""
        response = await async_client.post(
            "/convert", files={"file": ("empty.odp", b"")}
        )
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_convert_odp_too_large(
        self, async_client: httpx.AsyncClient
    ):
        """POST /convert with oversized file returns 400."""
        large_file = b"x" * (16 * 1024 * 1024 + 1)  # 16MB + 1
        response = await async_client.post(
            "/convert", files={"file": ("large.odp", large_file)}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] in ("FILE_TOO_LARGE", "FILE_CORRUPTED")

    @pytest.mark.anyio
    async def test_convert_odp_no_file(
        self, async_client: httpx.AsyncClient
    ):
        """POST /convert without file returns 422."""
        response = await async_client.post("/convert")
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_convert_odp_mime_type(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """POST /convert with correct MIME type succeeds."""
        response = await async_client.post(
            "/convert",
            files={
                "file": (
                    "test.odp",
                    sample_odp_bytes,
                    "application/vnd.oasis.opendocument.presentation",
                )
            },
        )
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_convert_odp_corrupted_file(
        self, async_client: httpx.AsyncClient
    ):
        """POST /convert with corrupted ODP file returns error."""
        # Not a valid ZIP/ODP
        corrupted = b"This is not a valid ODP file content at all"
        response = await async_client.post(
            "/convert", files={"file": ("corrupted.odp", corrupted)}
        )
        # Should return an error (either 400 or 500 depending on implementation)
        assert response.status_code in (400, 500)

@pytest.mark.anyio
async def test_convert_odp_to_json(
    async_client: httpx.AsyncClient, sample_odp_bytes: bytes
):
    """POST /convert with ODP → JSON."""
    response = await async_client.post(
        "/convert", files={"file": ("test.odp", sample_odp_bytes)}, params={"format": "json"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["format"] == "odp"
    assert "json" in data
    
    json_data = data["json"]
    # ODP should have slides with content
    if "slides" in json_data:
        assert isinstance(json_data["slides"], list)
        assert len(json_data["slides"]) > 0


@pytest.mark.anyio
async def test_convert_odp_to_jsonl(
    async_client: httpx.AsyncClient, sample_odp_bytes: bytes
):
    """POST /convert with ODP → JSONL."""
    response = await async_client.post(
        "/convert", files={"file": ("test.odp", sample_odp_bytes)}, params={"format": "jsonl"}
    )
    assert response.status_code == 200
    data = response.json()
    
    jsonl_data = data["jsonl"]
    assert isinstance(jsonl_data, list)
    assert len(list(jsonl_data)) >= 3  # type: ignore[arg-type]
    
    # Verify event types
    event_types: list[str] = [e.split('{"type": ')[1].split('}')[0] for e in jsonl_data if isinstance(e, str)]  # type: ignore[assignment]
    assert "start" in event_types
    assert "end" in event_types
