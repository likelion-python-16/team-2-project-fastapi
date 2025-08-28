# app/routers/follow.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.database import get_db
from app.security import verify_token
from app.models.user import User
from app.models.challenge import Challenge
from app.models.following import Following
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["Follow"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user_required(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    payload = verify_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="비활성 사용자거나 존재하지 않습니다.")
    return user

class ChallengeCard(BaseModel):
    id: int
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    fee_type: str
    participation_fee: int
    fee: int
    thumbnail_url: Optional[str] = None

    class Config:
        from_attributes = True

def _to_card(ch: Challenge) -> ChallengeCard:
    fee_val = (ch.fee or 0)
    part_fee_val = (ch.participation_fee or 0)
    fee_type = "유료" if (fee_val > 0 or part_fee_val > 0) else "무료"
    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        start_date=ch.start_date.isoformat() if ch.start_date else None,
        end_date=ch.end_date.isoformat() if ch.end_date else None,
        status=ch.status,
        fee_type=fee_type,
        participation_fee=part_fee_val,
        fee=fee_val,
        thumbnail_url=getattr(ch, "thumbnail_url", None),
    )

@router.post("/follow/{target_user_id}")
def follow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_required),
):
    if target_user_id == me.id:
        raise HTTPException(status_code=400, detail="자기 자신을 팔로우할 수 없습니다.")

    target = db.query(User).filter(User.id == target_user_id, User.is_active == True).first()
    if not target:
        raise HTTPException(status_code=404, detail="대상 사용자를 찾을 수 없습니다.")

    exists = db.query(Following).filter(
        and_(
            Following.follower_id == me.id,
            Following.following_id == target_user_id
        )
    ).first()
    if exists:
        return {"message": "이미 팔로우 중입니다."}

    new_follow = Following(follower_id=me.id, following_id=target_user_id)
    db.add(new_follow)
    db.commit()
    return {"message": "팔로우했습니다."}

@router.delete("/follow/{target_user_id}")
def unfollow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_required),
):
    rel = db.query(Following).filter(
        and_(
            Following.follower_id == me.id,
            Following.following_id == target_user_id
        )
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="팔로우 관계가 없습니다.")
    db.delete(rel)
    db.commit()
    return {"message": "언팔로우했습니다."}

@router.get("/following/challenges", response_model=List[ChallengeCard])
def following_challenges(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_required),
):
    subq = db.query(Following.following_id).filter(Following.follower_id == me.id).subquery()

    rows = (
        db.query(Challenge)
        .filter(Challenge.creator_id.in_(subq))
        .order_by(desc(getattr(Challenge, "created_at", Challenge.id)))
        .limit(limit)
        .all()
    )
    return [_to_card(c) for c in rows]