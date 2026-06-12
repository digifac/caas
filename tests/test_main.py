"""Tests for app/main.py — entry point re-exports."""


class TestMainReExports:
    """Verify that app.main re-exports all expected symbols."""

    def test_app_reexported(self):
        """app.main.app should be the FastAPI application."""
        from app.main import app
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_task_manager_reexported(self):
        """app.main.task_manager should be the TaskManager instance."""
        from app.main import task_manager
        from app.task_manager import TaskManager

        assert isinstance(task_manager, TaskManager)

    def test_app_error_reexported(self):
        """app.main.AppError should be the AppError class with _messages dict."""
        from app.main import AppError

        assert hasattr(AppError, "_messages")
        assert "SERVER_ERROR" in AppError._messages  # type: ignore[attr-defined]
        assert hasattr(AppError, "get")

    def test_clean_lines_reexported(self):
        """app.main.clean_lines should be callable."""
        from app.main import clean_lines

        assert callable(clean_lines)

    def test_convert_worker_reexported(self):
        """app.main.convert_worker should be callable."""
        from app.main import convert_worker

        assert callable(convert_worker)

    def test_all_exports_present(self):
        """__all__ should contain all expected symbols."""
        from app import main

        expected = {
            "app",
            "task_manager",
            "AppError",
            "clean_lines",
            "convert_worker",
        }
        assert set(main.__all__) == expected

    def test_app_is_same_instance_as_api_app(self):
        """app.main.app should be the same instance as app.api.app."""
        from app.api import app as api_app
        from app.main import app as main_app

        assert main_app is api_app

    def test_task_manager_is_same_instance_as_api_task_manager(self):
        """app.main.task_manager should be the same instance as app.api.task_manager."""
        from app.api import task_manager as api_tm
        from app.main import task_manager as main_tm

        assert main_tm is api_tm
