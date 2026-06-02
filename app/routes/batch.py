"""Batch conversion routes: /convert/batch, /batch/{batch_id}."""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.converter import _convert_worker
from app.error_handler import ErrorHandler, error
from app.ip_helpers import _get_client_ip
from app.task_manager import QueueFullError, TaskManager, TaskStatus
from app.validation import validate_file_content, validate_filename

logger = logging.getLogger(__name__)


def register_batch_routes(app: FastAPI) -> None:
    """Register batch-related routes on the FastAPI app instance."""

    @app.post("/convert/batch", response_model=dict[str, Any])
    async def convert_batch(
        request: Request,
        files: list[UploadFile] = File(...),  # noqa: B008
        async_mode: str | None = Query(default=None, alias="async"),
    ):
        """
        Convert multiple PDF, DOCX, ODT, ODP, ODS, HTML, XLSX, or PPTX documents to Markdown in a single request.

        Each file is processed independently; failures on one file don't block others.
        Returns a list of per-file results with independent success/error status.

        - Without `async=true`: synchronous conversion (all files processed inline).
        - With `?async=true`: each valid file is submitted as a background task.
        """
        client_ip = _get_client_ip(request)
        batch_id = str(uuid.uuid4())[:8]

        # --- 0. Logging: batch request received ---
        logger.info(
            "[%s] Batch request from %s: %d file(s)",
            batch_id,
            client_ip,
            len(files),
        )

        # --- 1. Validate batch not empty (fail-fast, no content read) ---
        if not files:
            error(400, "BATCH_EMPTY")

        # --- 2. Validate file count (fail-fast, no content read) ---
        if len(files) > settings.max_files_per_request:
            logger.warning(
                "[%s] Rejected batch from %s: %d file(s) exceeds limit of %d",
                batch_id,
                client_ip,
                len(files),
                settings.max_files_per_request,
            )
            error(400, "TOO_MANY_FILES")

        # --- 2b. Validate filenames/extensions (fail-fast, no content read) ---
        for file in files:
            if not file.filename:
                logger.warning(
                    "[%s] Rejected batch from %s: missing filename",
                    batch_id,
                    client_ip,
                )
                error(400, "MISSING_FILENAME")

            assert file.filename is not None
            filename_error = validate_filename(file.filename)
            if filename_error:
                logger.warning(
                    "[%s] Rejected batch from %s: invalid filename (%s)",
                    batch_id,
                    client_ip,
                    filename_error,
                )
                error(400, "INVALID_FILENAME")

            assert file.filename is not None
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("pdf", "docx", "odt", "odp", "html", "xlsx", "pptx", "ods"):
                logger.warning(
                    "[%s] Rejected batch from %s: unsupported format '%s'",
                    batch_id,
                    client_ip,
                    ext,
                )
                error(400, "UNSUPPORTED_FORMAT")

        # --- 3. Rate limiting: each file counts as 1 request ---
        for _ in files:
            if not await app.state.rate_limiter.is_allowed(client_ip):
                logger.warning(
                    "[%s] Rate limit exceeded for %s (%d files in batch)",
                    batch_id,
                    client_ip,
                    len(files),
                )
                error(429, "RATE_LIMIT_EXCEEDED")

        # --- 4. Read files incrementally with total size check (fail-fast) ---
        file_contents: list[bytes] = []
        total_size = 0
        max_total_bytes = settings.max_total_size_mb * 1024 * 1024
        for file in files:
            content = await file.read()
            total_size += len(content)

            # Fail-fast: check total size after each file read
            if total_size > max_total_bytes:
                logger.warning(
                    "[%s] Total size exceeded by %s: %.1f MB > %d MB",
                    batch_id,
                    client_ip,
                    total_size / 1024 / 1024,
                    settings.max_total_size_mb,
                )
                error(400, "TOTAL_SIZE_EXCEEDED")

            file_contents.append(content)

        # --- 5. Async mode: submit valid files as background tasks ---
        if async_mode and async_mode.lower() == "true":
            return await _handle_async_batch(
                batch_id,
                files,
                file_contents,
                client_ip,
                app.state.task_manager,
                settings,
            )

        # --- 6. Synchronous mode: process each file independently ---
        results: list[dict[str, Any]] = []
        succeeded = 0
        failed = 0

        # Filenames/extensions already validated above (fail-fast), so we skip
        # those checks here and only validate content + convert.
        for index, (file, content) in enumerate(
            zip(files, file_contents, strict=False)
        ):
            assert file.filename is not None
            ext = file.filename.rsplit(".", 1)[-1].lower()

            # Validate file size (per-file limit)
            max_bytes = settings.max_file_size_mb * 1024 * 1024
            if len(content) > max_bytes:
                results.append(
                    ErrorHandler.make_batch_error_result(
                        index, file.filename, "FILE_TOO_LARGE"
                    )
                )
                failed += 1
                continue

            # Validate file content (magic bytes, MIME, ZIP bomb, structure)
            validation_error = validate_file_content(content, ext)
            if validation_error:
                logger.warning(
                    "[%s] Validation failed for %s: %s",
                    batch_id,
                    file.filename,
                    validation_error,
                )
                results.append(
                    ErrorHandler.make_batch_error_result(
                        index, file.filename, "FILE_CORRUPTED",
                        detail=validation_error,
                    )
                )
                failed += 1
                continue

            # Convert file
            try:
                conversion_result = await _convert_worker(content, ext)
                result: dict[str, Any] = {
                    "index": index,
                    "filename": file.filename,
                    "success": True,
                    "markdown": conversion_result["markdown"],
                }
                succeeded += 1
                results.append(result)
            except ValueError as e:
                error_msg = str(e).lower()
                if "exceeding the limit" in error_msg or "too many pages" in error_msg:
                    logger.warning(
                        "[%s] PDF page limit exceeded for %s: %s",
                        batch_id,
                        file.filename,
                        e,
                    )
                    results.append(
                        ErrorHandler.make_batch_error_result(
                            index, file.filename, "PDF_TOO_MANY_PAGES",
                            detail=str(e),
                        )
                    )
                    failed += 1
                else:
                    raise
            except Exception as e:
                logger.exception(
                    "[%s] Batch conversion failed for %s: %s",
                    batch_id,
                    file.filename,
                    e,
                )
                results.append(
                    ErrorHandler.make_batch_error_result(
                        index, file.filename, "CONVERSION_FAILED",
                        detail=str(e),
                    )
                )
                failed += 1

        # Determine status code: 207 if any failure, 200 if all succeeded
        status_code = 207 if failed > 0 else 200

        # --- 7. Logging: batch request completed ---
        logger.info(
            "[%s] Batch completed: %d succeeded, %d failed (from %s)",
            batch_id,
            succeeded,
            failed,
            client_ip,
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "batch_id": batch_id,
                "total_files": len(files),
                "succeeded": succeeded,
                "failed": failed,
                "results": results,
            },
        )

    @app.get("/batch/{batch_id}", response_model=dict[str, Any])
    async def get_batch_status(batch_id: str):
        """
        Retrieve the status and results of an asynchronous batch.

        Returns per-task status/result for every file in the batch.
        Error details are only exposed when debug mode is enabled.
        """
        batch_results = app.state.task_manager.get_batch_results(batch_id)
        if batch_results is None:
            error(404, "BATCH_NOT_FOUND")

        return batch_results


async def _handle_async_batch(
    batch_id: str,
    files: list[UploadFile],
    file_contents: list[bytes],
    client_ip: str,
    task_manager: TaskManager,
    settings: Any,
) -> JSONResponse:
    """
    Validate files and submit valid ones as background tasks under a batch.

    Invalid files are immediately marked as failed tasks within the batch
    so they appear correctly during polling.
    Filenames/extensions are already validated by the caller (fail-fast).
    """
    # Each entry: (original_index, filename, task_id)
    # Preserves original file order regardless of validation outcome.
    entries: list[tuple] = []
    invalid_count = 0

    # Phase 1 — validate every file; invalid ones get a failed task immediately
    valid_files: list[tuple] = []  # (index, filename, content, ext)
    for index, (file, content) in enumerate(zip(files, file_contents, strict=False)):
        assert file.filename is not None
        filename = file.filename

        # Validate file size (per-file limit)
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            entries.append(
                (
                    index,
                    filename,
                    task_manager.submit_failed_task("FILE_TOO_LARGE"),
                )
            )
            invalid_count += 1
            continue

        # Validate file content (magic bytes, MIME, ZIP bomb, structure)
        ext = filename.rsplit(".", 1)[-1].lower()
        validation_error = validate_file_content(content, ext)
        if validation_error:
            logger.warning(
                "[%s] Validation failed for %s: %s",
                batch_id,
                filename,
                validation_error,
            )
            entries.append(
                (
                    index,
                    filename,
                    task_manager.submit_failed_task(
                        "FILE_CORRUPTED", error_detail=validation_error
                    ),
                )
            )
            invalid_count += 1
            continue

        valid_files.append((index, filename, content, ext))

    # Phase 2 — enforce max_tasks_per_request; excess valid files become failed tasks
    max_tasks = settings.max_tasks_per_request
    if len(valid_files) > max_tasks:
        logger.warning(
            "[%s] Queue saturation: %d valid files from %s, limiting to %d tasks",
            batch_id,
            len(valid_files),
            client_ip,
            max_tasks,
        )
        for index, filename, _content, _ext in valid_files[max_tasks:]:
            entries.append(
                (
                    index,
                    filename,
                    task_manager.submit_failed_task("TOO_MANY_FILES"),
                )
            )
            invalid_count += 1
        valid_files = valid_files[:max_tasks]

    # Phase 3 — submit remaining valid files as real tasks
    for index, filename, content, ext in valid_files:
        try:
            entries.append(
                (index, filename, task_manager.submit(_convert_worker, content, ext))
            )
        except QueueFullError as e:
            logger.warning(
                "[%s] Queue full for %s: %s",
                batch_id,
                client_ip,
                e,
            )
            error(429, "QUEUE_FULL", detail=str(e))

    # Sort by original index so tasks appear in the same order as input files
    entries.sort(key=lambda e: e[0])
    task_ids = [e[2] for e in entries]
    filenames = [e[1] for e in entries]

    # Register the batch with ALL tasks (valid + invalid) in original order
    task_manager.register_batch(batch_id, task_ids, filenames, len(files))

    # Build response — use actual task status from the task manager
    tasks = []
    for i, task_id in enumerate(task_ids):
        task_result = await task_manager.get_task(task_id)
        tasks.append(
            {
                "index": i,
                "filename": filenames[i],
                "task_id": task_id,
                "status": task_result.status.value
                if task_result
                else TaskStatus.PENDING.value,
            }
        )

    # --- Logging: async batch submitted ---
    logger.info(
        "[%s] Async batch submitted: %d tasks, %d failed (from %s)",
        batch_id,
        len(task_ids),
        invalid_count,
        client_ip,
    )

    return JSONResponse(
        status_code=200,
        content={
            "batch_id": batch_id,
            "total_files": len(files),
            "succeeded": 0,
            "failed": invalid_count,
            "tasks": tasks,
            "message": f"{len(task_ids)} file(s) submitted. Use GET /batch/{batch_id} to retrieve results.",
        },
    )
