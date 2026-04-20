from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.availability import check_availability
from backend.csv_import import import_skus_csv
from backend.db import count_skus

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
PUBLIC_STATIC = ROOT_DIR / "public" / "static"
_ON_VERCEL = bool(os.getenv("VERCEL"))


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
        {"request": request, "result": None, "import_notice": None, "sku_count": count},
    )


@app.post("/check", response_class=HTMLResponse)
def check(
    request: Request,
    sku: str = Form(...),
    quantity: int = Form(...),
    requested_delivery_date: date = Form(...),
    delivery_location_code: str = Form(""),
):
    bad = _config_error_response(request)
    if bad:
        return bad
    try:
        result = check_availability(sku, quantity, requested_delivery_date, delivery_location_code)
        count = count_skus()
    except Exception as e:
        print("hornbach-sku check:", repr(e), flush=True)
        return _db_error_response(request, e)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": result, "import_notice": None, "sku_count": count},
    )


@app.post("/import", response_class=HTMLResponse)
async def import_csv(request: Request, file: UploadFile = File(...)):
    bad = _config_error_response(request)
    if bad:
        return bad
    raw = (await file.read()).decode("utf-8-sig")
    try:
        inserted, errs = import_skus_csv(raw)
        notice = {"inserted": inserted, "errors": errs}
        count = count_skus()
    except Exception as e:
        print("hornbach-sku import:", repr(e), flush=True)
        return _db_error_response(request, e)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": None, "import_notice": notice, "sku_count": count},
    )


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=302)
