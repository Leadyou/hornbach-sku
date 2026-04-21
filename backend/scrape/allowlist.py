from __future__ import annotations

import os
from urllib.parse import urlparse

_DEFAULT = "www.obi.de,obi.de"


def allowed_hosts() -> set[str]:
    raw = os.getenv("SCRAPE_ALLOWED_HOSTS", _DEFAULT)
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def assert_https_allowed_host(url: str) -> None:
    p = urlparse(url.strip())
    if (p.scheme or "").lower() != "https":
        raise ValueError("Dozwolony jest wyłącznie adres https://")
    host = (p.hostname or "").lower()
    if not host:
        raise ValueError("Brak hosta w URL.")
    if host not in allowed_hosts():
        allowed = ", ".join(sorted(allowed_hosts()))
        raise ValueError(f"Host „{host}” nie jest na liście dozwolonych. Ustaw SCRAPE_ALLOWED_HOSTS ({allowed}).")
