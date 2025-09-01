from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

# ✅ 기존 임포트에 get_current_user 추가
from app.security import normalize_phone, id_fingerprint, get_current_user
from ..core.database import get_db
from ..models.user import User
from ..schemas.auth import UserOut
from ..utils.logging import logger
from app.security import create_access_token, create_refresh_token
from app.security import validate_password_strength
from fastapi import Body

# 라우터 생성
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

# =========================
# 내 정보 (아바타용) ✅ 추가
# =========================
DEFAULT_AVATAR = "/static/pictures/defaultprofile.jpeg"

@router.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    """
    내 프로필 조회
    - 프로필 이미지가 없으면 기본 이미지로 대체
    - 프론트는 'profile_image_url'만 사용
    """
    img = getattr(current_user, "profile_image", None) or DEFAULT_AVATAR
    return {
        "id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "email": current_user.email,
        "profile_image_url": img,
        "is_active": current_user.is_active,
        "provider": getattr(current_user, 'provider', None) or None,
        "provider_linked": bool(getattr(current_user, 'provider', None) and getattr(current_user, 'provider_id', None)),
    }

# ------------------------
# 온보딩 필요 여부 (소셜 로그인 후 보조 수집)
# ------------------------
@router.get("/me/needs-onboarding")
def needs_onboarding(current_user: User = Depends(get_current_user)):
    phone_missing = (getattr(current_user, 'phone_encrypted', None) is None)
    ident_missing = (getattr(current_user, 'identification_number', None) is None)
    return {
        "phone_missing": phone_missing,
        "ident_missing": ident_missing,
        "username": current_user.username,
        "name": current_user.name,
        "email": current_user.email,
    }

# ------------------------
# 소셜 온보딩: 현재 사용자 정보 보강
# ------------------------
@router.post("/me/onboarding")
def update_onboarding(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        # 이름(선택): 소셜 가입 온보딩 중 사용자 수정 허용
        nm = (payload.get('name') or '').strip()
        if nm:
            current_user.name = nm
        # 전화번호
        phone = (payload.get('phone') or '').strip()
        if phone:
            try:
                current_user.set_phone(phone)
            except Exception:
                pass
        # 주민등록번호(암호화)
        ident = payload.get('identification_number')
        if ident is not None:
            try:
                current_user.set_identification_number(ident)
            except Exception:
                from fastapi import HTTPException
                raise HTTPException(400, '주민등록번호 형식이 올바르지 않습니다')
        # 성별
        g = (payload.get('gender') or '').strip().lower()
        if g in ('male','female','other',''):
            current_user.gender = g or current_user.gender
        # 지역
        if 'region_living' in payload:
            current_user.region_living = (payload.get('region_living') or '').strip()
        if 'region_active' in payload:
            current_user.region_active = (payload.get('region_active') or '').strip()
        # 프로필 이미지
        if (payload.get('profile_image') or '').strip():
            current_user.profile_image = (payload.get('profile_image') or '').strip()
        # 소개
        if 'introduction' in payload:
            current_user.introduction = (payload.get('introduction') or '').strip()
        # 소셜 가입자는 이메일 인증 없이 사용 가능
        current_user.is_active = True
        current_user.email_verified = True

        db.commit(); db.refresh(current_user)
        return {
            "message": "온보딩 정보가 저장되었습니다.",
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "name": current_user.name,
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"온보딩 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="온보딩 저장에 실패했습니다")

# ------------------------
# 소셜 계정 → 기존 계정으로 연동
# ------------------------
@router.post("/me/link-existing")
def link_existing_account(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    현재 로그인(소셜) 사용자를, 입력한 기존 계정으로 연동합니다.
    Body: { login: username or email, password }
    처리:
      - login/password 검증으로 대상 계정 찾기
      - 대상 계정에 provider/provider_id가 비어있으면 현재 사용자의 provider 정보를 이전
      - 현재 소셜 전용 임시 계정은 삭제
      - 대상 계정 기준으로 새 토큰 반환
    """
    login = (payload.get("login") or "").strip().lower()
    password = payload.get("password") or ""
    if not login or not password:
        raise HTTPException(status_code=400, detail="login과 password가 필요합니다")

    # 현재 계정이 소셜 식별자를 갖고 있어야 함
    if not (current_user.provider and current_user.provider_id):
        raise HTTPException(status_code=400, detail="현재 계정은 소셜 로그인 계정이 아닙니다")

    # 대상 계정 찾기 (username 또는 email)
    target = (
        db.query(User)
        .filter((User.username == login) | (User.email == login))
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="대상 계정을 찾을 수 없습니다")
    if not target.verify_password(password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")

    # 이미 같은 사용자면 바로 토큰 재발급
    if target.id == current_user.id:
        claims = {"sub": target.username, "user_id": target.id, "tv": (target.token_version or 0)}
        return {
            "access_token": create_access_token(data=claims),
            "refresh_token": create_refresh_token(data=claims),
            "token_type": "bearer",
            "message": "이미 동일 계정입니다"
        }

    # 대상 계정에 이미 다른 소셜이 연결돼 있다면 보호
    if target.provider and target.provider_id and (
        (target.provider != current_user.provider) or (target.provider_id != current_user.provider_id)
    ):
        raise HTTPException(status_code=409, detail="대상 계정에는 이미 다른 소셜이 연결되어 있습니다")

    # 소셜 식별자를 대상 사용자로 이전
    target.provider = current_user.provider
    target.provider_id = current_user.provider_id
    target.is_active = True
    target.email_verified = True

    # 현재(임시) 사용자는 삭제
    try:
        tmp_id = current_user.id
        db.delete(current_user)
        db.commit()
        logger.info(f"계정 연동: tmp_user_id={tmp_id} -> user_id={target.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"계정 연동 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="계정 연동에 실패했습니다")

    # 대상 기준 새 토큰 발급
    target.token_version = (target.token_version or 0) + 1
    db.commit(); db.refresh(target)
    claims = {"sub": target.username, "user_id": target.id, "tv": (target.token_version or 0)}
    return {
        "access_token": create_access_token(data=claims),
        "refresh_token": create_refresh_token(data=claims),
        "token_type": "bearer",
        "message": "계정 연동 완료"
    }

# ------------------------
# 내 전화번호 마스킹 조회
# ------------------------
@router.get("/me/phone-masked")
def get_phone_masked(current_user: User = Depends(get_current_user)):
    def _mask_phone_str(raw: str | None) -> str | None:
        if not raw:
            return None
        digits = normalize_phone(raw)
        if not digits or len(digits) < 7:
            return None
        if len(digits) == 11 and digits.startswith('010'):
            return f"010-****-**{digits[-2:]}"
        head = digits[:3]
        tail2 = digits[-2:]
        return f"{head}-****-**{tail2}"

    try:
        decrypted = current_user.get_phone()
    except Exception:
        decrypted = None
    masked = _mask_phone_str(decrypted)
    if not masked:
        masked = _mask_phone_str(current_user.phone)
    return {"phone_masked": masked}

# ------------------------
# 내 비밀번호 확인 (게이트)
# ------------------------
@router.post("/me/verify-password")
def verify_password_gate(payload: dict = Body(...), current_user: User = Depends(get_current_user)):
    pw = payload.get('password') or ''
    if not current_user.verify_password(pw):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
    return {"ok": True}

# ------------------------
# 사용자명 변경 (토큰 재발급)
# ------------------------
@router.patch("/me/username")
def update_username(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    username = (payload.get('username') or '').strip().lower()
    if not username:
        raise HTTPException(400, "username이 필요합니다")
    if db.query(User.id).filter(User.username == username, User.id != current_user.id).first():
        raise HTTPException(409, "이미 사용 중인 아이디입니다")
    current_user.username = username
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit(); db.refresh(current_user)
    claims = {"sub": current_user.username, "user_id": current_user.id, "tv": current_user.token_version}
    return {
        "access_token": create_access_token(data=claims),
        "refresh_token": create_refresh_token(data=claims),
        "token_type": "bearer",
    }

# ------------------------
# 전화번호 변경
# ------------------------
@router.patch("/me/phone")
def update_phone(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw = (payload.get('phone') or '').strip()
    norm = normalize_phone(raw)
    if not (norm and len(norm) == 11 and norm.startswith('010')):
        raise HTTPException(400, "전화번호 형식이 올바르지 않습니다")
    # 중복 체크(plain 저장 컬럼)
    formatted = f"010-{norm[3:7]}-{norm[7:]}"
    if db.query(User.id).filter(User.phone == formatted, User.id != current_user.id).first():
        raise HTTPException(409, "이미 사용 중인 전화번호입니다")
    current_user.set_phone(norm)
    db.commit(); db.refresh(current_user)
    return {"message": "전화번호가 변경되었습니다"}

# ------------------------
# 비밀번호 변경
# ------------------------
@router.post("/me/change-password")
def change_password(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_password = payload.get('new_password') or ''
    if not validate_password_strength(new_password):
        raise HTTPException(400, "비밀번호가 요구사항을 충족하지 않습니다")
    # 새 비밀번호가 기존 비밀번호와 동일한 경우 차단
    if current_user.verify_password(new_password):
        raise HTTPException(400, "새 비밀번호가 현재 비밀번호와 같습니다")
    current_user.set_password(new_password)
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit(); db.refresh(current_user)
    claims = {"sub": current_user.username, "user_id": current_user.id, "tv": current_user.token_version}
    return {
        "access_token": create_access_token(data=claims),
        "refresh_token": create_refresh_token(data=claims),
        "token_type": "bearer",
        "message": "비밀번호가 변경되었습니다"
    }

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
