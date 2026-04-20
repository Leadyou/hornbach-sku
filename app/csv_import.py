from __future__ import annotations

import csv
import io
from typing import Tuple

from app.db import get_conn

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
    rows: list[tuple] = []

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
        available_from = line.get("available_from", "") or None
        delivery_location_code = line.get("delivery_location_code", "") or ""

        rows.append((sku, name, stock, lead, available_from, delivery_location_code))

    if not rows and not errors:
        return 0, ["Brak danych do importu."]

    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO sku_item (sku, name, stock_quantity, lead_time_days, available_from, delivery_location_code)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                name = excluded.name,
                stock_quantity = excluded.stock_quantity,
                lead_time_days = excluded.lead_time_days,
                available_from = excluded.available_from,
                delivery_location_code = excluded.delivery_location_code
            """,
            rows,
        )
        conn.commit()

    return len(rows), errors
