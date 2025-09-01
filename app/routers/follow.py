# app/routers/follow.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.models.challenge import Challenge
from app.models.following import Following
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["Follow"])

class ChallengeCard(BaseModel):
    id: int
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    mode: Optional[str] = None
    payment_type: str
    entry_fee: int = 0
    monthly_fee: int = 0
    current_participants: int = 0
    max_participants: Optional[int] = None
    cover_image: Optional[str] = None

    class Config:
        from_attributes = True

def _to_card(ch: Challenge) -> ChallengeCard:
    # payment_type 결정
    entry_fee_val = getattr(ch, 'entry_fee', 0) or 0
    monthly_fee_val = getattr(ch, 'monthly_fee', 0) or 0
    
    if entry_fee_val > 0 and monthly_fee_val > 0:
        payment_type = "both"
    elif entry_fee_val > 0:
        payment_type = "entry_fee"
    elif monthly_fee_val > 0:
        payment_type = "monthly_fee"
    else:
        payment_type = "free"
    
    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        start_date=ch.start_date.isoformat() if ch.start_date else None,
        end_date=ch.end_date.isoformat() if ch.end_date else None,
        status=ch.status,
        mode=getattr(ch, 'mode', None),
        payment_type=payment_type,
        entry_fee=entry_fee_val,
        monthly_fee=monthly_fee_val,
        current_participants=getattr(ch, 'current_participants', 0) or 0,
        max_participants=getattr(ch, 'max_participants', None),
        cover_image=getattr(ch, 'cover_image', None),
    )

@router.post("/follow/{target_user_id}")
def follow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
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
    me: User = Depends(get_current_user),
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
    me: User = Depends(get_current_user),
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

@router.get("/following/users")
def get_following_users(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """현재 사용자가 팔로우하는 사용자 ID 목록 반환"""
    following_ids = db.query(Following.following_id).filter(Following.follower_id == me.id).all()
    return {"following_user_ids": [row.following_id for row in following_ids]}