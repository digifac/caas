"""Externalized configuration via pydantic-settings (.env / environment variables)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    CAAS application configuration.

    Values can be set via:
    - Environment variables (e.g., CAAS_RATE_LIMIT_MAX=60)
    - .env file at the project root
    - Default values below
    """

    # --- Rate Limiting ---
    rate_limit_max_requests: int = 30
    """Maximum number of requests allowed per window."""

    rate_limit_window_seconds: int = 60
    """Sliding window duration in seconds."""

    rate_limit_enabled: bool = True
    """Enable/disable rate limiting (enabled by default)."""

    rate_limit_max_keys: int = 10000
    """Maximum number of tracked IP keys before eviction."""

    # --- Task Manager ---
    task_max_concurrent: int = 0
    """Number of tasks executed concurrently (0 = auto, uses os.cpu_count())."""

    task_max_queue_size: int = 20
    """Maximum queue size."""

    task_result_ttl_seconds: int = 1800
    """Result retention time in seconds (30 min)."""

    task_cleanup_interval_seconds: int = 60
    """Expired result cleanup interval in seconds."""

    task_max_tasks: int = 500
    """Maximum number of tasks kept in memory/storage."""

    # --- Upload ---
    max_file_size_mb: int = 50
    """Maximum uploaded file size in MB."""

    # --- Batch / Multi-Upload ---
    max_files_per_request: int = 10
    """Maximum number of files allowed in a single batch request."""

    max_total_size_mb: int = 100
    """Maximum total size of all files in a batch request (MB)."""

    max_tasks_per_request: int = 10
    """Maximum number of async tasks submitted per batch request (defaults to max_files_per_request)."""

    # --- ZIP Bomb Protection ---
    zip_max_compression_ratio: float = 100.0
    """Maximum allowed compression ratio per file (decompressed size / compressed size).
    Default 20x is safe for Office documents whose XML files compress well."""

    zip_max_total_decompressed_mb: int = 100
    """Maximum total decompressed size in MB for a ZIP archive."""

    zip_max_files: int = 1000
    """Maximum number of files allowed in a ZIP archive."""

    zip_max_file_name_length: int = 255
    """Maximum file name length in a ZIP archive."""

    # --- DOCX Validation ---
    docx_required_files: str = "[Content_Types].xml,word/document.xml"
    """Files required in a valid DOCX (comma-separated)."""

    # --- XLSX Validation ---
    xlsx_required_files: str = "[Content_Types].xml,xl/workbook.xml"
    """Files required in a valid XLSX (comma-separated)."""

    # --- ODS Validation ---
    ods_required_files: str = "mimetype,META-INF/manifest.xml,content.xml"
    """Files required in a valid ODS (comma-separated)."""

    ods_max_sheets: int = 50
    """Maximum number of sheets allowed in an ODS document (0 = unlimited)."""

    # --- OCR ---
    ocr_languages: str = "fra+eng"
    """Tesseract languages used for OCR (e.g., 'fra+eng', 'eng', 'deu+eng')."""

    ocr_scale: int = 4
    """Zoom factor for PDF → image rendering (4 ≈ 300 DPI)."""

    # --- PDF ---
    pdf_max_pages: int = 500
    """Maximum number of pages allowed for a PDF document (0 = unlimited)."""

    # --- Markdown Conversion ---
    markdown_heading_detection: bool = True
    """Enable/disable automatic heading detection for uppercase short lines during conversion."""

    # --- Security ---
    trusted_proxies: str = ""
    """List of trusted proxy IPs/CIDRs (comma-separated). E.g., '10.0.0.0/8,172.16.0.0/12'. Empty = no proxy."""

    # --- CORS ---
    cors_origins: str = ""
    """Comma-separated list of allowed CORS origins. Empty = no CORS (same-origin only). E.g., 'http://localhost:3000,https://app.example.com'."""

    cors_allow_credentials: bool = False
    """Allow credentials (cookies, auth headers) in CORS requests."""

    cors_max_age: int = 600
    """Cache duration for preflight responses in seconds."""

    # --- Redis (optional) ---
    redis_url: str = ""
    """Redis connection URL for shared state (task results, rate limiting) across multiple workers/instances.
    Empty = in-memory mode (default). E.g., 'redis://localhost:6379/0'."""

    # --- Streaming ---
    streaming_enabled: bool = True
    """Enable streaming responses for large documents via SSE."""

    streaming_chunk_size: int = 1024
    """Minimum chunk size in bytes before yielding a streaming event."""

    # --- Server ---
    host: str = "0.0.0.0"
    """Server listening IP address."""

    port: int = 8000
    """Server port."""

    reload: bool = False
    """Auto-reload mode (set to True only for development)."""

    debug: bool = False
    """Debug mode: exposes error details to clients (set to True only for development)."""

    model_config = SettingsConfigDict(
        env_prefix="CAAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ocr_languages_resolved(self) -> str:
        """Return OCR languages with fra+eng guaranteed (always included)."""
        required = {"fra", "eng"}
        current = {
            lang.strip() for lang in self.ocr_languages.split("+") if lang.strip()
        }
        merged = required | current
        return "+".join(sorted(merged))

    @property
    def redis_enabled(self) -> bool:
        """Auto-detected: True when redis_url is configured."""
        return bool(self.redis_url.strip())

    @property
    def cors_origins_list(self) -> list:
        """Return the list of allowed CORS origins."""
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxies_list(self) -> list:
        """Return the list of trusted proxies (CIDR strings or IPs)."""
        if not self.trusted_proxies:
            return []
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]


# Global configuration instance
settings = Settings()
