"""Tests for HTML to Markdown conversion."""

import asyncio

import httpx
import pytest
from app.converters.html import sanitize_url, convert_html_to_md

# Import fixtures from modules
from tests.fixtures.common import async_client # type: ignore[import-not-found]
from tests.fixtures.html import sample_html_bytes, sample_html_latin1_bytes, sample_html_minimal_bytes # type: ignore[import-not-found]


@pytest.mark.anyio
async def test_convert_html_success(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with a valid HTML returns markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "markdown" in data
    assert data["format"] == "html"
    assert data["size_bytes"] == len(sample_html_bytes)
    assert "Main Title" in data["markdown"]


@pytest.mark.anyio
async def test_convert_html_headings(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts headings to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "# Main Title" in markdown


@pytest.mark.anyio
async def test_convert_html_links(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts links to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "[our website](https://example.com)" in markdown


@pytest.mark.anyio
async def test_convert_html_bold_italic(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts bold and italic to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "**bold**" in markdown
    assert "*italic*" in markdown


@pytest.mark.anyio
async def test_convert_html_lists(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts lists to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "- First item" in markdown
    assert "- Second item" in markdown
    assert "1. Step one" in markdown
    assert "2. Step two" in markdown


@pytest.mark.anyio
async def test_convert_html_table(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts tables to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "| Name | Value |" in markdown
    assert "| --- | --- |" in markdown
    assert "| A | 1 |" in markdown
    assert "| B | 2 |" in markdown


@pytest.mark.anyio
async def test_convert_html_blockquote(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts blockquotes to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "> A quoted paragraph" in markdown


@pytest.mark.anyio
async def test_convert_html_code_block(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts code blocks to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "```" in markdown
    assert "def hello():" in markdown


@pytest.mark.anyio
async def test_convert_html_image(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts images to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "![test image](image.png)" in markdown


@pytest.mark.anyio
async def test_convert_html_horizontal_rule(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with HTML correctly converts horizontal rules to Markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "---" in markdown


@pytest.mark.anyio
async def test_convert_html_minimal(
    async_client: httpx.AsyncClient, sample_html_minimal_bytes: bytes
):
    """POST /convert with minimal HTML returns correct markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("minimal.html", sample_html_minimal_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    markdown = data["markdown"]
    assert "# Hello World" in markdown
    assert "This is a simple paragraph." in markdown


@pytest.mark.anyio
async def test_convert_html_latin1_encoding(
    async_client: httpx.AsyncClient, sample_html_latin1_bytes: bytes
):
    """POST /convert with Latin-1 encoded HTML returns correct markdown."""
    response = await async_client.post(
        "/convert", files={"file": ("latin1.html", sample_html_latin1_bytes)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    markdown = data["markdown"]
    assert "Document en français" in markdown
    assert "àéîôù" in markdown


@pytest.mark.anyio
async def test_convert_html_uppercase_extension(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """POST /convert with .HTML extension (uppercase) works."""
    response = await async_client.post(
        "/convert", files={"file": ("test.HTML", sample_html_bytes)}
    )
    assert response.status_code == 200
    assert response.json()["format"] == "html"


@pytest.mark.anyio
async def test_convert_async_html_completes(
    async_client: httpx.AsyncClient, sample_html_bytes: bytes
):
    """An async HTML task reaches completed status with correct markdown."""
    response = await async_client.post(
        "/convert?async=true", files={"file": ("test.html", sample_html_bytes)}
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    status_data = {}
    for _ in range(40):
        await asyncio.sleep(0.25)
        status_res = await async_client.get(f"/task/{task_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        if status_data["status"] in ("completed", "failed"):
            break

    assert status_data["status"] == "completed"
    assert status_data["result"]["format"] == "html"
    assert "Main Title" in status_data["result"]["markdown"]


# ---------------------------------------------------------------------------
# URL Sanitization & Security Tests
# ---------------------------------------------------------------------------


class TestURLSanitization:
    """Tests for URL sanitization in HTML conversion."""

    def test_sanitize_url_blocks_javascript_scheme(self):
        """javascript: URLs should be replaced with #."""
        assert sanitize_url("javascript:alert('XSS')") == "#"

    def test_sanitize_url_blocks_javascript_uppercase(self):
        """Uppercase JAVASCRIPT: should also be blocked."""
        assert sanitize_url("JAVASCRIPT:alert('XSS')") == "#"

    def test_sanitize_url_blocks_mixed_case_javascript(self):
        """Mixed case JaVaScRiPt: should also be blocked."""
        assert sanitize_url("JaVaScRiPt:alert('XSS')") == "#"

    def test_sanitize_url_blocks_vbscript_scheme(self):
        """vbscript: URLs should be replaced with #."""
        assert sanitize_url("vbscript:msgbox('XSS')") == "#"

    def test_sanitize_url_blocks_data_scheme(self):
        """data: URLs should be replaced with #."""
        assert sanitize_url("data:text/html,<script>alert(1)</script>") == "#"

    def test_sanitize_url_blocks_data_scheme_with_whitespace(self):
        """data: URLs with leading whitespace should be blocked."""
        assert sanitize_url("  data:text/html;base64,PHNjcmlwdD4=") == "#"

    def test_sanitize_url_blocks_file_scheme(self):
        """file: URLs should be replaced with #."""
        assert sanitize_url("file:///etc/passwd") == "#"

    def test_sanitize_url_blocks_blob_scheme(self):
        """blob: URLs should be replaced with #."""
        assert sanitize_url("blob:https://example.com/abc123") == "#"

    def test_sanitize_url_allows_http(self):
        """http: URLs should be allowed."""
        assert sanitize_url("http://example.com") == "http://example.com"

    def test_sanitize_url_allows_https(self):
        """https: URLs should be allowed."""
        assert sanitize_url("https://example.com/page") == "https://example.com/page"

    def test_sanitize_url_allows_mailto(self):
        """mailto: URLs should be allowed."""
        assert sanitize_url("mailto:test@example.com") == "mailto:test@example.com"

    def test_sanitize_url_allows_tel(self):
        """tel: URLs should be allowed."""
        assert sanitize_url("tel:+33123456789") == "tel:+33123456789"

    def test_sanitize_url_allows_relative(self):
        """Relative URLs should be allowed."""
        assert sanitize_url("/page/about") == "/page/about"

    def test_sanitize_url_allows_anchor(self):
        """Anchor URLs should be allowed."""
        assert sanitize_url("#section-1") == "#section-1"

    def test_sanitize_url_empty_string(self):
        """Empty URL should return empty string."""
        assert sanitize_url("") == ""

    def test_sanitize_url_none(self):
        """None/empty URL should be handled gracefully."""
        assert sanitize_url("") == ""


class TestHTMLSanitizationIntegration:
    """Integration tests for HTML sanitization during conversion."""

    def test_javascript_href_in_link_is_blocked(self):
        """Links with javascript: href should be sanitized."""
        html = b"<a href=\"javascript:alert('XSS')\">Click me</a>"
        md = convert_html_to_md(html)
        assert "[Click me](#)" in md
        assert "javascript:" not in md

    def test_data_href_in_link_is_blocked(self):
        """Links with data: href should be sanitized."""
        html = b'<a href="data:text/html,<h1>Hi</h1>">Data Link</a>'
        md = convert_html_to_md(html)
        assert "[Data Link](#)" in md
        assert "data:" not in md

    def test_file_href_in_link_is_blocked(self):
        """Links with file: href should be sanitized."""
        html = b'<a href="file:///etc/passwd">Secret File</a>'
        md = convert_html_to_md(html)
        assert "[Secret File](#)" in md
        assert "file:" not in md

    def test_javascript_src_in_img_is_blocked(self):
        """Images with javascript: src should be sanitized."""
        html = b'<img src="javascript:alert(1)" alt="evil">'
        md = convert_html_to_md(html)
        assert "![evil](#)" in md
        assert "javascript:" not in md

    def test_data_src_in_img_is_blocked(self):
        """Images with data: src should be sanitized."""
        html = b'<img src="data:image/png;base64,abc123" alt="data img">'
        md = convert_html_to_md(html)
        assert "![data img](#)" in md
        assert "data:" not in md

    def test_event_handlers_removed_from_elements(self):
        """Event handler attributes should be stripped from elements."""
        html = b'<div onclick="alert(1)"><a href="https://example.com" onmouseover="steal()">Link</a></div>'
        md = convert_html_to_md(html)
        # The link text should still be present
        assert "Link" in md
        # Event handlers should not appear in output
        assert "onclick" not in md
        assert "onmouseover" not in md

    def test_img_onerror_event_removed(self):
        """onerror event on img should be removed."""
        html = b'<img src="image.png" alt="test" onerror="alert(1)">'
        md = convert_html_to_md(html)
        assert "![test](image.png)" in md
        assert "onerror" not in md

    def test_body_onload_removed(self):
        """onload event on body should be removed."""
        html = b'<body onload="alert(1)"><p>Hello</p></body>'
        md = convert_html_to_md(html)
        assert "Hello" in md
        assert "onload" not in md

    def test_mixed_safe_and_unsafe_urls(self):
        """Safe URLs should be preserved while unsafe ones are blocked."""
        html = b"""
        <a href="https://example.com">Safe</a>
        <a href="javascript:alert(1)">Unsafe</a>
        <a href="/relative/path">Relative</a>
        """
        md = convert_html_to_md(html)
        assert "[Safe](https://example.com)" in md
        assert "[Unsafe](#)" in md
        assert "[Relative](/relative/path)" in md

    def test_script_tags_removed(self):
        """Script tags should be completely removed."""
        html = b'<p>Before</p><script>alert("XSS")</script><p>After</p>'
        md = convert_html_to_md(html)
        assert "Before" in md
        assert "After" in md
        assert "alert" not in md
        assert "XSS" not in md

    def test_iframe_removed(self):
        """Iframe content should not appear in output."""
        html = b'<p>Safe content</p><iframe src="javascript:alert(1)"></iframe>'
        md = convert_html_to_md(html)
        assert "Safe content" in md
        assert "javascript:" not in md

    def test_svg_onload_removed(self):
        """SVG with onload should have the handler removed."""
        html = b'<svg onload="alert(1)"><text>Harmless SVG</text></svg>'
        md = convert_html_to_md(html)
        assert "onload" not in md

    def test_form_action_javascript_blocked(self):
        """Form with javascript: action should be sanitized."""
        html = b'<form action="javascript:submit()"><input type="text"></form>'
        md = convert_html_to_md(html)
        assert "javascript:" not in md

    def test_encoded_javascript_scheme_blocked(self):
        """URL-encoded javascript scheme should still be blocked."""
        # Some encodings like tabs or newlines before the scheme
        html = b'<a href="\tjavascript:alert(1)">Encoded</a>'
        md = convert_html_to_md(html)
        assert "javascript:" not in md

    def test_newline_javascript_scheme_blocked(self):
        """Newline before javascript scheme should be blocked."""
        html = b'<a href="\njavascript:alert(1)">Newline</a>'
        md = convert_html_to_md(html)
        assert "javascript:" not in md
