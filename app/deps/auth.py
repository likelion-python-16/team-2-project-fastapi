# app/deps/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.security import verify_access_token

# 문서용 경로도 실제 로그인 엔드포인트로 맞춰주기
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # refresh 토큰이면 막기 (payload에 typ 들어오면 체크)
    typ = payload.get("typ")
    if typ and typ != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    # 우선순위: user_id → sub
    ident = payload.get("user_id") or payload.get("sub")
    if ident is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token payload missing subject")

    # 🔑 숫자면 id로, 아니면 username으로 조회
    user = None
    try:
        user_id = int(ident)
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    except (TypeError, ValueError):
        user = db.query(User).filter(User.username == str(ident), User.is_active.is_(True)).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user
