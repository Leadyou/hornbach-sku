from __future__ import annotations

import csv
import io
from typing import Any, Tuple

from app.db import upsert_sku_rows

EXPECTED_HEADERS = (
    "sku",
    "name",
    "stock_quantity",
    "lead_time_days",
    "available_from",
    "delivery_location_code",
)


def import_skus_csv(content: str) -> Tuple[int, list[str]]:
    """
    CSV columns (nagłówek w pierwszym wierszu):
    sku,name,stock_quantity,lead_time_days,available_from,delivery_location_code

    available_from: YYYY-MM-DD lub puste
    delivery_location_code: opcjonalne; puste = dowolna lokalizacja przy sprawdzaniu
    """
    errors: list[str] = []
    rows: list[dict[str, Any]] = []

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return 0, ["Plik nie zawiera nagłówka kolumn."]

    normalized = {h.strip().lower(): h for h in reader.fieldnames if h}
    missing = [h for h in EXPECTED_HEADERS if h not in normalized]
    if missing:
        return 0, [f"Brakujące kolumny: {', '.join(missing)}. Wymagane: {', '.join(EXPECTED_HEADERS)}."]

    for i, raw in enumerate(reader, start=2):
        line = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        sku = line.get("sku", "")
        if not sku:
            errors.append(f"Wiersz {i}: puste SKU — pominięto.")
            continue
        try:
            stock = int(line.get("stock_quantity", "0") or 0)
            lead = int(line.get("lead_time_days", "0") or 0)
        except ValueError:
            errors.append(f"Wiersz {i} ({sku}): stock_quantity i lead_time_days muszą być liczbami całkowitymi.")
            continue

        name = line.get("name", "")
        available_raw = (line.get("available_from", "") or "").strip()
        available_from: str | None = available_raw if available_raw else None
        delivery_location_code = (line.get("delivery_location_code", "") or "").strip()

        rows.append(
            {
                "sku": sku,
                "name": name,
                "stock_quantity": stock,
                "lead_time_days": lead,
                "available_from": available_from,
                "delivery_location_code": delivery_location_code,
            }
        )

    if not rows and not errors:
        return 0, ["Brak danych do importu."]

    upsert_sku_rows(rows)

    return len(rows), errors
