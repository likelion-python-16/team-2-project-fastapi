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
from app.security import (
    create_access_token,
    create_refresh_token,
    validate_password_strength,
    id_fingerprint,
    normalize_phone,
)
from sqlalchemy.exc import IntegrityError

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
    # 요청 스코프를 명시적으로 확장: name, email, profile_image
    oauth.register(
        name='naver',
        api_base_url='https://openapi.naver.com',
        authorize_url='https://nid.naver.com/oauth2.0/authorize',
        access_token_url='https://nid.naver.com/oauth2.0/token',
        client_id=settings.naver_client_id,
        client_secret=settings.naver_client_secret,
        client_kwargs={'scope': 'name email profile_image'},
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
    # 계정 선택만 강제하고, 이미 동의한 앱은 자동 진행
    return await oauth.google.authorize_redirect(
        request, redirect_uri, nonce=nonce, prompt='select_account', include_granted_scopes='true'
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
        pic = extra.get('picture')
        request.session['last_social_identity'] = {
            'provider': 'google',
            'email': email,
            'name': name,
            'sub': sub,
            'picture': pic,
            'profile_image': pic,
        }
        from app.utils.logging import logger as _logger
        try: _logger.info(f"[social] google userinfo picture={pic}")
        except Exception: pass
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
        # 사용자가 동의를 취소한 경우(error=access_denied 등) 홈으로 돌려보낸다
        if request.query_params.get('error'):
            # optional: 메시지 플래시 용도 쿼리파라미터
            front = _front_base(request)
            return RedirectResponse(f"{front}/home", status_code=303)
        token = await oauth.naver.authorize_access_token(request)
    except Exception as e:
        msg = str(e).lower()
        if 'mismatch' in msg and 'state' in msg:
            return RedirectResponse(str(request.url_for('login_naver')), status_code=303)
        # 취소/거부 등 기타 오류도 홈으로 안전 리다이렉트
        front = _front_base(request)
        return RedirectResponse(f"{front}/home", status_code=303)
    # 프로필 불러오기
    resp = await oauth.naver.get('/v1/nid/me', token=token)
    data = resp.json()
    info = (data or {}).get('response') or {}
    pid = info.get('id')
    email = (info.get('email') or '').lower()
    # name 동의가 없으면 nickname으로 보강
    name = info.get('name') or info.get('nickname') or (email.split('@')[0] if email else 'naver_user')
    extra = {
        'gender': info.get('gender'),
        'profile_image': info.get('profile_image'),
        'birthyear': info.get('birthyear'),
        'mobile': info.get('mobile') or info.get('mobile_e164'),
    }
    try:
        pic = extra.get('profile_image')
        request.session['last_social_identity'] = {
            'provider': 'naver',
            'email': email,
            'name': name,
            'sub': pid,
            'picture': pic,
            'profile_image': pic,
        }
        from app.utils.logging import logger as _logger
        try: _logger.info(f"[social] naver userinfo profile_image={pic}")
        except Exception: pass
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
        # 이메일로만 매칭된 경우(아직 provider_id 미연동): 이름까지 같은 경우에만 머지로 안내
        if (not getattr(user, 'provider', None) or not getattr(user, 'provider_id', None)) and provider_id:
            def _norm(s: str | None) -> str:
                return (s or '').strip().casefold()
            names_match = _norm(user.name) == _norm(name)
            if not names_match:
                # 이름이 다르면 신규 온보딩으로 유도 (주민번호 확인 후 연동 안내는 온보딩에서 처리)
                try:
                    pic = (extra.get('picture') if extra else None) or (extra.get('profile_image') if extra else None)
                    request.session['pending_social'] = request.session.get('pending_social') or {
                        'provider': provider, 'email': email, 'name': name, 'sub': provider_id,
                        'picture': pic,
                        'profile_image': pic,
                    }
                except Exception:
                    pass
                front = _front_base(request)
                return RedirectResponse(f"{front}/social/onboarding?provider={provider}", status_code=303)
            try:
                pic = (extra.get('picture') if extra else None) or (extra.get('profile_image') if extra else None)
                request.session['pending_social'] = request.session.get('pending_social') or {
                    'provider': provider, 'email': email, 'name': name, 'sub': provider_id,
                    'picture': pic,
                    'profile_image': pic,
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
        
        # 쿠키 설정 (듀얼 인증 지원)
        front = _front_base(request)
        url = f"{front}/auth/callback?access={access}&refresh={refresh}&provider={provider}"
        response = RedirectResponse(url, status_code=303)
        
        # HttpOnly 쿠키 설정으로 세션 유지
        from app.core.config import settings
        secure_flag = not settings.debug  # prod: True, dev: False
        response.set_cookie(
            key="access_token",
            value=access,
            httponly=True,
            secure=secure_flag,
            samesite="lax",
            max_age=settings.jwt_access_token_expire_minutes * 60,
            path="/",
        )
        return response
    else:
        # 기존 계정 없음 → 온보딩으로 유도 (여기서 신규 생성은 하지 않음)
        try:
            request.session['pending_social'] = request.session.get('last_social_identity') or {
                'provider': provider,
                'email': email,
                'name': name,
                'sub': provider_id,
            }
            if extra:
                pic = (extra.get('picture') if extra else None) or (extra.get('profile_image') if extra else None)
                request.session['pending_social']['picture'] = pic
                request.session['pending_social']['profile_image'] = pic
        except Exception:
            pass
        front = _front_base(request)
        url = f"{front}/social/onboarding?provider={provider}"
        return RedirectResponse(url, status_code=303)


@router.post('/match-existing-social')
def match_existing_social(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    소셜 스텝1에서 기존 계정 존재 가능성을 빠르게 판단하기 위한 매칭 API.
    입력: { name, phone, identification }
    출력: { by_name_phone, by_name_ident, by_phone_ident, by_ident_only, email_masked?, username_masked? }
    """
    from app.models.user import User
    name = (payload.get('name') or '').strip()
    raw_phone = (payload.get('phone') or '').strip()
    raw_ident = (payload.get('identification') or '').strip()

    # 정규화
    p_norm = None; p_fp = None
    try:
        if raw_phone:
            p_norm = normalize_phone(raw_phone)
            if p_norm: p_fp = id_fingerprint(p_norm)
    except Exception:
        p_norm = None; p_fp = None
    i_fp = None
    try:
        if raw_ident:
            import re
            ident_digits = re.sub(r'\D+', '', raw_ident)
            if len(ident_digits) == 13:
                i_fp = id_fingerprint(ident_digits)
    except Exception:
        i_fp = None

    # 매칭 쿼리들
    def q_by_name_phone():
        if not (name and (p_fp or p_norm)): return None
        q = db.query(User).filter(User.name == name)
        if p_fp:
            q = q.filter(User.phone_fingerprint == p_fp)
        else:
            q = q.filter(User.phone == p_norm)
        return q.first()

    def q_by_name_ident():
        if not (name and i_fp): return None
        return db.query(User).filter(User.name == name, User.identification_fingerprint == i_fp).first()

    def q_by_phone_ident():
        if not ((p_fp or p_norm) and i_fp): return None
        q = db.query(User).filter(User.identification_fingerprint == i_fp)
        if p_fp:
            q = q.filter(User.phone_fingerprint == p_fp)
        else:
            q = q.filter(User.phone == p_norm)
        return q.first()

    def q_by_ident_only():
        if not i_fp: return None
        return db.query(User).filter(User.identification_fingerprint == i_fp).first()

    m_name_phone = q_by_name_phone()
    m_name_ident = q_by_name_ident()
    m_phone_ident = q_by_phone_ident()
    m_ident_only = q_by_ident_only()

    # 하나라도 일치하는 사용자가 있으면 마스킹 정보 제공
    picked = m_ident_only or m_name_ident or m_name_phone or m_phone_ident
    def mask_username(u: str | None) -> str | None:
        if not u: return None
        if len(u) <= 2: return u[0] + '*'
        return u[:2] + '*' * max(1, len(u) - 3) + u[-1]
    def mask_email(e: str | None) -> str | None:
        if not e or '@' not in e: return None
        local, dom = e.split('@', 1)
        lm = (local[:2] + '*' * max(1, len(local) - 3) + local[-1]) if len(local) > 2 else (local[0] + '*')
        parts = dom.split('.')
        if len(parts) == 1:
            d = parts[0]
            dm = (d[:2] + '*' * max(1, len(d) - 3) + d[-1]) if len(d) > 2 else (d[0] + '*')
            return f"{lm}@{dm}"
        first = parts[0]
        rest = '.'.join(parts[1:])
        fm = (first[:2] + '*' * max(1, len(first) - 3) + first[-1]) if len(first) > 2 else (first[0] + '*')
        return f"{lm}@{fm}{('.' + rest) if rest else ''}"

    return {
        'by_name_phone': bool(m_name_phone),
        'by_name_ident': bool(m_name_ident),
        'by_phone_ident': bool(m_phone_ident),
        'by_ident_only': bool(m_ident_only),
        'email_masked': mask_email(getattr(picked, 'email', None)) if picked else None,
        'username_masked': mask_username(getattr(picked, 'username', None)) if picked else None,
    }

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
    """
    소셜 온보딩 완료 → 새 계정 생성 또는 연동 유도
    - 자동 생성은 콜백에서 하지 않음. 이 엔드포인트에서 최종 생성.
    - identification_number가 기존 계정과 일치하면 생성하지 않고 연동 안내 정보 반환.
    - username은 반드시 명시(자동 생성 금지) → 미제공 시 400.
    """
    ident_sess = request.session.get('pending_social') or request.session.get('last_social_identity')
    if not ident_sess:
        raise HTTPException(400, 'No pending social identity')

    provider = ident_sess.get('provider')
    provider_id = ident_sess.get('sub')
    email = (ident_sess.get('email') or '').lower()
    social_name = ident_sess.get('name')

    # 이미 연결된 계정이면 토큰만 재발급
    linked = None
    if provider and provider_id:
        linked = db.query(User).filter(User.provider == provider, User.provider_id == provider_id).first()
    if linked:
        claims = {"sub": linked.username, "user_id": linked.id, "tv": (linked.token_version or 0)}
        return JSONResponse({"access_token": create_access_token(data=claims), "refresh_token": create_refresh_token(data=claims), "token_type": "bearer", "user_id": linked.id})

    # 필수 입력: username, identification_number
    username = (payload.get('username') or '').strip().lower()
    if not username:
        raise HTTPException(400, 'username is required')
    import re as _re
    if not _re.match(r'^[a-z][a-z0-9]*$', username):
        raise HTTPException(400, 'username must start with a letter and contain only letters and digits')
    identification_number = (payload.get('identification_number') or '').strip()
    if not identification_number:
        raise HTTPException(400, 'identification_number is required')

    # 주민번호로 기존 사용자 존재 여부 확인 → 있으면 연동 유도 정보 반환
    try:
        fp_ident = id_fingerprint(identification_number)
    except Exception:
        raise HTTPException(400, '주민등록번호 형식이 올바르지 않습니다')
    existing_by_ident = db.query(User).filter(User.identification_fingerprint == fp_ident).first()
    if existing_by_ident:
        # 연동 안내 (아이디/이메일 전달)
        return JSONResponse(
            status_code=409,
            content={
                'action': 'merge_required',
                'message': '기존 계정이 확인되었습니다. 해당 계정으로 로그인하여 연동해 주세요.',
                'existing': {
                    'id': existing_by_ident.id,
                    'username': existing_by_ident.username,
                    'email': existing_by_ident.email,
                    'name': existing_by_ident.name,
                }
            }
        )

    # username/email 중복 검사
    if db.query(User.id).filter(User.username == username).first():
        raise HTTPException(409, '이미 사용 중인 아이디입니다')
    if email and db.query(User.id).filter(User.email == email).first():
        raise HTTPException(409, '이미 사용 중인 이메일입니다')

    # 생성
    user = User(
        username=username,
        email=email or f"{username}@example.com",
        name=(payload.get('name') or '').strip() or social_name or username,
        provider=provider,
        provider_id=provider_id,
        email_verified=True,
        is_active=True,
        introduction=(payload.get('introduction') or ''),
    )
    # 비밀번호는 선택 입력 (없으면 랜덤)
    raw_pw = (payload.get('password') or '').strip()
    if raw_pw:
        if not validate_password_strength(raw_pw):
            raise HTTPException(400, '비밀번호가 요구사항을 충족하지 않습니다')
        user.set_password(raw_pw)
    else:
        user.set_password(secrets.token_urlsafe(12))

    # 필수: 주민등록번호 저장 (검증 포함)
    try:
        user.set_identification_number(identification_number)
    except Exception:
        raise HTTPException(400, '주민등록번호 형식이 올바르지 않습니다')

    # 보조 필드
    pic = ident_sess.get('picture') or (payload.get('profile_image') or '').strip()
    if pic:
        user.profile_image = pic
    if payload.get('phone'):
        try:
            user.set_phone(payload.get('phone'))
        except Exception:
            pass
    if payload.get('gender') in ('male','female','other', None, ''):
        user.gender = (payload.get('gender') or user.gender)
    user.region_living = payload.get('region_living') or ''
    user.region_active = payload.get('region_active') or ''

    # 선제 중복: 전화번호 충돌
    try:
        if payload.get('phone'):
            p_norm = normalize_phone(payload.get('phone'))
            p_fp = id_fingerprint(p_norm) if p_norm else None
            if p_fp:
                exists_phone = db.query(User.id).filter(User.phone_fingerprint == p_fp).first()
                if exists_phone:
                    raise HTTPException(409, '이미 사용 중인 전화번호입니다')
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '중복된 정보가 있어 가입을 완료할 수 없습니다')

    # 세션 정리 후 토큰 발급
    try:
        request.session.pop('pending_social', None)
    except Exception:
        pass
    claims = {"sub": user.username, "user_id": user.id, "tv": (user.token_version or 0)}
    return JSONResponse({
        "access_token": create_access_token(data=claims),
        "refresh_token": create_refresh_token(data=claims),
        "token_type": "bearer",
        "user_id": user.id
    })


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
