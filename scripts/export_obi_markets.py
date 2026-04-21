#!/usr/bin/env python3
"""
Eksport listy sklepów OBI.de do CSV (slug, URL, tytuł strony, heurystyczny kod PL).

Uruchom lokalnie (może potrwać kilka minut przy ~400 sklepach):

  cd /ścieżka/do/hornbach
  source .venv/bin/activate
  python scripts/export_obi_markets.py -o obi_markets.csv

Nie ustawiaj SCRAPER_TOKEN — ten skrypt woła moduły bezpośrednio.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scrape.obi_catalog import enrich_markets, list_market_slugs, markets_to_csv_bytes


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output", default="obi_markets.csv", help="Plik wyjściowy CSV")
    p.add_argument("--limit", type=int, default=0, help="0 = wszystkie wykryte slugi")
    p.add_argument("--delay", type=float, default=0.35, help="Pauza między zapytaniami (s)")
    args = p.parse_args()

    print("Pobieranie listy slugów z obi.de/markt …", flush=True)
    slugs = list_market_slugs()
    print(f"Znaleziono slugów: {len(slugs)}", flush=True)
    if args.limit and args.limit > 0:
        slugs = slugs[: args.limit]
        print(f"Ograniczenie do {len(slugs)} sklepów.", flush=True)

    rows = enrich_markets(slugs, delay_sec=args.delay)
    data = markets_to_csv_bytes(rows)
    Path(args.output).write_bytes(data)
    print(f"Zapisano: {args.output} ({len(rows)} wierszy)", flush=True)


if __name__ == "__main__":
    main()
