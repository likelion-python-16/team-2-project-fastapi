# app/routers/users_mypage.py  (F-1-10, 11, 15, 16 + 프로필 GET/PATCH)
from typing import Optional
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, desc, literal

from pydantic import BaseModel, field_validator

# ✅ 프로젝트 일관: core.database / security 사용
from app.core.database import get_db
from app.security import get_current_user
from app.deps.pagination import pagination_params

from app.models.user import User
from app.models.following import Following
from app.models.finance import Payment, Refund
from app.models.pointhistory import PointHistory, PointHistoryType

from app.schemas.finance import SpendSummaryOut, PaymentOut, PaymentListOut
from app.schemas.user import UserBrief, FollowListOut
from app.schemas.point import PointHistoryOut, PointHistoryListOut


# =============================
# 내부 유틸
# =============================
def _as_dt(x: Optional[str]) -> Optional[datetime]:
    if not x:
        return None
    try:
        return datetime.fromisoformat(x)
    except Exception:
        return None

def _user_payload(me: User) -> dict:
    """프런트에서 바로 쓰도록 키 통일."""
    return {
        "id": me.id,
        "username": me.username,
        "email": me.email,
        "name": me.name,
        "phone": getattr(me, "phone", None),
        "home_region": getattr(me, "region_living", None),
        "active_region": getattr(me, "region_active", None),
        "avatar_url": getattr(me, "profile_image", None),
        "introduction": getattr(me, "introduction", "") or "",
        "manner_score": int(getattr(me, "manner_score", 0) or 0),
        "total_points": int(getattr(me, "total_points", 0) or 0),
        "is_active": bool(getattr(me, "is_active", True)),
    }


# =============================
# ✅ API 라우터 (/api/v1/users/*)
# =============================
router = APIRouter(prefix="/api/v1/users", tags=["users"])

# -----------------------------
# F-1-10: 지금까지 쓴 금액 요약
# -----------------------------
@router.get("/me/spend/summary", response_model=SpendSummaryOut)
def my_spend_summary(
    include_deposit: bool = False,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    pay_type_cond = literal(True) if include_deposit else (Payment.payment_type == "fee")

    total_paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            and_(Payment.user_id == me.id, Payment.status == "paid", pay_type_cond)
        )
    ).scalar_one()

    total_refunded = db.execute(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            and_(Refund.user_id == me.id, Refund.processed_at.isnot(None))
        )
    ).scalar_one()

    return SpendSummaryOut(
        total_paid=int(total_paid or 0),
        total_refunded=int(total_refunded or 0),
        net_spent=int(total_paid or 0) - int(total_refunded or 0),
    )

# -----------------------------
# F-1-15: 결제 내역
# -----------------------------
@router.get("/me/payments", response_model=PaymentListOut)
def my_payments(
    status: Optional[str] = Query(None, description="예: paid / pending / cancelled / refunded"),
    payment_type: Optional[str] = Query(None, description="예: fee / deposit"),
    date_from: Optional[str] = Query(None, description="ISO8601 시작(>=)"),
    date_to: Optional[str] = Query(None, description="ISO8601 종료(<)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    conds = [Payment.user_id == me.id]
    if status:
        conds.append(Payment.status == status)
    if payment_type:
        conds.append(Payment.payment_type == payment_type)

    _df = _as_dt(date_from)
    _dt = _as_dt(date_to)
    if _df:
        conds.append(Payment.created_at >= _df)
    if _dt:
        conds.append(Payment.created_at < _dt)

    total = db.execute(
        select(func.count()).select_from(Payment).where(and_(*conds))
    ).scalar_one()

    items = []
    if total:
        rows = db.execute(
            select(Payment)
            .where(and_(*conds))
            .order_by(desc(Payment.created_at), desc(Payment.id))
            .offset(pg["skip"])
            .limit(pg["limit"])
        ).scalars().all()
        items = [PaymentOut.model_validate(r, from_attributes=True) for r in rows]

    return PaymentListOut(items=items, total=int(total or 0), skip=pg["skip"], limit=pg["limit"])

# -----------------------------
# F-1-16: 포인트 내역
# -----------------------------
@router.get("/me/points", response_model=PointHistoryListOut)
def my_point_history(
    type: Optional[PointHistoryType] = Query(None, description="gain/use/refund"),
    challenge_id: Optional[int] = Query(None, description="특정 챌린지 필터"),
    date_from: Optional[str] = Query(None, description="ISO8601 시작(>=)"),
    date_to: Optional[str] = Query(None, description="ISO8601 종료(<)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    conds = [PointHistory.user_id == me.id]
    if type is not None:
        conds.append(PointHistory.type == type)
    if challenge_id is not None:
        conds.append(PointHistory.challenge_id == challenge_id)

    _df = _as_dt(date_from)
    _dt = _as_dt(date_to)
    if _df:
        conds.append(PointHistory.created_at >= _df)
    if _dt:
        conds.append(PointHistory.created_at < _dt)

    total = db.execute(
        select(func.count()).select_from(PointHistory).where(and_(*conds))
    ).scalar_one()

    items = []
    if total:
        rows = db.execute(
            select(PointHistory)
            .where(and_(*conds))
            .order_by(desc(PointHistory.created_at), desc(PointHistory.id))
            .offset(pg["skip"])
            .limit(pg["limit"])
        ).scalars().all()
        items = [PointHistoryOut.model_validate(r, from_attributes=True) for r in rows]

    current_points = int(me.total_points or 0)

    return PointHistoryListOut(
        items=items,
        total=int(total or 0),
        skip=pg["skip"],
        limit=pg["limit"],
        current_points=current_points,
    )

# -----------------------------
# F-1-11: 팔로우/팔로워
# -----------------------------
@router.get("/me/following", response_model=FollowListOut)
def my_following(
    only_active: bool = Query(True, description="활성 사용자만"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    active_cond = (User.is_active == True) if only_active else literal(True)  # noqa: E712

    total = db.execute(
        select(func.count())
        .select_from(Following)
        .join(User, User.id == Following.following_id)
        .where(and_(Following.follower_id == me.id, active_cond))
    ).scalar_one()

    users = []
    if total:
        rows = db.execute(
            select(User)
            .join(Following, Following.following_id == User.id)
            .where(and_(Following.follower_id == me.id, active_cond))
            .order_by(desc(Following.created_at), desc(User.id))
            .offset(pg["skip"])
            .limit(pg["limit"])
        ).scalars().all()
        users = [UserBrief.model_validate(u, from_attributes=True) for u in rows]

    return FollowListOut(items=users, total=int(total or 0), skip=pg["skip"], limit=pg["limit"])

@router.get("/me/followers", response_model=FollowListOut)
def my_followers(
    only_active: bool = Query(True, description="활성 사용자만"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    active_cond = (User.is_active == True) if only_active else literal(True)  # noqa: E712

    total = db.execute(
        select(func.count())
        .select_from(Following)
        .join(User, User.id == Following.follower_id)
        .where(and_(Following.following_id == me.id, active_cond))
    ).scalar_one()

    users = []
    if total:
        rows = db.execute(
            select(User)
            .join(Following, Following.follower_id == User.id)
            .where(and_(Following.following_id == me.id, active_cond))
            .order_by(desc(Following.created_at), desc(User.id))
            .offset(pg["skip"])
            .limit(pg["limit"])
        ).scalars().all()
        users = [UserBrief.model_validate(u, from_attributes=True) for u in rows]

    return FollowListOut(items=users, total=int(total or 0), skip=pg["skip"], limit=pg["limit"])

# -----------------------------
# ✅ 내 프로필 읽기 (충돌 방지를 위해 /me/profile 권장)
# -----------------------------
@router.get("/me/profile")
def get_my_profile(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    return _user_payload(me)

# (선택) 과거 호환: /me 도 제공하지만, 다른 라우터의 /users/{user_id}와 충돌 가능
@router.get("/me")
def get_my_profile_legacy(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    return _user_payload(me)

# -----------------------------
# ✅ 내 프로필 수정 (PATCH /api/v1/users/me/profile)
# -----------------------------
class UserProfileUpdateIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    home_region: Optional[str] = None   # -> region_living
    active_region: Optional[str] = None # -> region_active
    avatar_url: Optional[str] = None    # -> profile_image
    introduction: Optional[str] = None  # -> introduction
    notify: Optional[bool] = None       # 현재 저장 안 함

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v):
        if v is None:
            return v
        digits = "".join(ch for ch in str(v) if ch.isdigit())
        return digits[:32]

@router.patch("/me/profile")
def update_my_profile(
    payload: UserProfileUpdateIn,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    changed = False

    if payload.name is not None:
        me.name = payload.name.strip()
        changed = True
    if payload.phone is not None:
        me.phone = payload.phone
        changed = True
    if payload.home_region is not None:
        me.region_living = payload.home_region.strip()
        changed = True
    if payload.active_region is not None:
        me.region_active = payload.active_region.strip()
        changed = True
    if payload.avatar_url is not None:
        me.profile_image = payload.avatar_url.strip()
        changed = True
    if payload.introduction is not None:
        me.introduction = payload.introduction.strip()
        changed = True

    if changed:
        me.updated_at = datetime.utcnow()
        db.add(me)
        db.commit()
        db.refresh(me)

    return _user_payload(me)


# =============================
# ✅ 페이지 라우터 (/mypage) — 템플릿 경로 안전 + 폴백
# =============================
page_router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@page_router.get("/mypage", response_class=HTMLResponse)
async def mypage_self(request: Request):
    ctx = {"request": request, "view_user_id": None}
    try:
        return templates.TemplateResponse("mypage/index.html", ctx)
    except TemplateNotFound:
        html = f"""
        <!doctype html>
        <html><head><meta charset="utf-8"><title>MyPage</title>
        <style>body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Noto Sans KR,sans-serif;padding:24px}}</style>
        </head><body>
          <h1>My Page</h1>
          <p>템플릿 <code>app/templates/mypage/index.html</code> 이(가) 없어 임시 페이지를 표시합니다.</p>
          <p>템플릿 디렉토리: <code>{TEMPLATE_DIR}</code></p>
        </body></html>
        """
        return HTMLResponse(content=html, status_code=200)

@page_router.get("/mypage/{user_id}", response_class=HTMLResponse)
async def mypage_public(request: Request, user_id: int):
    ctx = {"request": request, "view_user_id": user_id}
    try:
        return templates.TemplateResponse("mypage/index.html", ctx)
    except TemplateNotFound:
        html = f"""
        <!doctype html>
        <html><head><meta charset=\"utf-8\"><title>MyPage</title>
        <style>body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Noto Sans KR,sans-serif;padding:24px}}</style>
        </head><body>
          <h1>My Page (User {user_id})</h1>
          <p>템플릿 <code>app/templates/mypage/index.html</code> 이(가) 없어 임시 페이지를 표시합니다.</p>
          <p>템플릿 디렉토리: <code>{TEMPLATE_DIR}</code></p>
        </body></html>
        """
        return HTMLResponse(content=html, status_code=200)
