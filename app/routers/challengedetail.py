# app/routers/challengedetail.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/pages/challenges", tags=["pages-challenges"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/{challenge_id}")
def challenge_detail_page(challenge_id: int, request: Request):
    return templates.TemplateResponse(
        "challenge_detail.html",
        {"request": request, "challenge_id": challenge_id},
    )
