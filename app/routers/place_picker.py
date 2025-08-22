# app/routers/place_picker.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/pages/place-picker", response_class=HTMLResponse)
def place_picker_page(request: Request):
    # scope, rid 는 프론트에서 location.search 로 읽어 사용
    return templates.TemplateResponse("place_picker.html", {"request": request})
