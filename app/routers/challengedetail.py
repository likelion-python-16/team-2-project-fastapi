# app/routers/challengedetail.py
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.security import get_current_user_optional
from app.models.user import User
from app.models.participation import Participation
from app.models.challenge import Challenge

router = APIRouter(prefix="/pages/challenges", tags=["pages-challenges"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/{challenge_id}")
def challenge_detail_page(
    challenge_id: int, 
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    # 사용자의 이 챌린지에서의 역할 조회
    user_role = ""
    if current_user:
        participation = db.query(Participation).filter(
            Participation.user_id == current_user.id,
            Participation.challenge_id == challenge_id
        ).first()
        
        if participation:
            user_role = participation.role.value
    
    return templates.TemplateResponse(
        "challenge_detail.html",
        {
            "request": request, 
            "challenge_id": challenge_id,
            "current_user": current_user,
            "user_role": user_role
        },
    )
