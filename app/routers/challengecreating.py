# app/routers/challengecreating.py
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/pages/challenges", tags=["pages-challenges"])

BASE_DIR = Path(__file__).resolve().parent.parent  # app/routers -> app
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/new", response_class=HTMLResponse)
def challenge_create_page(request: Request):
    return templates.TemplateResponse("challenge_create.html", {"request": request})

@router.get("/{challenge_id}", response_class=HTMLResponse)
def challenge_detail_page(request: Request, challenge_id: int):
    return templates.TemplateResponse("challenge_detail.html", {"request": request, "challenge_id": challenge_id})
