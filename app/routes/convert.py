"""Conversion routes: /, /convert, /task/{task_id}, /tasks."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.templating import Jinja2Templates

from app.config import settings
from app.converter import _convert_worker
from app.error_handler import ErrorHandler, error
from app.ip_helpers import _get_client_ip
from app.streaming import convert_stream
from app.task_manager import TaskStatus
from app.validation import validate_file_content

logger = logging.getLogger(__name__)

_jinja_templates = Jinja2Templates(directory="app/templates")


def register_convert_routes(app: FastAPI) -> None:
    """Register conversion-related routes on the FastAPI app instance."""

    @app.get("/")
    async def root(request: Request):
        """Return the file upload form."""
        return _jinja_templates.TemplateResponse(
            request, "form.html", {"request": request}
        )

    @app.post("/convert", response_model=dict[str, Any])
    async def convert_document(
        request: Request,
        file: UploadFile = File(...),  # noqa: B008
        async_mode: str | None = Query(default=None, alias="async"),
        streaming: str | None = Query(default=None),
    ):
        """
        Convert a PDF, DOCX, ODT, ODP, ODS, HTML, XLSX, or PPTX document to Markdown.

        - Without `async=true` parameter: synchronous conversion (default behavior).
        - With `?async=true`: the task is submitted in the background and a task_id is returned.
        - With `?streaming=true`: the result is streamed back via Server-Sent Events (SSE).
        """
        client_ip = _get_client_ip(request)
        if not await app.state.rate_limiter.is_allowed(client_ip):
            error(429, "RATE_LIMIT_EXCEEDED")

        if not file.filename:
            error(400, "MISSING_FILENAME")

        assert file.filename is not None
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("pdf", "docx", "odt", "odp", "ods", "html", "xlsx", "pptx"):
            error(400, "UNSUPPORTED_FORMAT")

        # Check if streaming is requested and enabled
        use_streaming = (
            streaming and streaming.lower() == "true" and settings.streaming_enabled
        )

        try:
            content = await file.read()
            max_bytes = settings.max_file_size_mb * 1024 * 1024
            if len(content) > max_bytes:
                error(400, "FILE_TOO_LARGE")

            validation_error = validate_file_content(content, ext)
            if validation_error:
                logger.warning(
                    "Validation failed for %s: %s", file.filename, validation_error
                )
                error(400, "FILE_CORRUPTED", detail=validation_error)

            if async_mode and async_mode.lower() == "true":
                task_id = app.state.task_manager.submit(_convert_worker, content, ext)
                content = None  # type: ignore[assignment]  # Explicit memory release
                return {
                    "success": True,
                    "task_id": task_id,
                    "status": TaskStatus.PENDING.value,
                    "message": "Task submitted in the background. Use GET /task/{task_id} to retrieve the result.",
                }

            # Streaming mode: return a StreamingResponse with SSE events
            if use_streaming:
                return StreamingResponse(
                    _streaming_generator(content, ext),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # Disable nginx buffering
                    },
                )

            try:
                result = await _convert_worker(content, ext)
            except ValueError as e:
                error_msg = str(e).lower()
                if "exceeding the limit" in error_msg or "too many pages" in error_msg:
                    logger.warning("PDF page limit exceeded for %s: %s", file.filename, e)
                    error(400, "PDF_TOO_MANY_PAGES", detail=str(e))
                raise
            except Exception as e:
                # Catch all conversion errors and convert to unified error format
                logger.error("Conversion failed for %s: %s", file.filename, e)
                error(500, "CONVERSION_FAILED", detail=str(e))
            finally:
                content = None  # type: ignore[assignment]  # Explicit memory release
            return result

        except HTTPException:
            # Re-raise HTTPException (from error()) without catching it
            raise

    @app.get("/task/{task_id}", response_model=dict[str, Any])
    async def get_task_status(task_id: str):
        """
        Retrieve the status and result of an asynchronous task.
        """
        task = await app.state.task_manager.get_task(task_id)
        if task is None:
            error(404, "TASK_NOT_FOUND")

        response: dict[str, Any] = {
            "task_id": task.task_id,
            "status": task.status.value,
        }

        if task.status == TaskStatus.COMPLETED and task.result:
            response["result"] = task.result
        elif task.status == TaskStatus.FAILED:
            error_code = task.error or "CONVERSION_FAILED"
            error_response = ErrorHandler.make_error_response(
                error_code, detail=task.error_detail
            )
            response.update(error_response)

        return response

    @app.get("/tasks", response_model=dict[str, Any])
    async def get_tasks_overview():
        """Overview of the task queue."""
        return {
            "active": app.state.task_manager.get_active_count(),
            "pending": app.state.task_manager.get_pending_count(),
            "max_concurrent": app.state.task_manager.max_concurrent,
        }


async def _streaming_generator(content: bytes, ext: str) -> AsyncGenerator[str, None]:
    """Async generator that wraps the streaming converter for StreamingResponse."""
    try:
        async for chunk in convert_stream(content, ext):
            yield chunk
    except Exception as e:
        logger.exception("Streaming error for format %s: %s", ext, e)
        # Yield an error event with standardized format
        error_response = ErrorHandler.make_error_response(
            "CONVERSION_FAILED", detail=str(e)
        )
        error_event = json.dumps({"status": "error", **error_response})
        yield f"data: {error_event}\n\n"
