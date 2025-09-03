# app/routers/pages.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
from pathlib import Path
from app.core.database import get_db
from app.models.user import User
from app.core.deps import get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 관심사 JSON (없으면 건너뛰어도 됨)
try:
    INTERESTS = json.loads(Path("data/category_keywords.json").read_text(encoding="utf-8"))
except Exception:
    INTERESTS = {}

@router.get("/signup", response_class=HTMLResponse)
def signup_step1(request: Request, db: Session = Depends(get_db)):
    # 일반 회원가입은 항상 허용 (관리자 존재 여부와 무관)
    return templates.TemplateResponse("signup_step1.html", {"request": request})

@router.get("/signup/step2", response_class=HTMLResponse)
def signup_step2(request: Request, db: Session = Depends(get_db)):
    # 일반 회원가입은 항상 허용
    return templates.TemplateResponse("signup_step2.html", {"request": request})

@router.get("/signup/step3", response_class=HTMLResponse)
def signup_step3(request: Request, db: Session = Depends(get_db)):
    # 일반 회원가입은 항상 허용
    return templates.TemplateResponse(
        "signup_step3.html",
        {"request": request, "interests_json": json.dumps(INTERESTS, ensure_ascii=False)},
    )

@router.get("/signup/complete", response_class=HTMLResponse)
def signup_complete(request: Request, db: Session = Depends(get_db)):
    # 일반 회원가입은 항상 허용
    return templates.TemplateResponse("signup_complete.html", {"request": request})

@router.get("/social/onboarding", response_class=HTMLResponse)
def social_onboarding(request: Request):
    return templates.TemplateResponse("social_onboarding.html", {"request": request})

# ----------------------
# Social-only signup flow
# ----------------------
@router.get("/signup/social/step1", response_class=HTMLResponse)
def social_step1(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("signup1forsocial.html", {"request": request})

@router.get("/signup/social/step2", response_class=HTMLResponse)
def social_step2(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("signup2forsocial.html", {"request": request})

@router.get("/signup/social/step3", response_class=HTMLResponse)
def social_step3(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("signup3forsocial.html", {"request": request})

@router.get("/signup/social/complete", response_class=HTMLResponse)
def social_complete(request: Request, db: Session = Depends(get_db)):
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

@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user_from_cookie(request, db)
        if not current_user:
            return RedirectResponse(url="/login?next=/profile", status_code=303)
        return templates.TemplateResponse("profile.html", {"request": request, "user": current_user})
    except Exception:
        return RedirectResponse(url="/login?next=/profile", status_code=303)
