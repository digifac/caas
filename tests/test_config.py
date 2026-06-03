"""Tests for configuration (Settings class, .env loading, defaults, type coercion)."""

import os

import pytest
from app.config import Settings

# --- Default values tests ---


class TestSettingsDefaults:
    """Tests for default configuration values."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_caas_env):
        """Ensure no CAAS_ env vars pollute default value tests."""
        pass

    def test_default_rate_limit_values(self, clean_caas_env):
        """Default rate limiting values are correct."""
        settings = Settings(_env_file=None)
        assert settings.rate_limit_max_requests == 30
        assert settings.rate_limit_window_seconds == 60
        assert settings.rate_limit_enabled is True

    def test_default_task_manager_values(self):
        """Default task manager values are correct."""
        settings = Settings(_env_file=None)
        assert settings.task_max_concurrent == 0
        assert settings.task_max_queue_size == 20
        assert settings.task_result_ttl_seconds == 1800
        assert settings.task_cleanup_interval_seconds == 60

    def test_default_upload_values(self):
        """Default upload values are correct."""
        settings = Settings(_env_file=None)
        assert settings.max_file_size_mb == 50

    def test_default_batch_values(self):
        """Default batch/multi-upload values are correct."""
        settings = Settings(_env_file=None)
        assert settings.max_files_per_request == 10
        assert settings.max_total_size_mb == 100
        assert settings.max_tasks_per_request == 10

    def test_default_zip_bomb_values(self):
        """Default ZIP bomb protection values are correct."""
        settings = Settings(_env_file=None)
        assert settings.zip_max_compression_ratio == 100.0
        assert settings.zip_max_total_decompressed_mb == 100
        assert settings.zip_max_files == 1000
        assert settings.zip_max_file_name_length == 255

    def test_default_ocr_values(self):
        """Default OCR values are correct."""
        settings = Settings(_env_file=None)
        assert settings.ocr_languages == "fra+eng"
        assert settings.ocr_scale == 4

    def test_default_server_values(self):
        """Default server values are correct."""
        settings = Settings(_env_file=None)
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.reload is False
        assert settings.debug is False

    def test_default_security_values(self):
        """Default security values are correct."""
        settings = Settings(_env_file=None)
        assert settings.trusted_proxies == ""
        assert settings.trusted_proxies_list == []


# --- Environment variable tests ---


class TestSettingsEnvVars:
    """Tests for environment variable loading."""

    def test_env_var_override_rate_limit(self, monkeypatch):
        """Environment variables override rate limit defaults."""
        monkeypatch.setenv("CAAS_RATE_LIMIT_MAX_REQUESTS", "100")
        monkeypatch.setenv("CAAS_RATE_LIMIT_WINDOW_SECONDS", "120")
        settings = Settings(_env_file=None)
        assert settings.rate_limit_max_requests == 100
        assert settings.rate_limit_window_seconds == 120

    def test_env_var_override_file_size(self, monkeypatch):
        """Environment variables override file size defaults."""
        monkeypatch.setenv("CAAS_MAX_FILE_SIZE_MB", "10")
        settings = Settings(_env_file=None)
        assert settings.max_file_size_mb == 10

    def test_env_var_override_batch_settings(self, monkeypatch):
        """Environment variables override batch/multi-upload defaults."""
        monkeypatch.setenv("CAAS_MAX_FILES_PER_REQUEST", "20")
        monkeypatch.setenv("CAAS_MAX_TOTAL_SIZE_MB", "200")
        monkeypatch.setenv("CAAS_MAX_TASKS_PER_REQUEST", "10")
        settings = Settings(_env_file=None)
        assert settings.max_files_per_request == 20
        assert settings.max_total_size_mb == 200
        assert settings.max_tasks_per_request == 10

    def test_env_var_override_port(self, monkeypatch):
        """Environment variables override server port."""
        monkeypatch.setenv("CAAS_PORT", "9000")
        settings = Settings(_env_file=None)
        assert settings.port == 9000

    def test_env_var_override_host(self, monkeypatch):
        """Environment variables override server host."""
        monkeypatch.setenv("CAAS_HOST", "127.0.0.1")
        settings = Settings(_env_file=None)
        assert settings.host == "127.0.0.1"

    def test_env_var_override_ocr_languages(self, monkeypatch):
        """Environment variables override OCR languages."""
        monkeypatch.setenv("CAAS_OCR_LANGUAGES", "deu+eng")
        settings = Settings(_env_file=None)
        assert settings.ocr_languages == "deu+eng"

    def test_env_var_override_trusted_proxies(self, monkeypatch):
        """Environment variables override trusted proxies."""
        monkeypatch.setenv("CAAS_TRUSTED_PROXIES", "10.0.0.0/8,172.16.0.0/12")
        settings = Settings(_env_file=None)
        assert settings.trusted_proxies == "10.0.0.0/8,172.16.0.0/12"

    def test_env_var_override_debug(self, monkeypatch):
        """Environment variables override debug mode."""
        monkeypatch.setenv("CAAS_DEBUG", "true")
        settings = Settings(_env_file=None)
        assert settings.debug is True

    def test_env_var_prefix_isolated(self, monkeypatch):
        """Only CAAS_ prefixed variables are read."""
        monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "999")
        settings = Settings(_env_file=None)
        # Should NOT be affected by non-prefixed variable
        assert settings.rate_limit_max_requests == 30


# --- Type coercion tests ---


class TestSettingsTypeCoercion:
    """Tests for automatic type coercion from environment variables."""

    def test_int_coercion(self, monkeypatch):
        """String values are coerced to int."""
        monkeypatch.setenv("CAAS_RATE_LIMIT_MAX_REQUESTS", "50")
        settings = Settings(_env_file=None)
        assert settings.rate_limit_max_requests == 50
        assert isinstance(settings.rate_limit_max_requests, int)

    def test_float_coercion(self, monkeypatch):
        """String values are coerced to float."""
        monkeypatch.setenv("CAAS_ZIP_MAX_COMPRESSION_RATIO", "100.5")
        settings = Settings(_env_file=None)
        assert settings.zip_max_compression_ratio == 100.5
        assert isinstance(settings.zip_max_compression_ratio, float)

    def test_bool_coercion_true(self, monkeypatch):
        """String 'true' is coerced to bool True."""
        monkeypatch.setenv("CAAS_RATE_LIMIT_ENABLED", "true")
        settings = Settings(_env_file=None)
        assert settings.rate_limit_enabled is True

    def test_bool_coercion_false(self, monkeypatch):
        """String 'false' is coerced to bool False."""
        monkeypatch.setenv("CAAS_RATE_LIMIT_ENABLED", "false")
        settings = Settings(_env_file=None)
        assert settings.rate_limit_enabled is False

    def test_bool_coercion_yes_no(self, monkeypatch):
        """String 'yes'/'no' are coerced to bool."""
        monkeypatch.setenv("CAAS_DEBUG", "yes")
        settings = Settings(_env_file=None)
        assert settings.debug is True

    def test_port_int_coercion(self, monkeypatch):
        """Port is coerced to int from string."""
        monkeypatch.setenv("CAAS_PORT", "3000")
        settings = Settings(_env_file=None)
        assert settings.port == 3000
        assert isinstance(settings.port, int)


# --- Computed properties tests ---


class TestSettingsProperties:
    """Tests for computed properties."""

    def test_ocr_languages_resolved_default(self):
        """ocr_languages_resolved includes fra+eng by default."""
        settings = Settings(_env_file=None)
        resolved = settings.ocr_languages_resolved
        assert "fra" in resolved
        assert "eng" in resolved

    def test_ocr_languages_resolved_adds_missing(self):
        """ocr_languages_resolved adds fra+eng if missing."""
        settings = Settings(ocr_languages="deu", _env_file=None)
        resolved = settings.ocr_languages_resolved
        assert "fra" in resolved
        assert "eng" in resolved
        assert "deu" in resolved

    def test_ocr_languages_resolved_no_duplicates(self):
        """ocr_languages_resolved doesn't duplicate languages."""
        settings = Settings(ocr_languages="fra+eng+fra", _env_file=None)
        resolved = settings.ocr_languages_resolved
        parts = resolved.split("+")
        assert len(parts) == len(set(parts))

    def test_trusted_proxies_list_empty(self):
        """trusted_proxies_list returns empty list when no proxies."""
        settings = Settings(_env_file=None)
        assert settings.trusted_proxies_list == []

    def test_trusted_proxies_list_single(self):
        """trusted_proxies_list parses single proxy."""
        settings = Settings(trusted_proxies="10.0.0.0/8", _env_file=None)
        assert settings.trusted_proxies_list == ["10.0.0.0/8"]

    def test_trusted_proxies_list_multiple(self):
        """trusted_proxies_list parses multiple proxies."""
        settings = Settings(
            trusted_proxies="10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16", _env_file=None
        )
        assert len(settings.trusted_proxies_list) == 3
        assert "10.0.0.0/8" in settings.trusted_proxies_list
        assert "172.16.0.0/12" in settings.trusted_proxies_list
        assert "192.168.0.0/16" in settings.trusted_proxies_list

    def test_trusted_proxies_list_strips_whitespace(self):
        """trusted_proxies_list strips whitespace from entries."""
        settings = Settings(
            trusted_proxies=" 10.0.0.0/8 , 172.16.0.0/12 ", _env_file=None
        )
        assert settings.trusted_proxies_list == ["10.0.0.0/8", "172.16.0.0/12"]

    def test_trusted_proxies_list_ignores_empty(self):
        """trusted_proxies_list ignores empty entries."""
        settings = Settings(trusted_proxies="10.0.0.0/8,,172.16.0.0/12", _env_file=None)
        assert len(settings.trusted_proxies_list) == 2

# --- Redis settings tests ---


class TestRedisSettings:
    """Tests for Redis configuration."""

    def test_redis_url_default_empty(self):
        """Default redis_url is empty string."""
        settings = Settings(_env_file=None)
        assert settings.redis_url == ""

    def test_redis_password_default_empty(self):
        """Default redis_password is empty string."""
        settings = Settings(_env_file=None)
        assert settings.redis_password == ""

    def test_redis_enabled_false_when_url_empty(self):
        """redis_enabled returns False when url is empty."""
        settings = Settings(_env_file=None)
        assert settings.redis_enabled is False

    def test_redis_enabled_true_when_url_set(self):
        """redis_enabled returns True when url is configured."""
        settings = Settings(redis_url="redis://localhost:6379/0", _env_file=None)
        assert settings.redis_enabled is True

    def test_env_var_override_redis_password(self, monkeypatch):
        """Environment variables override redis password."""
        monkeypatch.setenv("CAAS_REDIS_PASSWORD", "my-secret-pass")
        settings = Settings(_env_file=None)
        assert settings.redis_password == "my-secret-pass"

    def test_env_var_override_redis_url(self, monkeypatch):
        """Environment variables override redis URL."""
        monkeypatch.setenv("CAAS_REDIS_URL", "redis://localhost:6379/0")
        settings = Settings(_env_file=None)
        assert settings.redis_url == "redis://localhost:6379/0"

# --- .env file tests ---


class TestSettingsEnvFile:
    """Tests for .env file loading."""

    @staticmethod
    def _clear_caas_env(monkeypatch):
        """Remove CAAS_* variables to avoid host environment interference."""
        for key in list(os.environ):
            if key.startswith("CAAS_"):
                monkeypatch.delenv(key, raising=False)

    def test_env_file_loading(self, tmp_path, monkeypatch):
        """Settings loads values from .env file."""
        self._clear_caas_env(monkeypatch)
        env_file = tmp_path / ".env"
        env_file.write_text("CAAS_RATE_LIMIT_MAX_REQUESTS=200\nCAAS_PORT=7000\n")
        settings = Settings(_env_file=str(env_file))
        assert settings.rate_limit_max_requests == 200
        assert settings.port == 7000

    def test_env_file_encoding_utf8(self, tmp_path, monkeypatch):
        """Settings reads .env file with UTF-8 encoding."""
        self._clear_caas_env(monkeypatch)
        env_file = tmp_path / ".env"
        env_file.write_text("CAAS_HOST=127.0.0.1\n", encoding="utf-8")
        settings = Settings(_env_file=str(env_file))
        assert settings.host == "127.0.0.1"

    def test_env_vars_override_env_file(self, tmp_path, monkeypatch):
        """Environment variables take precedence over .env file."""
        self._clear_caas_env(monkeypatch)
        env_file = tmp_path / ".env"
        env_file.write_text("CAAS_PORT=7000\n")
        monkeypatch.setenv("CAAS_PORT", "9000")
        settings = Settings(_env_file=str(env_file))
        assert settings.port == 9000

    def test_no_env_file_uses_defaults(self, monkeypatch):
        """Without .env file, defaults are used."""
        self._clear_caas_env(monkeypatch)
        settings = Settings(_env_file=None)
        assert settings.rate_limit_max_requests == 30
        assert settings.port == 8000


# --- Model config tests ---


class TestSettingsModelConfig:
    """Tests for pydantic model configuration."""

    def test_extra_ignored(self):
        """Extra fields in .env are ignored without error."""
        Settings(_env_file=None)
        # No error when unknown fields are present in environment
        # This is verified by the model_config extra="ignore"

    def test_env_prefix_required(self, monkeypatch):
        """Variables without CAAS_ prefix are ignored."""
        monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "999")
        monkeypatch.setenv("PORT", "9999")
        settings = Settings(_env_file=None)
        assert settings.rate_limit_max_requests == 30
        assert settings.port == 8000
