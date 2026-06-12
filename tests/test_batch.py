"""Tests for the batch (multi-upload) endpoint — Phase 6."""

import asyncio
import io
from typing import Any, cast

import httpx
import pytest
from app.api import app, task_manager

from fixtures.batch import docx_bytes, pdf_bytes_1, pdf_bytes_2  # type: ignore[import-not-found]

@pytest.fixture(autouse=True)
def reset_state():
    """Reset rate limiter and task manager between tests."""
    app.state.rate_limiter._requests.clear()
    task_manager.tasks.clear()
    task_manager.batches.clear()
    yield


# =============================================================================
# 1. Single file in batch (backward compatibility edge case)
# =============================================================================


class TestBatchSingleFile:
    """A batch with a single file should behave like a normal conversion."""

    @pytest.mark.anyio
    async def test_single_file_in_batch_returns_success(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Single valid PDF in batch returns success with correct structure."""
        response = await async_client.post(
            "/convert/batch",
            files=[("files", ("doc1.pdf", pdf_bytes_1))],
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["total_files"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["index"] == 0
        assert result["filename"] == "doc1.pdf"
        assert result["success"] is True
        assert "markdown" in result
        assert "Document Un" in result["markdown"]


# =============================================================================
# 2. Empty file list → 400
# =============================================================================


class TestBatchEmpty:
    """Submitting no files should return a 400 BATCH_EMPTY error."""

    @pytest.mark.anyio
    async def test_empty_batch_returns_error(self, async_client: httpx.AsyncClient):
        """POST /convert/batch with no files returns an error (422 from FastAPI validation).

        FastAPI's `File(...)` requires at least one file, so it returns 422 before
        our BATCH_EMPTY check is reached. This is expected behavior.
        """
        response = await async_client.post(
            "/convert/batch",
            files=[],
        )
        # FastAPI returns 422 Unprocessable Entity for missing required file field
        assert response.status_code == 422


# =============================================================================
# 3. Exceeding max_files_per_request → 400
# =============================================================================


class TestBatchTooManyFiles:
    """Submitting more files than allowed should return a 400 error."""

    @pytest.mark.anyio
    async def test_exceeding_max_files_returns_400(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """More than max_files_per_request files returns TOO_MANY_FILES."""
        from app.config import settings

        files = [
            ("files", (f"doc{i}.pdf", pdf_bytes_1))
            for i in range(settings.max_files_per_request + 1)
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "TOO_MANY_FILES"

    @pytest.mark.anyio
    async def test_exactly_max_files_is_allowed(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Exactly max_files_per_request files should succeed."""
        from app.config import settings

        files = [
            ("files", (f"doc{i}.pdf", pdf_bytes_1))
            for i in range(settings.max_files_per_request)
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        # Should succeed (200 or 207)
        assert response.status_code in (200, 207)
        data = response.json()
        assert data["total_files"] == settings.max_files_per_request


# =============================================================================
# 4. Exceeding max_total_size_mb → 400
# =============================================================================


class TestBatchTotalSizeExceeded:
    """Total size exceeding the limit should return a 400 error."""

    @pytest.mark.anyio
    async def test_exceeding_total_size_returns_400(
        self, async_client: httpx.AsyncClient
    ):
        """Batch with total size > max_total_size_mb returns TOTAL_SIZE_EXCEEDED."""
        from app.config import settings

        # Create files that exceed the total size limit
        # Default max_total_size_mb is 100 MB
        large_content = b"%PDF-1.4 " + b"x" * (
            settings.max_total_size_mb * 1024 * 1024 // 2 + 1
        )
        files = [
            ("files", ("big1.pdf", large_content)),
            ("files", ("big2.pdf", large_content)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "TOTAL_SIZE_EXCEEDED"


# =============================================================================
# 5. Mixed valid/invalid files → partial results
# =============================================================================


class TestBatchMixedFiles:
    """Batch with a mix of valid and invalid files returns partial results."""

    @pytest.mark.anyio
    async def test_mixed_valid_invalid_returns_partial(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Valid PDF + invalid (corrupted) file returns 207 with partial results."""
        # Create a corrupted PDF (wrong magic bytes)
        corrupted = b"this is not a pdf" * 100

        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("corrupted.pdf", corrupted)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        # 207 Multi-Status for partial failure
        assert response.status_code == 207
        data = response.json()
        assert data["total_files"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        assert len(data["results"]) == 2

        # First file should succeed
        assert data["results"][0]["success"] is True
        assert "Document Un" in data["results"][0]["markdown"]

        # Second file should fail
        assert data["results"][1]["success"] is False
        assert data["results"][1]["error_code"] == "FILE_CORRUPTED"

    @pytest.mark.anyio
    async def test_mixed_with_unsupported_format(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Batch with unsupported format file fails fast with 400."""
        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("unsupported.txt", b"plain text")),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        # Should fail fast because of unsupported format
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "UNSUPPORTED_FORMAT"

    @pytest.mark.anyio
    async def test_all_files_fail_returns_207(self, async_client: httpx.AsyncClient):
        """All corrupted files returns 207 with all failures."""
        corrupted1 = b"not a pdf" * 100
        corrupted2 = b"also not a pdf" * 100

        files = [
            ("files", ("bad1.pdf", corrupted1)),
            ("files", ("bad2.pdf", corrupted2)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 0
        assert data["failed"] == 2
        for result in data["results"]:
            assert result["success"] is False

    @pytest.mark.anyio
    async def test_mixed_pdf_and_docx(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes, docx_bytes: bytes
    ):
        """Batch with both PDF and DOCX files converts both correctly."""
        files = [
            ("files", ("doc.pdf", pdf_bytes_1)),
            ("files", ("doc.docx", docx_bytes)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["succeeded"] == 2
        assert "Document Un" in data["results"][0]["markdown"]
        assert "DOCX Content" in data["results"][1]["markdown"]


# =============================================================================
# 6. Rate limiting with batch (N files = N counted requests)
# =============================================================================


class TestBatchRateLimiting:
    """Each file in a batch counts as 1 request for rate limiting."""

    @pytest.mark.anyio
    async def test_batch_counts_each_file_for_rate_limit(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Sending a batch of N files consumes N rate limit slots."""
        from app.rate_limiter import RateLimiter

        # Create a rate limiter with a small limit
        limiter = RateLimiter(max_requests=3, window_seconds=60, enabled=True)
        app.state.rate_limiter = limiter

        # Send batch of 2 files → should consume 2 slots
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
            ("files", ("doc2.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code in (200, 207)

        # Send batch of 1 file → should consume 1 more slot (total = 3)
        response2 = await async_client.post(
            "/convert/batch",
            files=[("files", ("doc3.pdf", pdf_bytes_1))],
        )
        assert response2.status_code in (200, 207)

        # Next request should be rate-limited (4th file > 3 limit)
        response3 = await async_client.post(
            "/convert/batch",
            files=[("files", ("doc4.pdf", pdf_bytes_1))],
        )
        assert response3.status_code == 429

    @pytest.mark.anyio
    async def test_rate_limit_exceeded_mid_batch(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """If rate limit is exceeded during batch processing, request is rejected."""
        from app.rate_limiter import RateLimiter

        # Limit of 2 requests
        limiter = RateLimiter(max_requests=2, window_seconds=60, enabled=True)
        app.state.rate_limiter = limiter

        # Try to send batch of 3 files → should be rejected (3 > 2)
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
            ("files", ("doc2.pdf", pdf_bytes_1)),
            ("files", ("doc3.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 429
        data = response.json()
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"


# =============================================================================
# 7. Async batch mode with ?async=true
# =============================================================================


class TestBatchAsyncMode:
    """Async batch mode submits files as background tasks."""

    @pytest.mark.anyio
    async def test_async_batch_submits_tasks(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes, pdf_bytes_2: bytes
    ):
        """POST /convert/batch?async=true returns task_ids for each file."""
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
            ("files", ("doc2.pdf", pdf_bytes_2)),
        ]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert "tasks" in data
        assert len(data["tasks"]) == 2
        for task in data["tasks"]:
            assert "task_id" in task
            assert task["status"] == "pending"
            assert "filename" in task

    @pytest.mark.anyio
    async def test_async_batch_tasks_complete(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes, pdf_bytes_2: bytes
    ):
        """Async batch tasks reach completed status with correct results."""
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
            ("files", ("doc2.pdf", pdf_bytes_2)),
        ]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        task_ids = [t["task_id"] for t in data["tasks"]]

        # Poll until all tasks are complete
        for _ in range(40):
            await asyncio.sleep(0.25)
            all_done = True
            for tid in task_ids:
                status_res = await async_client.get(f"/task/{tid}")
                status_data = status_res.json()
                if status_data["status"] not in ("completed", "failed"):
                    all_done = False
                    break
            if all_done:
                break

        # Verify all tasks completed
        for tid in task_ids:
            status_res = await async_client.get(f"/task/{tid}")
            status_data = status_res.json()
            assert status_data["status"] == "completed"
            assert "markdown" in status_data["result"]


# =============================================================================
# 8. Batch retrieval with GET /batch/{batch_id}
# =============================================================================


class TestBatchRetrieval:
    """GET /batch/{batch_id} returns aggregated batch results."""

    @pytest.mark.anyio
    async def test_get_batch_returns_results(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes, pdf_bytes_2: bytes
    ):
        """GET /batch/{batch_id} returns all task results for a batch."""
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
            ("files", ("doc2.pdf", pdf_bytes_2)),
        ]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        assert response.status_code == 200
        batch_id = response.json()["batch_id"]

        # Wait for tasks to complete
        for _ in range(40):
            await asyncio.sleep(0.25)
            batch_res = await async_client.get(f"/batch/{batch_id}")
            batch_data = batch_res.json()
            if batch_data.get("all_done"):
                break

        # Retrieve batch results
        batch_res = await async_client.get(f"/batch/{batch_id}")
        assert batch_res.status_code == 200
        batch_data = batch_res.json()
        assert batch_data["batch_id"] == batch_id
        assert batch_data["total_files"] == 2
        assert "results" in batch_data
        assert len(batch_data["results"]) == 2
        assert batch_data["all_done"] is True

    @pytest.mark.anyio
    async def test_get_batch_not_found(self, async_client: httpx.AsyncClient):
        """GET /batch/{batch_id} with unknown ID returns 404."""
        response = await async_client.get("/batch/nonexistent-batch-id")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "BATCH_NOT_FOUND"

    @pytest.mark.anyio
    async def test_get_batch_shows_partial_results(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """GET /batch/{batch_id} shows correct status for in-progress tasks."""
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
            ("files", ("doc2.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        batch_id = response.json()["batch_id"]

        # Check batch immediately (tasks may still be pending/processing)
        batch_res = await async_client.get(f"/batch/{batch_id}")
        assert batch_res.status_code == 200
        batch_data = batch_res.json()
        assert batch_data["batch_id"] == batch_id
        assert "pending" in batch_data
        assert "processing" in batch_data
        assert "succeeded" in batch_data
        assert "failed" in batch_data


# =============================================================================
# 9. Queue saturation with large batch
# =============================================================================


class TestBatchQueueSaturation:
    """Large batches respect queue limits and max_tasks_per_request."""

    @pytest.mark.anyio
    async def test_batch_respects_max_tasks_per_request(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Async batch limits submitted tasks to max_tasks_per_request."""
        from app.config import settings

        # Create more files than max_tasks_per_request but within max_files_per_request
        num_files = min(
            settings.max_tasks_per_request + 3, settings.max_files_per_request
        )
        if num_files <= settings.max_tasks_per_request:
            pytest.skip(
                "max_tasks_per_request >= max_files_per_request; no excess to test"
            )
        files = [("files", (f"doc{i}.pdf", pdf_bytes_1)) for i in range(num_files)]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        # All files should be in the batch (valid tasks + failed tasks for excess)
        assert len(data["tasks"]) == num_files
        # Only max_tasks_per_request should be queued as valid tasks (pending)
        # the rest should be failed (too many files)
        pending_tasks = [t for t in data["tasks"] if t["status"] == "pending"]
        assert len(pending_tasks) <= settings.max_tasks_per_request
        # Excess files should be counted as failed
        assert data["failed"] == num_files - settings.max_tasks_per_request

    @pytest.mark.anyio
    async def test_batch_queue_full_returns_429(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """When queue is full, batch submission returns 429."""
        from app.task_manager import TaskManager

        # Create a task manager with very small queue
        small_manager = TaskManager(max_concurrent=1, max_queue_size=2)
        app.state.task_manager = small_manager

        # Fill the queue first
        async def slow_task() -> dict[str, Any]:
            await asyncio.sleep(5)
            return {"ok": True}

        small_manager.submit(slow_task)  # type: ignore[misc]
        small_manager.submit(slow_task)  # type: ignore[misc]

        # Now try to submit a batch — should fail with queue full
        files = [
            ("files", ("doc1.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        assert response.status_code == 429
        data = response.json()
        assert data["error_code"] == "QUEUE_FULL"


# =============================================================================
# 10. ZIP bomb with one file in a batch
# =============================================================================


class TestBatchZipBomb:
    """ZIP bomb detection works for DOCX files within a batch."""

    @pytest.mark.anyio
    async def test_zip_bomb_docx_in_batch(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """A DOCX with extreme compression ratio is rejected in batch."""
        import zipfile

        # Create a DOCX-like ZIP with extreme compression ratio (ZIP bomb)
        # A very small compressed file that decompresses to a huge size
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write a large repetitive string (will compress well)
            large_content = "A" * (10 * 1024 * 1024)  # 10 MB of 'A's
            zf.writestr("word/document.xml", large_content)
            zf.writestr("[Content_Types].xml", "<Types/>")
        zip_bomb_bytes = buf.getvalue()

        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("bomb.docx", zip_bomb_bytes)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        # Should return 207 (partial failure) because one file is a ZIP bomb
        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        # The ZIP bomb file should be marked as corrupted
        assert data["results"][1]["success"] is False
        assert data["results"][1]["error_code"] == "FILE_CORRUPTED"

    @pytest.mark.anyio
    async def test_zip_bomb_docx_in_async_batch(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """A ZIP bomb DOCX in async batch is rejected before task submission."""
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            large_content = "B" * (10 * 1024 * 1024)
            zf.writestr("word/document.xml", large_content)
            zf.writestr("[Content_Types].xml", "<Types/>")
        zip_bomb_bytes = buf.getvalue()

        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("bomb.docx", zip_bomb_bytes)),
        ]
        response = await async_client.post(
            "/convert/batch?async=true",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        # Both files appear in tasks: valid PDF as pending, bomb DOCX as failed
        assert len(data["tasks"]) == 2
        # The valid PDF should be pending
        valid_task = [t for t in data["tasks"] if t["filename"] == "valid.pdf"][0]
        assert valid_task["status"] == "pending"
        # The bomb DOCX should be failed
        bomb_task = [t for t in data["tasks"] if t["filename"] == "bomb.docx"][0]
        assert bomb_task["status"] == "failed"
        # The bomb should be counted as failed
        assert data["failed"] == 1


# =============================================================================
# 11. XLSX files in batch
# =============================================================================


class TestBatchXlsx:
    """XLSX files should be properly handled in batch mode."""

    @pytest.mark.anyio
    async def test_xlsx_in_batch_returns_success(
        self, async_client: httpx.AsyncClient, sample_xlsx_bytes: bytes
    ):
        """Valid XLSX in batch returns success with Markdown output."""
        response = await async_client.post(
            "/convert/batch",
            files=[("files", ("test.xlsx", sample_xlsx_bytes))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        result = data["results"][0]
        assert result["success"] is True
        assert "markdown" in result
        assert "# Feuille1" in result["markdown"]

    @pytest.mark.anyio
    async def test_mixed_xlsx_pdf_batch(
        self,
        async_client: httpx.AsyncClient,
        sample_xlsx_bytes: bytes,
        pdf_bytes_1: bytes,
    ):
        """Batch with both XLSX and PDF files converts both successfully."""
        files = [
            ("files", ("data.xlsx", sample_xlsx_bytes)),
            ("files", ("doc.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        # XLSX result
        xlsx_result = data["results"][0]
        assert xlsx_result["success"] is True
        assert "# Feuille1" in xlsx_result["markdown"]
        # PDF result
        pdf_result = data["results"][1]
        assert pdf_result["success"] is True
        assert "Document Un" in pdf_result["markdown"]

    @pytest.mark.anyio
    async def test_xlsx_multi_sheet_in_batch(
        self, async_client: httpx.AsyncClient, sample_xlsx_multi_sheet_bytes: bytes
    ):
        """Multi-sheet XLSX in batch returns Markdown with all sheets."""
        response = await async_client.post(
            "/convert/batch",
            files=[("files", ("multi.xlsx", sample_xlsx_multi_sheet_bytes))],
        )
        assert response.status_code == 200
        data = response.json()
        result = data["results"][0]
        assert result["success"] is True
        markdown = result["markdown"]
        assert "# Données" in markdown
        assert "# Résumé" in markdown

    @pytest.mark.anyio
    async def test_invalid_xlsx_in_batch(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Invalid XLSX in batch fails gracefully without blocking other files."""
        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("fake.xlsx", b"Not a real XLSX file")),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        # PDF should succeed
        assert data["results"][0]["success"] is True
        # XLSX should fail
        assert data["results"][1]["success"] is False


# =============================================================================
# 12. PPTX files in batch
# =============================================================================


class TestBatchPptx:
    """PPTX files should be properly handled in batch mode."""

    @pytest.mark.anyio
    async def test_pptx_in_batch_returns_success(
        self, async_client: httpx.AsyncClient, sample_pptx_bytes: bytes
    ):
        """Valid PPTX in batch returns success with Markdown output."""
        response = await async_client.post(
            "/convert/batch",
            files=[("files", ("test.pptx", sample_pptx_bytes))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        result = data["results"][0]
        assert result["success"] is True
        assert "markdown" in result
        assert "Présentation de Test" in result["markdown"]

    @pytest.mark.anyio
    async def test_mixed_pptx_pdf_batch(
        self,
        async_client: httpx.AsyncClient,
        sample_pptx_bytes: bytes,
        pdf_bytes_1: bytes,
    ):
        """Batch with both PPTX and PDF files converts both successfully."""
        files = [
            ("files", ("presentation.pptx", sample_pptx_bytes)),
            ("files", ("doc.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        # PPTX result
        pptx_result = data["results"][0]
        assert pptx_result["success"] is True
        assert "Présentation de Test" in pptx_result["markdown"]
        # PDF result
        pdf_result = data["results"][1]
        assert pdf_result["success"] is True
        assert "Document Un" in pdf_result["markdown"]

    @pytest.mark.anyio
    async def test_invalid_pptx_in_batch(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Invalid PPTX in batch fails gracefully without blocking other files."""
        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("fake.pptx", b"Not a real PPTX file")),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        # PDF should succeed
        assert data["results"][0]["success"] is True
        # PPTX should fail
        assert data["results"][1]["success"] is False


# =============================================================================
# 13. ODP files in batch
# =============================================================================


class TestBatchOdp:
    """ODP files should be properly handled in batch mode."""

    @pytest.mark.anyio
    async def test_odp_in_batch_returns_success(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """Valid ODP in batch returns success with Markdown output."""
        response = await async_client.post(
            "/convert/batch",
            files=[("files", ("test.odp", sample_odp_bytes))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        result = data["results"][0]
        assert result["success"] is True
        assert "markdown" in result
        assert "Présentation de Test" in result["markdown"]

    @pytest.mark.anyio
    async def test_mixed_odp_pdf_batch(
        self,
        async_client: httpx.AsyncClient,
        sample_odp_bytes: bytes,
        pdf_bytes_1: bytes,
    ):
        """Batch with both ODP and PDF files converts both successfully."""
        files = [
            ("files", ("presentation.odp", sample_odp_bytes)),
            ("files", ("doc.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        # ODP result
        odp_result = data["results"][0]
        assert odp_result["success"] is True
        assert "Présentation de Test" in odp_result["markdown"]
        # PDF result
        pdf_result = data["results"][1]
        assert pdf_result["success"] is True
        assert "Document Un" in pdf_result["markdown"]

    @pytest.mark.anyio
    async def test_mixed_odp_docx_pdf_batch(
        self,
        async_client: httpx.AsyncClient,
        sample_odp_bytes: bytes,
        pdf_bytes_1: bytes,
        docx_bytes: bytes,
    ):
        """Batch with ODP, DOCX, and PDF files converts all successfully."""
        files = [
            ("files", ("presentation.odp", sample_odp_bytes)),
            ("files", ("document.docx", docx_bytes)),
            ("files", ("doc.pdf", pdf_bytes_1)),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 3
        assert data["succeeded"] == 3
        assert data["failed"] == 0
        # ODP result
        odp_result = data["results"][0]
        assert odp_result["success"] is True
        assert "Présentation de Test" in odp_result["markdown"]
        # DOCX result
        docx_result = data["results"][1]
        assert docx_result["success"] is True
        # PDF result
        pdf_result = data["results"][2]
        assert pdf_result["success"] is True
        assert "Document Un" in pdf_result["markdown"]

    @pytest.mark.anyio
    async def test_odp_async_batch(
        self, async_client: httpx.AsyncClient, sample_odp_bytes: bytes
    ):
        """ODP in async batch mode submits and completes successfully."""
        response = await async_client.post(
            "/convert/batch?async=true",
            files=[("files", ("test.odp", sample_odp_bytes))],
        )
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert len(data["tasks"]) == 1
        task_id = data["tasks"][0]["task_id"]
        assert data["tasks"][0]["status"] == "pending"

        # Poll until task completes
        for _ in range(40):
            await asyncio.sleep(0.25)
            status_res = await async_client.get(f"/task/{task_id}")
            status_data = cast(dict[str, Any], status_res.json())  # type: ignore[assignment]
            if status_data.get("status") in ("completed", "failed"):
                break

        assert status_data["status"] == "completed"  # type: ignore[index]
        result = status_data.get("result", {})  # type: ignore[index]
        assert "markdown" in result  # type: ignore[index]
        assert "Présentation de Test" in result["markdown"]  # type: ignore[index]

    @pytest.mark.anyio
    async def test_invalid_odp_in_batch(
        self, async_client: httpx.AsyncClient, pdf_bytes_1: bytes
    ):
        """Invalid ODP in batch fails gracefully without blocking other files."""
        files = [
            ("files", ("valid.pdf", pdf_bytes_1)),
            ("files", ("fake.odp", b"Not a real ODP file")),
        ]
        response = await async_client.post(
            "/convert/batch",
            files=files,
        )
        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        # PDF should succeed
        assert data["results"][0]["success"] is True
        # ODP should fail
        assert data["results"][1]["success"] is False
