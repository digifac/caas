"""In-memory application metrics with Prometheus exposition helpers."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import perf_counter
from typing import Any

from fastapi import FastAPI, Request


class AppMetrics:
    """Collect HTTP and runtime metrics for Prometheus and HTML rendering."""

    _HISTOGRAM_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self) -> None:
        self._lock = Lock()
        self._started_at = perf_counter()
        self._requests_total: dict[tuple[str, str, str], int] = defaultdict(int)
        self._request_duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._request_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._request_duration_buckets: dict[tuple[str, str], list[int]] = defaultdict(
            lambda: [0] * (len(self._HISTOGRAM_BUCKETS) + 1)
        )
        self._inprogress_requests: dict[tuple[str, str], int] = defaultdict(int)

    @staticmethod
    def _escape_label(value: str) -> str:
        result: str = value.replace("\\", "\\\\").replace("\n", "\n").replace('"', '\\"')
        return result

    @staticmethod
    def _route_label(request: Request) -> str:
        route = request.scope.get("route")
        route_path = getattr(route, "path", None)
        if isinstance(route_path, str):
            return route_path  # type: ignore[return-value]
        return str(request.url.path)

    def start_request(self, method: str, path: str) -> None:
        """Track an in-progress request for method/path."""
        with self._lock:
            self._inprogress_requests[(method, path)] += 1

    def finish_request(self, method: str, path: str, status_code: int, duration: float) -> None:
        """Record counters and histogram values for a completed request."""
        status = str(status_code)
        with self._lock:
            self._requests_total[(method, path, status)] += 1
            self._request_duration_count[(method, path)] += 1
            self._request_duration_sum[(method, path)] += duration

            buckets = self._request_duration_buckets[(method, path)]
            placed = False
            for idx, upper_bound in enumerate(self._HISTOGRAM_BUCKETS):
                if duration <= upper_bound:
                    buckets[idx] += 1
                    placed = True
                    break
            if not placed:
                buckets[-1] += 1

            inprogress_key = (method, path)
            if self._inprogress_requests[inprogress_key] > 0:
                self._inprogress_requests[inprogress_key] -= 1

    def middleware(self, app: FastAPI):
        """Return a FastAPI middleware function to instrument HTTP requests."""

        async def metrics_middleware(request: Request, call_next):
            method = request.method
            path = self._route_label(request)
            self.start_request(method, path)

            started = perf_counter()
            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            finally:
                duration = perf_counter() - started
                path = self._route_label(request)
                self.finish_request(method, path, status_code, duration)

        return metrics_middleware

    def _runtime_snapshot(self, app: FastAPI) -> dict[str, Any]:
        task_manager = getattr(app.state, "task_manager", None)
        rate_limiter = getattr(app.state, "rate_limiter", None)
        return {
            "uptime_seconds": max(perf_counter() - self._started_at, 0.0),
            "task_active": task_manager.get_active_count() if task_manager else 0,
            "task_pending": task_manager.get_pending_count() if task_manager else 0,
            "task_max_concurrent": task_manager.max_concurrent if task_manager else 0,
            "rate_limiter_enabled": 1 if getattr(rate_limiter, "enabled", False) else 0,
        }

    def render_prometheus(self, app: FastAPI) -> str:
        """Render all metrics in Prometheus text exposition format."""
        runtime = self._runtime_snapshot(app)
        lines: list[str] = [
            "# HELP caas_http_requests_total Total HTTP requests handled by CAAS.",
            "# TYPE caas_http_requests_total counter",
        ]

        with self._lock:
            request_items = sorted(self._requests_total.items())
            duration_keys = sorted(self._request_duration_count.keys())
            inprogress_items = sorted(self._inprogress_requests.items())

            for (method, path, status), count in request_items:
                lines.append(
                    "caas_http_requests_total"
                    f'{{method="{self._escape_label(method)}",path="{self._escape_label(path)}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP caas_http_request_duration_seconds HTTP request latency in seconds.",
                    "# TYPE caas_http_request_duration_seconds histogram",
                ]
            )
            for key in duration_keys:
                method, path = key
                bucket_counts = self._request_duration_buckets[key]
                cumulative = 0
                for idx, bound in enumerate(self._HISTOGRAM_BUCKETS):
                    cumulative += bucket_counts[idx]
                    lines.append(
                        "caas_http_request_duration_seconds_bucket"
                        f'{{method="{self._escape_label(method)}",path="{self._escape_label(path)}",le="{bound}"}} {cumulative}'
                    )
                cumulative += bucket_counts[-1]
                lines.append(
                    "caas_http_request_duration_seconds_bucket"
                    f'{{method="{self._escape_label(method)}",path="{self._escape_label(path)}",le="+Inf"}} {cumulative}'
                )
                lines.append(
                    "caas_http_request_duration_seconds_count"
                    f'{{method="{self._escape_label(method)}",path="{self._escape_label(path)}"}} {self._request_duration_count[key]}'
                )
                lines.append(
                    "caas_http_request_duration_seconds_sum"
                    f'{{method="{self._escape_label(method)}",path="{self._escape_label(path)}"}} {self._request_duration_sum[key]:.6f}'
                )

            lines.extend(
                [
                    "# HELP caas_http_inprogress_requests Number of in-progress HTTP requests.",
                    "# TYPE caas_http_inprogress_requests gauge",
                ]
            )
            for (method, path), value in inprogress_items:
                lines.append(
                    "caas_http_inprogress_requests"
                    f'{{method="{self._escape_label(method)}",path="{self._escape_label(path)}"}} {value}'
                )

        lines.extend(
            [
                "# HELP caas_uptime_seconds Process uptime in seconds.",
                "# TYPE caas_uptime_seconds gauge",
                f"caas_uptime_seconds {runtime['uptime_seconds']:.3f}",
                "# HELP caas_tasks_active Current number of active conversion tasks.",
                "# TYPE caas_tasks_active gauge",
                f"caas_tasks_active {runtime['task_active']}",
                "# HELP caas_tasks_pending Current number of pending conversion tasks.",
                "# TYPE caas_tasks_pending gauge",
                f"caas_tasks_pending {runtime['task_pending']}",
                "# HELP caas_tasks_max_concurrent Maximum number of concurrent conversion tasks.",
                "# TYPE caas_tasks_max_concurrent gauge",
                f"caas_tasks_max_concurrent {runtime['task_max_concurrent']}",
                "# HELP caas_rate_limiter_enabled Whether the rate limiter is enabled (1=true, 0=false).",
                "# TYPE caas_rate_limiter_enabled gauge",
                f"caas_rate_limiter_enabled {runtime['rate_limiter_enabled']}",
            ]
        )

        return "\n".join(lines) + "\n"

    def get_dashboard_context(self, app: FastAPI) -> dict[str, Any]:
        """Build context payload used by the metrics HTML template."""
        runtime = self._runtime_snapshot(app)

        with self._lock:
            request_items = sorted(self._requests_total.items(), key=lambda item: item[0])
            duration_items = sorted(
                self._request_duration_count.items(), key=lambda item: item[0]
            )
        requests = [
            {
                "method": method,
                "path": path,
                "status": status,
                "total": count,
            }
            for (method, path, status), count in request_items
        ]
        latencies = [
            {
                "method": method,
                "path": path,
                "count": count,
                "average": (self._request_duration_sum[(method, path)] / count)
                if count
                else 0.0,
            }
            for (method, path), count in duration_items
        ]

        return {
            "runtime": runtime,
            "requests": requests,
            "latencies": latencies,
            "refresh_seconds": 10,
        }
