"""Application entry point — re-exports from api and converter modules.

Tests import from `app.main` for backward compatibility.
"""

from app.api import app, task_manager
from app.converter import _clean_lines, _convert_worker, get_html_form
from app.errors import AppError

__all__ = [
    "app",
    "task_manager",
    "AppError",
    "get_html_form",
    "_clean_lines",
    "_convert_worker",
]
