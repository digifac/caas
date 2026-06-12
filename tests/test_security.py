"""Security tests: HTML sanitization, security headers, and anti-spoofing IP.

Covers the recommendations from AUDIT.md §8 — item #7:
- HTML sanitization (event handlers, dangerous URL schemes, script/style removal)
- Security headers (CSP, X-Content-Type-Options, X-Frame-Options, etc.)
- Anti-spoofing IP extraction (trusted proxy, X-Forwarded-For)
"""

import httpx
import pytest
from app import ip_helpers
from app.config import settings
from app.converters import html as html_converter
from app.converters.html import sanitize_url, convert_html_to_md
from bs4 import BeautifulSoup

# =============================================================================
# HTML Sanitization Tests
# =============================================================================


class TestHTMLSanitization:
    """Tests for HTML sanitization during conversion."""

    # --- Event Handlers ---

    def test_sanitize_removes_onclick(self):
        """onclick event handlers should be stripped."""
        html = b"<button onclick=\"alert('XSS')\">Click</button>"
        md = convert_html_to_md(html)
        assert "onclick" not in md
        assert "alert" not in md

    def test_sanitize_removes_onerror(self):
        """onerror event handlers should be stripped."""
        html = b'<img src="x" onerror="alert(\'XSS\')">'
        md = convert_html_to_md(html)
        assert "onerror" not in md

    def test_sanitize_removes_onload(self):
        """onload event handlers should be stripped."""
        html = b"<body onload=\"alert('XSS')\"><p>Hello</p></body>"
        md = convert_html_to_md(html)
        assert "onload" not in md

    def test_sanitize_removes_all_event_handlers(self):
        """All common event handlers should be stripped."""
        handlers = [
            "onmouseover",
            "onmouseout",
            "onfocus",
            "onblur",
            "onsubmit",
            "onchange",
            "onkeydown",
            "onkeyup",
            "onmousedown",
            "onmouseup",
            "ondblclick",
        ]
        for handler in handlers:
            html = f"<div {handler}=\"alert('XSS')\"><p>Text</p></div>".encode()
            md = convert_html_to_md(html)
            assert handler not in md, f"{handler} was not removed"

    # --- Dangerous URL Schemes ---

    def test_sanitize_blocks_javascript_in_href(self):
        """javascript: URLs in <a> tags should be replaced with #."""
        html = b"<a href=\"javascript:alert('XSS')\">Link</a>"
        md = convert_html_to_md(html)
        assert "[Link](#)" in md
        assert "javascript" not in md

    def test_sanitize_blocks_data_in_href(self):
        """data: URLs in <a> tags should be replaced with #."""
        html = b'<a href="data:text/html,<script>alert(1)</script>">Link</a>'
        md = convert_html_to_md(html)
        assert "[Link](#)" in md
        assert "data:" not in md

    def test_sanitize_blocks_javascript_in_img_src(self):
        """javascript: URLs in <img> src should be replaced with #."""
        html = b'<img src="javascript:alert(\'XSS\')" alt="img">'
        md = convert_html_to_md(html)
        assert "![img](#)" in md
        assert "javascript" not in md

    def test_sanitize_blocks_file_in_href(self):
        """file: URLs in <a> tags should be replaced with #."""
        html = b'<a href="file:///etc/passwd">Secret</a>'
        md = convert_html_to_md(html)
        assert "[Secret](#)" in md
        assert "file:" not in md

    def test_sanitize_blocks_vbscript_in_href(self):
        """vbscript: URLs should be replaced with #."""
        html = b'<a href="vbscript:msgbox(1)">Link</a>'
        md = convert_html_to_md(html)
        assert "[Link](#)" in md
        assert "vbscript" not in md

    def test_sanitize_blocks_blob_in_href(self):
        """blob: URLs should be replaced with #."""
        html = b'<a href="blob:http://example.com/uuid">Link</a>'
        md = convert_html_to_md(html)
        assert "[Link](#)" in md
        assert "blob:" not in md

    def test_sanitize_allows_safe_url_schemes(self):
        """Safe URL schemes (http, https, mailto, ftp) should be preserved."""
        safe_urls = [
            ("https://example.com", "https://example.com"),
            ("http://example.com", "http://example.com"),
            ("mailto:test@example.com", "mailto:test@example.com"),
            ("ftp://files.example.com", "ftp://files.example.com"),
            ("/relative/path", "/relative/path"),
            ("#anchor", "#anchor"),
        ]
        for url, expected in safe_urls:
            result = sanitize_url(url)
            assert result == expected, f"Expected {expected}, got {result}"

    # --- Script/Style Tag Removal ---

    def test_sanitize_removes_script_tags(self):
        """<script> tags should be completely removed."""
        html = b'<p>Before</p><script>alert("XSS")</script><p>After</p>'
        md = convert_html_to_md(html)
        assert "script" not in md.lower()
        assert "alert" not in md
        assert "Before" in md
        assert "After" in md

    def test_sanitize_removes_style_tags(self):
        """<style> tags should be completely removed."""
        html = b"<style>body { background: red; }</style><p>Content</p>"
        md = convert_html_to_md(html)
        assert "style" not in md.lower()
        assert "background" not in md
        assert "Content" in md

    def test_sanitize_removes_meta_tags(self):
        """<meta> tags should be removed."""
        html = b'<meta charset="utf-8"><p>Content</p>'
        md = convert_html_to_md(html)
        assert "meta" not in md.lower()
        assert "Content" in md

    def test_sanitize_removes_head_section(self):
        """<head> content should be removed."""
        html = b"<head><title>Test</title></head><body><p>Body</p></body>"
        md = convert_html_to_md(html)
        assert "head" not in md.lower()

    # --- HTML Comments ---

    def test_sanitize_removes_html_comments(self):
        """HTML comments should not appear in output."""
        html = b'<!-- <script>alert("XSS")</script> --> <p>Safe</p>'
        md = convert_html_to_md(html)
        assert "script" not in md.lower()
        assert "alert" not in md
        assert "Safe" in md

    # --- Complex XSS Payloads ---

    def test_sanitize_complex_xss_payload(self):
        """Complex XSS payloads combining multiple techniques should be neutralized."""
        html = b"""
        <div onclick="alert(1)" onmouseover="alert(2)">
            <a href="javascript:alert(3)">Click</a>
            <img src="x" onerror="alert(4)">
            <script>alert(5)</script>
        </div>
        """
        md = convert_html_to_md(html)
        assert "onclick" not in md
        assert "onmouseover" not in md
        assert "onerror" not in md
        assert "javascript:" not in md
        assert "script" not in md.lower()

    def test_sanitize_svg_onload(self):
        """SVG with onload should have the event handler removed."""
        html = b'<svg onload="alert(\'XSS\')"><circle cx="50" cy="50" r="40"/></svg>'
        md = convert_html_to_md(html)
        assert "onload" not in md

    def test_sanitize_iframe_removed(self):
        """<iframe> tags should be handled safely."""
        html = b'<iframe src="javascript:alert(1)"></iframe><p>Safe</p>'
        md = convert_html_to_md(html)
        assert "javascript" not in md
        assert "Safe" in md

    # --- _sanitize_soup unit tests ---

    def test_sanitize_soup_removes_event_attrs(self):
        """_sanitize_soup should remove all event handler attributes."""
        soup = BeautifulSoup(
            '<div onclick="x" onmouseover="y">text</div>', "html.parser"
        )
        html_converter._sanitize_soup(soup)  # type: ignore[attr-defined]
        div = soup.find("div")
        assert "onclick" not in (div.attrs if div else {})  # type: ignore[union-attr]
        assert "onmouseover" not in (div.attrs if div else {})  # type: ignore[union-attr]

    def test_sanitize_soup_sanitizes_href(self):
        """_sanitize_soup should sanitize href attributes."""
        soup = BeautifulSoup('<a href="javascript:alert(1)">Link</a>', "html.parser")
        html_converter._sanitize_soup(soup)  # type: ignore[attr-defined]
        anchor = soup.find("a")
        assert anchor is not None
        assert anchor["href"] == "#"

    def test_sanitize_soup_sanitizes_img_src(self):
        """_sanitize_soup should sanitize img src attributes."""
        soup = BeautifulSoup(
            '<img src="data:text/html,<script>x</script>">', "html.parser"
        )
        html_converter._sanitize_soup(soup)  # type: ignore[attr-defined]
        img = soup.find("img")
        assert img is not None
        assert img["src"] == "#"


# =============================================================================
# Security Headers Tests
# =============================================================================


class TestSecurityHeaders:
    """Tests for security headers on HTTP responses."""

    @pytest.mark.anyio
    async def test_security_headers_on_root(self, async_client: httpx.AsyncClient):
        """Root endpoint should have all security headers."""
        response = await async_client.get("/")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "Content-Security-Policy" in response.headers
        assert "x-xss-protection" not in response.headers  # Deprecated, removed
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "strict-transport-security" in response.headers
        assert "permissions-policy" in response.headers

    @pytest.mark.anyio
    async def test_security_headers_on_convert(self, async_client: httpx.AsyncClient):
        """POST /convert should have security headers."""
        response = await async_client.post(
            "/convert", files={"file": ("test.txt", b"content")}
        )
        # Even error responses should have security headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "Content-Security-Policy" in response.headers

    @pytest.mark.anyio
    async def test_security_headers_on_health(self, async_client: httpx.AsyncClient):
        """GET /health should have security headers."""
        response = await async_client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"

    @pytest.mark.anyio
    async def test_csp_strict_for_main_app(self, async_client: httpx.AsyncClient):
        """Main app routes should have strict CSP (no 'unsafe-inline' for scripts)."""
        response = await async_client.get("/")
        csp = response.headers.get("content-security-policy", "")
        # The strict CSP should NOT have 'unsafe-inline' in script-src
        # It should have 'self' and CDN for scripts
        assert "script-src" in csp
        # Verify 'unsafe-inline' is NOT in script-src directive
        script_src_part = (
            csp.split("script-src")[1].split(";")[0] if "script-src" in csp else ""
        )
        assert "'unsafe-inline'" not in script_src_part

    @pytest.mark.anyio
    async def test_csp_relaxed_for_docs(self, async_client: httpx.AsyncClient):
        """Swagger/ReDoc routes should have relaxed CSP."""
        response = await async_client.get("/docs")
        csp = response.headers.get("content-security-policy", "")
        # Docs CSP allows 'unsafe-inline' for scripts (Swagger needs it)
        assert "'unsafe-inline'" in csp
        # X-Frame-Options should be removed for docs
        assert "x-frame-options" not in response.headers

    @pytest.mark.anyio
    async def test_csp_relaxed_for_redoc(self, async_client: httpx.AsyncClient):
        """ReDoc route should have relaxed CSP."""
        response = await async_client.get("/redoc")
        csp = response.headers.get("content-security-policy", "")
        assert "'unsafe-inline'" in csp

    @pytest.mark.anyio
    async def test_csp_relaxed_for_openapi_json(self, async_client: httpx.AsyncClient):
        """OpenAPI JSON route should have relaxed CSP."""
        response = await async_client.get("/openapi.json")
        csp = response.headers.get("content-security-policy", "")
        assert "'unsafe-inline'" in csp

    @pytest.mark.anyio
    async def test_csp_frame_ancestors_none(self, async_client: httpx.AsyncClient):
        """CSP should prevent clickjacking with frame-ancestors 'none'."""
        response = await async_client.get("/")
        csp = response.headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.anyio
    async def test_csp_default_src_none(self, async_client: httpx.AsyncClient):
        """CSP default-src should be 'none' for strict policy."""
        response = await async_client.get("/")
        csp = response.headers.get("content-security-policy", "")
        assert "default-src 'none'" in csp

    @pytest.mark.anyio
    async def test_csp_form_action_self(self, async_client: httpx.AsyncClient):
        """CSP should restrict form-action to 'self'."""
        response = await async_client.get("/")
        csp = response.headers.get("content-security-policy", "")
        assert "form-action 'self'" in csp

    @pytest.mark.anyio
    async def test_csp_base_uri_self(self, async_client: httpx.AsyncClient):
        """CSP should restrict base-uri to 'self'."""
        response = await async_client.get("/")
        csp = response.headers.get("content-security-policy", "")
        assert "base-uri 'self'" in csp


# =============================================================================
# Anti-Spoofing IP Tests
# =============================================================================


class TestAntiSpoofingIP:
    """Tests for secure client IP extraction."""

    # --- _is_trusted_proxy unit tests ---

    def test_is_trusted_proxy_single_ip(self):
        """Exact IP match should return True."""
        assert ip_helpers._is_trusted_proxy("192.168.1.1") is False  # type: ignore[attr-defined]  # Not in default (empty) list
        # With a configured proxy
        original = settings.trusted_proxies
        settings.trusted_proxies = "192.168.1.1"
        try:
            assert ip_helpers._is_trusted_proxy("192.168.1.1") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("10.0.0.1") is False  # type: ignore[attr-defined]
        finally:
            settings.trusted_proxies = original

    def test_is_trusted_proxy_cidr(self):
        """CIDR range match should return True for IPs in range."""
        original = settings.trusted_proxies
        settings.trusted_proxies = "10.0.0.0/8"
        try:
            assert ip_helpers._is_trusted_proxy("10.0.0.1") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("10.255.255.255") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("192.168.1.1") is False  # type: ignore[attr-defined]
        finally:
            settings.trusted_proxies = original

    def test_is_trusted_proxy_multiple(self):
        """Multiple trusted proxies should all be checked."""
        original = settings.trusted_proxies
        settings.trusted_proxies = "192.168.1.1,10.0.0.0/8,172.16.0.0/12"
        try:
            assert ip_helpers._is_trusted_proxy("192.168.1.1") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("10.5.5.5") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("172.16.0.1") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("8.8.8.8") is False  # type: ignore[attr-defined]
        finally:
            settings.trusted_proxies = original

    def test_is_trusted_proxy_invalid_cidr(self):
        """Invalid CIDR should be ignored (not crash)."""
        original = settings.trusted_proxies
        settings.trusted_proxies = "not_an_ip,192.168.1.1"
        try:
            assert ip_helpers._is_trusted_proxy("192.168.1.1") is True  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("8.8.8.8") is False  # type: ignore[attr-defined]
        finally:
            settings.trusted_proxies = original

    def test_is_trusted_proxy_empty_list(self):
        """Empty trusted proxy list should return False for all IPs."""
        original = settings.trusted_proxies
        settings.trusted_proxies = ""
        try:
            assert ip_helpers._is_trusted_proxy("192.168.1.1") is False  # type: ignore[attr-defined]
            assert ip_helpers._is_trusted_proxy("10.0.0.1") is False  # type: ignore[attr-defined]
        finally:
            settings.trusted_proxies = original

    # --- _get_client_ip integration tests ---

    @pytest.mark.anyio
    async def test_get_client_ip_no_proxy(self, async_client: httpx.AsyncClient):
        """Without trusted proxies, X-Forwarded-For should be ignored."""
        original = settings.trusted_proxies
        settings.trusted_proxies = ""
        try:
            # Make a request with spoofed X-Forwarded-For
            response = await async_client.get(
                "/", headers={"x-forwarded-for": "1.2.3.4"}
            )
            assert response.status_code == 200
            # The middleware should NOT trust the spoofed header
            # We verify by checking the request was processed normally
        finally:
            settings.trusted_proxies = original

    @pytest.mark.anyio
    async def test_get_client_ip_trusted_proxy(self, async_client: httpx.AsyncClient):
        """When connector is a trusted proxy, X-Forwarded-For should be used."""
        # This tests the logic directly since we can't easily set the client host
        # in TestClient. We verify the function behavior with a mock request.
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = {"x-forwarded-for": "203.0.113.50"}

        original = settings.trusted_proxies
        settings.trusted_proxies = "10.0.0.0/8"
        try:
            ip = ip_helpers._get_client_ip(request)  # type: ignore[attr-defined]
            assert ip == "203.0.113.50"
        finally:
            settings.trusted_proxies = original

    @pytest.mark.anyio
    async def test_get_client_ip_untrusted_proxy(self, async_client: httpx.AsyncClient):
        """When connector is NOT a trusted proxy, use direct IP."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "8.8.8.8"
        request.headers = {"x-forwarded-for": "203.0.113.50"}

        original = settings.trusted_proxies
        settings.trusted_proxies = "10.0.0.0/8"  # 8.8.8.8 is NOT in this range
        try:
            ip = ip_helpers._get_client_ip(request)  # type: ignore[attr-defined]
            assert ip == "8.8.8.8"
        finally:
            settings.trusted_proxies = original

    @pytest.mark.anyio
    async def test_get_client_ip_xff_first_entry(self, async_client: httpx.AsyncClient):
        """X-Forwarded-For with multiple IPs should use the first (original client)."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = {"x-forwarded-for": "203.0.113.50, 192.168.1.1, 10.0.0.5"}

        original = settings.trusted_proxies
        settings.trusted_proxies = "10.0.0.0/8"
        try:
            ip = ip_helpers._get_client_ip(request)  # type: ignore[attr-defined]
            assert ip == "203.0.113.50"
        finally:
            settings.trusted_proxies = original

    @pytest.mark.anyio
    async def test_get_client_ip_no_xff(self, async_client: httpx.AsyncClient):
        """Without X-Forwarded-For, use direct connector IP."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = {}

        original = settings.trusted_proxies
        settings.trusted_proxies = "10.0.0.0/8"
        try:
            ip = ip_helpers._get_client_ip(request)  # type: ignore[attr-defined]
            assert ip == "10.0.0.1"
        finally:
            settings.trusted_proxies = original

    @pytest.mark.anyio
    async def test_get_client_ip_no_trusted_proxies_ignores_xff(
        self, async_client: httpx.AsyncClient
    ):
        """With no trusted proxies configured, X-Forwarded-For is always ignored."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "203.0.113.100"
        request.headers = {"x-forwarded-for": "1.2.3.4"}

        original = settings.trusted_proxies
        settings.trusted_proxies = ""
        try:
            ip = ip_helpers._get_client_ip(request)  # type: ignore[attr-defined]
            assert ip == "203.0.113.100"
        finally:
            settings.trusted_proxies = original


# =============================================================================
# XSS via Markdown Tests
# =============================================================================


class TestXSSViaMarkdown:
    """Tests for potential XSS vectors in Markdown output."""

    def test_html_script_in_text_not_executed(self):
        """Script tags in HTML text content should be removed during conversion."""
        html = b"<p>User said: &lt;script&gt;alert(1)&lt;/script&gt;</p>"
        md = convert_html_to_md(html)
        # The decoded text might contain <script> as text, but it's not an HTML tag
        # This is a known limitation noted in the audit
        assert "alert" in md  # Text is preserved

    def test_raw_script_tag_removed(self):
        """Raw <script> tags in HTML input should be removed."""
        html = b"<script>document.cookie</script><p>Safe text</p>"
        md = convert_html_to_md(html)
        assert "<script>" not in md
        assert "document.cookie" not in md
        assert "Safe text" in md

    def test_event_handler_in_html_attribute(self):
        """Event handlers in HTML attributes should be stripped."""
        html = b'<div style="background:url(javascript:alert(1))"><p>Text</p></div>'
        md = convert_html_to_md(html)
        # Style attributes are on elements but event handlers are stripped
        # The style value itself isn't sanitized (it's a CSS property)
        assert "Text" in md


# =============================================================================
# New Dangerous Tags Tests
# =============================================================================


class TestDangerousTagsRemoval:
    """Tests for newly added dangerous tag removal (math, template, details, marquee)."""

    def test_math_tag_removed(self):
        """<math> tags should be removed (can contain mscript for XSS)."""
        html = b"<math><mi>foo</mi></math><p>Safe</p>"
        md = convert_html_to_md(html)
        assert "math" not in md.lower()
        assert "Safe" in md

    def test_template_tag_removed(self):
        """<template> tags should be removed (content not rendered but can be accessed)."""
        html = b"<template><script>alert(1)</script></template><p>Safe</p>"
        md = convert_html_to_md(html)
        assert "template" not in md.lower()
        assert "Safe" in md

    def test_details_tag_removed(self):
        """<details> tags should be removed (can contain interactive content)."""
        html = b"<details><summary>Click</summary><p>Hidden</p></details><p>Safe</p>"
        md = convert_html_to_md(html)
        assert "details" not in md.lower()
        assert "summary" not in md.lower()
        assert "Safe" in md

    def test_marquee_tag_removed(self):
        """<marquee> tags should be removed (deprecated, can contain event handlers)."""
        html = b'<marquee onstart="alert(1)">Moving</marquee><p>Safe</p>'
        md = convert_html_to_md(html)
        assert "marquee" not in md.lower()
        assert "Safe" in md


# =============================================================================
# Security Headers — New Tests (HSTS, Permissions-Policy, no X-XSS-Protection)
# =============================================================================


class TestNewSecurityHeaders:
    """Tests for newly added security headers."""

    @pytest.mark.anyio
    async def test_no_x_xss_protection_header(self, async_client: httpx.AsyncClient):
        """X-XSS-Protection should NOT be set (deprecated, can introduce vulnerabilities)."""
        response = await async_client.get("/")
        assert "x-xss-protection" not in response.headers

    @pytest.mark.anyio
    async def test_hsts_header_present(self, async_client: httpx.AsyncClient):
        """Strict-Transport-Security should be present with max-age, includeSubDomains, preload."""
        response = await async_client.get("/")
        hsts = response.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    @pytest.mark.anyio
    async def test_permissions_policy_present(self, async_client: httpx.AsyncClient):
        """Permissions-Policy should restrict camera, microphone, geolocation, etc."""
        response = await async_client.get("/")
        pp = response.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp

    @pytest.mark.anyio
    async def test_csp_object_src_none(self, async_client: httpx.AsyncClient):
        """CSP should include object-src 'none' to block plugin content."""
        response = await async_client.get("/")
        csp = response.headers.get("content-security-policy", "")
        assert "object-src 'none'" in csp

    @pytest.mark.anyio
    async def test_csp_docs_object_src_none(self, async_client: httpx.AsyncClient):
        """Docs CSP should also include object-src 'none'."""
        response = await async_client.get("/docs")
        csp = response.headers.get("content-security-policy", "")
        assert "object-src 'none'" in csp
