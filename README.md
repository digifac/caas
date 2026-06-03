# 🔄 CAAS — Conversion as a Service

**Convert PDF, DOCX, ODT, ODP, XLSX, ODS, PPTX, and HTML files to Markdown, 100 % in-memory (zero-disk I/O).**

[![CI](https://github.com/digifac/caas/actions/workflows/ci.yml/badge.svg)](https://github.com/digifac/caas/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **⚠️ Beta Release**: This project is currently in **beta** and may not be suitable for production use. APIs, configurations, and behaviors are subject to change without notice. You can deploy it at your own risk.

---

## 📋 Table of Contents

- [About](#-about)
- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Security](#-security)
- [Tests](#-tests)
- [Docker](#-docker)
- [Examples](#-examples)
- [Dependencies](#-dependencies)
- [License](#-license)
- [Author](#-author)

---

## 💡 About

CAAS is a focused, purpose-built service that converts **PDF**, **DOCX**, **ODT**, **ODP**, **XLSX**, **ODS**, **PPTX**, and **HTML** documents into clean **Markdown**. It is **not** a universal file converter — its sole goal is to produce high-quality Markdown output optimized for consumption by Large Language Models (LLMs) and orchestration/chain-building tools such as [n8n](https://n8n.io), LangChain, LlamaIndex, and similar frameworks.

By limiting the scope to these eight widely-used document formats, CAAS delivers a reliable, fast, and secure conversion pipeline without the complexity of supporting dozens of file types.

---

## ✨ Features

### Conversion

- **PDF → Markdown**: native text extraction via `pdfplumber` with single-pass design (text extracted once per page, cached)
- **DOCX → Markdown**: pure Python conversion via `mammoth`
- **ODT → Markdown**: pure Python conversion via `odfpy` with support for headings, paragraphs, and lists
- **XLSX → Markdown**: spreadsheet-to-table conversion via `openpyxl` with multi-sheet support, merged cells handling, and date/number formatting
- **ODS → Markdown**: OpenDocument Spreadsheet conversion via `ezodf` with multi-sheet support, merged cells handling, and special characters escaping
- **PPTX → Markdown**: PowerPoint presentation conversion via `python-pptx` with slide-by-slide text extraction, title detection, bullet lists, and table support
- **ODP → Markdown**: OpenDocument Presentation conversion via `odfpy` with slide-by-slide text extraction, title detection, bullet lists, and streaming support
- **HTML → Markdown**: robust parsing via `beautifulsoup4` with support for headings, lists, tables, code blocks, blockquotes, inline formatting, and security sanitization
- **Modular converter architecture**: each format has its own converter module under `app/converters/`, sharing common utilities from `base.py`
- **Automatic OCR**: fallback to Tesseract for scanned PDFs (60+ languages available), batched for efficiency (pypdfium2 opened only once)
- **Link extraction**: recovery of URI hyperlinks embedded in PDFs
- **Markdown heading detection**: automatic detection of ALL-CAPS headings with acronym exclusion (configurable via `CAAS_MARKDOWN_HEADING_DETECTION`)

### Processing Modes

- **Synchronous mode**: immediate response with the converted Markdown
- **Asynchronous mode**: queue with polling support (`?async=true`), background task processing with concurrency control
- **Streaming mode**: progressive delivery via Server-Sent Events (SSE) (`?streaming=true`), ideal for large documents
  - PDF: yields one page per SSE event (true progressive streaming)
  - DOCX/ODT/XLSX/PPTX/HTML: yields chunks of configurable size (`CAAS_STREAMING_CHUNK_SIZE`)
  - Events include metadata (`started`, markdown chunks, `complete`, `error`)
- **Batch mode**: convert multiple files in a single request (`POST /convert/batch`), independent per-file results (failures don't block others)
- **Async batch mode**: submit multiple files for background processing (`POST /convert/batch?async=true`), track with `GET /batch/{batch_id}`
- **Queue saturation protection**: limit async tasks per request via `CAAS_MAX_TASKS_PER_REQUEST`

### Security

- **File validation**: magic bytes, MIME type, ZIP bomb detection, DOCX structure checks, path traversal detection
- **HTML sanitization**: blocks dangerous URL schemes (`javascript:`, `data:`, etc.) and strips event handlers (`onclick`, `onerror`, etc.)
- **Anti-spoofing protection**: secure IP extraction with trusted proxy support
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `X-XSS-Protection`, `Referrer-Policy`
- **CORS support**: configurable via `CAAS_CORS_ORIGINS`, disabled by default (same-origin only)
- **Secure error handling**: generic messages in production, full details in server logs, `request_id` for tracing
- **PDF page limit**: configurable maximum pages via `CAAS_PDF_MAX_PAGES`

### Performance & Reliability

- **Rate limiting**: native sliding window per IP, configurable (30 req/min by default), zero external dependency
- **Memory protection**: strict upper bounds on memory usage
  - Rate limiter evicts oldest IP keys when `CAAS_RATE_LIMIT_MAX_KEYS` is exceeded (default: 10 000)
  - Task manager evicts completed tasks when `CAAS_TASK_MAX_TASKS` is exceeded (default: 500), persisting them to storage first
- **Zero-disk I/O**: everything runs in memory, no temporary files on disk
- **Independent OCR module**: reusable `app/ocr.py` module with proper resource cleanup (PIL Image / pypdfium2 PdfDocument)
- **Task manager**: async queue with concurrency limiting, automatic cleanup of expired results, batch tracking
- **Health check**: `GET /health` endpoint for load balancers and orchestrators

### User Interface

- **Web interface**: built-in upload form with drag & drop, batch upload support, and async polling (Jinja2 templating)
- **Metrics dashboard**: live HTML page at `/metrics/ui` with auto-refresh, uptime, request counters, latency histograms, and runtime gauges
- **OpenAPI documentation**: auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`)

### Streaming

- **Server-Sent Events (SSE)**: progressive delivery of Markdown chunks via `?streaming=true`
- **PDF**: true progressive streaming — yields one page per SSE event
- **DOCX / ODT / ODP / XLSX / ODS / PPTX / HTML**: chunked streaming — full conversion then split into configurable chunks
- **SSE metadata events**: `started` (format, size), markdown chunks, `complete`, and `error`
- **Configurable**: enable/disable via `CAAS_STREAMING_ENABLED`, chunk size via `CAAS_STREAMING_CHUNK_SIZE`

### Metrics & Monitoring

- **Prometheus endpoint** (`GET /metrics`): text exposition format compatible with Prometheus scraping
  - HTTP request counter (`caas_http_requests_total`) by method/path/status
  - HTTP latency histogram (`caas_http_request_duration_seconds`)
  - In-progress requests gauge (`caas_http_inprogress_requests`)
  - Runtime gauges (uptime, active/pending tasks, rate limiter state)
- **HTML dashboard** (`GET /metrics/ui`): live visualization with auto-refresh
- **Zero external dependency**: in-memory collector, no additional services required

---

## 🏗️ Architecture

```
caas/
├── main.py                  # Entry point (uvicorn)
├── app/
│   ├── __init__.py
│   ├── api.py               # FastAPI application factory, middleware registration, exception handlers
│   ├── config.py            # Configuration via pydantic-settings (.env / environment variables)
│   ├── converter.py         # Conversion orchestration (delegates to converter modules)
│   ├── ocr.py               # Independent OCR module (pypdfium2 + pytesseract, reusable)
│   ├── streaming.py         # Streaming conversion via SSE (per-page for PDF, chunked for others)
│   ├── task_manager.py      # Async task manager (queue, concurrency, batches, cleanup)
│   ├── rate_limiter.py      # Native sliding-window rate limiter (zero dependency)
│   ├── validation.py        # File validation (magic bytes, MIME, ZIP bomb, DOCX structure)
│   ├── errors.py            # Secure error messages (generic codes, full details in logs)
│   ├── exceptions.py        # FastAPI exception handlers
│   ├── middleware.py        # Security headers middleware (CSP, X-Frame-Options, etc.)
│   ├── ip_helpers.py        # Secure client IP extraction with trusted proxy support
│   ├── redis_client.py      # Async Redis client with conditional import
│   ├── metrics.py           # In-memory metrics collector (counters, histograms, gauges)
│   ├── converters/          # Modular converter architecture
│   │   ├── __init__.py
│   │   ├── base.py          # Shared utilities (clean_lines, heading detection)
│   │   ├── pdf.py           # PDF → Markdown (pdfplumber + OCR fallback + link extraction)
│   │   ├── docx.py          # DOCX → Markdown (mammoth)
│   │   ├── odt.py           # ODT → Markdown (odfpy — headings, paragraphs, lists)
│   │   ├── xlsx.py          # XLSX → Markdown (openpyxl — multi-sheet, merged cells, dates)
│   │   ├── ods.py           # ODS → Markdown (ezodf — multi-sheet, merged cells, special chars)
│   │   ├── pptx.py          # PPTX → Markdown (python-pptx — slides, titles, bullets, tables)
│   │   ├── odp.py           # ODP → Markdown (odfpy — slides, titles, bullets)
│   │   └── html.py          # HTML → Markdown (BeautifulSoup4 + sanitization)
│   ├── storage/             # Storage abstraction layer (Strategy pattern)
│   │   ├── __init__.py
│   │   ├── base.py          # StorageProtocol (ABC)
│   │   ├── memory.py        # MemoryStorage (default, in-memory dict with TTL)
│   │   └── redis.py         # RedisStorage (redis.asyncio for shared state)
│   ├── routes/              # Modular route registration
│   │   ├── __init__.py
│   │   ├── convert.py       # /, /convert, /task/{task_id}, /tasks
│   │   ├── batch.py         # /convert/batch, /batch/{batch_id}
│   │   ├── health.py        # /health
│   │   └── metrics.py       # /metrics (Prometheus), /metrics/ui (HTML dashboard)
│   ├── static/              # Static assets
│   │   ├── app.js           # Frontend JavaScript (drag & drop, batch upload, polling)
│   │   └── style.css        # Frontend styles
│   └── templates/
│       ├── form.html        # Upload form (Jinja2 templating, drag & drop, batch support)
│       └── metrics.html     # Metrics dashboard (auto-refresh, Jinja2 templating)
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures (PDF, DOCX, ODT, XLSX, HTML, scanned PDF)
│   ├── test_endpoints.py    # HTTP endpoint tests
│   ├── test_batch.py        # Batch conversion tests
│   ├── test_pdf.py          # PDF converter tests
│   ├── test_docx.py         # DOCX converter tests
│   ├── test_odt.py          # ODT converter tests
│   ├── test_xlsx.py         # XLSX converter tests
│   ├── test_ods.py          # ODS converter tests
│   ├── test_pptx.py         # PPTX converter tests
│   ├── test_odp.py          # ODP converter tests
│   ├── test_html.py         # HTML converter tests
│   ├── test_validation.py   # File validation tests
│   ├── test_rate_limiter.py # Rate limiter tests
│   ├── test_task_manager.py # Task manager tests
│   ├── test_config.py           # Configuration tests
│   ├── test_docker.py           # Docker build tests
│   ├── test_streaming.py        # Streaming (SSE) tests
│   ├── test_storage_memory.py   # In-memory storage tests
│   ├── test_storage_redis.py    # Redis storage tests
│   ├── test_storage_switching.py # Storage switching tests
│   ├── test_security.py         # Security tests
│   └── test_utils.py            # Utility function tests
├── Dockerfile               # Multi-stage image with Tesseract (60+ languages)
├── docker-compose.yml       # Docker orchestration
└── pyproject.toml           # Project configuration and dependencies
```

### PDF Conversion Flow

```
Upload PDF → Text extraction (pdfplumber)
                ├─ Text found → Cleanup → Markdown
                └─ No text → OCR (pypdfium2 + Tesseract) → Cleanup → Markdown
                              └─ Hyperlink extraction → Added to Markdown
```

### Validation Flow

```
Upload → Minimum size → Magic bytes → MIME type
                                        ├─ PDF: %PDF- header validation
                                        └─ DOCX/PPTX/XLSX: ZIP bomb detection + Office Open XML structure
```

---

## 🚀 Installation

### Recommended method: Docker Compose ⭐

> **This is the simplest and fastest method.** Docker Compose automatically manages all dependencies (Python, Tesseract OCR with 60+ languages, etc.) without installing anything on your machine.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/) installed.

```bash
# Clone the repository
git clone <repo-url>
cd caas

# Build and start the service
docker-compose up --build

# Or in the background (detached)
docker-compose up -d --build
```

The server will be available at `http://localhost:8000`.

**Useful commands:**

```bash
# View logs
docker-compose logs -f

# Stop the service
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

> **Configure via `.env`**: create a `.env` file at the project root to customize settings (API keys, rate limiting, OCR languages, etc.). See the [Configuration](#-configuration) section.

---

### Local installation

**Prerequisites:**

- **Python 3.12+**
- **Tesseract OCR** (for scanned PDF support)
  - Windows: [tesseract-ocr](https://github.com/UB-Mannheim/tesseract/wiki)
  - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng`
  - macOS: `brew install tesseract`

```bash
# Clone the repository
git clone <repo-url>
cd caas

# Create the virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# or
source .venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -e ".[dev]"

# Start the server
python main.py
```

The server will start on `http://localhost:8000`.

---

## ⚙️ Configuration

All settings are externalized via **environment variables** or a **`.env`** file at the project root. The `CAAS_` prefix is used for every variable.

### Available variables

| Variable                             | Default    | Description                                                   |
| ------------------------------------ | ---------- | ------------------------------------------------------------- |
| `CAAS_RATE_LIMIT_MAX_REQUESTS`       | `30`       | Maximum number of requests per window                         |
| `CAAS_RATE_LIMIT_WINDOW_SECONDS`     | `60`       | Sliding window duration (seconds)                             |
| `CAAS_RATE_LIMIT_ENABLED`            | `true`     | Enable/disable rate limiting                                  |
| `CAAS_RATE_LIMIT_MAX_KEYS`           | `10000`    | Maximum tracked IP keys before eviction                       |
| `CAAS_TASK_MAX_CONCURRENT`           | `0` (auto) | Concurrent tasks (0 = `os.cpu_count()`)                       |
| `CAAS_TASK_MAX_QUEUE_SIZE`           | `20`       | Maximum queue size                                            |
| `CAAS_TASK_RESULT_TTL_SECONDS`       | `1800`     | Result retention time (30 min)                                |
| `CAAS_TASK_CLEANUP_INTERVAL_SECONDS` | `60`       | Cleanup interval (seconds)                                    |
| `CAAS_TASK_MAX_TASKS`                | `500`      | Maximum tasks kept in memory/storage                          |
| `CAAS_MAX_FILE_SIZE_MB`              | `50`       | Maximum uploaded file size (MB)                               |
| `CAAS_MAX_FILES_PER_REQUEST`         | `10`       | Maximum files in a batch request                              |
| `CAAS_MAX_TOTAL_SIZE_MB`             | `100`      | Maximum total batch size (MB)                                 |
| `CAAS_MAX_TASKS_PER_REQUEST`         | `5`        | Maximum async tasks per batch                                 |
| `CAAS_OCR_LANGUAGES`                 | `fra+eng`  | Tesseract languages for OCR (fra+eng always included)         |
| `CAAS_OCR_SCALE`                     | `4`        | PDF → image zoom (4 ≈ 300 DPI)                                |
| `CAAS_PDF_MAX_PAGES`                 | `500`      | Maximum PDF pages (0 = unlimited)                             |
| `CAAS_MARKDOWN_HEADING_DETECTION`    | `true`     | Enable/disable automatic heading detection for ALL-CAPS lines |
| `CAAS_TRUSTED_PROXIES`               | _(empty)_  | Trusted proxy IPs/CIDRs                                       |
| `CAAS_CORS_ORIGINS`                  | _(empty)_  | Comma-separated allowed CORS origins                          |
| `CAAS_CORS_ALLOW_CREDENTIALS`        | `false`    | Allow credentials in CORS requests                            |
| `CAAS_CORS_MAX_AGE`                  | `600`      | Preflight cache duration (seconds)                            |
| `CAAS_HOST`                          | `0.0.0.0`  | Listening IP address                                          |
| `CAAS_PORT`                          | `8000`     | Server port                                                   |
| `CAAS_RELOAD`                        | `false`    | Auto-reload mode (development only)                           |
| `CAAS_DEBUG`                         | `false`    | Expose error details (development only)                       |
| `CAAS_REDIS_URL`                     | _(empty)_  | Redis URL for shared state across instances (optional)        |
| `CAAS_STREAMING_ENABLED`             | `true`     | Enable/disable streaming responses via SSE                    |
| `CAAS_STREAMING_CHUNK_SIZE`          | `1024`     | Minimum chunk size in bytes before yielding an SSE event      |

### Redis (optional)

> **CAAS supports optional Redis for shared state** (task results, rate limiting) across multiple workers/instances.
> By default, CAAS runs in **in-memory mode** (zero external dependency).
>
> Redis uses a **Strategy pattern** (`StorageProtocol`) with two implementations:
>
> - `MemoryStorage` — in-memory dict with TTL (default, no dependencies)
> - `RedisStorage` — `redis.asyncio` for shared state across instances
>
> To enable Redis, set `CAAS_REDIS_URL` and install the optional `redis` dependency:
>
> ```bash
> pip install -e ".[redis]"
> ```
>
> ```env
> CAAS_REDIS_URL=redis://localhost:6379/0
> ```
>
> When `CAAS_REDIS_URL` is set:
>
> - **Task results** are stored in Redis with native `EXPIRE` (no periodic cleanup needed)
> - **Rate limiting** uses `INCR` + `EXPIRE` for accurate cross-instance enforcement
> - **Batch tracking** is shared across all connected instances
>
> When `CAAS_REDIS_URL` is empty (default):
>
> - Everything runs in-memory with zero external dependencies
> - Behavior is identical to the original implementation (zero regression)
>
> #### Error handling
>
> If `CAAS_REDIS_URL` is set but the `redis` package is not installed, CAAS will refuse to start
> with a clear error message. If Redis is unreachable at runtime, a connection error is logged.

### Rate Limiting — Multi-Instance Consideration

> **In-memory mode (default):** the rate limiter stores request timestamps per process.
> It does **not** share state across multiple containers, workers, or processes.
>
> If you run CAAS behind a load balancer with multiple replicas, each instance will
> enforce its own independent rate limit. For example, with 3 replicas at 30 req/min,
> a client could effectively make up to 90 req/min before being throttled.
>
> **Solution — Redis mode:** when `CAAS_REDIS_URL` is configured, rate limiting uses
> Redis `INCR` + `EXPIRE` for accurate cross-instance enforcement. All replicas share
> the same counter, so the limit is enforced globally.
>
> **Alternatives for multi-instance deployments (without Redis):**
>
> - Use an external rate limiter (e.g., Redis-backed via Nginx, API gateway, or sidecar).
> - Run a single instance and scale vertically instead of horizontally.
> - Use a reverse proxy with built-in rate limiting (e.g., Nginx `limit_req_zone`).

### ZIP Bomb Protection

| Variable                             | Default | Description                      |
| ------------------------------------ | ------- | -------------------------------- |
| `CAAS_ZIP_MAX_COMPRESSION_RATIO`     | `100.0` | Maximum compression ratio        |
| `CAAS_ZIP_MAX_TOTAL_DECOMPRESSED_MB` | `100`   | Maximum decompressed size (MB)   |
| `CAAS_ZIP_MAX_FILES`                 | `100`   | Maximum number of files in a ZIP |
| `CAAS_ZIP_MAX_FILE_NAME_LENGTH`      | `255`   | Maximum file name length         |

### Example `.env`

```env
# Rate Limiting
CAAS_RATE_LIMIT_MAX_REQUESTS=60
CAAS_RATE_LIMIT_WINDOW_SECONDS=60

# Task Manager
CAAS_TASK_MAX_CONCURRENT=4
CAAS_TASK_MAX_QUEUE_SIZE=50

# Upload
CAAS_MAX_FILE_SIZE_MB=100

# Batch
CAAS_MAX_FILES_PER_REQUEST=10
CAAS_MAX_TOTAL_SIZE_MB=100
CAAS_MAX_TASKS_PER_REQUEST=5

# OCR
CAAS_OCR_LANGUAGES=fra+eng+deu
CAAS_OCR_SCALE=4

# PDF
CAAS_PDF_MAX_PAGES=500

# Markdown
CAAS_MARKDOWN_HEADING_DETECTION=true

# Security
CAAS_TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12

# CORS
CAAS_CORS_ORIGINS=http://localhost:3000,https://app.example.com
CAAS_CORS_ALLOW_CREDENTIALS=false
CAAS_CORS_MAX_AGE=600

# Server
CAAS_HOST=0.0.0.0
CAAS_PORT=8000
CAAS_DEBUG=false

# Redis (optional — shared state across instances)
# CAAS_REDIS_URL=redis://localhost:6379/0

# Streaming
CAAS_STREAMING_ENABLED=true
CAAS_STREAMING_CHUNK_SIZE=1024
```

---

## 💻 Usage

### Web interface

Open `http://localhost:8000` in your browser and drag & drop your PDF, DOCX, ODT, XLSX, ODS, PPTX, or HTML file.

### API — Synchronous mode

```bash
# Convert a PDF
curl -X POST "http://localhost:8000/convert" \
  -F "file=@document.pdf"

# Convert a DOCX
curl -X POST "http://localhost:8000/convert" \
  -F "file=@document.docx"

# Convert an ODT file
curl -X POST "http://localhost:8000/convert" \
  -F "file=@document.odt"

# Convert an HTML file
curl -X POST "http://localhost:8000/convert" \
  -F "file=@document.html"

# Convert an XLSX file
curl -X POST "http://localhost:8000/convert" \
  -F "file=@spreadsheet.xlsx"

# Convert a PPTX presentation
curl -X POST "http://localhost:8000/convert" \
  -F "file=@presentation.pptx"
```

**Response:**

```json
{
  "success": true,
  "markdown": "# Document Title\n\nConverted content...",
  "format": "pdf",
  "size_bytes": 245760
}
```

### API — Asynchronous mode

```bash
# Submit a background task
curl -X POST "http://localhost:8000/convert?async=true" \
  -F "file=@document.pdf"
```

**Response:**

```json
{
  "success": true,
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "message": "Task submitted in the background. Use GET /task/{task_id} to retrieve the result."
}
```

```bash
# Poll for the result
curl "http://localhost:8000/task/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

### API — Streaming mode

Stream the conversion result progressively via **Server-Sent Events (SSE)**. Ideal for large documents where you want to receive content as it's being converted instead of waiting for the full result.

```bash
# Stream a PDF conversion (yields one page per event)
curl -X POST "http://localhost:8000/convert?streaming=true" \
  -F "file=@document.pdf" \
  -N
```

**Response (SSE events):**

```
data: {"format": "pdf", "size_bytes": 245760, "status": "started"}

data: # Page 1 Title\n\nContent of the first page...

data: # Page 1 Title\n\nContent of the first page...\n\n# Page 2 Title\n\nContent of the second page...

data: {"status": "complete"}

```

> **How it works:**
>
> - **PDF**: yields accumulated markdown page-by-page (true progressive streaming)
> - **DOCX / ODT / XLSX / HTML**: the full document is converted first, then split into chunks of `CAAS_STREAMING_CHUNK_SIZE` bytes
> - Each event is an SSE-formatted `data:` line
> - The first event contains metadata (format, size, status)
> - The last event signals completion (`{"status": "complete"}`)
> - On error, an error event is emitted (`{"status": "error", "message": "..."}`)

#### Streaming with JavaScript

```javascript
const response = await fetch("http://localhost:8000/convert?streaming=true", {
  method: "POST",
  body: formData,
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  // Parse SSE events (lines starting with "data: ")
  for (const line of chunk.split("\n")) {
    if (line.startsWith("data: ")) {
      const data = line.slice(6);
      console.log(JSON.parse(data));
    }
  }
}
```

### API — Batch mode (multiple files)

Convert multiple files in a single HTTP request. Each file is processed independently; failures on one file don't block others.

```bash
# Synchronous batch — convert multiple files at once
curl -X POST "http://localhost:8000/convert/batch" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.docx" \
  -F "files=@doc3.pdf"
```

**Response:**

```json
{
  "batch_id": "abc12345",
  "total_files": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    {
      "index": 0,
      "filename": "doc1.pdf",
      "success": true,
      "markdown": "# Title\n\nContent..."
    },
    {
      "index": 1,
      "filename": "doc2.docx",
      "success": true,
      "markdown": "# Title\n\nContent..."
    },
    {
      "index": 2,
      "filename": "doc3.pdf",
      "success": false,
      "error_code": "FILE_CORRUPTED",
      "message": "File appears to be corrupted or invalid."
    }
  ]
}
```

> **Status codes:** `200` when all files succeed, `207 Multi-Status` when some files fail.

#### Async batch mode

Submit a batch of files for background processing:

```bash
# Async batch — submit multiple files for background conversion
curl -X POST "http://localhost:8000/convert/batch?async=true" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.docx"
```

**Response:**

```json
{
  "batch_id": "abc12345",
  "total_files": 2,
  "tasks": [
    {
      "index": 0,
      "filename": "doc1.pdf",
      "task_id": "xyz78901",
      "status": "pending"
    },
    {
      "index": 1,
      "filename": "doc2.docx",
      "task_id": "xyz78902",
      "status": "pending"
    }
  ]
}
```

```bash
# Retrieve all results for the batch
curl "http://localhost:8000/batch/abc12345"
```

### OpenAPI Documentation

FastAPI automatically generates interactive documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 📡 API Reference

| Method | Endpoint                    | Description                                                  |
| ------ | --------------------------- | ------------------------------------------------------------ |
| `GET`  | `/`                         | HTML upload form                                             |
| `POST` | `/convert`                  | Convert PDF/DOCX/ODT/XLSX/PPTX/HTML → Markdown (synchronous) |
| `POST` | `/convert?async=true`       | Submit in background (asynchronous)                          |
| `POST` | `/convert?streaming=true`   | Stream result via Server-Sent Events (SSE)                   |
| `POST` | `/convert/batch`            | Convert multiple files in one request (batch)                |
| `POST` | `/convert/batch?async=true` | Submit batch in background (async batch)                     |
| `GET`  | `/task/{task_id}`           | Task status and result                                       |
| `GET`  | `/batch/{batch_id}`         | Retrieve all results for an async batch                      |
| `GET`  | `/tasks`                    | Queue overview                                               |
| `GET`  | `/health`                   | Health check for load balancers                              |
| `GET`  | `/metrics`                  | Prometheus text exposition format                            |
| `GET`  | `/metrics/ui`               | HTML metrics dashboard with auto-refresh                     |

### Parameters

| Parameter   | Type               | Required | Description                                                           |
| ----------- | ------------------ | -------- | --------------------------------------------------------------------- |
| `file`      | `UploadFile`       | ✅       | PDF, DOCX, ODT, XLSX, ODS, PPTX, or HTML file (max size configurable) |
| `files`     | `list[UploadFile]` | ✅       | List of PDF/DOCX/ODT/XLSX/PPTX/HTML files (batch endpoint)            |
| `async`     | `query`            | ❌       | `"true"` for asynchronous mode                                        |
| `streaming` | `query`            | ❌       | `"true"` for streaming mode (SSE)                                     |

### Error codes

| Code  | Description                                                                                                                               |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `400` | Unsupported format, missing file, file too large, corrupted file, too many files, total size exceeded, empty batch, or PDF too many pages |
| `404` | Task ID or batch ID does not exist or has expired                                                                                         |
| `429` | Rate limit exceeded                                                                                                                       |
| `500` | Internal conversion error                                                                                                                 |

### Error responses

Every error includes an `error_code` and a generic message. In debug mode (`CAAS_DEBUG=true`), full details are exposed.

```json
{
  "request_id": "a1b2c3d4",
  "error_code": "FILE_TOO_LARGE",
  "message": "The file exceeds the maximum allowed size."
}
```

---

## 🔒 Security

### Security headers

Every HTTP response includes the following security headers:

| Header                      | Value                                          | Purpose                                                               |
| --------------------------- | ---------------------------------------------- | --------------------------------------------------------------------- |
| `X-Content-Type-Options`    | `nosniff`                                      | Prevents MIME-type sniffing                                           |
| `X-Frame-Options`           | `DENY`                                         | Prevents clickjacking via iframes                                     |
| `Content-Security-Policy`   | `default-src 'none'; ...`                      | Restricts content sources (CSP strict, `object-src 'none'`, SRI hash) |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Forces HTTPS (HSTS)                                                   |
| `Permissions-Policy`        | `camera=(), microphone=(), ...`                | Restricts unused browser APIs                                         |
| `Referrer-Policy`           | `strict-origin-when-cross-origin`              | Controls referrer information                                         |

> **Note:** `X-XSS-Protection` has been intentionally removed — it is deprecated by all modern browsers and can introduce XSS-escaping vulnerabilities. The strict CSP provides superior protection.

### CORS

Cross-Origin Resource Sharing is **disabled by default** (same-origin only). To allow external clients, configure `CAAS_CORS_ORIGINS`:

```env
# Allow specific origins
CAAS_CORS_ORIGINS=http://localhost:3000,https://app.example.com
CAAS_CORS_ALLOW_CREDENTIALS=false
CAAS_CORS_MAX_AGE=600
```

### IP anti-spoofing protection

Client IP extraction is secured:

- **Without trusted proxy**: direct IP only (ignores `X-Forwarded-For`)
- **With trusted proxy**: uses `X-Forwarded-For` only if the direct connector is in `CAAS_TRUSTED_PROXIES`

### File validation

Every uploaded file is validated before conversion:

1. **Minimum size**: detection of empty or truncated files
2. **Magic bytes**: match between file header and extension
3. **MIME type**: consistency with expected format
4. **ZIP bomb detection** (DOCX): compression ratio, total size, file count, suspicious names, nested archives
5. **DOCX structure**: presence of required files, path traversal detection

### Secure error handling

- Errors return generic messages to the client
- Full details (stack traces) are only logged on the server side
- Every error response includes a `request_id` for tracing

---

## 🧪 Tests

```bash
# Run all tests
pytest tests/ -v

# With code coverage
pytest tests/ -v --cov=app --cov-report=html
```

Tests cover:

- **HTTP endpoints**: synchronous/asynchronous conversion, errors, rate limiting
- **Validation**: magic bytes, MIME type, ZIP bomb, DOCX structure
- **Converters**: PDF, DOCX, ODT, XLSX, ODS, PPTX, HTML individual converter tests
- **Streaming**: SSE progressive delivery tests
- **Storage**: in-memory, Redis, and storage switching tests
- **Task manager**: queue, concurrency, cleanup, batch tracking
- **Security**: headers, CORS, IP extraction, anti-spoofing
- **Metrics**: Prometheus exposition format and HTML dashboard rendering
- **Benchmarks**: performance measurements
- **Utilities**: text cleanup, Markdown structure detection

---

## 🐳 Docker

### Build and run

#### Via Docker Compose (recommended) ⭐

```bash
# Build and start
docker-compose up --build

# Run in the background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop and remove containers
docker-compose down
```

#### Via `docker run`

##### Pull from GitHub Container Registry (recommended)

No build step required — just pull the pre-built image:

```bash
# Latest release
docker pull ghcr.io/digifac/caas:latest

# Run it
docker run -d \
  --name caas \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  ghcr.io/digifac/caas:latest
```

##### Build locally

Build the image first:

```bash
docker build -t caas .
```

**Basic run:**

```bash
docker run -p 8000:8000 --name caas caas
```

**With environment variables (recommended):**

```bash
docker run -d \
  --name caas \
  -p 8000:8000 \
  -e CAAS_WORKERS=4 \
  -e CAAS_MAX_FILE_SIZE_MB=50 \
  -e CAAS_OCR_LANGUAGES=fra+eng \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  caas
```

**With a `.env` file:**

```bash
docker run -d \
  --name caas \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  caas
```

**With Redis for horizontal scaling:**

```bash
# Start Redis first
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Then start CAAS connected to Redis
docker run -d \
  --name caas \
  -p 8000:8000 \
  -e CAAS_REDIS_URL=redis://host.docker.internal:6379/0 \
  --restart unless-stopped \
  caas
```

> **Tip:** On macOS/Linux, use `host.docker.internal` to reach the host. On Windows Docker Desktop, it works the same way. For Linux without Docker Desktop, replace it with your actual host IP or run Redis in a separate container and link them via a custom network:
>
> ```bash
> docker network create caas-network
> docker run -d --name redis --network caas-network redis:7-alpine
> docker run -d --name caas --network caas-network \
>   -p 8000:8000 \
>   -e CAAS_REDIS_URL=redis://redis:6379/0 \
>   caas
> ```

### Docker image

The image includes:

- Python 3.12 (slim)
- Tesseract OCR with **60+ languages** (French, English, German, Spanish, Chinese, Japanese, Arabic, Hindi, etc.)
- Additional scripts (Armenian, Bengali, Devanagari, Greek, etc.)

### Redis (optional — shared state across instances)

The `docker-compose.yml` includes an optional **Redis** service for shared state (task results, rate limiting) across multiple CAAS workers/instances.

When Redis is enabled, task results and rate limiting are shared across all CAAS instances connected to the same Redis server, enabling true horizontal scaling.

**Enable Redis in production:**

```env
CAAS_REDIS_URL=redis://redis:6379/0
```

> **Without `CAAS_REDIS_URL`**, CAAS runs in **in-memory mode** (zero external dependency).
> Redis is only needed when running **multiple replicas** behind a load balancer.

#### Single instance (no Redis needed)

For a single CAAS instance, comment out the Redis dependency:

```yaml
services:
  caas:
    # ... configuration ...
    # Remove or comment out `depends_on: redis`
```

#### Multiple instances (with Redis)

To run multiple CAAS workers sharing the same state:

```yaml
services:
  caas:
    build:
      context: .
      dockerfile: Dockerfile
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
      - CAAS_REDIS_URL=redis://redis:6379/0
    deploy:
      replicas: 3
    depends_on:
      redis:
        condition: service_healthy

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

> **Note:** when running multiple replicas, you'll need a reverse proxy (Nginx, HAProxy, etc.) to distribute traffic. See the [examples/](examples/) directory for ready-to-use configurations.

### Healthcheck

A healthcheck is configured in `docker-compose.yml` to verify service availability.

---

## 📂 Examples

Ready-to-use configuration examples for deploying CAAS in production. See the [examples/](examples/) directory for full setups.

| Example                                                  | Description                                                   |
| -------------------------------------------------------- | ------------------------------------------------------------- |
| [Authelia](examples/authelia/)                           | Nginx reverse proxy with Authelia authentication (2FA, LDAP)  |
| [HAProxy + Let's Encrypt](examples/haproxy-letsencrypt/) | Reverse proxy with TLS termination and API key authentication |
| [Nginx + Let's Encrypt](examples/nginx-letsencrypt/)     | Reverse proxy with TLS termination and API key authentication |
| [Prometheus](examples/prometheus/)                       | Monitoring stack scraping CAAS metrics endpoint               |
| [n8n Workflows](examples/n8n/)                           | Ready-to-import n8n workflows for document conversion         |

---

## 📦 Dependencies

### Core

| Package             | Version Range      | Role                          |
| ------------------- | ------------------ | ----------------------------- |
| `fastapi`           | ≥ 0.115.0, < 1.0.0 | Asynchronous web framework    |
| `jinja2`            | ≥ 3.1.0, < 4.0.0   | Server-side templating        |
| `uvicorn`           | ≥ 0.32.0, < 1.0.0  | ASGI server (development)     |
| `gunicorn`          | ≥ 22.0.0, < 24.0.0 | WSGI HTTP server (production) |
| `python-multipart`  | ≥ 0.0.9, < 1.0.0   | File upload support           |
| `pydantic`          | ≥ 2.10.0, < 3.0.0  | Data validation               |
| `pydantic-settings` | ≥ 2.0.0, < 3.0.0   | Configuration via .env        |
| `pdfplumber`        | ≥ 0.11.0, < 1.0.0  | PDF text extraction           |
| `pypdfium2`         | ≥ 4.0.0, < 6.0.0   | PDF → image rendering (OCR)   |
| `mammoth`           | ≥ 1.8.0, < 2.0.0   | DOCX → Markdown conversion    |
| `odfpy`             | ≥ 1.4.0, < 2.0.0   | ODT → Markdown conversion     |
| `openpyxl`          | ≥ 3.1.0, < 4.0.0   | XLSX → Markdown conversion    |
| `python-pptx`       | ≥ 0.6.21, < 1.0.0  | PPTX → Markdown conversion    |
| `beautifulsoup4`    | ≥ 4.12.0, < 5.0.0  | HTML parsing                  |
| `pytesseract`       | ≥ 0.3.10, < 1.0.0  | Tesseract OCR interface       |
| `Pillow`            | ≥ 10.0.0, < 13.0.0 | Image processing              |

### Optional

| Package | Version Range    | Role                                       |
| ------- | ---------------- | ------------------------------------------ |
| `redis` | ≥ 5.0.0, < 6.0.0 | Shared state across instances (`.[redis]`) |

### Development

| Package          | Version Range     | Role                    |
| ---------------- | ----------------- | ----------------------- |
| `pytest`         | ≥ 8.0.0, < 10.0.0 | Test framework          |
| `pytest-asyncio` | ≥ 0.24.0, < 1.0.0 | Async test support      |
| `httpx`          | ≥ 0.27.0, < 1.0.0 | HTTP client for testing |
| `pytest-cov`     | ≥ 5.0.0, < 7.0.0  | Code coverage           |
| `reportlab`      | ≥ 4.0.0, < 5.0.0  | PDF generation (tests)  |
| `ruff`           | ≥ 0.4.0, < 2.0.0  | Linter & formatter      |
| `mypy`           | ≥ 1.10.0, < 3.0.0 | Static type checking    |
| `pre-commit`     | ≥ 3.7.0, < 6.0.0  | Git hooks management    |
| `fakeredis`      | ≥ 2.0.0, < 3.0.0  | Redis mock for testing  |

---

## 📄 License

This project is licensed under the [MIT](LICENSE) License.
