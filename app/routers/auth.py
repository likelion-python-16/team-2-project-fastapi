# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from datetime import timedelta

from app.schemas.auth import SignUpIn, LoginIn, TokenOut, RefreshTokenIn
from app.models.user import User
from app.core.database import get_db  # 기존 정의된 것 사용
from app.security import (
    create_access_token, 
    create_refresh_token,
    validate_password_strength, 
    get_password_requirements
)
from app.utils.logging import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpIn, db: Session = Depends(get_db)):
    """사용자 회원가입"""
    
    # 비밀번호 강도 검증
    if not validate_password_strength(payload.password):
        requirements = get_password_requirements()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "비밀번호가 요구사항을 충족하지 않습니다",
                "requirements": requirements
            }
        )
    
    # 중복 체크 (낙관적 처리)
    existing_user = db.query(User).filter(
        or_(User.username == payload.username, User.email == payload.email)
    ).first()
    
    if existing_user:
        # 보안상 구체적인 정보 제공하지 않음
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 사용자명 또는 이메일입니다"
        )
    
    # 사용자 생성
    try:
        user = User(
            username=payload.username,
            email=payload.email,
            name=payload.name or payload.username,
            is_active=True,
        )
        user.set_password(payload.password)
        
        # 식별번호가 있다면 암호화하여 저장
        if hasattr(payload, 'identification_number') and payload.identification_number:
            user.set_identification_number(payload.identification_number)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 로그 기록 (개인정보 제외)
        logger.info(f"회원가입 성공: user_id={user.id}, username={user.username}")
        
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"회원가입 DB 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 사용자명 또는 이메일입니다"
        )
    except ValueError as e:
        db.rollback()
        logger.error(f"회원가입 검증 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"회원가입 예상치 못한 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 오류가 발생했습니다"
        )
    
    # JWT 토큰 생성
    try:
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        return TokenOut(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except Exception as e:
        logger.error(f"토큰 생성 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 생성에 실패했습니다"
        )

@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """사용자 로그인"""
    
    # 사용자 조회 (username 또는 email로)
    user = db.query(User).filter(
        or_(User.username == payload.login, User.email == payload.login)
    ).first()
    
    # 사용자 존재 여부 및 비밀번호 검증
    if not user or not user.verify_password(payload.password):
        # 로그인 실패 로그 (보안상 구체적 정보 제외)
        logger.warning(f"로그인 실패 시도: login={payload.login}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다"
        )
    
    # 계정 활성화 상태 확인
    if not user.is_active:
        logger.warning(f"비활성화된 계정 로그인 시도: user_id={user.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비활성화된 계정입니다"
        )
    
    # JWT 토큰 생성
    try:
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        # 로그인 성공 로그
        logger.info(f"로그인 성공: user_id={user.id}, username={user.username}")
        
        return TokenOut(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except Exception as e:
        logger.error(f"로그인 토큰 생성 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 생성에 실패했습니다"
        )

@router.post("/refresh", response_model=TokenOut)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """리프레시 토큰으로 새 액세스 토큰 발급"""
    from app.security import verify_refresh_token
    
    # 리프레시 토큰 검증
    payload = verify_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 리프레시 토큰입니다"
        )
    
    # 사용자 존재 확인
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다"
        )
    
    # 새 토큰 발급
    try:
        new_access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        new_refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        return TokenOut(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer")
    
    except Exception as e:
        logger.error(f"토큰 갱신 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 갱신에 실패했습니다"
        )

@router.post("/logout")
def logout():
    """로그아웃 (클라이언트에서 토큰 삭제)"""
    # JWT는 stateless이므로 서버에서 할 일이 없음
    # 실제로는 블랙리스트 관리나 Redis 사용 가능
    return {"message": "로그아웃되었습니다"}