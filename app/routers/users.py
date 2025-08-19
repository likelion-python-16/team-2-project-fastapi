# app/routers/users.py

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Literal, List, Dict, Any, Optional
from datetime import datetime, timezone, date as ddate
from sqlalchemy.orm import Session

from app.schemas.user import MeOut, MeUpdateIn  # ← 핵심: MeOut/MeUpdateIn 사용
from app.deps.auth import get_current_user
from app.db.session import get_db

from app.models.challenge import Challenge
from app.models.participation import Participation
from app.models.user import User
from app.models.tag import Tag, UserTag  # ⬅️ 조인 테이블

router = APIRouter(prefix="/api/v1/users", tags=["users"])

# ─────────────────────────────────────────────────────────────
# 0) /api/v1/users/me : 현재 유저 정보
# ─────────────────────────────────────────────────────────────
@router.get("/me", response_model=MeOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user

# ─────────────────────────────────────────────────────────────
# 1) 프로필 수정: PATCH /api/v1/users/me
# ─────────────────────────────────────────────────────────────
@router.patch("/me", response_model=MeOut)
def update_me(
    payload: MeUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        return current_user  # 변경 없음

    # 이메일 중복 체크(값이 들어온 경우만)
    if "email" in data:
        exists = (
            db.query(User)
            .filter(User.email == data["email"], User.id != current_user.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Email already in use")

    # 필드 적용
    for k, v in data.items():
        if hasattr(current_user, k):
            setattr(current_user, k, v)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

# ─────────────────────────────────────────────────────────────
# 2) 관심 태그: GET/POST/DELETE
# ─────────────────────────────────────────────────────────────
def _tag_to_dict(t: Tag) -> dict:
    return {
        "id": t.id,
        "name": getattr(t, "name", None) or getattr(t, "tag", None) or "",
        "icon_url": getattr(t, "icon_url", None),
    }

@router.get("/me/tags", response_model=List[Dict[str, Any]])
def get_my_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Tag)
        .join(UserTag, UserTag.tag_id == Tag.id)
        .filter(UserTag.user_id == current_user.id, Tag.is_active == True)
        .order_by(Tag.id.asc())
        .all()
    )
    return [_tag_to_dict(t) for t in rows]

# 구버전 호환
@router.get("/me/tags/detail", response_model=List[Dict[str, Any]])
def get_my_tags_detail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_my_tags(db=db, current_user=current_user)

from pydantic import BaseModel
class TagAddIn(BaseModel):
    tag_id: int

@router.post("/me/tags", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def add_my_tag(
    payload: TagAddIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tag = db.query(Tag).filter(Tag.id == payload.tag_id, Tag.is_active == True).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found or inactive")

    exists = (
        db.query(UserTag)
        .filter(UserTag.user_id == current_user.id, UserTag.tag_id == payload.tag_id)
        .first()
    )
    if exists:
        return _tag_to_dict(tag)

    db.add(UserTag(user_id=current_user.id, tag_id=payload.tag_id))
    db.commit()
    return _tag_to_dict(tag)

@router.delete("/me/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_my_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ut = (
        db.query(UserTag)
        .filter(UserTag.user_id == current_user.id, UserTag.tag_id == tag_id)
        .first()
    )
    if not ut:
        return  # 멱등
    db.delete(ut)
    db.commit()
    return

# ─────────────────────────────────────────────────────────────
# 3) 챌린지 목록
# ─────────────────────────────────────────────────────────────
def _to_date(v):
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