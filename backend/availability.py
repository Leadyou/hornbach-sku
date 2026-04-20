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
    name: Optional[str] = None
    stock_quantity: Optional[int] = None
    lead_time_days: Optional[int] = None
    earliest_feasible_date: Optional[date] = None
    delivery_location_code: Optional[str] = None


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


def _compute_earliest_delivery(row: dict[str, Any], today: date) -> tuple[int, Optional[date], date]:
    stock = int(row["stock_quantity"])
    lead = int(row["lead_time_days"])
    available_from = _coerce_available_from(row.get("available_from"))
    earliest = today + timedelta(days=lead)
    if available_from is not None and available_from > earliest:
        earliest = available_from
    return stock, available_from, earliest


def get_availability_report(sku: str, quantity: int, delivery_location_code: str = "") -> dict[str, Any]:
    """
    Raport dla UI (bez wymuszania daty dostawy od użytkownika).
    Zwraca słownik gotowy do JSON (daty jako ISO).
    """
    sku_clean = (sku or "").strip()
    today = date.today()

    if not sku_clean:
        return {"ok": False, "code": "empty_sku", "message": "Podaj numer SKU."}

    if quantity < 1:
        return {"ok": False, "code": "bad_quantity", "message": "Ilość musi być co najmniej 1."}

    loc = (delivery_location_code or "").strip()
    row = fetch_sku(sku_clean)

    if row is None:
        return {
            "ok": False,
            "code": "not_found",
            "sku": sku_clean,
            "quantity_requested": quantity,
            "message": "Nie znaleziono SKU w katalogu. Zaimportuj dane w zakładce „Data”.",
        }

    name = (row.get("name") or "").strip() or "—"
    row_loc = (row.get("delivery_location_code") or "").strip()
    stock, available_from, earliest = _compute_earliest_delivery(row, today)

    if row_loc and loc and row_loc != loc:
        return {
            "ok": False,
            "code": "location_mismatch",
            "sku": sku_clean,
            "name": name,
            "quantity_requested": quantity,
            "stock_quantity": stock,
            "lead_time_days": int(row["lead_time_days"]),
            "earliest_feasible_date": earliest.isoformat(),
            "delivery_location_catalog": row_loc,
            "delivery_location_requested": loc,
            "message": f"SKU jest przypisane do lokalizacji „{row_loc}”, a podano „{loc}”.",
        }

    qty_ok = quantity <= stock
    lead = int(row["lead_time_days"])

    parts: list[str] = []
    if qty_ok:
        parts.append(
            f"Na magazynie jest wystarczająca ilość ({stock} szt.; zamówienie: {quantity} szt.)."
        )
    else:
        parts.append(
            f"Stan magazynowy ({stock} szt.) jest mniejszy niż żądana ilość ({quantity} szt.)."
        )

    parts.append(
        f"Czas realizacji: {lead} dni kalendarzowych licząc od dziś ({today.isoformat()})."
    )
    if available_from:
        parts.append(f"Towar dostępny od: {available_from.isoformat()}.")
    parts.append(f"Najwcześniejsza możliwa data dostawy (przy złożeniu zamówienia dziś): {earliest.isoformat()}.")

    if row_loc:
        parts.append(f"Lokalizacja dostawy w katalogu: {row_loc}.")

    summary = " ".join(parts)

    return {
        "ok": True,
        "code": "ok" if qty_ok else "insufficient_stock",
        "sku": sku_clean,
        "name": name,
        "quantity_requested": quantity,
        "stock_quantity": stock,
        "quantity_feasible": qty_ok,
        "lead_time_days": lead,
        "available_from": available_from.isoformat() if available_from else None,
        "earliest_feasible_date": earliest.isoformat(),
        "delivery_location_code": row_loc or None,
        "message": summary,
    }


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

    name = (row.get("name") or "").strip() or None

    row_loc = (row.get("delivery_location_code") or "").strip()
    if row_loc and loc and row_loc != loc:
        stock, _, earliest = _compute_earliest_delivery(row, date.today())
        return CheckResult(
            ok=False,
            message=f"SKU jest przypisane do innej lokalizacji dostawy ({row_loc}), a podano: {loc}.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
            name=name,
            stock_quantity=stock,
            lead_time_days=int(row["lead_time_days"]),
            earliest_feasible_date=earliest,
            delivery_location_code=row_loc or None,
        )

    stock, available_from, earliest = _compute_earliest_delivery(row, date.today())
    lead = int(row["lead_time_days"])

    if quantity > stock:
        return CheckResult(
            ok=False,
            message=f"Brak wystarczającej ilości. Dostępne: {stock}, żądane: {quantity}.",
            sku=sku,
            quantity=quantity,
            requested_delivery_date=requested_delivery_date,
            name=name,
            stock_quantity=stock,
            lead_time_days=lead,
            earliest_feasible_date=earliest,
            delivery_location_code=row_loc or None,
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
            name=name,
            stock_quantity=stock,
            lead_time_days=lead,
            earliest_feasible_date=earliest,
            delivery_location_code=row_loc or None,
        )

    return CheckResult(
        ok=True,
        message="SKU jest dostępne w podanej ilości i terminie.",
        sku=sku,
        quantity=quantity,
        requested_delivery_date=requested_delivery_date,
        name=name,
        stock_quantity=stock,
        lead_time_days=lead,
        earliest_feasible_date=earliest,
        delivery_location_code=row_loc or None,
    )
