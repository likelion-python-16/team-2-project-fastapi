# app/routers/users_mypage.py  (F-1-10, 11, 15, 16 + 프로필 GET/PATCH)
from typing import Optional
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, desc, literal

from pydantic import BaseModel, field_validator

# ✅ 프로젝트 일관: core.database / security 사용
from app.core.database import get_db
from app.security import get_current_user
# Simple pagination helper
def pagination_params(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    skip = (page - 1) * limit
    return {"page": page, "limit": limit, "skip": skip}

from app.models.user import User
from app.models.following import Following
from app.models.payment import Payment, Refund
from app.models.pointhistory import PointHistory, PointHistoryType
from app.models.tag import Tag, UserTag

from app.schemas.payment import PaymentOut, SpendSummaryOut, PaymentListOut
from app.schemas.auth import UserBrief, FollowListOut, PointHistoryOut, PointHistoryListOut


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
        "is_admin": bool(getattr(me, "is_admin", False)),
        "is_superadmin": bool(getattr(me, "is_superadmin", False)),
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
    """지출 요약 (실제 payments/refunds 테이블 기준)"""
    from sqlalchemy import text
    
    # 결제 총액 조회 (실제 payments 테이블)
    payment_query = """
    SELECT COALESCE(SUM(amount), 0) as total_paid 
    FROM payments 
    WHERE user_id = :user_id AND status = 'completed'
    """
    if not include_deposit:
        payment_query += " AND transaction_type = 'entry_fee'"
    
    total_paid_result = db.execute(text(payment_query), {"user_id": me.id})
    total_paid = float(total_paid_result.fetchone()[0] or 0)

    # 환불 총액 조회 (실제 refunds 테이블)
    refund_query = """
    SELECT COALESCE(SUM(refund_amount), 0) as total_refunded 
    FROM refunds 
    WHERE user_id = :user_id AND status = 'completed'
    """
    
    total_refunded_result = db.execute(text(refund_query), {"user_id": me.id})
    total_refunded = float(total_refunded_result.fetchone()[0] or 0)

    result = SpendSummaryOut(
        total_paid=int(total_paid),
        total_refunded=int(total_refunded),
        net_spent=int(total_paid - total_refunded),
    )
    print(f"DEBUG: SpendSummary for user {me.id}: {result}")  # 임시 디버깅
    return result

# -----------------------------
# F-1-15: 결제 내역
# -----------------------------
@router.get("/me/payments", response_model=PaymentListOut)
def my_payments(
    status: Optional[str] = Query(None, description="예: paid / pending / cancelled / refunded"),
    transaction_type: Optional[str] = Query(None, description="예: entry_fee / monthly_fee"),
    date_from: Optional[str] = Query(None, description="ISO8601 시작(>=)"),
    date_to: Optional[str] = Query(None, description="ISO8601 종료(<)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    """사용자 결제 내역 (실제 payments 테이블 기준)"""
    # 실제 payments 테이블에 직접 SQL 쿼리 사용
    from sqlalchemy import text
    
    # 조건 빌드
    where_conditions = ["user_id = :user_id"]
    params = {"user_id": me.id}
    
    if status:
        # 프론트엔드 호환성을 위한 상태 매핑
        if status == "paid":
            params["status"] = "completed"
        else:
            params["status"] = status
        where_conditions.append("status = :status")
    
    if transaction_type:
        where_conditions.append("transaction_type = :transaction_type")
        params["transaction_type"] = transaction_type

    _df = _as_dt(date_from)
    _dt = _as_dt(date_to)
    if _df:
        where_conditions.append("created_at >= :date_from")
        params["date_from"] = _df
    if _dt:
        where_conditions.append("created_at < :date_to")
        params["date_to"] = _dt
    
    where_clause = " AND ".join(where_conditions)
    
    # 총 개수 조회
    count_query = f"SELECT COUNT(*) as total FROM payments WHERE {where_clause}"
    total_result = db.execute(text(count_query), params)
    total = total_result.fetchone()[0]
    
    items = []
    if total > 0:
        # 데이터 조회
        data_query = f"""
        SELECT id, user_id, challenge_id, amount, transaction_type, status, 
               method, order_id, payment_key, created_at, updated_at
        FROM payments 
        WHERE {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
        """
        params.update({"limit": pg["limit"], "offset": pg["skip"]})
        
        rows = db.execute(text(data_query), params)
        
        # 결과를 PaymentOut 형태로 변환
        for row in rows:
            item = {
                "id": row.id,
                "user_id": row.user_id,
                "challenge_id": row.challenge_id,
                "amount": int(row.amount),  # float에서 int로 변경
                "status": row.status,
                "transaction_type": row.transaction_type,  # 올바른 필드명 사용
                "method": row.method or "card",  # 기본값을 올바른 enum 값으로 변경
                "created_at": row.created_at,
                "order_id": row.order_id or f"ORDER-{row.id}",
                "payment_key": row.payment_key
            }
            items.append(item)

    print(f"DEBUG: Payments query - status={status}, total={total}, items={len(items)}")  # 임시 디버깅
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
        # Prefer the consolidated single-file template
        return templates.TemplateResponse("mypage.html", ctx)
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
        return templates.TemplateResponse("mypage.html", ctx)
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


# =============================
# Missing Endpoints for MyPage
# =============================

@router.get("/me/visibility")
def get_user_visibility(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """사용자 공개/비공개 설정 조회"""
    return {
        "followers": False,  # 팔로워 목록 공개 여부
        "interests": False,  # 관심사 공개 여부
        "challenges": False,  # 참여 챌린지 공개 여부
        "reviews": False     # 리뷰 공개 여부
    }

@router.patch("/me/visibility")
def update_user_visibility(
    visibility_data: dict,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """사용자 공개/비공개 설정 수정"""
    # TODO: 실제 데이터베이스 업데이트 로직 구현
    return {"message": "Visibility settings updated"}

@router.get("/me/interests")
def get_user_interests(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """사용자 관심사 태그 조회"""
    user_tags = db.execute(
        select(Tag).join(UserTag).where(UserTag.user_id == me.id, Tag.is_active == True)
    ).scalars().all()
    
    tag_ids = [tag.id for tag in user_tags]
    tags = [{"id": tag.id, "tag": tag.tag, "is_active": tag.is_active} for tag in user_tags]
    return {"tag_ids": tag_ids, "tags": tags}

@router.patch("/me/interests")
def update_user_interests(
    interests_data: dict,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """사용자 관심사 태그 수정"""
    tag_ids = interests_data.get("tag_ids", [])
    
    # 기존 관심사 모두 삭제 (더 안전하고 효율적)
    from sqlalchemy import delete
    db.execute(
        delete(UserTag).where(UserTag.user_id == me.id)
    )
    db.flush()  # 삭제를 먼저 처리
    
    # 새 관심사 추가
    added_tags = []
    for tag_id in tag_ids:
        try:
            # 태그가 존재하는지 확인
            tag = db.execute(select(Tag).where(Tag.id == tag_id, Tag.is_active == True)).scalar_one_or_none()
            if tag:
                user_tag = UserTag(user_id=me.id, tag_id=tag_id)
                db.add(user_tag)
                added_tags.append(tag_id)
        except Exception as e:
            # 개별 태그 추가 실패 시 건너뛰기
            print(f"Failed to add tag {tag_id}: {e}")
            continue
    
    try:
        db.commit()
        return {"message": "Interests updated", "tag_ids": added_tags}
    except Exception as e:
        db.rollback()
        return {"error": "Failed to update interests", "details": str(e)}

@router.get("/me/reviews")
def get_user_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """사용자 리뷰 내역 조회"""
    # TODO: 실제 리뷰 데이터 조회 로직 구현
    return {
        "items": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }


# ========================
# 회원정보 수정 관련 API들  
# ========================

@router.get("/me/phone-masked")
def get_phone_masked(
    me: User = Depends(get_current_user)
):
    """마스킹된 전화번호 조회"""
    if not me.phone:
        return {"phone_masked": None}
    
    # 전화번호 마스킹: 010-1234-5678 -> 010-***4-5678
    phone = me.phone
    if len(phone) >= 7:
        masked = phone[:3] + "-***" + phone[-4:]
    else:
        masked = "***-****-****" 
    
    return {"phone_masked": masked}


@router.post("/me/verify-password")
def verify_current_password(
    payload: dict,
    me: User = Depends(get_current_user)
):
    """현재 비밀번호 검증"""
    from passlib.context import CryptContext
    
    password = payload.get("password", "")
    if not password:
        raise HTTPException(400, "비밀번호를 입력해주세요")
    
    # 비밀번호 검증
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    if not pwd_context.verify(password, me.password_hash):
        raise HTTPException(400, "비밀번호가 올바르지 않습니다")
    
    return {"message": "비밀번호 검증 성공"}


@router.patch("/me/username")
def update_username(
    payload: dict,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """사용자명 변경"""
    from app.security import create_access_token, create_refresh_token
    
    new_username = payload.get("username", "").strip().lower()
    if not new_username:
        raise HTTPException(400, "사용자명을 입력해주세요")
    
    # 중복 체크
    existing = db.query(User).filter(User.username == new_username, User.id != me.id).first()
    if existing:
        raise HTTPException(409, "이미 사용 중인 사용자명입니다")
    
    # 업데이트
    me.username = new_username
    db.commit()
    
    # 새 토큰 생성 (사용자명이 토큰에 포함되므로)
    access_token = create_access_token(data={"sub": me.username, "user_id": me.id})
    refresh_token = create_refresh_token(data={"sub": me.username, "user_id": me.id})
    
    return {
        "message": "사용자명이 변경되었습니다",
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@router.patch("/me/phone")  
def update_phone(
    payload: dict,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """전화번호 변경 (모든 소셜 연동 계정도 가능)"""
    from app.security import normalize_phone, id_fingerprint
    
    new_phone = payload.get("phone", "").strip()
    if not new_phone:
        raise HTTPException(400, "전화번호를 입력해주세요")
    
    # 전화번호 정규화
    try:
        normalized_phone = normalize_phone(new_phone)
        phone_fp = id_fingerprint(normalized_phone)
    except Exception:
        raise HTTPException(400, "올바르지 않은 전화번호 형식입니다")
    
    # 강화된 중복 체크 (fingerprint, 평문, encrypted 모두 체크)
    existing_queries = [
        db.query(User).filter(User.phone_fingerprint == phone_fp, User.id != me.id),
        db.query(User).filter(User.phone == normalized_phone, User.id != me.id)
    ]
    
    for query in existing_queries:
        existing = query.first()
        if existing:
            raise HTTPException(409, "이미 등록된 전화번호입니다")
    
    # 업데이트
    me.phone = normalized_phone
    me.phone_fingerprint = phone_fp
    db.commit()
    
    return {"message": "전화번호가 변경되었습니다"}


@router.post("/me/change-password")
def change_password(
    payload: dict,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """비밀번호 변경"""
    from passlib.context import CryptContext
    from app.security import validate_password_strength, get_password_requirements
    
    new_password = payload.get("new_password", "")
    if not new_password:
        raise HTTPException(400, "새 비밀번호를 입력해주세요")
    
    # 비밀번호 강도 검증
    if not validate_password_strength(new_password):
        requirements = get_password_requirements()
        raise HTTPException(400, {"message": "비밀번호가 요구사항을 충족하지 않습니다", "requirements": requirements})
    
    # 기존 비밀번호와 동일한지 체크
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    if pwd_context.verify(new_password, me.password_hash):
        raise HTTPException(400, "새 비밀번호는 현재 비밀번호와 다르게 설정해주세요")
    
    # 새 비밀번호 해시 생성
    new_password_hash = pwd_context.hash(new_password)
    
    # 업데이트
    me.password_hash = new_password_hash
    db.commit()
    
    return {"message": "비밀번호가 변경되었습니다"}

