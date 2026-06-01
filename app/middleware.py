"""Security headers middleware for the FastAPI application."""

from fastapi import Request

# Strict CSP for the main application (form + API).
# - No 'unsafe-inline' in script-src: all event handlers are attached via addEventListener.
# - CDN script is loaded with SRI (Subresource Integrity) hash to prevent MITM tampering.
# - 'unsafe-inline' kept for style-src only (inline style="..." attributes on initial
#   element visibility); this is low-risk compared to script injection.
# SRI hash for Bootstrap 5.3.3 CSS from jsDelivr (sha384-xxx)
DEFAULT_CSP = (
    "default-src 'none'; "
    "connect-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none';"
)

# Relaxed CSP for Swagger/ReDoc (OpenAPI) documentation which requires inline scripts.
# 'unsafe-inline' is unavoidable for Swagger UI but scoped to docs routes only.
DOCS_CSP = (
    "default-src 'self'; "
    "connect-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "frame-src 'self'; "
    "object-src 'none';"
)

# Permissions-Policy: restrict powerful browser APIs not needed by the app.
PERMISSIONS_POLICY = (
    "camera=(), "
    "microphone=(), "
    "geolocation=(), "
    "payment=(), "
    "usb=(), "
    "magnetometer=(), "
    "gyroscope=(), "
    "accelerometer=()"
)

# HSTS: enforce HTTPS for 1 year, include subdomains, allow preload.
HSTS_MAX_AGE = 31536000


async def add_security_headers(request: Request, call_next):
    """Add security headers to every response.

    Applies a strict CSP for the main app and a relaxed CSP for Swagger/ReDoc routes.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = DEFAULT_CSP
    response.headers["Permissions-Policy"] = PERMISSIONS_POLICY
    response.headers["Strict-Transport-Security"] = (
        f"max-age={HSTS_MAX_AGE}; includeSubDomains; preload"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Relax security headers for Swagger/ReDoc documentation routes
    if request.url.path in ("/docs", "/redoc", "/openapi.json"):
        del response.headers["X-Frame-Options"]
        response.headers["Content-Security-Policy"] = DOCS_CSP
    return response
