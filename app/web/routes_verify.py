# app/web/routes_verify.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/verify/success", response_class=HTMLResponse)
def verify_success():
    """이메일 인증 성공 페이지"""
    with open("app/templates/verify_success.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

@router.get("/verify/fail", response_class=HTMLResponse)  
def verify_fail():
    """이메일 인증 실패 페이지"""
    with open("app/templates/verify_fail.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)