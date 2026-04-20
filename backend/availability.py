from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from backend.db import fetch_sku


@dataclass
class CheckResult:
    ok: bool
    message: str
    sku: str
    quantity: int
    requested_delivery_date: date
    stock_quantity: Optional[int] = None
    lead_time_days: Optional[int] = None
    earliest_feasible_date: Optional[date] = None


def _parse_date(s: str) -> date:
    return date.fromisoformat(s.strip())


def _coerce_available_from(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if type(value) is date:
        return value
    if isinstance(value, str):
        t = value.strip()
        if not t:
            return None
        try:
            return _parse_date(t[:10])
        except ValueError:
            return None
    return None


def check_availability(
    sku: str,
    quantity: int,
    requested_delivery_date: date,
    delivery_location_code: str = "",
) -> CheckResult:
    sku = sku.strip()
    if not sku:
        return CheckResult(
            ok=False,
            message="Podaj numer SKU.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
        )
    if quantity < 1:
        return CheckResult(
            ok=False,
            message="Ilość musi być co najmniej 1.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
        )

    loc = (delivery_location_code or "").strip()

    row = fetch_sku(sku)

    if row is None:
        return CheckResult(
            ok=False,
            message="Nie znaleziono SKU w katalogu. Upewnij się, że dane zostały zaimportowane.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
        )

    row_loc = (row.get("delivery_location_code") or "").strip()
    if row_loc and loc and row_loc != loc:
        return CheckResult(
            ok=False,
            message=f"SKU jest przypisane do innej lokalizacji dostawy ({row_loc}), a podano: {loc}.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
            stock_quantity=int(row["stock_quantity"]),
            lead_time_days=int(row["lead_time_days"]),
        )

    stock = int(row["stock_quantity"])
    lead = int(row["lead_time_days"])
    today = date.today()

    available_from = _coerce_available_from(row.get("available_from"))

    earliest = today + timedelta(days=lead)
    if available_from is not None and available_from > earliest:
        earliest = available_from

    if quantity > stock:
        return CheckResult(
            ok=False,
            message=f"Brak wystarczającej ilości. Dostępne: {stock}, żądane: {quantity}.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
            stock_quantity=stock,
            lead_time_days=lead,
            earliest_feasible_date=earliest,
        )

    if requested_delivery_date < earliest:
        return CheckResult(
            ok=False,
            message=(
                f"Termin jest zbyt krótki względem czasu realizacji ({lead} dni kalendarzowych"
                + (f", dostępność od {available_from}" if available_from else "")
                + f"). Najwcześniejsza możliwa data dostawy: {earliest.isoformat()}."
            ),
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
            stock_quantity=stock,
            lead_time_days=lead,
            earliest_feasible_date=earliest,
        )

    return CheckResult(
        ok=True,
        message="SKU jest dostępne w podanej ilości i terminie.",
        sku=sku,
        quantity=quantity,
        requested_delivery_date=requested_delivery_date,
        stock_quantity=stock,
        lead_time_days=lead,
        earliest_feasible_date=earliest,
    )
