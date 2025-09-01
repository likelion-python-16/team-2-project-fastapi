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

@router.get("/social/onboarding", response_class=HTMLResponse)
def social_onboarding(request: Request):
    return templates.TemplateResponse("social_onboarding.html", {"request": request})

# ----------------------
# Social-only signup flow
# ----------------------
@router.get("/signup/social/step1", response_class=HTMLResponse)
def social_step1(request: Request):
    return templates.TemplateResponse("signup1forsocial.html", {"request": request})

@router.get("/signup/social/step2", response_class=HTMLResponse)
def social_step2(request: Request):
    return templates.TemplateResponse("signup2forsocial.html", {"request": request})

@router.get("/signup/social/step3", response_class=HTMLResponse)
def social_step3(request: Request):
    return templates.TemplateResponse("signup3forsocial.html", {"request": request})

@router.get("/signup/social/complete", response_class=HTMLResponse)
def social_complete(request: Request):
    return templates.TemplateResponse("signup_complete_social.html", {"request": request})

@router.get("/account/edit", response_class=HTMLResponse)
def account_edit(request: Request):
    return templates.TemplateResponse("account_edit.html", {"request": request})

@router.get("/social/merge", response_class=HTMLResponse)
def social_merge(request: Request):
    return templates.TemplateResponse("social_merge.html", {"request": request})

@router.get("/social/merge-done", response_class=HTMLResponse)
def social_merge_done(request: Request):
    return templates.TemplateResponse("social_merge_done.html", {"request": request})
