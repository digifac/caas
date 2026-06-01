# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- **ODP → Markdown** converter (`app/converters/odp.py`)
  - OpenDocument Presentation conversion via `odfpy`
  - Slide-by-slide text extraction with `## Slide N` headers
  - Title detection and bullet lists support
  - Streaming support via `_convert_odp_stream` in `app/streaming.py`
  - Full validation: magic bytes, MIME type, ZIP structure, minimum file size
  - Tests: `test_odp.py` (unit, API sync, API async/batch tests)
- **ODS → Markdown** converter (`app/converters/ods.py`)
  - OpenDocument Spreadsheet conversion via `ezodf`
  - Multi-sheet support with sheet name headers and `---` separators
  - Merged cells handling (fills merged ranges with top-left value)
  - Special characters escaping (`|` → `\|`, newlines → spaces)
  - Empty sheets skipped with optional placeholder message
  - Streaming support via `_convert_ods_stream` in `app/streaming.py`
  - Full validation: magic bytes, MIME type, ZIP structure, minimum file size
  - Tests: `test_ods.py` (unit, API sync, API async/batch tests)
- **PPTX → Markdown** converter (`app/converters/pptx.py`)
  - PowerPoint presentation conversion via `python-pptx`
  - Slide-by-slide text extraction with `## Slide N` headers
  - Title detection (`slide.shapes.title`)
  - Bullet lists support (nested lists preserved)
  - Table extraction from slides
  - Warnings logged for unsupported elements (images, charts, SmartArt, etc.)
  - Post-processing with `clean_lines()` from `app/converters/base.py`
  - Streaming support via `_convert_pptx_stream` in `app/streaming.py`
  - Full validation: magic bytes, MIME type, ZIP structure, minimum file size
  - Tests: `test_pptx.py` (unit, integration, validation tests)
- **Renforced security headers** in `app/middleware.py`
  - **Permissions-Policy** — restricts unused browser APIs (`camera`, `microphone`, `geolocation`, `payment`, `usb`, `magnetometer`, `gyroscope`, `accelerometer`)
  - **HSTS** — `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` forces HTTPS
  - **CSP hardened** — `object-src 'none'` added to both app and docs policies; SRI hash for `script-src`
  - **X-XSS-Protection removed** — deprecated header that can introduce XSS-escaping vulnerabilities; strict CSP provides superior protection
- **Extended HTML sanitization** in `app/converters/html.py`
  - Added 6 dangerous tags to `_DANGEROUS_TAGS`: `math`, `template`, `details`, `marquee`, `video`, `audio`
  - Rationale: `math` mscript XSS, `template` content access, interactive content, deprecated tags, external resource loading
- **New security tests** in `tests/test_security.py`
  - `TestDangerousTagsRemoval` — 4 tests for new dangerous tags (math, template, details, marquee)
  - `TestNewSecurityHeaders` — 5 tests (no X-XSS-Protection, HSTS present, Permissions-Policy present, CSP object-src none, CSP docs object-src none)
  - **56 security tests** total (was 47)
- **Memory protection for RateLimiter** — strict upper bound on tracked IP keys
  - `rate_limit_max_keys` parameter (default: `10000`) limits the number of tracked IPs
  - Proactive eviction of oldest keys when limit is exceeded (`_evict_oldest_if_over_limit`)
  - Guarantees bounded memory consumption even under extreme load
- **Memory protection for TaskManager** — strict upper bound on in-memory tasks
  - `task_max_tasks` parameter (default: `500`) limits the number of tasks kept in memory
  - Proactive eviction of old completed/failed tasks when limit is exceeded (`_evict_completed_tasks`)
  - Evicted tasks are persisted to storage before removal from memory
  - Async-safe cleanup startup via lock (`_cleanup_lock`)
- **New configuration variables**
  - `CAAS_RATE_LIMIT_MAX_KEYS` — maximum tracked IP keys before eviction (default: `10000`)
  - `CAAS_TASK_MAX_TASKS` — maximum tasks kept in memory/storage (default: `500`)
- **Streaming mode** via Server-Sent Events (SSE) (`?streaming=true`)
  - `app/streaming.py` — progressive delivery of Markdown chunks
  - PDF: true progressive streaming (yields one page per SSE event)
  - DOCX/ODT/HTML: chunked streaming (configurable via `CAAS_STREAMING_CHUNK_SIZE`)
  - SSE metadata events: `started` (format, size), markdown chunks, `complete`, `error`
  - `CAAS_STREAMING_ENABLED` — enable/disable streaming (default: `true`)
  - `CAAS_STREAMING_CHUNK_SIZE` — minimum chunk size in bytes (default: `1024`)
  - `X-Accel-Buffering: no` header to disable nginx buffering
  - Tests: `test_streaming.py`
- **Modular route registration** (`app/routes/`)
  - `app/routes/convert.py` — `/`, `/convert`, `/task/{task_id}`, `/tasks`
  - `app/routes/batch.py` — `/convert/batch`, `/batch/{batch_id}`
  - `app/routes/health.py` — `/health`
- **Optional Redis support** for shared state across instances
  - `StorageProtocol` (ABC) with `MemoryStorage` (default) and `RedisStorage` (`redis.asyncio`)
  - `TaskManager` and `RateLimiter` accept interchangeable `StorageProtocol`
  - Activation via `CAAS_REDIS_URL` environment variable (zero regression when empty)
  - `[redis]` optional dependency in `pyproject.toml`
  - `docker-compose.yml` includes optional Redis service
  - `app/storage/` — new storage abstraction layer (`base.py`, `memory.py`, `redis.py`)
  - `app/redis_client.py` — async Redis client with conditional import
  - Tests: `test_storage_memory.py`, `test_storage_redis.py`, `test_storage_switching.py`
- **HTML → Markdown** converter (`app/converters/html.py`)
  - BeautifulSoup4-based parsing with custom Markdown output
  - Security sanitization: blocks dangerous URL schemes (`javascript:`, `data:`, etc.) and strips event handlers
  - Supports headings, paragraphs, lists, links, images, tables, code blocks, blockquotes, and inline formatting
- **ODT → Markdown** converter (`app/converters/odt.py`)
  - Pure Python conversion via `odfpy` (zero external dependencies beyond the library)
  - Handles paragraphs, headings, list items, tabs, and line breaks
- **XLSX → Markdown** converter (`app/converters/xlsx.py`)
  - Spreadsheet-to-table conversion via `openpyxl`
  - Multi-sheet support with sheet name headers and `---` separators
  - Merged cells handling (fills merged ranges with top-left value)
  - Date/time formatting via `datetime`, number formatting with configurable precision
  - Special characters escaping (`|` → `\|`, newlines → spaces)
  - Empty sheets skipped with optional placeholder message
  - Streaming support via `_convert_xlsx_stream` in `app/streaming.py`
  - Tests: `test_xlsx.py`, XLSX tests in `test_endpoints.py`, `test_batch.py`, `test_streaming.py`
- **ZIP utilities refactoring** (`app/zip_utils.py`)
  - Extracted from `app/validation.py` for reuse by XLSX converter
  - Functions: `safe_unzip()`, `safe_unzip_to_bytes()`, `detect_zip_bomb()`, `safe_zip_path()`
- **New configuration variables**
  - `CAAS_XLSX_MAX_SHEETS` — maximum sheets processed (default: `50`)
  - `CAAS_XLSX_MAX_ROWS` — maximum rows per sheet (default: `10000`)
  - `CAAS_XLSX_MAX_COLS` — maximum columns per sheet (default: `52`)
  - `CAAS_XLSX_NUMBER_PRECISION` — decimal places for numbers (default: `6`)
  - `CAAS_XLSX_EMPTY_SHEET_MESSAGE` — placeholder for empty sheets (empty = skip)
- **Shared converter utilities** (`app/converters/base.py`)
  - `clean_lines()` — common text cleanup and Markdown structure detection
  - `is_uppercase_heading()` — ALL-CAPS heading detection with configurable thresholds
- **Batch / Multi-Upload** support via `POST /convert/batch`
  - Upload multiple PDF/DOCX files in a single HTTP request
  - Independent per-file results (failures don't block other files)
  - `207 Multi-Status` response when some files fail
  - Each file counts toward rate limiting (N files = N requests)
- **Async batch mode** (`POST /convert/batch?async=true`)
  - Each valid file submitted as a separate background task
  - `GET /batch/{batch_id}` to retrieve all results for a batch
  - Queue saturation protection via `CAAS_MAX_TASKS_PER_REQUEST`
- **Batch configuration variables**
  - `CAAS_MAX_FILES_PER_REQUEST` — maximum files per batch (default: 10)
  - `CAAS_MAX_TOTAL_SIZE_MB` — maximum total batch size (default: 100 MB)
  - `CAAS_MAX_TASKS_PER_REQUEST` — maximum async tasks per batch (default: 5)
- **New error codes**: `TOO_MANY_FILES`, `TOTAL_SIZE_EXCEEDED`, `BATCH_PARTIAL_FAILURE`, `BATCH_EMPTY`, `BATCH_NOT_FOUND`, `QUEUE_FULL`
- **Batch request logging** with `batch_id`, file count, and client IP
- **Health check endpoint** (`GET /health`) for load balancers and orchestrators

### Changed

- **Improved heading detection** in `app/converters/base.py` — `is_uppercase_heading()` now excludes common acronyms (`API`, `URL`, `HTTP`, etc.) and requires minimum 3 characters to reduce false positives
- **Extracted OCR logic** into a new independent `app/ocr.py` module
  - Reusable by any converter (not coupled to PDF converter)
  - Functions: `ocr_image`, `ocr_pdf_page`, `ocr_pdf_pages`, `ocr_image_bytes`
  - Zero-disk I/O with proper resource cleanup (PIL Image / pypdfium2 PdfDocument)
- **Improved type annotations** in `app/ocr.py` — `lang: Optional[str] = None` for correctness.

- **Split monolithic `app/main.py`** into modular architecture:
  - `app/api.py` — FastAPI application factory, middleware registration, exception handlers
  - `app/converter.py` — Conversion orchestration (delegates to converter modules)
  - `app/errors.py` — Secure error messages
  - `app/main.py` — Thin entry point with re-exports
  - `app/routes/` — Modular route registration (convert, batch, health)
  - `app/converters/` — Per-format converter modules (pdf, docx, odt, html)
  - `app/storage/` — Storage abstraction layer (memory, redis)

### To Do

- Add automated deployment workflow
- Penetration testing on batch endpoint

---

## [1.0.0] - 2026-05-21

### Added

- **PDF → Markdown** conversion via `pdfplumber` with native text extraction
- **DOCX → Markdown** conversion via `mammoth`
- **Automatic OCR** fallback using Tesseract for scanned PDFs (60+ languages)
- **Link extraction** for URI hyperlinks embedded in PDFs
- **Synchronous mode** for immediate conversion responses
- **Asynchronous mode** with queue and polling support (`?async=true`)
- **Rate limiting** with native sliding window per IP (30 req/min default)
- **File validation**: magic bytes, MIME type, ZIP bomb detection, DOCX structure checks
- **Anti-spoofing protection** with secure IP extraction and trusted proxy support
- **Web interface** with built-in upload form and drag & drop
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`
- **CORS middleware** configurable via `CAAS_CORS_ORIGINS`
- **Docker support** with multi-stage build and Tesseract (60+ languages)
- **Non-root Docker user** (`appuser`) for improved container security
- `.dockerignore` and `.gitignore` for clean builds
- `.env.example` with all `CAAS_*` configuration variables documented
- **Comprehensive test suite**: endpoints, validation, rate limiter, task manager, config

### Changed

- **Split `app/main.py`** into modular architecture:
  - `app/converter.py` — PDF/DOCX conversion logic, OCR, text cleanup
  - `app/api.py` — FastAPI endpoints, middleware, exception handlers
  - `app/errors.py` — Secure error messages
  - `app/main.py` — Thin entry point with re-exports
- **Tightened version upper bounds** in `requirements.txt` to prevent breaking changes
- **Separated dev and production dependencies** into `requirements-dev.txt` and `[project.optional-dependencies]`
- **Completed `pyproject.toml`** with full project metadata, authors, license, URLs, and build system
- **Removed personal info** from `app/templates/form.html`
- **Zero-disk I/O**: all conversions run entirely in memory with no temporary files

### Security

- Secure error handling: generic messages in production, full details in server logs
- Anti-spoofing IP extraction with trusted proxy configuration
- ZIP bomb detection during file validation
- Non-root container execution

---

[Unreleased]: https://github.com/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/compare/v1.0.0
