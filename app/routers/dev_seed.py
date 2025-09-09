from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.following import Following

router = APIRouter(prefix="/api/v1/dev", tags=["Dev Utilities"])


class SeedRequest(BaseModel):
    primary_username: str | None = None  # 팔로워를 받는 사용자 (A)
    follower_username: str | None = None  # A를 팔로우할 사용자 (B)
    password: str | None = None  # 둘 다 동일한 패스워드 적용 (기본: SecurePass1!)


def _ensure_user(db: Session, username: str, password: str, email: str | None = None) -> User:
    u = db.query(User).filter(User.username == username).first()
    if u:
        return u
    u = User(
        username=username,
        email=email or f"{username}@example.com",
        name=username,
        is_active=True,
    )
    u.set_password(password)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.post("/seed/follow-demo")
def seed_follow_demo(payload: SeedRequest | None = None, db: Session = Depends(get_db)):
    """
    개발/로컬 환경에서 테스트용 계정 2개를 만들고(B가 A를 팔로우) 관계를 생성합니다.
    - 기본 계정: A=test_user_a, B=test_user_b, 비밀번호=SecurePass1!
    - settings.debug 가 False 인 경우 비활성화됩니다.
    응답으로 두 계정의 id/username, 설정된 비밀번호, 팔로우 생성 여부를 반환합니다.
    """
    if not settings.debug:
        raise HTTPException(status_code=403, detail="This endpoint is disabled in non-debug environments")

    req = payload or SeedRequest()
    password = req.password or "SecurePass1!"
    a_username = req.primary_username or "test_user_a"
    b_username = req.follower_username or "test_user_b"

    a = _ensure_user(db, a_username, password)
    b = _ensure_user(db, b_username, password)

    # B -> A 를 팔로우 (중복이면 무시)
    rel = db.query(Following).filter(
        Following.follower_id == b.id,
        Following.following_id == a.id,
    ).first()
    created = False
    if not rel:
        rel = Following(follower_id=b.id, following_id=a.id)
        db.add(rel)
        db.commit()
        created = True

    return {
        "primary": {"id": a.id, "username": a.username},
        "follower": {"id": b.id, "username": b.username},
        "password": password,
        "follow_created": created,
    }

