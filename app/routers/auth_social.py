from __future__ import annotations
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config as StarConfig
import secrets

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.security import create_access_token, create_refresh_token, validate_password_strength

router = APIRouter(prefix="/auth", tags=["Authentication"])

def _api_base() -> str:
    return (settings.api_base_url or "http://localhost:8001/api/v1").rstrip('/')
def _front_base(request: Request) -> str:
    base = (settings.front_base_url or '').strip().rstrip('/')
    if base:
        return base
    xf_proto = request.headers.get('x-forwarded-proto')
    xf_host = request.headers.get('x-forwarded-host')
    if xf_proto and xf_host:
        return f"{xf_proto}://{xf_host}"
    return str(request.base_url).rstrip('/')

star_cfg = StarConfig(environ={})
oauth = OAuth(star_cfg)

# Google OpenID Connect
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        client_kwargs={'scope': 'openid email profile'},
    )

# Naver OAuth2
if settings.naver_client_id and settings.naver_client_secret:
    oauth.register(
        name='naver',
        api_base_url='https://openapi.naver.com',
        authorize_url='https://nid.naver.com/oauth2.0/authorize',
        access_token_url='https://nid.naver.com/oauth2.0/token',
        client_id=settings.naver_client_id,
        client_secret=settings.naver_client_secret,
        client_kwargs={'scope': 'profile'},
    )


@router.get('/login/google')
async def login_google(request: Request):
    # authlib OAuth 객체는 iterable이 아니므로 hasattr로 등록 여부 확인
    if not hasattr(oauth, 'google'):
        raise HTTPException(503, 'Google login not configured')
    # 현재 요청의 호스트/포트 기준으로 콜백 URL 생성 (세션 일치 보장)
    redirect_uri = str(request.url_for('callback_google'))
    # fresh 모드 저장(기존 연동 무시하고 새 계정으로 가져오기)
    try:
        if request.query_params.get('fresh') in ('1','true','yes'):
            request.session['social_fresh'] = True
    except Exception:
        pass
    # clear stale pending merge state when starting a new social login
    try:
        request.session.pop('pending_social', None)
        request.session.pop('merge_candidate_user_id', None)
    except Exception:
        pass
    # nonce for ID token
    nonce = secrets.token_urlsafe(16)
    request.session['nonce'] = nonce
    # 항상 동의 화면 노출 (최신 정보 승인)
    return await oauth.google.authorize_redirect(
        request, redirect_uri, nonce=nonce, prompt='consent', include_granted_scopes='true'
    )


@router.get('/callback/google')
async def callback_google(request: Request, db: Session = Depends(get_db)):
    if not hasattr(oauth, 'google'):
        raise HTTPException(503, 'Google login not configured')
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        # 세션 state가 유실되었을 때 재시도 유도 (authlib 버전에 따라 예외 타입이 다를 수 있음)
        msg = str(e).lower()
        if 'mismatch' in msg and 'state' in msg:
            return RedirectResponse(str(request.url_for('login_google')), status_code=303)
        raise
    nonce = request.session.pop('nonce', None)
    # ID 토큰에서 기본 클레임 파싱
    userinfo = await oauth.google.parse_id_token(token, nonce=nonce)
    # 보완: userinfo endpoint로 추가 정보 보강 (특히 picture)
    try:
        resp = await oauth.google.get('userinfo', token=token)
        if resp and resp.ok:
            u2 = resp.json() or {}
            if userinfo is None:
                userinfo = u2
            else:
                # fill missing fields
                for k in ('email','name','picture','sub'):
                    if not userinfo.get(k) and u2.get(k):
                        userinfo[k] = u2.get(k)
    except Exception:
        pass
    if not userinfo:
        raise HTTPException(400, 'Google userinfo not found')
    sub = userinfo.get('sub')
    email = (userinfo.get('email') or '').lower()
    name = userinfo.get('name') or (email.split('@')[0] if email else 'google_user')
    extra = {
        'gender': None,
        'picture': userinfo.get('picture')
    }
    try:
        request.session['last_social_identity'] = {
            'provider': 'google',
            'email': email,
            'name': name,
            'sub': sub,
            'picture': extra.get('picture'),
        }
    except Exception:
        pass
    return _issue_tokens_and_redirect(request, db, provider='google', provider_id=sub, email=email, name=name, extra=extra)


@router.get('/login/naver')
async def login_naver(request: Request):
    if not hasattr(oauth, 'naver'):
        raise HTTPException(503, 'Naver login not configured')
    redirect_uri = str(request.url_for('callback_naver'))
    # clear stale pending merge state when starting a new social login
    try:
        request.session.pop('pending_social', None)
        request.session.pop('merge_candidate_user_id', None)
    except Exception:
        pass
    # fresh 모드 저장
    try:
        if request.query_params.get('fresh') in ('1','true','yes'):
            request.session['social_fresh'] = True
    except Exception:
        pass
    # 항상 재동의 화면 노출
    return await oauth.naver.authorize_redirect(request, redirect_uri, auth_type='reprompt')


@router.get('/callback/naver')
async def callback_naver(request: Request, db: Session = Depends(get_db)):
    if not hasattr(oauth, 'naver'):
        raise HTTPException(503, 'Naver login not configured')
    try:
        token = await oauth.naver.authorize_access_token(request)
    except Exception as e:
        msg = str(e).lower()
        if 'mismatch' in msg and 'state' in msg:
            return RedirectResponse(str(request.url_for('login_naver')), status_code=303)
        raise
    # 프로필 불러오기
    resp = await oauth.naver.get('/v1/nid/me', token=token)
    data = resp.json()
    info = (data or {}).get('response') or {}
    pid = info.get('id')
    email = (info.get('email') or '').lower()
    name = info.get('name') or (email.split('@')[0] if email else 'naver_user')
    extra = {
        'gender': info.get('gender'),
        'profile_image': info.get('profile_image'),
        'birthyear': info.get('birthyear'),
        'mobile': info.get('mobile') or info.get('mobile_e164'),
    }
    try:
        request.session['last_social_identity'] = {
            'provider': 'naver',
            'email': email,
            'name': name,
            'sub': pid,
            'picture': extra.get('profile_image'),
        }
    except Exception:
        pass
    return _issue_tokens_and_redirect(request, db, provider='naver', provider_id=pid, email=email, name=name, extra=extra)


def _issue_tokens_and_redirect(request: Request, db: Session, provider: str, provider_id: str | None, email: str | None, name: str | None, extra: dict | None = None):
    if not provider_id and not email:
        raise HTTPException(400, 'No identifier from provider')
    # 매핑: provider_id -> email -> 신규
    user = None
    if provider_id:
        user = db.query(User).filter(User.provider == provider, User.provider_id == provider_id).first()
    # 사용자가 fresh=1로 요청한 경우, 기존 연동을 분리하고 새 계정으로 유입
    try:
        fresh = bool(request.session.pop('social_fresh', False))
    except Exception:
        fresh = False
    if user and fresh:
        # 기존 사용자에서 소셜 연동 해제
        user.provider = None
        user.provider_id = None
        db.commit(); db.refresh(user)
        user = None
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
    DEFAULT_PROFILE_IMAGE = "/static/pictures/defaultprofile.jpeg"

    if user:
        # 기존 사용자 업데이트(연동/보강)
        # 이메일로만 매칭된 경우(아직 provider_id 미연동): 사용자 확인 페이지로 보냄
        if (not getattr(user, 'provider', None) or not getattr(user, 'provider_id', None)) and provider_id:
            try:
                request.session['pending_social'] = request.session.get('pending_social') or {
                    'provider': provider, 'email': email, 'name': name, 'sub': provider_id,
                    'picture': (extra.get('picture') if extra else None) or (extra.get('profile_image') if extra else None)
                }
                request.session['merge_candidate_user_id'] = user.id
            except Exception:
                pass
            front = _front_base(request)
            return RedirectResponse(f"{front}/social/merge", status_code=303)

        changed = False
        if provider and provider_id and (not getattr(user, 'provider', None) or not getattr(user, 'provider_id', None)):
            user.provider = provider
            user.provider_id = provider_id
            changed = True

        if extra:
            # 프로필 이미지: 비어있거나 기본 이미지이면 갱신
            pic = extra.get('picture') or extra.get('profile_image')
            if pic and (not user.profile_image or user.profile_image == DEFAULT_PROFILE_IMAGE):
                user.profile_image = pic
                changed = True
            # 휴대전화: 비어 있으면 설정
            mobile = extra.get('mobile')
            if mobile and not user.phone_encrypted:
                try:
                    user.set_phone(mobile)
                    changed = True
                except Exception:
                    pass
            # 출생연도: 비어 있으면 설정
            if extra.get('birthyear') and not getattr(user, 'birth_year', None):
                user.birth_year = str(extra.get('birthyear'))
                changed = True
            # 성별: other이면 갱신
            g = (extra.get('gender') or '').lower()
            if g and (user.gender == 'other'):
                if g in ('m','male','1'):
                    user.gender = 'male'; changed = True
                elif g in ('f','female','0'):
                    user.gender = 'female'; changed = True
        if changed:
            db.commit(); db.refresh(user)

        claims = {"sub": user.username, "user_id": user.id, "tv": (user.token_version or 0)}
        access = create_access_token(data=claims)
        refresh = create_refresh_token(data=claims)
        front = _front_base(request)
        url = f"{front}/auth/callback?access={access}&refresh={refresh}&provider={provider}"
        return RedirectResponse(url, status_code=303)
    else:
        # 신규 사용자는 생성 지연: 세션에 보관하고 온보딩으로 이동
        try:
            request.session['pending_social'] = request.session.get('last_social_identity') or {
                'provider': provider,
                'email': email,
                'name': name,
                'sub': provider_id,
            }
            # 보조 정보도 포함
            if extra:
                request.session['pending_social']['picture'] = extra.get('picture') or extra.get('profile_image')
        except Exception:
            pass
        front = _front_base(request)
        url = f"{front}/social/onboarding?provider={provider}"
        return RedirectResponse(url, status_code=303)


@router.get('/identity/last')
async def last_social_identity(request: Request):
    # 우선 pending_social(생성 지연), 없으면 last_social_identity
    data = request.session.get('pending_social') or request.session.get('last_social_identity') or {}
    return data

# -------------------------
# Merge UI: info for confirmation
# -------------------------
@router.get('/social/merge-info')
async def social_merge_info(request: Request, db: Session = Depends(get_db)):
    ident = request.session.get('pending_social') or {}
    uid = request.session.get('merge_candidate_user_id')
    if not uid:
        raise HTTPException(400, 'No merge candidate')
    user = db.query(User).get(int(uid))
    if not user:
        raise HTTPException(404, 'User not found')
    # phone masked
    def _mask_phone(raw: str | None) -> str | None:
        if not raw:
            return None
        import re
        d = re.sub(r'\D+', '', raw)
        if len(d) >= 7:
            head = d[:3]
            tail = d[-2:]
            if len(d) == 11 and d.startswith('010'):
                return f"010-****-**{tail}"
            return f"{head}-****-**{tail}"
        return None
    phone_plain = None
    try:
        phone_plain = user.get_phone()
    except Exception:
        phone_plain = None
    masked = _mask_phone(phone_plain) or _mask_phone(user.phone)
    return {
        'existing': {
            'id': user.id,
            'username': user.username,
            'name': user.name,
            'email': user.email,
            'phone_masked': masked,
            'profile_image_url': user.profile_image,
        },
        'social': {
            'provider': ident.get('provider'),
            'email': ident.get('email'),
            'name': ident.get('name'),
            'picture': ident.get('picture'),
        }
    }

# -------------------------
# Prepare merge from Step1 (set candidate by login, then show merge page)
# -------------------------
@router.post('/social/prepare-merge')
async def social_prepare_merge(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    login = (payload.get('login') or '').strip().lower()
    if not login:
        raise HTTPException(400, 'login is required')

    # ensure we have latest social identity in session
    # Prefer last_social_identity (most recent login) over leftover pending_social
    last_ident = request.session.get('last_social_identity')
    pending_ident = request.session.get('pending_social')
    ident = last_ident or pending_ident
    if not ident:
        raise HTTPException(400, 'No pending social identity')

    # find existing user by username or email
    user = db.query(User).filter((User.username == login) | (User.email == login)).first()
    if not user:
        raise HTTPException(404, '사용자를 찾을 수 없습니다')

    try:
        request.session['merge_candidate_user_id'] = user.id
        # If pending_social exists for a different provider, overwrite with latest
        if pending_ident and last_ident and (pending_ident.get('provider') != last_ident.get('provider')):
            request.session['pending_social'] = last_ident
        else:
            request.session['pending_social'] = ident
    except Exception:
        pass

    front = _front_base(request)
    return {'url': f"{front}/social/merge"}

# -------------------------
# Merge apply: require password, optional field updates
# -------------------------
@router.post('/social/merge-apply')
async def social_merge_apply(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    ident = request.session.get('pending_social') or {}
    uid = request.session.get('merge_candidate_user_id')
    if not uid or not ident:
        raise HTTPException(400, 'No pending social merge')
    user: User = db.query(User).get(int(uid))
    if not user:
        raise HTTPException(404, 'User not found')
    password = (payload.get('password') or '').strip()
    if not user.verify_password(password):
        raise HTTPException(401, '비밀번호가 올바르지 않습니다')
    # apply updates
    if payload.get('update_name') and ident.get('name'):
        user.name = ident.get('name')
    if payload.get('update_profile_image') and ident.get('picture'):
        user.profile_image = ident.get('picture')
    # 이메일 변경 옵션
    if payload.get('update_email') and ident.get('email'):
        new_email = (ident.get('email') or '').strip().lower()
        if new_email and new_email != (user.email or '').strip().lower():
            # 중복 검사
            exists = db.query(User.id).filter(User.email == new_email, User.id != user.id).first()
            if exists:
                raise HTTPException(409, '이미 사용 중인 이메일입니다')
            user.email = new_email
    if payload.get('update_phone') and payload.get('phone'):
        try:
            user.set_phone(payload.get('phone'))
        except Exception:
            pass
    # link provider
    user.provider = ident.get('provider')
    user.provider_id = ident.get('sub')
    user.is_active = True
    user.email_verified = True
    db.commit(); db.refresh(user)
    # clear session
    try:
        request.session.pop('pending_social', None)
        request.session.pop('merge_candidate_user_id', None)
    except Exception:
        pass
    # tokens
    claims = {"sub": user.username, "user_id": user.id, "tv": (user.token_version or 0)}
    access = create_access_token(data=claims)
    refresh = create_refresh_token(data=claims)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

# -------------------------
# Finalize (create user after onboarding)
# -------------------------
@router.post('/social/finalize')
async def social_finalize(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    ident = request.session.get('pending_social') or request.session.get('last_social_identity')
    if not ident:
        raise HTTPException(400, 'No pending social identity')
    provider = ident.get('provider'); provider_id = ident.get('sub'); email = (ident.get('email') or '').lower();
    # allow payload name override; fall back to social identity, then email local-part
    name = (payload.get('name') or '').strip() or ident.get('name') or (email.split('@')[0] if email else 'user')

    # 혹시 이미 동일 이메일/소셜로 존재한다면 그 계정으로 토큰 발급
    user = None
    if provider and provider_id:
        user = db.query(User).filter(User.provider == provider, User.provider_id == provider_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
    if user:
        claims = {"sub": user.username, "user_id": user.id, "tv": (user.token_version or 0)}
        access = create_access_token(data=claims)
        refresh = create_refresh_token(data=claims)
        return JSONResponse({"access_token": access, "refresh_token": refresh, "token_type": "bearer", "user_id": user.id})

    # 새 사용자 생성
    # username 우선 사용(중복이면 뒤에 숫자붙임)
    base_username = (payload.get('username') or (email.split('@')[0] if email else f"{provider}_user")).lower()
    uname = base_username; i = 1
    while db.query(User).filter(User.username == uname).first() is not None:
        i += 1; uname = f"{base_username}{i}"
    from app.models.user import User as U
    user = U(
        username=uname,
        email=email or f"{uname}@example.com",
        name=name or uname,
        provider=provider,
        provider_id=provider_id,
        email_verified=True,
        is_active=True,
        introduction=(payload.get('introduction') or ''),
    )
    # 비밀번호: 전달되면 강도 검증 후 사용, 없으면 랜덤
    raw_pw = (payload.get('password') or '').strip()
    if raw_pw:
        if not validate_password_strength(raw_pw):
            raise HTTPException(400, '비밀번호가 요구사항을 충족하지 않습니다')
        user.set_password(raw_pw)
    else:
        user.set_password(secrets.token_urlsafe(12))
    # 프로필 보강
    pic = ident.get('picture') or (payload.get('profile_image') or '').strip()
    if pic: user.profile_image = pic
    if payload.get('phone'): 
        try: user.set_phone(payload.get('phone'))
        except Exception: pass
    if payload.get('identification_number'):
        try:
            user.set_identification_number(payload.get('identification_number'))
        except Exception:
            raise HTTPException(400, '주민등록번호 형식이 올바르지 않습니다')
    if payload.get('gender') in ('male','female','other',None,''):
        user.gender = (payload.get('gender') or user.gender)
    user.region_living = payload.get('region_living') or ''
    user.region_active = payload.get('region_active') or ''

    db.add(user); db.commit(); db.refresh(user)

    # 세션 비우기
    try:
        request.session.pop('pending_social', None)
    except Exception:
        pass

    claims = {"sub": user.username, "user_id": user.id, "tv": (user.token_version or 0)}
    access = create_access_token(data=claims)
    refresh = create_refresh_token(data=claims)
    return JSONResponse({"access_token": access, "refresh_token": refresh, "token_type": "bearer", "user_id": user.id})


# -------------------------
# Link to existing account (no JWT yet)
# -------------------------
@router.post('/social/link-existing')
async def social_link_existing(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    ident = request.session.get('pending_social') or request.session.get('last_social_identity')
    if not ident:
        raise HTTPException(400, 'No pending social identity')
    provider = ident.get('provider'); provider_id = ident.get('sub')
    if not (provider and provider_id):
        raise HTTPException(400, 'Invalid social identity')

    login = (payload.get('login') or '').strip().lower(); password = payload.get('password') or ''
    if not (login and password):
        raise HTTPException(400, 'login and password are required')
    target = db.query(User).filter((User.username == login) | (User.email == login)).first()
    if not target or not target.verify_password(password):
        raise HTTPException(401, '아이디/비밀번호가 올바르지 않습니다')

    # 바인딩
    if target.provider and target.provider_id and (target.provider != provider or target.provider_id != provider_id):
        raise HTTPException(409, '이미 다른 소셜이 연결되어 있습니다')
    target.provider = provider; target.provider_id = provider_id
    target.is_active = True; target.email_verified = True
    db.commit(); db.refresh(target)
    try: request.session.pop('pending_social', None)
    except Exception: pass

    claims = {"sub": target.username, "user_id": target.id, "tv": (target.token_version or 0)}
    access = create_access_token(data=claims)
    refresh = create_refresh_token(data=claims)
    return JSONResponse({"access_token": access, "refresh_token": refresh, "token_type": "bearer", "user_id": target.id})
