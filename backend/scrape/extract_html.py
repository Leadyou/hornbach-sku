from __future__ import annotations

import json
import re
from typing import Any, Optional

_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_MARKET_SLUG_RE = re.compile(
    r"""href=["'](?:https://(?:www\.)?obi\.de)?/markt/([a-z0-9][a-z0-9-]{1,80})/?["']""",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]{2,240})</title>", re.IGNORECASE)
_PLZ_RE = re.compile(r"\b(\d{5})\b")

_SKIP_SLUG_PREFIXES = ("services", "mietgeraete", "informationen", "corporate")
_SKIP_SLUGS = frozenset({"markt", "suche", "c"})


def extract_next_data(html: str) -> Optional[dict[str, Any]]:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def summarize_next_data(data: Optional[dict[str, Any]], max_keys: int = 24) -> Optional[dict[str, Any]]:
    if not data:
        return None
    out: dict[str, Any] = {"keys": list(data.keys())[:max_keys]}
    props = data.get("props")
    if isinstance(props, dict):
        out["props_keys"] = list(props.keys())[:max_keys]
        pp = props.get("pageProps")
        if isinstance(pp, dict):
            out["pageProps_keys"] = list(pp.keys())[:max_keys]
    return out


def extract_obi_market_slugs(html: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in _MARKET_SLUG_RE.findall(html):
        sl = raw.strip().lower()
        if len(sl) < 3 or sl in _SKIP_SLUGS:
            continue
        if any(sl.startswith(p) for p in _SKIP_SLUG_PREFIXES):
            continue
        if sl in seen:
            continue
        seen.add(sl)
        out.append(sl)
    return out


def guess_dominant_plz(html: str) -> Optional[str]:
    counts: dict[str, int] = {}
    for m in _PLZ_RE.finditer(html):
        plz = m.group(1)
        counts[plz] = counts.get(plz, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def extract_html_title(html: str) -> Optional[str]:
    m = _TITLE_RE.search(html)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()
