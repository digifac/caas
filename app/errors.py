"""Secure error messages: generic codes for clients, full details in logs.

All error responses are normalized through the ErrorHandler module.
This module provides the error code → message mapping used by ErrorHandler.
"""

from typing import Any


class AppError:
    """Error code to message mapping.

    Use ErrorHandler for building error responses; this class only stores
    the code/message pairs.
    """

    _messages: dict[str, str] = {
        "CONVERSION_FAILED": "Document conversion failed.",
        "FILE_TOO_LARGE": "File exceeds the maximum allowed size.",
        "FILE_CORRUPTED": "File appears to be corrupted or invalid.",
        "UNSUPPORTED_FORMAT": "Unsupported format. Use PDF, DOCX, ODT, ODP, HTML, XLSX, ODS, or PPTX.",
        "MISSING_FILENAME": "Filename is missing.",
        "RATE_LIMIT_EXCEEDED": "Too many requests. Please try again later.",
        "TASK_NOT_FOUND": "Task not found or expired.",
        "SERVER_ERROR": "An internal error occurred.",
        "TOO_MANY_FILES": "Too many files in the request.",
        "TOTAL_SIZE_EXCEEDED": "Total size of all files exceeds the maximum allowed.",
        "BATCH_PARTIAL_FAILURE": "Some files in the batch failed to convert.",
        "BATCH_EMPTY": "No files provided in the batch request.",
        "BATCH_NOT_FOUND": "Batch not found or expired.",
        "QUEUE_FULL": "Task queue is full. Please try again later.",
        "PDF_TOO_MANY_PAGES": "PDF exceeds the maximum allowed number of pages.",
    }

    @classmethod
    def get(cls, code: str) -> dict[str, Any]:
        """Return a simple error_code + message dictionary.

        Debug detail handling is managed by ErrorHandler, not this method.
        """
        message = cls._messages.get(code, cls._messages["SERVER_ERROR"])
        return {
            "error_code": code,
            "message": message,
        }
