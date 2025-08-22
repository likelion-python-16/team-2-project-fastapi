# app/routers/map.py
import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/map", tags=["Map"])

@router.get("/", response_class=HTMLResponse)
async def get_map(request: Request):
    # 네이버 API Key 읽기
    key = os.getenv("NAVER_MAPS_CLIENT_ID") or os.getenv("X_NCP_APIGW_API_KEY_ID")
    if not key:
        key = "YOUR_KEY_HERE"  # fallback (테스트용)

    return templates.TemplateResponse(
        "map_dynamic.html",
        {"request": request, "ncpKeyId": key},
    )
