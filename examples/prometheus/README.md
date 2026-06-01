# Prometheus Monitoring Example

This example shows how to run CAAS with Prometheus and scrape application metrics from /metrics.

## Directory Structure

```
prometheus/
|- docker-compose.yml
|- prometheus.yml
`- README.md
```

## What You Get

- CAAS service on http://localhost:8000
- Prometheus UI on http://localhost:9090
- CAAS metrics endpoint at http://localhost:8000/metrics
- CAAS metrics dashboard at http://localhost:8000/metrics/ui

## Quick Start

From this directory:

```bash
docker compose up -d --build
```

## Verify

```bash
# CAAS metrics (Prometheus format)
curl http://localhost:8000/metrics

# CAAS metrics HTML page
curl http://localhost:8000/metrics/ui
```

In Prometheus UI, open:

- http://localhost:9090/targets (target health)
- http://localhost:9090/graph (query metrics)

Example queries:

- caas_http_requests_total
- caas_http_request_duration_seconds_count
- caas_tasks_active
- caas_tasks_pending

## Notes

- Prometheus scrapes every 15 seconds (see prometheus.yml).
- The sample job label is caas.
- You can adjust labels, intervals, and retention in the compose and config files.
