"""Shared HTTP helper for source tools.

Centralizes timeouts, redirect following, and polite retry/backoff on rate limits
(429) and transient server errors — so every source tool is a good API citizen without
duplicating the logic. This is the seed of the ``SourceClient`` layer in ARCHITECTURE §7.
"""

from __future__ import annotations

import time

import httpx

from researchos.logging import get_logger

log = get_logger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


def get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> httpx.Response:
    """GET with redirect-following and exponential backoff on rate limits/5xx.

    Raises ``httpx.HTTPStatusError`` on non-retryable 4xx and after exhausting retries.
    """
    attempt = 0
    while True:
        resp = httpx.get(
            url, params=params, headers=headers, timeout=timeout, follow_redirects=True
        )
        if resp.status_code in _RETRY_STATUS and attempt < max_retries:
            wait = 2.0**attempt
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = float(retry_after)
            log.warning("HTTP %s from %s — retrying in %.1fs", resp.status_code, url, wait)
            time.sleep(wait)
            attempt += 1
            continue
        resp.raise_for_status()
        return resp
