from __future__ import annotations

from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import EmailStr, BaseModel, Field
from sqlalchemy import func, or_, desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from sqlalchemy.orm.attributes import flag_modified
from app.models.user import User
from app.models.following import Following
from app.models.review import Review, ReviewStatus
from app.models import Tag  # ← 활성 태그 검증 위해 추가
from app.schemas.auth import UserOut
from app.schemas.user_public import UserPublicOut
from app.schemas.user import UserBrief, FollowListOut
from app.security import normalize_phone, id_fingerprint
from app.utils.logging import logger

# 로그인 유저 의존성 (프로젝트 경로에 맞게 조정)
from app.dependencies.auth import get_current_user  # ← 경로 다르면 수정

# -------------------------------------------------
# Router
# -------------------------------------------------
router = APIRouter(prefix="/users", tags=["users"])


# =========================
# ✅ 관심 태그 전용 스키마
# =========================
class InterestUpdateIn(BaseModel):
    tag_ids: List[int] = Field(default_factory=list, description="선택한 태그 ID 배열")

class InterestOut(BaseModel):
    tag_ids: List[int]
    tags: List[dict]  # {id, tag, icon_url}


# =========================
# ✅ 리뷰 응답 스키마
# =========================
class ReviewItemOut(BaseModel):
    created_at: str
    rating: float
    content: str
    challenge_title: Optional[str] = None

class ReviewListOut(BaseModel):
    items: List[ReviewItemOut]
    total: int
    skip: int
    limit: int


# =========================
# ✅ 섹션 공개 설정 스키마/유틸
# =========================
class VisibilitySettings(BaseModel):
    profile: Optional[bool] = True
    followers: Optional[bool] = True
    challenges: Optional[bool] = True
    interests: Optional[bool] = True
    reviews: Optional[bool] = True

def _get_visibility_from_prefs(prefs: Optional[Dict]) -> Dict[str, bool]:
    base = {"profile": True, "followers": True, "challenges": True, "interests": True, "reviews": True}
    if not prefs:
        return base
    v = (prefs or {}).get("visibility") or {}
    out = base.copy()
    for k in list(base.keys()):
        if isinstance(v.get(k), bool):
            out[k] = bool(v[k])
    return out


# =========================
# ✅ 관심 태그 API (유저 전용)
# =========================
@router.get("/me/interests", response_model=InterestOut)
async def get_my_interests(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    ids = (me.preferences or {}).get("interest_tag_ids", [])
    if not ids:
        return InterestOut(tag_ids=[], tags=[])

    rows = db.query(Tag).filter(Tag.id.in_(ids), Tag.is_active.is_(True)).all()
    m = {t.id: t for t in rows}
    ordered = [m[i] for i in ids if i in m]
    return InterestOut(
        tag_ids=ids,
        tags=[{"id": t.id, "tag": t.tag, "icon_url": getattr(t, "icon_url", None)} for t in ordered],
    )

@router.patch("/me/interests", response_model=InterestOut)
async def save_my_interests(
    body: InterestUpdateIn,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    # 최대 10개 제한
    if len(body.tag_ids) > 10:
        raise HTTPException(status_code=400, detail="태그는 최대 10개까지 선택할 수 있어요.")

    # 활성 태그만 허용
    if body.tag_ids:
        rows = db.query(Tag.id).filter(Tag.id.in_(body.tag_ids), Tag.is_active.is_(True)).all()
        valid_ids = {r.id for r in rows}
        if len(valid_ids) != len(set(body.tag_ids)):
            raise HTTPException(status_code=400, detail="존재하지 않거나 비활성화된 태그가 포함되어 있어요.")

    # SQLAlchemy JSON 컬럼은 내부 변경을 추적하지 않을 수 있으니
    # 새로운 dict로 재할당하고 변경 플래그를 명시해 안전하게 반영한다.
    current = dict(me.preferences or {})
    current["interest_tag_ids"] = list(body.tag_ids)
    me.preferences = current
    try:
        flag_modified(me, "preferences")
    except Exception:
        pass

    db.add(me)
    db.commit()
    db.refresh(me)

    # 저장 후 상세 반환 (입력 순서 유지)
    tags = []
    if body.tag_ids:
        tag_rows = db.query(Tag).filter(Tag.id.in_(body.tag_ids), Tag.is_active.is_(True)).all()
        tag_map = {t.id: t for t in tag_rows}
        tags = [
            {"id": i, "tag": tag_map[i].tag, "icon_url": getattr(tag_map[i], "icon_url", None)}
            for i in body.tag_ids if i in tag_map
        ]
    return InterestOut(tag_ids=body.tag_ids, tags=tags)


# =========================
# ✅ 공개 설정 조회/수정
# =========================
@router.get("/me/visibility", response_model=VisibilitySettings)
async def get_my_visibility(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    return VisibilitySettings(**_get_visibility_from_prefs(me.preferences))


@router.patch("/me/visibility", response_model=VisibilitySettings)
async def update_my_visibility(
    body: VisibilitySettings,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    prefs: Dict = dict(me.preferences or {})
    vis = dict(_get_visibility_from_prefs(prefs))
    for k, v in body.model_dump(exclude_none=True).items():
        if k == "profile":
            continue  # 프로필은 항상 공개
        if isinstance(v, bool):
            vis[k] = bool(v)
    # 서버 강제 규칙: 프로필은 항상 공개
    vis["profile"] = True
    prefs["visibility"] = vis
    me.preferences = prefs
    try:
        flag_modified(me, "preferences")
    except Exception:
        pass
    db.add(me)
    db.commit()
    db.refresh(me)
    return VisibilitySettings(**_get_visibility_from_prefs(me.preferences))


@router.get("/{user_id}/visibility", response_model=VisibilitySettings)
async def get_user_visibility(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or getattr(u, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return VisibilitySettings(**_get_visibility_from_prefs(u.preferences))


# =========================
# ✅ 공개 팔로워/팔로잉 조회
# =========================
@router.get("/{user_id}/followers", response_model=FollowListOut)
async def public_followers(
    user_id: int = Path(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    only_active: bool = Query(True),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    # 공개 설정 확인
    vis = _get_visibility_from_prefs(getattr(user, 'preferences', None))
    if vis.get("followers") is False:
        return FollowListOut(items=[], total=0, skip=skip, limit=limit)

    # 총합
    total = (
        db.query(Following)
        .join(User, User.id == Following.follower_id)
        .filter(Following.following_id == user_id)
        .count()
    )

    items: List[UserBrief] = []
    if total:
        rows = (
            db.query(User)
            .join(Following, Following.follower_id == User.id)
            .filter(Following.following_id == user_id)
            .order_by(desc(Following.created_at), desc(User.id))
            .offset(skip)
            .limit(limit)
            .all()
        )
        items = [UserBrief.model_validate(r, from_attributes=True) for r in rows]

    return FollowListOut(items=items, total=int(total or 0), skip=skip, limit=limit)


@router.get("/{user_id}/following", response_model=FollowListOut)
async def public_following(
    user_id: int = Path(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    only_active: bool = Query(True),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    # 공개 설정 확인
    vis = _get_visibility_from_prefs(getattr(user, 'preferences', None))
    if vis.get("followers") is False:
        return FollowListOut(items=[], total=0, skip=skip, limit=limit)

    total = (
        db.query(Following)
        .join(User, User.id == Following.following_id)
        .filter(Following.follower_id == user_id)
        .count()
    )

    items: List[UserBrief] = []
    if total:
        rows = (
            db.query(User)
            .join(Following, Following.following_id == User.id)
            .filter(Following.follower_id == user_id)
            .order_by(desc(Following.created_at), desc(User.id))
            .offset(skip)
            .limit(limit)
            .all()
        )
        items = [UserBrief.model_validate(r, from_attributes=True) for r in rows]

    return FollowListOut(items=items, total=int(total or 0), skip=skip, limit=limit)

@router.get("/{user_id}/interests", response_model=InterestOut)
async def get_user_interests(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """공개 프로필: 해당 유저의 선택된 태그만 노출"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    # 공개 설정 확인
    vis = _get_visibility_from_prefs(getattr(user, 'preferences', None))
    if vis.get("interests") is False:
        return InterestOut(tag_ids=[], tags=[])

    ids = (user.preferences or {}).get("interest_tag_ids", [])
    if not ids:
        return InterestOut(tag_ids=[], tags=[])

    rows = db.query(Tag).filter(Tag.id.in_(ids), Tag.is_active.is_(True)).all()
    m = {t.id: t for t in rows}
    ordered = [m[i] for i in ids if i in m]
    return InterestOut(
        tag_ids=ids,
        tags=[{"id": t.id, "tag": t.tag, "icon_url": getattr(t, "icon_url", None)} for t in ordered],
    )


# -------------------------------------------------
# 사용자 목록 / 통계 / 검색
# -------------------------------------------------
@router.get("/", response_model=List[UserOut])
async def get_users(
    skip: int = Query(0, ge=0, description="건너뛸 개수"),
    limit: int = Query(100, ge=1, le=200, description="조회 개수(최대 200)"),
    db: Session = Depends(get_db),
):
    """모든 사용자 목록 조회 (페이지네이션)"""
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        logger.info("사용자 목록 조회: %d명 (skip=%d, limit=%d)", len(users), skip, limit)
        return users
    except Exception as e:
        logger.error("사용자 목록 조회 오류: %s", str(e))
        raise HTTPException(status_code=500, detail="사용자 목록을 가져오는데 실패했습니다")


@router.get("/count")
async def get_users_count(db: Session = Depends(get_db)):
    """전체/활성 사용자 수 조회"""
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active.is_(True)).count()
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
        }
    except Exception as e:
        logger.error("사용자 수 조회 오류: %s", str(e))
        raise HTTPException(status_code=500, detail="사용자 수를 가져오는데 실패했습니다")


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=2, description="검색어(2자 이상)"),
    limit: int = Query(20, ge=1, le=50, description="최대 결과 수"),
    db: Session = Depends(get_db),
):
    """사용자 검색 (username, email, name)"""
    try:
        qnorm = q.strip().lower()
        users = (
            db.query(User)
            .filter(
                or_(
                    func.lower(User.username).contains(qnorm),
                    func.lower(User.email).contains(qnorm),
                    func.lower(User.name).contains(qnorm),
                )
            )
            .limit(limit)
            .all()
        )
        return {
            "query": q,
            "results": len(users),
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "name": u.name,
                    "is_active": u.is_active,
                }
                for u in users
            ],
        }
    except Exception as e:
        logger.error("사용자 검색 오류: %s", str(e))
        raise HTTPException(status_code=500, detail="사용자 검색에 실패했습니다")


# -------------------------------------------------
# 중복 검사 (회원가입/수정 전)
# -------------------------------------------------
@router.get("/dup-check")
def check_duplicates(
    username: Optional[str] = Query(None, description="사용자명"),
    email: Optional[EmailStr] = Query(None, description="이메일"),
    phone: Optional[str] = Query(None, description="전화번호(하이픈 가능)"),
    ident: Optional[str] = Query(None, description="주민/식별번호(하이픈 가능)"),
    name: Optional[str] = Query(None, description="실명(동명이인 방지)"),
    exclude_user_id: Optional[int] = Query(None, description="수정 시 자기 자신 제외"),
    db: Session = Depends(get_db),
):
    """
    ✅ 회원가입/수정 시 중복 검사
    - username, email, phone, ident 개별 필드 중복 여부
    - name + ident + (email or phone) 조합 → 동일인 여부 판단
    """
    if not any([username, email, phone, ident, name]):
        raise HTTPException(status_code=400, detail="검사할 파라미터가 없습니다")

    u = username.strip().lower() if username else None
    e = str(email).strip().lower() if email else None
    n = name.strip() if name else None

    p_norm = normalize_phone(phone) if phone else None
    p_fp = id_fingerprint(p_norm) if p_norm else None
    fp_ident = id_fingerprint(ident) if ident else None

    def not_me(q):
        return q.filter(User.id != exclude_user_id) if exclude_user_id else q

    username_exists = (
        not_me(db.query(User.id).filter(func.lower(User.username) == u)).first() is not None
        if u else "not_provided"
    )
    email_exists = (
        not_me(db.query(User.id).filter(func.lower(User.email) == e)).first() is not None
        if e else "not_provided"
    )
    phone_exists = (
        (
            not_me(db.query(User.id).filter(User.phone_fingerprint == p_fp)).first() is not None
            or not_me(db.query(User.id).filter(User.phone == p_norm)).first() is not None
        )
        if p_norm else "not_provided"
    )
    ident_exists = (
        not_me(db.query(User.id).filter(User.identification_fingerprint == fp_ident)).first() is not None
        if fp_ident else "not_provided"
    )

    duplicate_person_by_email = (
        not_me(
            db.query(User.id).filter(
                User.identification_fingerprint == fp_ident,
                func.lower(User.name) == n.lower(),
                func.lower(User.email) == e,
            )
        ).first() is not None
        if n and fp_ident and e else "not_checked"
    )
    duplicate_person_by_phone = (
        not_me(
            db.query(User.id).filter(
                User.identification_fingerprint == fp_ident,
                func.lower(User.name) == n.lower(),
                or_(User.phone_fingerprint == p_fp, User.phone == p_norm),
            )
        ).first() is not None
        if n and fp_ident and p_norm else "not_checked"
    )

    any_dup = any(x is True for x in [
        username_exists, email_exists, phone_exists, ident_exists,
        duplicate_person_by_email, duplicate_person_by_phone,
    ])

    return {
        "available": not any_dup,
        "username": username_exists,
        "email": email_exists,
        "phone": phone_exists,
        "ident": ident_exists,
        "composite": {
            "duplicate_person_by_email": duplicate_person_by_email,
            "duplicate_person_by_phone": duplicate_person_by_phone,
            "rule": "name + ident + (email or phone) 일치 시 같은 사람으로 간주",
        },
        "message": "제공한 값만 검사합니다. phone은 fingerprint 기준으로 우선 검사하며, 레거시 phone(숫자열)도 보조로 확인합니다.",
    }


# -------------------------------------------------
# 단건 조회
# -------------------------------------------------
@router.get("/{user_id}", response_model=UserPublicOut)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """특정 사용자 조회"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="올바르지 않은 사용자 ID입니다")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"사용자 ID {user_id}를 찾을 수 없습니다")
    return UserPublicOut.model_validate(user, from_attributes=True)


@router.get("/username/{username}", response_model=UserPublicOut)
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """사용자명으로 사용자 조회"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # status_code 오탈자 수정
        raise HTTPException(status_code=404, detail=f"사용자명 '{username}'을 찾을 수 없습니다")
    return UserPublicOut.model_validate(user, from_attributes=True)


# -------------------------------------------------
# 계정 활성/비활성, 삭제
# -------------------------------------------------
@router.patch("/{user_id}/activate")
async def activate_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 활성화"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    user.is_active = True
    db.commit()
    return {"message": f"사용자 {user_id}가 활성화되었습니다"}


@router.patch("/{user_id}/deactivate")
async def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 비활성화"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    user.is_active = False
    db.commit()
    return {"message": f"사용자 {user_id}가 비활성화되었습니다"}


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 삭제 (주의: 실제 삭제됨)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    db.delete(user)
    db.commit()
    return {"message": f"사용자 {user_id}가 삭제되었습니다"}


__all__ = ["router"]



# =========================
# ✅ 리뷰 목록 (내/공개) – visibility.reviews 적용
# =========================
@router.get("/me/reviews", response_model=ReviewListOut)
async def get_my_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    q = db.query(Review).filter(Review.user_id == me.id, Review.status == ReviewStatus.visible)
    total = q.count()
    rows = q.order_by(desc(Review.created_at)).offset(skip).limit(limit).all()
    items = [
        ReviewItemOut(
            created_at=(r.created_at.isoformat() if getattr(r, 'created_at', None) else ''),
            rating=float(getattr(r, 'rating', 0) or 0),
            content=getattr(r, 'comment', '') or '',
            challenge_title=getattr(getattr(r, 'challenge', None), 'title', None),
        ) for r in rows
    ]
    return ReviewListOut(items=items, total=total, skip=skip, limit=limit)


@router.get("/{user_id}/reviews", response_model=ReviewListOut)
async def get_user_reviews(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    vis = (user.preferences or {}).get('visibility') or {}
    if vis.get('reviews') is False:
        return ReviewListOut(items=[], total=0, skip=skip, limit=limit)

    q = db.query(Review).filter(Review.user_id == user_id, Review.status == ReviewStatus.visible)
    total = q.count()
    rows = q.order_by(desc(Review.created_at)).offset(skip).limit(limit).all()
    items = [
        ReviewItemOut(
            created_at=(r.created_at.isoformat() if getattr(r, 'created_at', None) else ''),
            rating=float(getattr(r, 'rating', 0) or 0),
            content=getattr(r, 'comment', '') or '',
            challenge_title=getattr(getattr(r, 'challenge', None), 'title', None),
        ) for r in rows
    ]
    return ReviewListOut(items=items, total=total, skip=skip, limit=limit)
