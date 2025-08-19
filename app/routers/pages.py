# app/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 관심사 JSON (없으면 건너뛰어도 됨)
try:
    INTERESTS = json.loads(Path("data/category_keywords.json").read_text(encoding="utf-8"))
except Exception:
    INTERESTS = {}

@router.get("/signup", response_class=HTMLResponse)
def signup_step1(request: Request):
    return templates.TemplateResponse("signup_step1.html", {"request": request})

@router.get("/signup/step2", response_class=HTMLResponse)
def signup_step2(request: Request):
    return templates.TemplateResponse("signup_step2.html", {"request": request})

@router.get("/signup/step3", response_class=HTMLResponse)
def signup_step3(request: Request):
    return templates.TemplateResponse(
        "signup_step3.html",
        {"request": request, "interests_json": json.dumps(INTERESTS, ensure_ascii=False)},
    )

@router.get("/signup/complete", response_class=HTMLResponse)
def signup_complete(request: Request):
    return templates.TemplateResponse("signup_complete.html", {"request": request})
