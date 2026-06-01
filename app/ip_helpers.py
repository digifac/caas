"""IP helper functions for secure client IP extraction."""

import ipaddress
import logging

from fastapi import Request

from app.config import settings

logger = logging.getLogger(__name__)


def _is_trusted_proxy(host: str) -> bool:
    """Check whether the direct-connector IP is a trusted proxy."""
    for proxy in settings.trusted_proxies_list:
        try:
            if "/" in proxy:
                if ipaddress.ip_address(host) in ipaddress.ip_network(
                    proxy, strict=False
                ):
                    return True
            else:
                if host == proxy:
                    return True
        except ValueError:
            logger.warning("Ignoring invalid proxy IP/CIDR (length=%d)", len(proxy))
    return False


def _get_client_ip(request: Request) -> str:
    """
    Extract the client IP address securely.

    - If no trusted proxy is configured → direct IP only (anti-spoofing protection).
    - If the direct connector is a trusted proxy → X-Forwarded-For (first IP = original client).
    """
    client_host = (request.client and request.client.host) or "unknown"

    if _is_trusted_proxy(client_host):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return client_host
