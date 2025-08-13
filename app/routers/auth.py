from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.schemas.auth import SignUpIn, LoginIn, TokenOut
from app.models.user import User
from app.core.database import SessionLocal
from app.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpIn, db: Session = Depends(get_db)):
    # 중복 체크(낙관적 처리 + 예외 보강)
    if db.query(User).filter(or_(User.username == payload.username,
                                 User.email == payload.email)).first():
        raise HTTPException(status_code=400, detail="username or email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        name=payload.name or payload.username,
        is_active=True,
    )
    user.set_password(payload.password)  # ← 해시 저장 (password_hash 컬럼)

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="username or email already exists")
    db.refresh(user)

    token = create_access_token({"sub": user.username})
    return TokenOut(access_token=token)

@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(or_(User.username == payload.login,
                                     User.email == payload.login)).first()
    if not user or not user.verify_password(payload.password):  # ← 해시 검증
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})
    return TokenOut(access_token=token)
