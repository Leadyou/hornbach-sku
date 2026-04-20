import os
from functools import lru_cache


@lru_cache
def supabase_url() -> str:
    v = (os.getenv("SUPABASE_URL") or "").strip()
    if not v:
        raise RuntimeError("Brak zmiennej SUPABASE_URL (ustaw w .env lub środowisku).")
    return v.rstrip("/")


@lru_cache
def supabase_service_role_key() -> str:
    v = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not v:
        raise RuntimeError(
            "Brak SUPABASE_SERVICE_ROLE_KEY. W Dashboard → Project Settings → API "
            "skopiuj service_role (tylko po stronie serwera, nigdy w przeglądarce dla gości)."
        )
    return v
