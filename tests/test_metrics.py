"""Tests for Prometheus and HTML metrics endpoints."""

import httpx
import pytest

# Import fixtures from modules
from tests.fixtures.common import async_client


@pytest.mark.anyio
async def test_metrics_endpoint_prometheus_format(async_client: httpx.AsyncClient):
    """GET /metrics should expose Prometheus-compatible plain text metrics."""
    await async_client.get("/health")

    response = await async_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    assert "# TYPE caas_http_requests_total counter" in body
    assert "caas_http_requests_total" in body
    assert 'path="/health"' in body
    assert "caas_http_request_duration_seconds_bucket" in body
    assert "caas_uptime_seconds" in body
    assert "caas_tasks_active" in body


@pytest.mark.anyio
async def test_metrics_ui_endpoint_html(async_client: httpx.AsyncClient):
    """GET /metrics/ui should return a dedicated HTML metrics dashboard."""
    await async_client.get("/health")

    response = await async_client.get("/metrics/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>CAAS Metrics</title>" in response.text
    assert "Prometheus endpoint" in response.text
    assert "/health" in response.text
