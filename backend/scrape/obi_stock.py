from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from backend.scrape.fetch_json import fetch_json_get

_STOCK_PATH = "/api/pdp/v1/stock"
_DATA_FILE = Path(__file__).resolve().parent / "data" / "obi_default_store_ids.txt"
_CHUNK = 50  # decyzja: max. storeIds na jedno żądanie GET do obi.de


def default_store_ids() -> list[str]:
    if not _DATA_FILE.is_file():
        return []
    raw = _DATA_FILE.read_text(encoding="utf-8")
    return [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]


def parse_store_ids_csv(csv: str) -> list[str]:
    return [x.strip() for x in (csv or "").replace("\n", ",").split(",") if x.strip()]


def fetch_product_stock(
    product_id: str,
    store_ids: list[str],
    *,
    delay_sec: float = 0.12,
    chunk: int = _CHUNK,
) -> tuple[list[dict[str, Any]], int]:
    """
    GET https://www.obi.de/api/pdp/v1/stock/{id}?storeIds=...
    Zwraca (wiersze {storeId, availableQuantity}, liczba_zapytań_http).
    """
    if not store_ids:
        raise ValueError("Brak identyfikatorów sklepów (storeIds).")
    merged: list[dict[str, Any]] = []
    batches = 0
    for i in range(0, len(store_ids), chunk):
        part = store_ids[i : i + chunk]
        url = f"https://www.obi.de{_STOCK_PATH}/{product_id}?storeIds={','.join(part)}"
        data = fetch_json_get(url)
        batches += 1
        if not isinstance(data, list):
            raise ValueError(f"Oczekiwano listy z API stock, otrzymano {type(data).__name__}.")
        for row in data:
            if isinstance(row, dict) and "storeId" in row:
                merged.append(
                    {
                        "storeId": str(row.get("storeId", "")),
                        "availableQuantity": row.get("availableQuantity"),
                    }
                )
        if i + chunk < len(store_ids) and delay_sec > 0:
            time.sleep(delay_sec)
    merged.sort(key=lambda r: r["storeId"])
    return merged, batches
