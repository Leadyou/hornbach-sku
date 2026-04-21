from __future__ import annotations

import httpx

from backend.scrape.allowlist import assert_https_allowed_host

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
_MAX_BYTES = 3_500_000


def fetch_html(url: str, timeout: float = 45.0) -> str:
    assert_https_allowed_host(url)
    headers = {"User-Agent": _DEFAULT_UA, "Accept-Language": "de-DE,de;q=0.9,pl;q=0.8"}
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        raw = r.content
        if len(raw) > _MAX_BYTES:
            raise ValueError(f"Strona przekracza limit {_MAX_BYTES} bajtów.")
        return raw.decode(r.encoding or "utf-8", errors="replace")
