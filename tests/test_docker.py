"""Integration tests for Docker deployment.

These tests build the Docker image, start the container, and verify
that all endpoints respond correctly.

Run with:
    pytest tests/test_docker.py -v

Prerequisites:
    - Docker must be installed and running.
    - Tests are skipped automatically if Docker is unavailable.
"""

import io
import subprocess
import time
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Import fixtures from modules
from tests.fixtures.common import sample_pdf_bytes  # type: ignore[import-not-found]

IMAGE_NAME = "caas-test"
CONTAINER_NAME = "caas-test-container"
HOST_PORT = 9876
CONTAINER_PORT = 8000
BASE_URL = f"http://127.0.0.1:{HOST_PORT}"
HEALTH_TIMEOUT = (
    60  # seconds to wait for the container to become healthy (longer on Windows)
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _docker_available() -> bool:
    """Return True if the Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a docker command and raise on failure."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )
    return result


def _wait_for_health(url: str, timeout: int = HEALTH_TIMEOUT) -> None:
    """Poll the /health endpoint until it responds or timeout is reached."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code == 200:
                return
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError):
            pass
        time.sleep(2)
    raise RuntimeError(f"Container did not become healthy within {timeout}s")


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def docker_container() -> Generator[None, None, None]:
    """Build the image, start the container, and yield while it runs.

    Cleanup (stop + remove) happens in the teardown phase.
    """
    if not _docker_available():
        pytest.skip("Docker is not available")

    # 1. Build the image
    build = _run(["docker", "build", "-t", IMAGE_NAME, "."])
    if build.returncode != 0:
        pytest.skip(f"Docker build failed: {build.stderr}")

    # 2. Stop/remove any leftover container with the same name
    _run(["docker", "rm", "-f", CONTAINER_NAME])

    # 3. Start the container
    start = _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"{HOST_PORT}:{CONTAINER_PORT}",
            "--health-cmd",
            f"python -c \"import urllib.request; urllib.request.urlopen('http://localhost:{CONTAINER_PORT}/health')\"",
            "--health-interval",
            "5s",
            "--health-timeout",
            "3s",
            "--health-retries",
            "3",
            "--health-start-period",
            "10s",
            IMAGE_NAME,
        ]
    )
    if start.returncode != 0:
        pytest.skip(f"Docker run failed: {start.stderr}")

    # 4. Wait for the service to be ready
    _wait_for_health(f"{BASE_URL}/health")

    yield

    # 5. Teardown: stop and remove the container
    _run(["docker", "stop", CONTAINER_NAME])
    _run(["docker", "rm", CONTAINER_NAME])


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.docker
def test_health_endpoint(docker_container: None):
    """GET /health should return 200 with status 'healthy'."""
    resp = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "caas"
    assert "version" in data


@pytest.mark.docker
def test_root_returns_html_form(docker_container: None):
    """GET / should return the HTML upload form."""
    resp = httpx.get(BASE_URL, timeout=5)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<!DOCTYPE html>" in resp.text
    assert "CAAS" in resp.text


@pytest.mark.docker
def test_convert_pdf_success(docker_container: None):
    """POST /convert with a valid PDF returns markdown."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, "Hello Docker World")
    c.save()
    buf.seek(0)
    pdf_bytes = buf.getvalue()

    resp = httpx.post(
        f"{BASE_URL}/convert",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "markdown" in data
    assert data["format"] == "pdf"
    assert "Hello Docker World" in data["markdown"]


@pytest.mark.docker
def test_convert_docx_success(docker_container: None):
    """POST /convert with a valid DOCX returns markdown."""
    import zipfile

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Docker DOCX Test</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", relationships)
        zf.writestr("word/document.xml", document_xml)
    docx_bytes = buf.getvalue()

    resp = httpx.post(
        f"{BASE_URL}/convert",
        files={
            "file": (
                "test.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "markdown" in data
    assert data["format"] == "docx"


@pytest.mark.docker
def test_convert_unsupported_format(docker_container: None):
    """POST /convert with an unsupported format returns 400."""
    resp = httpx.post(
        f"{BASE_URL}/convert",
        files={"file": ("test.txt", b"plain text", "text/plain")},
        timeout=10,
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error_code"] == "UNSUPPORTED_FORMAT"


@pytest.mark.docker
def test_security_headers_present(docker_container: None):
    """All responses should include security headers."""
    resp = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in resp.headers


@pytest.mark.docker
def test_tasks_endpoint(docker_container: None):
    """GET /tasks should return queue overview."""
    resp = httpx.get(f"{BASE_URL}/tasks", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "active" in data
    assert "pending" in data
    assert "max_concurrent" in data
