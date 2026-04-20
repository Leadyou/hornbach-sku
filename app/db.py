import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "availability.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sku_item (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                stock_quantity INTEGER NOT NULL DEFAULT 0,
                lead_time_days INTEGER NOT NULL DEFAULT 0,
                available_from TEXT,
                delivery_location_code TEXT DEFAULT ''
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
