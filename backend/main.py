from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend.availability import get_availability_report
from backend.csv_import import import_skus_csv
from backend.db import count_skus

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
PUBLIC_STATIC = ROOT_DIR / "public" / "static"
_ON_VERCEL = bool(os.getenv("VERCEL"))


class AnalyzeRequest(BaseModel):
    sku: str = Field(default="", max_length=256)
    quantity: int = Field(default=1, ge=1, le=10_000_000)


class OBIEnrichBody(BaseModel):
    limit: int = Field(default=20, ge=1, le=500)
    delay_sec: float = Field(default=0.3, ge=0.0, le=2.0)


def _env_truthy(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _scraper_token_required() -> bool:
    """Włącz SCRAPER_REQUIRE_TOKEN=1, żeby wymagać X-Scraper-Token (patrz _scrape_authenticated)."""
    return _env_truthy("SCRAPER_REQUIRE_TOKEN")


SCRAPER_PIN_MIN_LEN = 8


def _scrape_authenticated(request: Request) -> bool:
    if not _scraper_token_required():
        return True
    got = (request.headers.get("X-Scraper-Token") or "").strip()
    pin = (os.getenv("SCRAPER_PIN") or "").strip()
    long_tok = (os.getenv("SCRAPER_TOKEN") or "").strip()
    if not pin and not long_tok:
        return False
    if pin and len(pin) >= SCRAPER_PIN_MIN_LEN and len(got) == len(pin) and secrets.compare_digest(got, pin):
        return True
    if long_tok and len(got) == len(long_tok) and secrets.compare_digest(got, long_tok):
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(ROOT_DIR / ".env")
    app.state.supabase_config_error = None
    u = (os.getenv("SUPABASE_URL") or "").strip()
    k = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not u or not k:
        app.state.supabase_config_error = (
            "Brak SUPABASE_URL lub SUPABASE_SERVICE_ROLE_KEY w środowisku (Vercel → Settings → Environment Variables)."
        )
    if app.state.supabase_config_error:
        print("hornbach-sku config:", app.state.supabase_config_error, flush=True)
    if _scraper_token_required():
        pin = (os.getenv("SCRAPER_PIN") or "").strip()
        long_tok = (os.getenv("SCRAPER_TOKEN") or "").strip()
        if pin and len(pin) < SCRAPER_PIN_MIN_LEN:
            print(
                "hornbach-sku config: SCRAPER_PIN jest krótszy niż",
                SCRAPER_PIN_MIN_LEN,
                "— skraper nie zaakceptuje tego hasła.",
                flush=True,
            )
        if not pin and not long_tok:
            print(
                "hornbach-sku config: SCRAPER_REQUIRE_TOKEN=1, ale brak SCRAPER_PIN i SCRAPER_TOKEN — "
                "endpointy skrapera zwrócą 403.",
                flush=True,
            )
    yield


app = FastAPI(title="Sprawdzanie dostępności SKU", lifespan=lifespan)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
if not _ON_VERCEL and PUBLIC_STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(PUBLIC_STATIC)), name="static")


def _config_error_response(request: Request) -> Optional[HTMLResponse]:
    err = getattr(request.app.state, "supabase_config_error", None)
    if err:
        return templates.TemplateResponse(
            "config_error.html",
            {"request": request, "message": err},
            status_code=503,
        )
    return None


def _db_error_response(request: Request, exc: Exception) -> HTMLResponse:
    return templates.TemplateResponse(
        "config_error.html",
        {
            "request": request,
            "message": f"{type(exc).__name__}: {exc}",
        },
        status_code=502,
    )


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    bad = _config_error_response(request)
    if bad:
        return bad
    try:
        count = count_skus()
    except Exception as e:
        print("hornbach-sku count_skus:", repr(e), flush=True)
        return _db_error_response(request, e)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "sku_count": count,
            "scraper_token_required": _scraper_token_required(),
            "scraper_pin_min_len": SCRAPER_PIN_MIN_LEN,
        },
    )


@app.post("/api/analyze")
def api_analyze(request: Request, body: AnalyzeRequest):
    bad = _config_error_response(request)
    if bad:
        return JSONResponse({"ok": False, "message": "Brak konfiguracji serwera."}, status_code=503)
    try:
        report = get_availability_report(body.sku, body.quantity, "")
        return JSONResponse(report)
    except Exception as e:
        print("hornbach-sku api_analyze:", repr(e), flush=True)
        return JSONResponse({"ok": False, "code": "server", "message": str(e)}, status_code=500)


def _scrape_auth_error() -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "message": "Brak lub złe hasło skrapera. Na serwerze ustaw SCRAPER_PIN (min. "
            f"{SCRAPER_PIN_MIN_LEN} znaków — to samo wpisujesz w UI) i/lub opcjonalnie SCRAPER_TOKEN "
            "(długi sekret dla skryptów; nagłówek X-Scraper-Token musi się zgadzać).",
        },
        status_code=403,
    )


@app.post("/api/scrape/auth-check")
def api_scrape_auth_check(request: Request):
    """Lekka weryfikacja PIN / tokena przed pokazaniem reszty UI (bez Supabase, bez pobierania OBI)."""
    if not _scraper_token_required():
        return JSONResponse({"ok": True, "token_required": False})
    if not _scrape_authenticated(request):
        return _scrape_auth_error()
    return JSONResponse({"ok": True, "token_required": True})


@app.post("/api/scrape/obi/markets")
def api_scrape_obi_markets(request: Request, body: OBIEnrichBody):
    if not _scrape_authenticated(request):
        return _scrape_auth_error()
    bad = _config_error_response(request)
    if bad:
        return JSONResponse({"ok": False, "message": "Brak konfiguracji serwera."}, status_code=503)
    try:
        from backend.scrape.obi_catalog import enrich_markets, list_market_slugs

        all_slugs = list_market_slugs()
        take = all_slugs[: body.limit]
        rows = enrich_markets(take, delay_sec=body.delay_sec)
        return JSONResponse(
            {
                "ok": True,
                "slug_total": len(all_slugs),
                "fetched": len(rows),
                "rows": rows,
                "hint": "Kolumna postal_code_guess to heurystyka z HTML (należy zweryfikować). "
                "Pełna siatka EAN×sklep×zapas wymaga osobnego źródła danych OBI (API partnera / analiza PDP).",
            }
        )
    except ValueError as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=400)
    except Exception as e:
        print("hornbach-sku scrape_obi_markets:", repr(e), flush=True)
        return JSONResponse({"ok": False, "message": str(e)}, status_code=502)


@app.post("/api/import")
async def api_import(request: Request, file: UploadFile = File(...)):
    bad = _config_error_response(request)
    if bad:
        return JSONResponse({"ok": False, "message": "Brak konfiguracji serwera."}, status_code=503)
    raw = (await file.read()).decode("utf-8-sig")
    try:
        inserted, errs = import_skus_csv(raw)
        return JSONResponse({"ok": True, "inserted": inserted, "errors": errs})
    except Exception as e:
        print("hornbach-sku api_import:", repr(e), flush=True)
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=302)
