"""Tests for the API HTTP endpoints (generic tests only).

Extension-specific tests are in dedicated files:
- test_pdf.py, test_docx.py, test_html.py, test_odt.py
"""

import asyncio
import os

import httpx
import pytest

# Import fixtures from modules
from tests.fixtures.common import async_client

# =============================================================================
# Root endpoint
# =============================================================================


@pytest.mark.anyio
async def test_root_returns_html_form(async_client: httpx.AsyncClient):
    """GET / should return the HTML form with status 200."""
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!DOCTYPE html>" in response.text
    assert "CAAS" in response.text


# =============================================================================
# Validation & error handling
# =============================================================================


@pytest.mark.anyio
async def test_convert_unsupported_format(async_client: httpx.AsyncClient):
    """POST /convert with an unsupported format returns 400."""
    response = await async_client.post(
        "/convert", files={"file": ("test.txt", b"plain text")}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "UNSUPPORTED_FORMAT"
    assert "Unsupported format" in data["message"]


@pytest.mark.anyio
async def test_convert_no_filename(async_client: httpx.AsyncClient):
    """POST /convert without a filename returns a 4xx error."""
    response = await async_client.post("/convert", files={"file": ("", b"content")})
    assert 400 <= response.status_code < 500


@pytest.mark.anyio
async def test_convert_file_too_large(async_client: httpx.AsyncClient):
    """POST /convert with a file > 50 MB returns 400."""
    large_content = b"x" * (50 * 1024 * 1024 + 1)
    response = await async_client.post(
        "/convert", files={"file": ("huge.pdf", large_content)}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "FILE_TOO_LARGE"
    assert "maximum allowed size" in data["message"].lower()


# =============================================================================
# Async mode tests
# =============================================================================


@pytest.mark.anyio
async def test_convert_async_submits_task(
    async_client: httpx.AsyncClient, sample_pdf_bytes: bytes
):
    """POST /convert?async=true returns a task_id immediately."""
    response = await async_client.post(
        "/convert?async=true", files={"file": ("test.pdf", sample_pdf_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "message" in data


@pytest.mark.anyio
async def test_convert_async_task_not_found(async_client: httpx.AsyncClient):
    """GET /task/{task_id} with a non-existent ID returns 404."""
    response = await async_client.get("/task/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_tasks_overview(async_client: httpx.AsyncClient):
    """GET /tasks returns an overview of the queue."""
    response = await async_client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "active" in data
    assert "pending" in data
    assert "max_concurrent" in data
    assert data["max_concurrent"] == (os.cpu_count() or 1)


@pytest.mark.anyio
async def test_convert_async_unsupported_format(async_client: httpx.AsyncClient):
    """POST /convert?async=true with an unsupported format returns 400 (no task created)."""
    response = await async_client.post(
        "/convert?async=true", files={"file": ("test.txt", b"plain text")}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "UNSUPPORTED_FORMAT"
    assert "Unsupported format" in data["message"]


# =============================================================================
# XLSX conversion endpoint tests
# =============================================================================


@pytest.mark.anyio
async def test_convert_xlsx_valid_file(
    async_client: httpx.AsyncClient, sample_xlsx_bytes: bytes
):
    """POST /convert with a valid XLSX file returns 200 with Markdown."""
    response = await async_client.post(
        "/convert",
        files={
            "file": (
                "test.xlsx",
                sample_xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "markdown" in data
    # The markdown should contain the sheet heading and table
    assert "# Feuille1" in data["markdown"]
    assert "| ID |" in data["markdown"]
    assert "| Nom |" in data["markdown"] or "|Nom|" in data["markdown"]
    assert "Produit 2" in data["markdown"]
    assert "Catégorie_" in data["markdown"]


@pytest.mark.anyio
async def test_convert_xlsx_multi_sheet(
    async_client: httpx.AsyncClient, sample_xlsx_multi_sheet_bytes: bytes
):
    """POST /convert with a multi-sheet XLSX returns Markdown with multiple headings."""
    response = await async_client.post(
        "/convert",
        files={
            "file": (
                "multi.xlsx",
                sample_xlsx_multi_sheet_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    markdown = data["markdown"]
    # Should contain both sheet headings
    assert "# Données" in markdown
    assert "# Résumé" in markdown


@pytest.mark.anyio
async def test_convert_xlsx_invalid_file(async_client: httpx.AsyncClient):
    """POST /convert with an invalid XLSX file (wrong content) returns 400."""
    response = await async_client.post(
        "/convert",
        files={
            "file": (
                "fake.xlsx",
                b"This is not a valid XLSX file",
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_convert_xlsx_empty_file(async_client: httpx.AsyncClient):
    """POST /convert with an empty XLSX file returns 400."""
    response = await async_client.post(
        "/convert",
        files={"file": ("empty.xlsx", b"", "application/octet-stream")},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_convert_xlsx_async(
    async_client: httpx.AsyncClient, sample_xlsx_bytes: bytes
):
    """POST /convert?async=true with a valid XLSX file returns a task_id."""
    response = await async_client.post(
        "/convert?async=true",
        files={
            "file": (
                "test.xlsx",
                sample_xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "task_id" in data
    assert data["status"] == "pending"


@pytest.mark.anyio
async def test_convert_async_concurrency_limit(
    async_client: httpx.AsyncClient, sample_pdf_bytes: bytes
):
    """Multiple async tasks respect the concurrency limit."""
    import os

    max_concurrent = os.cpu_count() or 1

    # Submit more tasks than CPU cores to test the limit, but stay within the queue (max 20)
    num_tasks = min(max_concurrent + 2, 18)
    task_ids: list[str] = []
    for i in range(num_tasks):
        response = await async_client.post(
            "/convert?async=true", files={"file": ("test.pdf", sample_pdf_bytes)}
        )
        assert response.status_code == 200, (
            f"Request {i} failed: {response.status_code} - {response.text}"
        )
        task_ids.append(response.json()["task_id"])

    # Verify that the number of active tasks never exceeds the number of cores
    for _ in range(40):
        await asyncio.sleep(0.25)
        overview = await async_client.get("/tasks")
        data = overview.json()
        # Should never have more than max_concurrent tasks running
        assert data["active"] <= max_concurrent, (
            f"Concurrence dépassée : {data['active']} tâches actives"
        )

        # Check that all tasks are finished
        all_done = True
        for tid in task_ids:
            status_res = await async_client.get(f"/task/{tid}")
            status_data = status_res.json()
            if status_data["status"] not in ("completed", "failed"):
                all_done = False
                break

        if all_done:
            break
    else:
        # If we exit via else, the timeout is reached
        # Still verify that all tasks have a final status
        for tid in task_ids:
            status_res = await async_client.get(f"/task/{tid}")
            status_data = status_res.json()
            assert status_data["status"] in ("completed", "failed"), (
                f"Tâche {tid} bloquée dans {status_data['status']}"
            )

    # All tasks must be completed
    for tid in task_ids:
        status_res = await async_client.get(f"/task/{tid}")
        status_data = status_res.json()
        assert status_data["status"] == "completed"
