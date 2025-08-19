# app/routers/users.py

from fastapi import APIRouter, Depends, Query
from typing import Literal, List, Dict, Any
from datetime import datetime, timezone, date as ddate

from sqlalchemy.orm import Session

from app.schemas.user import UserOut
from app.deps.auth import get_current_user
from app.db.session import get_db

from app.models.challenge import Challenge
from app.models.participation import Participation
from app.models.user import User
from app.models.tag import Tag  # 🔹 tags/detail 응답용

router = APIRouter(prefix="/api/v1/users", tags=["users"])

# 1) /api/v1/users/me : 현재 유저 정보
@router.get("/me", response_model=UserOut)
def read_me(current_user: UserOut = Depends(get_current_user)):
    return current_user


# ---- 공통 유틸 ----
def _to_date(v):
    """datetime -> date, date -> date, 'YYYY-MM-DD' -> date"""
    if isinstance(v, ddate):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def _challenge_status(start_d: ddate | None, end_d: ddate | None, today: ddate) -> str | None:
    if not (start_d and end_d):
        return None
    if start_d <= today <= end_d:
        return "active"
    if end_d < today:
        return "finished"
    return "upcoming"


def _row_to_item(p: Participation, c: Challenge, today: ddate) -> dict:
    # ⚠️ 모델은 못 건드린다고 했으니 start_date/end_date만 사용
    start_d = _to_date(getattr(c, "start_date", None))
    end_d   = _to_date(getattr(c, "end_date", None))
    return {
        "challenge_id": c.id,
        "title": getattr(c, "title", None) or getattr(c, "name", None),
        "challenge_status": _challenge_status(start_d, end_d, today),
        "start_date": start_d,
        "end_date": end_d,
        "participation_id": p.id,
        "participation_status": getattr(p, "status", "active") if hasattr(p, "status") else "active",
        "role": getattr(p, "role", "participant"),
        "joined_at": getattr(p, "created_at", None),
    }


def _apply_status_filter(items: list[dict], status: str) -> list[dict]:
    if status in {"active", "finished", "upcoming"}:
        return [it for it in items if it.get("challenge_status") == status]
    return items


# 2) /api/v1/users/me/challenges : 현재 유저의 챌린지 목록
@router.get("/me/challenges")
def list_my_challenges(
    status: Literal["all", "active", "finished", "upcoming"] = Query("all"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(Participation, Challenge)
        .join(Challenge, Challenge.id == Participation.challenge_id)
        .filter(Participation.user_id == current_user.id)
        .order_by(Challenge.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = q.all()

    today = datetime.now(timezone.utc).date()
    items = [_row_to_item(p, c, today) for p, c in rows]
    items = _apply_status_filter(items, status)

    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


# 3) (옵션) /api/v1/users/{id}/challenges : 다른 유저의 챌린지 목록
@router.get("/{user_id}/challenges")
def list_user_challenges(
    user_id: int,
    status: Literal["all", "active", "finished", "upcoming"] = Query("all"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(Participation, Challenge)
        .join(Challenge, Challenge.id == Participation.challenge_id)
        .filter(Participation.user_id == user_id)
        .order_by(Challenge.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = q.all()

    today = datetime.now(timezone.utc).date()
    items = [_row_to_item(p, c, today) for p, c in rows]
    items = _apply_status_filter(items, status)

    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


# 4) /api/v1/users/me/tags/detail : 관심 태그 상세 (프론트가 호출)
@router.get("/me/tags/detail", response_model=List[Dict[str, Any]])
def get_my_tags_detail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    현재 로그인한 사용자의 관심 태그 목록.
    프론트는 'name' 키를 기대하므로 Tag.tag/Tag.name 중 있는 값을 name으로 변환.
    관계가 비어 있으면 [] 반환.
    """
    tags: List[Tag] = []
    # User 모델에 tags 관계가 있는 경우
    if hasattr(current_user, "tags") and current_user.tags:
        tags = current_user.tags  # lazy-load 관계 허용

    # (선택) 관계가 없다면, 조인 조회 로직을 여기에 추가하면 됨.

    return [
        {
            "id": t.id,
            "name": getattr(t, "name", None) or getattr(t, "tag", None) or "",
            "icon_url": getattr(t, "icon_url", None),
        }
        for t in (tags or [])
    ]
