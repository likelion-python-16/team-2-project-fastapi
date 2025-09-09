# app/routers/auth_social.py
from __future__ import annotations
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from sqlalchemy import or_
from starlette.config import Config as StarConfig
import secrets

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.security import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["Social Authentication"])

def _front_base(request: Request) -> str:
    """프론트엔드 기본 URL 추출
    - 로컬 개발(포트 포함)에서는 request.base_url 우선
    - 명시적으로 별도 도메인이 설정된 경우에만 settings.front_base_url 사용
    """
    cfg = (settings.front_base_url or '').strip().rstrip('/')
    if cfg:
        # 로컬 기본값이나 localhost/127.0.0.1처럼 포트 미지정인 경우는 무시하고 요청 기준 사용
        from urllib.parse import urlparse
        try:
            u = urlparse(cfg)
            host = (u.hostname or '').lower()
            if host and host not in ('localhost', '127.0.0.1'):
                return cfg
        except Exception:
            pass
    # X-Forwarded-* 헤더 확인(리버스 프록시 환경)
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
    except OAuthError as e:
        # 사용자가 동의 화면에서 취소했거나(access_denied) 기타 OAuth 오류
        return RedirectResponse(url=f"{_front_base(request)}/login?error=social_denied", status_code=303)
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
        frontend_url = f"{_front_base(request)}/auth/callback?access={access_token}&refresh={refresh_token}&provider=google"
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
        
        frontend_url = f"{_front_base(request)}/auth/callback?access={access_token}&refresh={refresh_token}&provider=google"
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
    except OAuthError as e:
        return RedirectResponse(url=f"{_front_base(request)}/login?error=social_denied", status_code=303)
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
        
        frontend_url = f"{_front_base(request)}/auth/callback?access={access_token}&refresh={refresh_token}&provider=naver"
        return RedirectResponse(url=frontend_url, status_code=303)
    
    # 동일 이메일의 기존 계정 확인
    existing_email_user = db.query(User).filter(User.email == email).first()
    
    if existing_email_user and not existing_email_user.provider:
        # 기존 일반 회원가입 계정에 네이버 연동
        existing_email_user.provider = 'naver'
        existing_email_user.provider_id = naver_id
        if profile_image:
            existing_email_user.profile_image = profile_image
        # birth_year 필드는 User 모델에 존재하지 않으므로 저장하지 않음
            
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
        # 'birth_year': birth_year  # User 모델에 컬럼이 없어 세션에는 보관만 하더라도 사용하지 않음
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
        # 'birth_year': pending.get('birth_year')
    }


@router.post('/match-existing-social')
def match_existing_social(payload: dict = Body(...), db: Session = Depends(get_db)):
    """소셜 1단계: 기존 계정 후보 탐지 (읽기 전용)
    - name + phone, name + ident, phone + ident, ident only 조합을 판별
    - 마스킹 힌트(username/email)
    """
    from app.security import id_fingerprint, normalize_phone

    name = (payload.get('name') or '').strip()
    phone_raw = (payload.get('phone') or '').strip()
    ident_raw = (payload.get('identification') or payload.get('identification_number') or '').strip()

    phone_fp = None
    ident_fp = None
    try:
        norm_phone = normalize_phone(phone_raw) if phone_raw else None
        phone_fp = id_fingerprint(norm_phone) if norm_phone else None
    except Exception:
        phone_fp = None
    try:
        ident_digits = ''.join([c for c in ident_raw if c.isdigit()]) if ident_raw else None
        ident_fp = id_fingerprint(ident_digits) if ident_digits else None
    except Exception:
        ident_fp = None

    # 후보 탐색
    users = []
    if ident_fp:
        u = db.query(User).filter(User.identification_fingerprint == ident_fp).first()
        if u:
            users.append(u)
    if phone_fp:
        u = db.query(User).filter(User.phone_fingerprint == phone_fp).first()
        if u and u not in users:
            users.append(u)

    def mask_email(email: str) -> str:
        if not email:
            return ''
        try:
            local, dom = email.split('@', 1)
        except ValueError:
            return ''
        def mask_part(s: str) -> str:
            if len(s) <= 2:
                return s[0] + '*'
            return s[:2] + '*' * max(1, len(s)-3) + s[-1]
        parts = dom.split('.')
        head = parts[0]
        tail = '.' + '.'.join(parts[1:]) if len(parts) > 1 else ''
        return mask_part(local) + '@' + mask_part(head) + tail

    def mask_username(u: str) -> str:
        if not u:
            return ''
        if len(u) <= 2:
            return u[0] + '*'
        return u[:2] + '*' * max(1, len(u)-3) + u[-1]

    by_name_phone = False
    by_name_ident = False
    by_phone_ident = False
    by_ident_only = False
    hint_user = None

    for u in users:
        if ident_fp and phone_fp and u.identification_fingerprint == ident_fp and u.phone_fingerprint == phone_fp:
            by_phone_ident = True
            hint_user = hint_user or u
        if ident_fp and u.identification_fingerprint == ident_fp:
            by_ident_only = True
            hint_user = hint_user or u
        if name and u.name and u.name.strip() == name:
            if phone_fp and u.phone_fingerprint == phone_fp:
                by_name_phone = True
                hint_user = hint_user or u
            if ident_fp and u.identification_fingerprint == ident_fp:
                by_name_ident = True
                hint_user = hint_user or u

    return {
        'by_name_phone': by_name_phone,
        'by_name_ident': by_name_ident,
        'by_phone_ident': by_phone_ident,
        'by_ident_only': by_ident_only,
        'email_masked': mask_email(hint_user.email) if hint_user else '',
        'username_masked': mask_username(hint_user.username) if hint_user else '',
    }


@router.post('/social/prepare-merge')
def social_prepare_merge(payload: dict = Body(...), request: Request = None, db: Session = Depends(get_db)):
    """병합 대상 기존 계정을 세션에 저장하고 프런트 병합 페이지 URL을 반환"""
    login = (payload.get('login') or '').strip()
    if not login:
        raise HTTPException(400, 'login required')
    user = db.query(User).filter(or_(User.username == login, User.email == login)).first()
    if not user:
        raise HTTPException(404, '계정을 찾을 수 없습니다')
    # 최근 소셜 식별 정보를 함께 저장하여 merge-info에서 표시
    social = request.session.get('pending_social') or request.session.get('last_social_identity') or {}
    try:
        request.session['merge_candidate'] = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'match_type': 'manual',
            'social_data': {
                'provider': social.get('provider'),
                'provider_id': social.get('provider_id') or social.get('sub'),
                'email': social.get('email'),
                'name': social.get('name'),
                'picture': social.get('profile_image') or social.get('picture')
            }
        }
    except Exception:
        pass
    return {'url': '/social/merge'}


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
    
    # 새 사용자 생성: 전화/주민번호는 모델 setter를 사용해 암호화/지문 처리
    new_user = User(
        username=username,
        email=pending['email'],
        password_hash='',  # 소셜 로그인은 비밀번호 없음
        name=pending['name'],
        region_living=region_living,
        region_active=region_active,
        profile_image=pending.get('profile_image', pending.get('picture', '')),
        provider=pending['provider'],
        provider_id=pending['provider_id'],
        # birth_year=pending.get('birth_year', ''),
        email_verified=True,  # 소셜 로그인은 이메일 인증 완료로 간주
        is_active=True,
        introduction='',  # 필수 필드이므로 빈 문자열
        gender='other'  # 기본값
    )
    try:
        if phone:
            new_user.set_phone(phone)
        if identification_number:
            new_user.set_identification_number(identification_number)
    except Exception:
        pass
    
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
    
    # introduction 처리: JSON이면 bio만 저장하고, interests.keywords는 태그로 연결
    intro_raw = payload.get('introduction') or ''
    introduction_text = ''
    intro_keywords = []
    if intro_raw and isinstance(intro_raw, str) and intro_raw.strip().startswith('{'):
        try:
            import json
            parsed = json.loads(intro_raw)
            if isinstance(parsed, dict):
                introduction_text = (parsed.get('bio') or '').strip()
                interests = parsed.get('interests') or {}
                kws = interests.get('keywords') or []
                if isinstance(kws, list):
                    intro_keywords = [str(k).strip() for k in kws if isinstance(k, str) and k.strip()]
        except Exception:
            introduction_text = ''
    else:
        introduction_text = (intro_raw or '').strip()

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
        introduction=introduction_text,
        # birth_year=ident.get('birth_year', ''),
    )
    
    # 비밀번호 설정: 전달된 비밀번호가 있으면 강도 검증 후 사용, 없으면 랜덤 생성
    try:
        from app.security import validate_password_strength
        raw_pw = (payload.get('password') or '').strip()
        if raw_pw:
            if not validate_password_strength(raw_pw):
                raise HTTPException(400, '비밀번호가 요구사항을 충족하지 않습니다')
            user.set_password(raw_pw)
        else:
            user.set_password(secrets.token_urlsafe(12))
    except HTTPException:
        raise
    except Exception:
        # 예외 시 안전하게 랜덤 비밀번호로 진행
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
    
    # 안전한 커밋: 중복(무결성) 오류를 500 대신 400/409로 안내
    from sqlalchemy.exc import IntegrityError
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as ie:
        db.rollback()
        # 이메일/사용자명 유니크 충돌 가능성 안내
        raise HTTPException(409, '이미 사용 중인 이메일/사용자명이 있습니다. 기존 계정으로 로그인하거나 연동해 주세요.')
    
    # 태그 연결 처리: (1) selected_tags, (2) introduction JSON의 interests.keywords
    selected_tags = list(payload.get('selected_tags', []) or [])
    if intro_keywords:
        for k in intro_keywords:
            if k not in selected_tags:
                selected_tags.append(k)
    if selected_tags:
        from app.models.tag import Tag
        from app.models.tag import UserTag
        from app.core.config import settings as _settings
        allow_dynamic = bool(getattr(_settings, 'allow_dynamic_tag_create', False))

        for tag_name in selected_tags:
            # 기존 태그 찾기 또는 생성
            tag = db.query(Tag).filter(Tag.tag == tag_name).first()
            if not tag:
                if not allow_dynamic:
                    continue
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
async def get_merge_info(request: Request, db: Session = Depends(get_db)):
    """계정 연동 정보 조회 (템플릿 기대 구조에 맞춤)"""
    merge_data = request.session.get('merge_candidate')
    if not merge_data:
        raise HTTPException(404, '연동할 계정 정보가 없습니다')

    # 기존 계정 상세 보강
    user = db.query(User).filter(User.id == merge_data['user_id']).first()
    def mask_phone(ph: str | None) -> str:
        if not ph:
            return ''
        d = ''.join(c for c in ph if c.isdigit())
        if len(d) == 11 and d.startswith('010'):
            return f"010-{d[3:7]}-{d[7:]}"
        return ph

    # phone: decrypt if necessary
    phone_plain = None
    try:
        if user and hasattr(user, 'get_phone'):
            phone_plain = user.get_phone()
    except Exception:
        phone_plain = None

    existing = {
        "username": merge_data.get('username', user.username if user else ''),
        "email": merge_data.get('email', user.email if user else ''),
        "name": merge_data.get('name', user.name if user else ''),
        "match_type": merge_data.get('match_type', ''),
        "phone_masked": mask_phone(phone_plain),
        "profile_image_url": (user.profile_image if user and getattr(user, 'profile_image', None) else ''),
    }
    social = {
        "provider": merge_data.get('social_data', {}).get('provider'),
        "email": merge_data.get('social_data', {}).get('email'),
        "name": merge_data.get('social_data', {}).get('name'),
        "picture": merge_data.get('social_data', {}).get('picture'),
    }

    # 기존 구조도 유지하여 다른 클라이언트와 호환
    return {
        "existing": existing,
        "social": social,
        "existing_account": existing,
        "social_data": merge_data.get('social_data', {}),
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

    # 사용자가 선택한 업데이트 적용
    if payload.get('update_name') and social_data.get('name'):
        user.name = social_data['name']
    if payload.get('update_email') and social_data.get('email'):
        user.email = social_data['email']
    if payload.get('update_profile_image') and social_data.get('picture'):
        user.profile_image = social_data['picture']
    # 전화번호 입력이 있으면 설정(검증은 모델/보조에서 수행)
    phone_digits = payload.get('phone')
    if phone_digits:
        try:
            user.set_phone(phone_digits)
        except Exception:
            pass
    
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


# Alias for template which calls /merge-apply
@router.post('/social/merge-apply')
async def merge_apply(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    return await confirm_merge(request, payload, db)


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
