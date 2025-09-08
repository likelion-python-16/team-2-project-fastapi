# app/routers/auth_social_new.py - Enhanced version from chriskang branch
from __future__ import annotations
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
# OAuth 관련 import는 실제 사용될 때 추가 필요
import secrets

# from app.core.config import settings  # unused in current implementation
from app.core.database import get_db
from app.models.user import User
from app.security import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["Social Authentication"])

# _front_base 함수는 현재 사용되지 않음

# OAuth 설정은 실제 구현시 추가 필요


@router.get('/identity/last')
async def last_social_identity(request: Request):
    """마지막 소셜 로그인 정보 반환"""
    data = request.session.get('pending_social') or request.session.get('last_social_identity') or {}
    return data


@router.post('/social/finalize')
async def social_finalize(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    """소셜 로그인 3단계 완료 후 사용자 생성"""
    ident = request.session.get('pending_social') or request.session.get('last_social_identity')
    if not ident:
        raise HTTPException(400, 'No pending social identity')
    
    provider = ident.get('provider')
    provider_id = ident.get('sub')
    email = (ident.get('email') or '').lower()
    
    # 필수 데이터 검증
    required_fields = ['name', 'username', 'phone', 'identification_number']
    for field in required_fields:
        if not payload.get(field):
            raise HTTPException(400, f'{field} is required')
    
    # 중복 검사
    existing_user = db.query(User).filter(User.username == payload['username'].lower()).first()
    if existing_user:
        raise HTTPException(400, '이미 사용중인 사용자명입니다')
    
    # 새 사용자 생성
    user = User(
        username=payload['username'].lower(),
        email=email or f"{payload['username']}@example.com",
        name=payload['name'],
        provider=provider,
        provider_id=provider_id,
        email_verified=True,
        is_active=True,
        gender=payload.get('gender') or 'other',
        region_living=payload.get('region_living') or '',
        region_active=payload.get('region_active') or '',
        profile_image=payload.get('profile_image') or ident.get('picture') or '/static/pictures/defaultprofile.svg',
        introduction=payload.get('introduction') or '',
    )
    
    # 비밀번호 설정 (소셜 로그인이므로 랜덤)
    user.set_password(secrets.token_urlsafe(12))
    
    # 전화번호 설정
    try:
        user.set_phone(payload['phone'])
    except Exception as e:
        raise HTTPException(400, f'전화번호 형식이 올바르지 않습니다: {str(e)}')
    
    # 주민번호 설정
    try:
        user.set_identification_number(payload['identification_number'])
    except Exception as e:
        raise HTTPException(400, f'주민등록번호 형식이 올바르지 않습니다: {str(e)}')
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 세션 정리
    try:
        request.session.pop('pending_social', None)
        request.session.pop('last_social_identity', None)
    except Exception:
        pass
    
    # JWT 토큰 생성
    claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version or 0}
    access_token = create_access_token(data=claims)
    refresh_token = create_refresh_token(data=claims)
    
    return JSONResponse({
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer",
        "user_id": user.id
    })
