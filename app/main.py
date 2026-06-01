"""Application entry point — re-exports from api and converter modules.

Tests import from `app.main` for backward compatibility.
"""

from app.api import app, task_manager
from app.converter import _clean_lines, _convert_worker
from app.errors import AppError

__all__ = [
    "app",
    "task_manager",
    "AppError",
    "_clean_lines",
    "_convert_worker",
]
