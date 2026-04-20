from __future__ import annotations

import os
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
        {"request": request, "sku_count": count},
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
