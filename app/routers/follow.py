# app/routers/follow.py
from datetime import date, datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.models.challenge import Challenge
from app.models.challenge_round import ChallengeRound
from app.models.following import Following  # follower_id -> followee_id

router = APIRouter(prefix="/api/v1/follow", tags=["Follow"])

class ChallengeCard(BaseModel):
    id: int
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None
    status: str
    fee_type: str
    participation_fee: int
    fee: int
    total_rounds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    class Config:
        from_attributes = True

class ListOut(BaseModel):
    items: List[ChallengeCard]
    page: int
    page_size: int
    has_next: bool

def _round_counts(db: Session, ids: List[int]) -> Dict[int, int]:
    if not ids: return {}
    rows = (
        db.query(ChallengeRound.challenge_id, func.count(ChallengeRound.id))
        .filter(ChallengeRound.challenge_id.in_(ids))
        .group_by(ChallengeRound.challenge_id)
        .all()
    )
    return {cid: cnt for cid, cnt in rows}

def _to_card(ch: Challenge, rounds: Optional[int]) -> ChallengeCard:
    entry = getattr(ch, "participation_fee", None) or getattr(ch, "entry_fee", 0) or 0
    monthly = getattr(ch, "fee", None) or getattr(ch, "monthly_fee", 0) or 0
    fee_type = "유료" if (entry > 0 or monthly > 0) else "무료"
    status_str = ch.status.value if hasattr(ch.status, "value") else str(ch.status)
    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        start_date=ch.start_date,
        end_date=ch.end_date,
        created_at=getattr(ch, "created_at", None),
        status=status_str,
        fee_type=fee_type,
        participation_fee=int(entry),
        fee=int(monthly),
        total_rounds=rounds,
        thumbnail_url=getattr(ch, "thumbnail_url", None),
    )

@router.get("/followed-challenges", response_model=ListOut, summary="팔로우한 유저가 만든 챌린지 목록")
def followed_challenges(
    page: int = 1,
    page_size: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 로그인 필수
):
    subq = (
        db.query(Following.following_id)
        .filter(Following.follower_id == current_user.id)
        .subquery()
    )

    q = (
        db.query(Challenge)
        .filter(Challenge.creator_id.in_(subq))
        .order_by(desc(Challenge.created_at))
    )

    rows = q.offset((max(page, 1) - 1) * page_size).limit(page_size + 1).all()
    has_next = len(rows) > page_size
    rows = rows[:page_size]

    ids = [c.id for c in rows]
    counts = _round_counts(db, ids)
    items = [_to_card(c, counts.get(c.id)) for c in rows]

    return ListOut(items=items, page=page, page_size=page_size, has_next=has_next)
