# app/core/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token   # ✅ payload 디코더 (함수 호출용)
from app.models.user import User

# =========================================
# ### [추가부분] OAuth2 스킴: 클라이언트가 보내는 Bearer 토큰을 문자열로 뽑아줌
#   - tokenUrl은 네 로그인 엔드포인트로 맞춰라.
#     예) "/api/v1/auth/login" 또는 "/auth/login"
# =========================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")  # ← 너네 라우트에 맞춰 수정

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),   # ✅ [수정] 여기서 '문자열' 토큰을 받는다
) -> User:
    # ✅ [수정] 문자열 토큰을 디코드해 payload(dict) 획득
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다",
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )
    return user
