
# app/deps/roles.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..deps.auth import get_current_user
from ..models.user import User

def require_admin(
    me: User = Depends(get_current_user),
) -> User:
    if not getattr(me, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return me
