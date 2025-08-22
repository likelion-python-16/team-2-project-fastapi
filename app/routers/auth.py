# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import SignUpIn, LoginIn, TokenOut, RefreshTokenIn
from app.security import (
    create_access_token,
    create_refresh_token,
    validate_password_strength,
    get_password_requirements,
    normalize_phone,
    id_fingerprint,
)

# --- 토큰으로 현재 유저 불러오기(로그아웃에 사용) ---
from app.dependencies.auth import get_current_user

# --- 로거 ---
from app.utils.logging import logger

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ✅ 사전 중복 체크용 (가입과 분리된 GET)
@router.get("/check-duplicates")
def check_duplicates(
    db: Session = Depends(get_db),
    username: str | None = Query(default=None),
    email: str | None = Query(default=None),
    phone: str | None = Query(default=None),
):
    taken = {"username": False, "email": False, "phone": False}

    if username:
        taken["username"] = db.query(User.id).filter(User.username == username.lower()).first() is not None

    if email:
        taken["email"] = db.query(User.id).filter(User.email == email).first() is not None

    if phone:
        # phone 은 정규화 + fingerprint 로 조회 (레거시 평문 컬럼 보조)
        try:
            norm = normalize_phone(phone)  # "070-1234-5678" -> "07012345678" 등, 프로젝트 구현 재사용
        except Exception:
            norm = None
        if norm:
            fp = id_fingerprint(norm)
            taken["phone"] = (
                db.query(User.id).filter(User.phone_fingerprint == fp).first() is not None
                or db.query(User.id).filter(User.phone == norm).first() is not None  # 레거시 호환
            )

    return {"taken": taken}


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpIn, db: Session = Depends(get_db)):
    """사용자 회원가입"""

    # 1) 비밀번호 강도 검증
    if not validate_password_strength(payload.password):
        requirements = get_password_requirements()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "비밀번호가 요구사항을 충족하지 않습니다", "requirements": requirements},
        )

    # 2) 입력 정규화
    username = payload.username.lower()
    email = str(payload.email)

    phone_norm = normalize_phone(getattr(payload, "phone", None))
    phone_fp = id_fingerprint(phone_norm) if phone_norm else None

    id_fp = id_fingerprint(getattr(payload, "identification_number", None)) if getattr(payload, "identification_number", None) else None

    # 3) 중복 검사 (레이스 컨디션 대비, IntegrityError도 아래서 잡음)
    if db.query(User).filter(or_(User.username == username, User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용 중인 사용자명 또는 이메일입니다")

    if phone_norm and (
        db.query(User).filter(User.phone_fingerprint == phone_fp).first()
        or db.query(User).filter(User.phone == phone_norm).first()
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 등록된 전화번호입니다")

    if id_fp and db.query(User).filter(User.identification_fingerprint == id_fp).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 등록된 식별번호입니다")

    # 4) 생성 & 저장
    try:
        user = User(
            username=username,
            email=email,
            name=(payload.name or username),
            phone=None,                      # 레거시 평문은 저장 안 함
            identification_number=None,      # 암호문은 set_identification_number 로
            identification_fingerprint=id_fp,
            gender=(payload.gender or "other"),
            region_living=(payload.region_living or ""),
            region_active=(payload.region_active or ""),
            profile_image=(payload.profile_image or ""),
            introduction=(payload.introduction or ""),  # TEXT NOT NULL → ''
        )
        user.set_password(payload.password)

        if getattr(payload, "identification_number", None):
            user.set_identification_number(payload.identification_number)

        # 전화번호(암호화 + fingerprint)
        user.set_phone(payload.phone)

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"회원가입 성공: user_id={user.id}, username={user.username}")

    except IntegrityError as e:
        db.rollback()
        logger.warning(f"회원가입 DB 무결성 오류: {str(e)}")
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용 중인 사용자명/이메일/전화번호/식별번호가 있습니다")
    except ValueError as e:
        db.rollback()
        logger.error(f"회원가입 검증 오류: {str(e)}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"회원가입 예상치 못한 오류: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "서버 오류가 발생했습니다")

    # 5) JWT 토큰 생성
    try:
        claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)
        return TokenOut(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    except Exception as e:
        logger.error(f"토큰 생성 오류: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "토큰 생성에 실패했습니다")


# ---------------------------
# 로그인
# ---------------------------
@router.post("/login", response_model=TokenOut, summary="로그인: JWT 발급")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """사용자 로그인 (성공 시 token_version 증가 → 기존 토큰 무효화)"""

    user = db.query(User).filter(
        or_(User.username == payload.login, User.email == payload.login)
    ).first()

    if not user or not user.verify_password(payload.password):
        logger.warning(f"로그인 실패 시도: login={payload.login}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다")

    if not user.is_active:
        logger.warning(f"비활성화된 계정 로그인 시도: user_id={user.id}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "비활성화된 계정입니다")

    try:
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        db.refresh(user)

        claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)

        logger.info(f"로그인 성공: user_id={user.id}, username={user.username}, tv={user.token_version}")
        return TokenOut(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    except Exception as e:
        db.rollback()
        logger.error(f"로그인 처리/토큰 생성 오류: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "토큰 생성에 실패했습니다")


@router.post("/refresh", response_model=TokenOut)
def refresh_token(payload: RefreshTokenIn, db: Session = Depends(get_db)):
    """리프레시 토큰으로 새 액세스 토큰 발급 (token_version 검증 포함)"""
    from app.security import verify_refresh_token

    data = verify_refresh_token(payload.refresh_token)
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 리프레시 토큰입니다")

    username = data.get("sub")
    tv_in_token = data.get("tv")
    if not username or tv_in_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 리프레시 토큰입니다")

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없습니다")

    if (user.token_version or 0) != int(tv_in_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "만료된 리프레시 토큰입니다")

    claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version}
    new_access = create_access_token(data=claims)
    new_refresh = create_refresh_token(data=claims)
    return TokenOut(access_token=new_access, refresh_token=new_refresh, token_type="bearer")


@router.post("/logout")
def logout():
    """클라이언트에서 access/refresh 토큰을 폐기하세요."""
    return {"message": "로그아웃되었습니다"}
