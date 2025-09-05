# app/routers/pages.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.deps import get_current_user_from_cookie
from app.models.user import User
import json
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 관심사 JSON (없으면 건너뛰어도 됨)
try:
    INTERESTS = json.loads(Path("data/category_keywords.json").read_text(encoding="utf-8"))
except Exception:
    INTERESTS = {}

@router.get("/signup/step1", response_class=HTMLResponse)
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

@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    return templates.TemplateResponse("reset_password.html", {"request": request})

@router.get("/points", response_class=HTMLResponse)
def points_page(request: Request, current_user: User = Depends(get_current_user_from_cookie)):
    return templates.TemplateResponse("points.html", {"request": request, "current_user": current_user})
