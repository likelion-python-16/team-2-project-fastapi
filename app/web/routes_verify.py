# app/web/routes_verify.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# 기존: templates = Jinja2Templates(directory="templates")
BASE_DIR = Path(__file__).resolve().parent.parent  # app/
TEMPLATE_DIR = BASE_DIR / "templates"              # app/templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter()

@router.get("/verify/success", response_class=HTMLResponse)
async def verify_success(request: Request):
    return templates.TemplateResponse("verify_success.html", {"request": request})

@router.get("/verify/fail", response_class=HTMLResponse)
async def verify_fail(request: Request, reason: str = "unknown"):
    return templates.TemplateResponse("verify_fail.html", {"request": request, "reason": reason})
