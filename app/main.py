from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.availability import check_availability
from app.csv_import import import_skus_csv
from app.db import count_skus, get_supabase

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    get_supabase()
    yield


app = FastAPI(title="Sprawdzanie dostępności SKU", lifespan=lifespan)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    count = count_skus()
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
    result = check_availability(sku, quantity, requested_delivery_date, delivery_location_code)
    count = count_skus()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": result, "import_notice": None, "sku_count": count},
    )


@app.post("/import", response_class=HTMLResponse)
async def import_csv(request: Request, file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8-sig")
    inserted, errs = import_skus_csv(raw)
    notice = {"inserted": inserted, "errors": errs}
    count = count_skus()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": None, "import_notice": notice, "sku_count": count},
    )


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=302)
