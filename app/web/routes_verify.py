# app/web/routes_verify.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/verify/success", response_class=HTMLResponse)
def verify_success(request: Request):
    """이메일 인증 성공 페이지 (Jinja 렌더)"""
    return templates.TemplateResponse("verify_success.html", {"request": request})

@router.get("/verify/fail", response_class=HTMLResponse)  
def verify_fail(request: Request):
    """이메일 인증 실패 페이지 (Jinja 렌더)"""
    return templates.TemplateResponse("verify_fail.html", {"request": request})
