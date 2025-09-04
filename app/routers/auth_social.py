# app/routers/auth_social.py
from __future__ import annotations
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config as StarConfig
import secrets

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.security import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["Social Authentication"])

def _front_base(request: Request) -> str:
    """프론트엔드 기본 URL 추출"""
    base = (settings.front_base_url or '').strip().rstrip('/')
    if base:
        return base
    # X-Forwarded-* 헤더 확인
    xf_proto = request.headers.get('x-forwarded-proto')
    xf_host = request.headers.get('x-forwarded-host')
    if xf_proto and xf_host:
        return f"{xf_proto}://{xf_host}"
    return str(request.base_url).rstrip('/')

# OAuth 설정
star_cfg = StarConfig(environ={})
oauth = OAuth(star_cfg)

# Google OpenID Connect 설정
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        client_kwargs={'scope': 'openid email profile'},
    )

# Naver OAuth2 설정
if settings.naver_client_id and settings.naver_client_secret:
    oauth.register(
        name='naver',
        api_base_url='https://openapi.naver.com',
        authorize_url='https://nid.naver.com/oauth2.0/authorize',
        access_token_url='https://nid.naver.com/oauth2.0/token',
        client_id=settings.naver_client_id,
        client_secret=settings.naver_client_secret,
        client_kwargs={'scope': 'profile email'},
    )


@router.get('/login/google')
async def login_google(request: Request):
    """Google 로그인 시작"""
    if not hasattr(oauth, 'google'):
        raise HTTPException(503, 'Google 로그인이 설정되지 않았습니다')
    
    # 콜백 URL 생성
    redirect_uri = str(request.url_for('callback_google'))
    
    # 세션 정리
    try:
        request.session.pop('pending_social', None)
        request.session.pop('merge_candidate_user_id', None)
    except Exception:
        pass
    
    # nonce 생성 (ID 토큰용)
    nonce = secrets.token_urlsafe(16)
    request.session['nonce'] = nonce
    
    # Google 인증 페이지로 리디렉트
    return await oauth.google.authorize_redirect(
        request, redirect_uri, nonce=nonce, prompt='consent'
    )


@router.get('/callback/google')
async def callback_google(request: Request, db: Session = Depends(get_db)):
    """Google 로그인 콜백 처리"""
    if not hasattr(oauth, 'google'):
        raise HTTPException(503, 'Google 로그인이 설정되지 않았습니다')
    
    try:
        # 액세스 토큰 받기
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        # 상태 불일치 시 재시도
        msg = str(e).lower()
        if 'mismatch' in msg and 'state' in msg:
            return RedirectResponse(str(request.url_for('login_google')), status_code=303)
        raise
    
    nonce = request.session.pop('nonce', None)
    
    # ID 토큰에서 사용자 정보 파싱
    userinfo = await oauth.google.parse_id_token(token, nonce=nonce)
    
    # 추가 사용자 정보 가져오기
    try:
        resp = await oauth.google.get('userinfo', token=token)
        if resp and resp.is_success:
            additional_info = resp.json()
            userinfo.update(additional_info)
    except Exception:
        pass
    
    google_id = userinfo.get('sub')
    email = userinfo.get('email', '').lower()
    name = userinfo.get('name', '')
    picture = userinfo.get('picture', '')
    
    if not google_id or not email:
        raise HTTPException(400, 'Google에서 필요한 정보를 받지 못했습니다')
    
    # 기존 Google 연동 계정 확인 (provider_id 기반)
    existing_user = db.query(User).filter(
        User.provider == 'google',
        User.provider_id == google_id
    ).first()
    
    if existing_user:
        # 기존 연동 계정으로 로그인
        existing_user.token_version = (existing_user.token_version or 0) + 1
        db.commit()
        
        claims = {"sub": existing_user.username, "user_id": existing_user.id, "tv": existing_user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)
        
        # 프론트엔드로 토큰과 함께 리디렉트
        frontend_url = f"{_front_base(request)}/login?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=frontend_url, status_code=303)
    
    # 동일 이메일의 기존 계정 확인 (일반 가입 또는 provider_id가 없는 Google 사용자)
    existing_email_user = db.query(User).filter(User.email == email).first()
    
    if existing_email_user:
        # 기존 계정이 있는 경우 Google 정보 업데이트하고 로그인
        existing_email_user.provider = 'google'
        existing_email_user.provider_id = google_id
        if picture:
            existing_email_user.profile_image = picture
        
        existing_email_user.token_version = (existing_email_user.token_version or 0) + 1
        db.commit()
        
        claims = {"sub": existing_email_user.username, "user_id": existing_email_user.id, "tv": existing_email_user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)
        
        frontend_url = f"{_front_base(request)}/login?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=frontend_url, status_code=303)
    
    # 새 계정 생성 필요 - 소셜 회원가입 페이지로 이동
    request.session['pending_social'] = {
        'provider': 'google',
        'provider_id': google_id,
        'email': email,
        'name': name,
        'picture': picture
    }
    
    frontend_url = f"{_front_base(request)}/social/onboarding"
    return RedirectResponse(url=frontend_url, status_code=303)


@router.get('/login/naver')  
async def login_naver(request: Request):
    """네이버 로그인 시작"""
    if not hasattr(oauth, 'naver'):
        raise HTTPException(503, '네이버 로그인이 설정되지 않았습니다')
    
    redirect_uri = str(request.url_for('callback_naver'))
    
    # 세션 정리
    try:
        request.session.pop('pending_social', None)
        request.session.pop('merge_candidate_user_id', None)
    except Exception:
        pass
    
    # 네이버 인증 페이지로 리디렉트
    return await oauth.naver.authorize_redirect(request, redirect_uri)


@router.get('/callback/naver')
async def callback_naver(request: Request, db: Session = Depends(get_db)):
    """네이버 로그인 콜백 처리"""
    if not hasattr(oauth, 'naver'):
        raise HTTPException(503, '네이버 로그인이 설정되지 않았습니다')
    
    try:
        token = await oauth.naver.authorize_access_token(request)
    except Exception as e:
        msg = str(e).lower()
        if 'mismatch' in msg and 'state' in msg:
            return RedirectResponse(str(request.url_for('login_naver')), status_code=303)
        raise
    
    # 네이버 사용자 정보 가져오기
    resp = await oauth.naver.get('/v1/nid/me', token=token)
    if not resp or not resp.is_success:
        raise HTTPException(400, '네이버에서 사용자 정보를 받지 못했습니다')
    
    data = resp.json()
    userinfo = data.get('response', {})
    
    naver_id = userinfo.get('id')
    email = userinfo.get('email', '').lower()
    name = userinfo.get('name', '')
    profile_image = userinfo.get('profile_image', '')
    birth_year = userinfo.get('birthyear', '')
    
    if not naver_id or not email:
        raise HTTPException(400, '네이버에서 필요한 정보를 받지 못했습니다')
    
    # 기존 네이버 연동 계정 확인
    existing_user = db.query(User).filter(
        User.provider == 'naver',
        User.provider_id == naver_id
    ).first()
    
    if existing_user:
        # 기존 연동 계정으로 로그인
        existing_user.token_version = (existing_user.token_version or 0) + 1
        db.commit()
        
        claims = {"sub": existing_user.username, "user_id": existing_user.id, "tv": existing_user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)
        
        frontend_url = f"{_front_base(request)}/login?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=frontend_url, status_code=303)
    
    # 동일 이메일의 기존 계정 확인
    existing_email_user = db.query(User).filter(User.email == email).first()
    
    if existing_email_user and not existing_email_user.provider:
        # 기존 일반 회원가입 계정에 네이버 연동
        existing_email_user.provider = 'naver'
        existing_email_user.provider_id = naver_id
        if profile_image:
            existing_email_user.profile_image = profile_image
        if birth_year:
            existing_email_user.birth_year = birth_year
            
        existing_email_user.token_version = (existing_email_user.token_version or 0) + 1
        db.commit()
        
        claims = {"sub": existing_email_user.username, "user_id": existing_email_user.id, "tv": existing_email_user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)
        
        frontend_url = f"{_front_base(request)}/login?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=frontend_url, status_code=303)
    
    # 새 계정 생성 필요
    request.session['pending_social'] = {
        'provider': 'naver',
        'provider_id': naver_id,
        'email': email,
        'name': name,
        'profile_image': profile_image,
        'birth_year': birth_year
    }
    
    frontend_url = f"{_front_base(request)}/social/onboarding"
    return RedirectResponse(url=frontend_url, status_code=303)


@router.get('/social/pending')
async def get_pending_social_info(request: Request):
    """임시 저장된 소셜 로그인 정보 조회"""
    pending = request.session.get('pending_social')
    if not pending:
        raise HTTPException(404, '대기 중인 소셜 로그인 정보가 없습니다')
    
    return {
        'provider': pending.get('provider'),
        'email': pending.get('email'),
        'name': pending.get('name'),
        'profile_image': pending.get('profile_image') or pending.get('picture'),
        'birth_year': pending.get('birth_year')
    }


@router.post('/social/complete-signup')
async def complete_social_signup(request: Request, payload: dict, db: Session = Depends(get_db)):
    """소셜 로그인 회원가입 완료"""
    pending = request.session.get('pending_social')
    if not pending:
        raise HTTPException(404, '대기 중인 소셜 로그인 정보가 없습니다')
    
    # 필수 정보 확인
    username = payload.get('username', '').strip().lower()
    phone = payload.get('phone', '').strip()
    identification_number = payload.get('identification_number', '').strip()
    region_living = payload.get('region_living', '').strip()
    region_active = payload.get('region_active', '').strip()
    
    if not all([username, phone, identification_number, region_living, region_active]):
        raise HTTPException(400, '필수 정보가 누락되었습니다')
    
    # 중복 체크
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, '이미 사용중인 사용자명입니다')
    
    # 새 사용자 생성
    from app.security import id_fingerprint, normalize_phone, encrypt_str
    
    # 전화번호 암호화 및 지문 생성
    phone_encrypted = encrypt_str(phone) if phone else None
    phone_fingerprint = id_fingerprint(phone) if phone else None
    
    # 주민번호 암호화 및 지문 생성  
    identification_encrypted = encrypt_str(identification_number) if identification_number else None
    identification_fingerprint = id_fingerprint(identification_number) if identification_number else None
    
    new_user = User(
        username=username,
        email=pending['email'],
        password_hash='',  # 소셜 로그인은 비밀번호 없음
        name=pending['name'],
        phone=normalize_phone(phone) if phone else None,
        phone_encrypted=phone_encrypted,
        phone_fingerprint=phone_fingerprint,
        identification_number=identification_encrypted,
        identification_fingerprint=identification_fingerprint,
        region_living=region_living,
        region_active=region_active,
        profile_image=pending.get('profile_image', pending.get('picture', '')),
        provider=pending['provider'],
        provider_id=pending['provider_id'],
        birth_year=pending.get('birth_year', ''),
        email_verified=True,  # 소셜 로그인은 이메일 인증 완료로 간주
        is_active=True,
        introduction='',  # 필수 필드이므로 빈 문자열
        gender='other'  # 기본값
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 태그 연결 처리
    selected_tags = payload.get('selected_tags', [])
    if selected_tags:
        from app.models.tag import Tag
        from app.models.tag import UserTag
        
        for tag_name in selected_tags:
            # 기존 태그 찾기 또는 생성
            tag = db.query(Tag).filter(Tag.tag == tag_name).first()
            if not tag:
                tag = Tag(tag=tag_name, is_active=True)
                db.add(tag)
                db.flush()
            
            # 사용자-태그 연결
            user_tag = UserTag(user_id=new_user.id, tag_id=tag.id)
            db.add(user_tag)
        
        db.commit()
    
    # 세션 정리
    request.session.pop('pending_social', None)
    
    # JWT 토큰 생성
    claims = {"sub": new_user.username, "user_id": new_user.id, "tv": new_user.token_version or 0}
    access_token = create_access_token(data=claims)
    refresh_token = create_refresh_token(data=claims)
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer',
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'name': new_user.name
        }
    }


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
    provider_id = ident.get('provider_id') or ident.get('sub')  # 둘 다 지원
    email = (ident.get('email') or '').lower()
    
    # 필수 데이터 검증
    required_fields = ['name', 'username', 'phone', 'identification_number']
    for field in required_fields:
        if not payload.get(field):
            raise HTTPException(400, f'{field} is required')
    
    # 기존 계정 감지 및 연동 제안
    from app.security import id_fingerprint, normalize_phone
    
    # 1. 사용자명 중복 검사
    existing_user = db.query(User).filter(User.username == payload['username'].lower()).first()
    if existing_user:
        raise HTTPException(400, '이미 사용중인 사용자명입니다')
    
    # 2. 기존 계정 찾기 (이메일, 전화번호, 주민번호로)
    merge_candidates = []
    
    # 이메일로 기존 계정 찾기
    if email:
        email_user = db.query(User).filter(User.email == email).first()
        if email_user and not email_user.provider:  # 일반 회원가입 계정
            merge_candidates.append(('email', email_user))
    
    # 전화번호로 기존 계정 찾기
    try:
        normalized_phone = normalize_phone(payload['phone'])
        if normalized_phone:
            phone_fp = id_fingerprint(normalized_phone)
            phone_user = db.query(User).filter(User.phone_fingerprint == phone_fp).first()
            if phone_user and not phone_user.provider and phone_user not in [u[1] for u in merge_candidates]:
                merge_candidates.append(('phone', phone_user))
    except Exception:
        pass
    
    # 주민번호로 기존 계정 찾기 (선택적)
    try:
        if payload.get('identification_number'):
            id_fp = id_fingerprint(payload['identification_number'])
            id_user = db.query(User).filter(User.identification_fingerprint == id_fp).first()
            if id_user and not id_user.provider and id_user not in [u[1] for u in merge_candidates]:
                merge_candidates.append(('identification', id_user))
    except Exception:
        pass
    
    # 기존 계정이 발견되면 연동 페이지로 안내
    if merge_candidates:
        # 세션에 연동 후보 저장
        candidate = merge_candidates[0][1]  # 첫 번째 후보 선택
        match_type = merge_candidates[0][0]
        
        try:
            request.session['merge_candidate'] = {
                'user_id': candidate.id,
                'username': candidate.username,
                'email': candidate.email,
                'name': candidate.name,
                'match_type': match_type,
                'social_data': {
                    'provider': provider,
                    'provider_id': provider_id,
                    'email': email,
                    'name': payload['name'],
                    'picture': ident.get('picture')
                }
            }
        except Exception:
            pass
        
        # 프론트엔드에 연동 제안 응답
        return {
            "action": "merge_required",
            "message": "기존 계정이 발견되었습니다. 계정을 연동하시겠습니까?",
            "match_type": match_type,
            "existing_user": {
                "username": candidate.username,
                "email": candidate.email,
                "name": candidate.name
            }
        }
    
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
        profile_image=payload.get('profile_image') or ident.get('picture') or '/static/pictures/defaultprofile.jpeg',
        introduction=payload.get('introduction') or '',
        birth_year=ident.get('birth_year', ''),
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
    
    # 태그 연결 처리
    selected_tags = payload.get('selected_tags', [])
    if selected_tags:
        from app.models.tag import Tag
        from app.models.tag import UserTag
        
        for tag_name in selected_tags:
            # 기존 태그 찾기 또는 생성
            tag = db.query(Tag).filter(Tag.tag == tag_name).first()
            if not tag:
                tag = Tag(tag=tag_name, is_active=True)
                db.add(tag)
                db.flush()
            
            # 사용자-태그 연결
            user_tag = UserTag(user_id=user.id, tag_id=tag.id)
            db.add(user_tag)
        
        db.commit()
    
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
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer",
        "user_id": user.id
    }


@router.get('/social/merge-info')
async def get_merge_info(request: Request):
    """계정 연동 정보 조회"""
    merge_data = request.session.get('merge_candidate')
    if not merge_data:
        raise HTTPException(404, '연동할 계정 정보가 없습니다')
    
    # 민감한 정보 마스킹은 현재 구현에서 사용하지 않음
    
    return {
        "existing_account": {
            "username": merge_data['username'],
            "email": merge_data['email'],
            "name": merge_data['name'],
            "match_type": merge_data['match_type']
        },
        "social_data": merge_data['social_data']
    }


@router.post('/social/merge-confirm')
async def confirm_merge(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    """계정 연동 확인 (비밀번호 검증)"""
    merge_data = request.session.get('merge_candidate')
    if not merge_data:
        raise HTTPException(404, '연동할 계정 정보가 없습니다')
    
    password = payload.get('password')
    if not password:
        raise HTTPException(400, '비밀번호를 입력해주세요')
    
    # 기존 계정 조회 및 비밀번호 확인
    user = db.query(User).filter(User.id == merge_data['user_id']).first()
    if not user or not user.verify_password(password):
        raise HTTPException(401, '비밀번호가 올바르지 않습니다')
    
    # 소셜 계정 정보로 기존 계정 업데이트
    social_data = merge_data['social_data']
    user.provider = social_data['provider']
    user.provider_id = social_data['provider_id']
    user.email_verified = True
    
    # 프로필 이미지 업데이트 (기존이 기본 이미지인 경우)
    if social_data.get('picture') and (not user.profile_image or 'defaultprofile' in user.profile_image):
        user.profile_image = social_data['picture']
    
    db.commit()
    db.refresh(user)
    
    # 세션 정리
    try:
        request.session.pop('merge_candidate', None)
        request.session.pop('pending_social', None)
        request.session.pop('last_social_identity', None)
    except:
        pass
    
    # JWT 토큰 생성
    claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version or 0}
    access_token = create_access_token(data=claims)
    refresh_token = create_refresh_token(data=claims)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "message": "계정 연동이 완료되었습니다"
    }


@router.post('/social/merge-decline')
async def decline_merge(request: Request):
    """계정 연동 거부 - 새 계정으로 진행"""
    try:
        request.session.pop('merge_candidate', None)
    except:
        pass
    
    return {
        "message": "새 계정으로 진행합니다. 다른 정보를 입력해주세요.",
        "action": "continue_new_account"
    }