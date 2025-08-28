# app/dependencies/auth.py (또는 기존 파일 경로 유지)
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.security import decode_token
from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _find_user_by_identifier(db: Session, ident: Optional[str | int]) -> Optional[User]:
    """ident가 숫자면 id로, 아니면 username/email로 조회"""
    if ident is None:
        return None

    # 1) 숫자처럼 보이면 id 우선
    try:
        uid = int(str(ident))
        user = db.query(User).filter(User.id == uid).first()
        if user:
            return user
    except (TypeError, ValueError):
        pass

    # 2) 문자열이면 username/email 매칭
    s = str(ident)
    return (
        db.query(User)
        .filter(or_(User.username == s, User.email == s))
        .first()
    )


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    # 토큰 디코드
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # 액세스 토큰만 허용
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    # 토큰 버전(tv)는 필수
    tv = payload.get("tv")
    if tv is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    # user 식별값: user_id/uid 우선, 폴백으로 sub
    raw_ident = payload.get("user_id") or payload.get("uid") or payload.get("sub")
    user = _find_user_by_identifier(db, raw_ident)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    # 토큰 버전 확인(정수 캐스팅 안전 처리)
    try:
        token_version = int(tv)
    except (TypeError, ValueError):
        token_version = tv  # 문자열이어도 비교 시 불일치로 처리됨

    if (user.token_version or 0) != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired by logout/password change")

    return user
