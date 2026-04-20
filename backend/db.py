from __future__ import annotations

from typing import Any, Optional

from supabase import Client, create_client

from backend.config import supabase_service_role_key, supabase_url

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(supabase_url(), supabase_service_role_key())
    return _client


def count_skus() -> int:
    sb = get_supabase()
    r = sb.table("sku_item").select("sku", count="exact", head=True).execute()
    return int(r.count) if r.count is not None else 0


def fetch_sku(sku: str) -> Optional[dict[str, Any]]:
    sb = get_supabase()
    r = (
        sb.table("sku_item")
        .select("sku, name, stock_quantity, lead_time_days, available_from, delivery_location_code")
        .eq("sku", sku)
        .limit(1)
        .execute()
    )
    rows = r.data or []
    return rows[0] if rows else None


def upsert_sku_rows(rows: list[dict[str, Any]], chunk_size: int = 200) -> None:
    if not rows:
        return
    sb = get_supabase()
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        sb.table("sku_item").upsert(chunk, on_conflict="sku").execute()
