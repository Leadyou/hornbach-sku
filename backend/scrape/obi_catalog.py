from __future__ import annotations

import csv
import io
import time
from typing import Any

from backend.scrape.extract_html import (
    extract_html_title,
    extract_obi_market_slugs,
    guess_dominant_plz,
)
from backend.scrape.fetch_html import fetch_html

OBI_MARKT_LIST = "https://www.obi.de/markt"


def list_market_slugs() -> list[str]:
    html = fetch_html(OBI_MARKT_LIST)
    return extract_obi_market_slugs(html)


def enrich_markets(slugs: list[str], delay_sec: float = 0.35) -> list[dict[str, Any]]:
    """Dla każdego sluga pobiera stronę marktu i próbuje wyciągnąć tytuł + dominujący kod PL."""
    rows: list[dict[str, Any]] = []
    for i, slug in enumerate(slugs):
        url = f"https://www.obi.de/markt/{slug}"
        html = fetch_html(url)
        rows.append(
            {
                "slug": slug,
                "url": url,
                "title": extract_html_title(html) or "",
                "postal_code_guess": guess_dominant_plz(html) or "",
            }
        )
        if i + 1 < len(slugs) and delay_sec > 0:
            time.sleep(delay_sec)
    return rows


def markets_to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["slug", "url", "title", "postal_code_guess"], extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")
