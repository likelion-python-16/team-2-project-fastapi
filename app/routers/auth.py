# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

# --- 모델/스키마 ---
from app.models.user import User
from app.models.tag import Tag, UserTag  # 회원가입에서 사용 (지금은 손대지 않음)
from app.schemas.auth import SignUpIn, LoginIn, TokenOut, RefreshTokenIn

# --- DB 세션 ---
try:
    from app.db.session import get_db   # 네 프로젝트 표준이 이거면 사용
except ImportError:
    from app.core.database import get_db  # 네가 원래 쓰던 경로면 이걸로

# --- 보안 유틸: 우리 security.py 시그니처에 맞춤 ---
from app.core.security import (
    verify_password,        # (pw, hashed) -> bool
    hash_password,          # 회원가입에서 필요 시 사용
    create_access_token,    # (sub=str(user.id), tv=user.token_version)
    create_refresh_token,   # (sub=str(user.id), tv=user.token_version)
    decode_token,           # decode + 검증, 실패 시 ValueError
)

# --- 토큰으로 현재 유저 불러오기(로그아웃에 사용) ---
from app.dependencies.auth import get_current_user

# --- 로거 ---
from app.utils.logging import logger

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------
# 로그인
# ---------------------------
@router.post("/login", response_model=TokenOut, summary="로그인: JWT 발급")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    # 스키마 호환: username_or_email 또는 login 둘 다 지원
    ident = (getattr(payload, "username_or_email", None) or getattr(payload, "login", "")).strip().lower()
    if not ident:
        raise HTTPException(status_code=400, detail="아이디/이메일을 입력하세요")

    user = (
        db.query(User)
        .filter(or_(User.username == ident, User.email == ident))
        .first()
    )

    # 비밀번호 확인: 모델 메서드가 있으면 우선, 없으면 보안유틸로
    ok = False
    if user:
        if hasattr(user, "verify_password"):
            ok = user.verify_password(payload.password)
        else:
            hashed = getattr(user, "hashed_password", None) or getattr(user, "password_hash", None)
            ok = hashed and verify_password(payload.password, hashed)

    if not user or not ok:
        logger.warning(f"로그인 실패 시도: ident={ident}")
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    if not user.is_active:
        logger.warning(f"비활성화 계정 로그인 시도: user_id={user.id}")
        raise HTTPException(status_code=401, detail="비활성화된 계정입니다")

    # tv(token_version) 포함해 발급 → 로그아웃/비번변경 시 구토큰 무효
    tv = (user.token_version or 0)
    access_token = create_access_token(sub=str(user.id), tv=tv)
    refresh_token = create_refresh_token(sub=str(user.id), tv=tv)

    logger.info(f"로그인 성공: user_id={user.id}, username={user.username}")
    return TokenOut(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


# ---------------------------
# 리프레시
# ---------------------------
@router.post("/refresh", response_model=TokenOut, summary="리프레시 토큰으로 재발급")
def refresh_token_endpoint(body: RefreshTokenIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="토큰 타입이 올바르지 않습니다")

    user_id = payload.get("sub")
    tv = payload.get("tv")
    if not user_id or tv is None:
        raise HTTPException(status_code=401, detail="토큰 정보가 손상되었습니다")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    if (user.token_version or 0) != tv:
        raise HTTPException(status_code=401, detail="토큰 버전이 만료되었습니다(재로그인 필요)")

    new_access = create_access_token(sub=str(user.id), tv=(user.token_version or 0))
    new_refresh = create_refresh_token(sub=str(user.id), tv=(user.token_version or 0))
    return TokenOut(access_token=new_access, refresh_token=new_refresh, token_type="bearer")


# ---------------------------
# 로그아웃 (서버 측 무효화: tv++)
# ---------------------------
@router.post("/logout", status_code=204, summary="로그아웃: 기존 토큰 전부 무효화")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.token_version = (current_user.token_version or 0) + 1
    db.add(current_user)
    db.commit()
    return None

@router.get("/whoami")
def whoami(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": getattr(current_user, "email", None),
        "is_active": getattr(current_user, "is_active", None),
        "token_version": getattr(current_user, "token_version", None),
    }