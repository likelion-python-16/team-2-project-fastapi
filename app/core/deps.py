from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.security import verify_token


def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional["User"]:
    """Parses JWT from HttpOnly cookie 'access_token' and returns the user if valid.

    Returns None if missing/invalid without raising, so callers can choose behavior.
    """
    from app.models.user import User  # local import to avoid circular

    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None

    sub = payload.get("sub")
    user: Optional[User] = None
    try:
        user_id = int(sub)
        user = db.query(User).filter(User.id == user_id).first()
    except Exception:
        # fallback by username/email if non-int sub
        if sub and hasattr(User, "username"):
            user = db.query(User).filter(User.username == str(sub)).first()
        elif sub and hasattr(User, "email"):
            user = db.query(User).filter(User.email == str(sub)).first()

    return user


def require_admin(request: Request, user = Depends(get_current_user_from_cookie)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    token = request.cookies.get("access_token")
    payload = verify_token(token) if token else None
    admin_mode = bool(payload.get("admin_mode")) if payload else False
    if not getattr(user, "is_admin", False) or not admin_mode:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")
    return user


def require_master_admin(user = Depends(require_admin)):
    # is_superadmin 필드가 있으면 우선 체크
    if hasattr(user, 'is_superadmin') and getattr(user, 'is_superadmin', False):
        return user
    
    # 기존 설정 기반 체크 (호환성)
    from app.core.config import settings
    master_ok = False
    if settings.admin_master_username:
        master_ok = (user.username == settings.admin_master_username)
    if not master_ok and settings.admin_master_email:
        try:
            master_ok = (user.email == settings.admin_master_email)
        except Exception:
            master_ok = False
    if not master_ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="슈퍼관리자 권한이 필요합니다")
    return user
