from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.security import normalize_phone, id_fingerprint
from ..core.database import get_db
from ..models.user import User
from ..schemas.auth import UserOut
from ..utils.logging import logger

# 라우터 생성
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

# -------------------------------
# 사용자 목록 / 조회 / 검색 API
# -------------------------------
@router.get("/", response_model=List[UserOut])
async def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """모든 사용자 목록 조회 (페이지네이션 포함)"""
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        logger.info(f"사용자 목록 조회: {len(users)}명")
        return users
    except Exception as e:
        logger.error(f"사용자 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 목록을 가져오는데 실패했습니다")


@router.get("/count")
async def get_users_count(db: Session = Depends(get_db)):
    """전체 사용자 수 조회"""
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
        }
    except Exception as e:
        logger.error(f"사용자 수 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 수를 가져오는데 실패했습니다")


@router.get("/search")
async def search_users(q: str, db: Session = Depends(get_db)):
    """사용자 검색 (username, email, name으로)"""
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="검색어는 2자 이상이어야 합니다")

    try:
        users = db.query(User).filter(
            User.username.contains(q) |
            User.email.contains(q) |
            User.name.contains(q)
        ).limit(20).all()
        return {
            "query": q,
            "results": len(users),
            "users": [
                {"id": u.id, "username": u.username, "email": u.email,
                 "name": u.name, "is_active": u.is_active}
                for u in users
            ],
        }
    except Exception as e:
        logger.error(f"사용자 검색 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 검색에 실패했습니다")


@router.get("/{user_id:int}", response_model=UserOut)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """특정 사용자 조회"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="올바르지 않은 사용자 ID입니다")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"사용자 ID {user_id}를 찾을 수 없습니다")
    return user


@router.get("/username/{username}", response_model=UserOut)
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """사용자명으로 사용자 조회"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"사용자명 '{username}'을 찾을 수 없습니다")
    return user

# -------------------------------
# 계정 활성/비활성, 삭제
# -------------------------------
@router.patch("/{user_id:int}/activate")
async def activate_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 활성화"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    user.is_active = True
    db.commit()
    return {"message": f"사용자 {user_id}가 활성화되었습니다"}


@router.patch("/{user_id:int}/deactivate")
async def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 비활성화"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    user.is_active = False
    db.commit()
    return {"message": f"사용자 {user_id}가 비활성화되었습니다"}


@router.delete("/{user_id:int}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 삭제 (주의: 실제 삭제됨)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    db.delete(user)
    db.commit()
    return {"message": f"사용자 {user_id}가 삭제되었습니다"}

# -------------------------------
# 중복 검사 (회원가입/수정 전)
# -------------------------------
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

    # --- Normalize & Fingerprint ---
    u = username.strip().lower() if username else None
    e = str(email).strip().lower() if email else None
    p_norm = normalize_phone(phone) if phone else None
    p_fp = id_fingerprint(p_norm) if p_norm else None
    fp_ident = id_fingerprint(ident) if ident else None
    n = name.strip() if name else None

    def not_me(q):
        return q.filter(User.id != exclude_user_id) if exclude_user_id else q

    # --- 개별 중복 체크 ---
    username_exists = (
        not_me(db.query(User.id).filter(func.lower(User.username) == u)).first() is not None
        if u else "not_provided"
    )
    email_exists = (
        not_me(db.query(User.id).filter(func.lower(User.email) == e)).first() is not None
        if e else "not_provided"
    )
    phone_exists = (
        not_me(db.query(User.id).filter(User.phone_fingerprint == p_fp)).first() is not None
        or not_me(db.query(User.id).filter(User.phone == p_norm)).first() is not None
        if p_norm else "not_provided"
    )
    ident_exists = (
        not_me(db.query(User.id).filter(User.identification_fingerprint == fp_ident)).first() is not None
        if fp_ident else "not_provided"
    )

    # --- 동명이인 조합 체크 ---
    duplicate_person_by_email = (
        not_me(db.query(User.id).filter(
            User.identification_fingerprint == fp_ident,
            func.lower(User.name) == func.lower(n),
            func.lower(User.email) == e,
        )).first() is not None
        if n and fp_ident and e else "not_checked"
    )
    duplicate_person_by_phone = (
        not_me(db.query(User.id).filter(
            User.identification_fingerprint == fp_ident,
            func.lower(User.name) == func.lower(n),
            (User.phone_fingerprint == p_fp) | (User.phone == p_norm),
        )).first() is not None
        if n and fp_ident and p_norm else "not_checked"
    )

    # --- 최종 ---
    any_dup = any(x is True for x in [
        username_exists, email_exists, phone_exists, ident_exists,
        duplicate_person_by_email, duplicate_person_by_phone
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
