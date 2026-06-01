"""Metrics routes: Prometheus format and human-friendly HTML page."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def register_metrics_routes(app: FastAPI) -> None:
    """Register metrics endpoints on the FastAPI app instance."""

    @app.get("/metrics", include_in_schema=False)
    async def metrics_export() -> PlainTextResponse:
        metrics = app.state.metrics
        payload = metrics.render_prometheus(app)
        return PlainTextResponse(
            content=payload,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/metrics/ui", include_in_schema=False)
    async def metrics_ui(request: Request):
        metrics = app.state.metrics
        context = metrics.get_dashboard_context(app)
        return templates.TemplateResponse(
            request=request,
            name="metrics.html",
            context=context,
        )
