# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import secrets
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.models.user import User
from app.models.email_verification import EmailVerification
from app.schemas.auth import SignUpIn, LoginIn, TokenOut, RefreshTokenIn
from app.services.mailer import send_email, build_verification_email, build_password_reset_email
from app.models.tag import Tag, UserTag
from app.security import (
    create_access_token,
    create_refresh_token,
    validate_password_strength,
    get_password_requirements,
    normalize_phone,
    id_fingerprint,
    get_current_user,
    # encrypt_str,  # unused
)
from app.utils.logging import logger
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ✅ 사전 중복 체크용 (가입과 분리된 GET)
@router.get("/check-duplicates")
def check_duplicates(
    db: Session = Depends(get_db),
    username: str | None = Query(default=None),
    email: str | None = Query(default=None),
    phone: str | None = Query(default=None),
    identification_number: str | None = Query(default=None),
):
    taken = {"username": False, "email": False, "phone": False, "identification_number": False}

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

    if identification_number:
        try:
            ident_norm = normalize_phone(identification_number)
        except Exception:
            ident_norm = None
        if ident_norm:
            fp = id_fingerprint(ident_norm)
            taken["identification_number"] = (
                db.query(User.id).filter(User.identification_fingerprint == fp).first() is not None
            )

    return {"taken": taken}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
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
        # introduction 처리: JSON 문자열이면 파싱해서 bio 부분만 추출
        introduction_text = ""  # 안전한 기본값
        if payload.introduction:
            introduction_text = payload.introduction
            if introduction_text.strip().startswith('{'):
                try:
                    import json
                    intro_data = json.loads(introduction_text)
                    introduction_text = intro_data.get('bio', '') if isinstance(intro_data, dict) else introduction_text
                except (json.JSONDecodeError, AttributeError):
                    # JSON 파싱 실패하면 빈 문자열로 안전하게 처리
                    introduction_text = ""
        
        # 최종 안전 검사
        if not introduction_text:
            introduction_text = ""
        
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
            introduction=introduction_text,  # JSON에서 bio 추출하거나 원본 텍스트
        )
        user.set_password(payload.password)

        if getattr(payload, "identification_number", None):
            user.set_identification_number(payload.identification_number)

        # 전화번호(암호화 + fingerprint)
        user.set_phone(payload.phone)

        db.add(user)
        db.commit()
        db.refresh(user)

        # 태그 저장: introduction이 JSON이면 interests.keywords를 UserTag에 반영
        intro_raw = getattr(payload, 'introduction', None)
        if intro_raw and isinstance(intro_raw, str) and intro_raw.strip().startswith('{'):
            try:
                import json
                parsed = json.loads(intro_raw)
                if isinstance(parsed, dict):
                    interests = (parsed.get('interests') or {})
                    keywords = interests.get('keywords') or []
                    if isinstance(keywords, list) and keywords:
                        from app.core.config import settings as _settings
                        allow_dynamic = bool(getattr(_settings, 'allow_dynamic_tag_create', False))
                        for kw in keywords:
                            if not kw or not isinstance(kw, str):
                                continue
                            _name = kw.strip()
                            if not _name:
                                continue
                            tag = db.query(Tag).filter(Tag.tag == _name).first()
                            if not tag:
                                if not allow_dynamic:
                                    continue  # 동적 생성 비활성: 존재하는 태그만 연결
                                tag = Tag(tag=_name, is_active=True)
                                db.add(tag)
                                db.flush()
                            exists = db.query(UserTag).filter(UserTag.user_id == user.id, UserTag.tag_id == tag.id).first()
                            if not exists:
                                db.add(UserTag(user_id=user.id, tag_id=tag.id))
                        db.commit()
            except Exception:
                # 태그 파싱 실패는 가입 성공에 영향을 주지 않음
                pass

        logger.info(f"회원가입 성공: user_id={user.id}, username={user.username}")

        # 이메일 인증 메일 발송 (설정이 활성화된 경우, 비차단)
        if settings.require_email_verification:
            try:
                from app.services.email import EmailService
                EmailService.send_verification_email(db, user)
                logger.info(f"이메일 인증 메일 발송 완료: user_id={user.id}, email={user.email}")
            except Exception as e:
                logger.error(f"이메일 인증 메일 발송 실패: user_id={user.id}, error={str(e)}")
                # 메일 발송 실패해도 회원가입은 성공으로 처리

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

    # 5) 이메일 인증 정책에 따른 응답
    if settings.require_email_verification:
        return {"message": "가입이 완료되었습니다. 이메일 인증을 완료해 주세요.", "user_id": user.id, "email": user.email}
    else:
        try:
            claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version}
            access_token = create_access_token(data=claims)
            refresh_token = create_refresh_token(data=claims)
            return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
        except Exception as e:
            logger.error(f"토큰 생성 오류: {str(e)}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "토큰 생성에 실패했습니다")


@router.post("/login", response_model=TokenOut)
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
        # 이메일 인증이 안 된 경우와 다른 이유로 비활성화된 경우 구분
        if not user.email_verified:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, 
                detail={
                    "message": "이메일 인증이 필요합니다", 
                    "action": "email_verification_required",
                    "user_id": user.id,
                    "email": user.email
                }
            )
        else:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "비활성화된 계정입니다")

    try:
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        db.refresh(user)

        claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)

        logger.info(f"로그인 성공: user_id={user.id}, username={user.username}, tv={user.token_version}")
        # 기본 JSON 바디
        body = TokenOut(access_token=access_token, refresh_token=refresh_token, token_type="bearer").model_dump()
        # 일반 로그인 시, 기존에 남아있을 수 있는 관리자 모드 쿠키 제거
        # (관리자 로그인이라도 /auth/login은 admin_mode를 설정하지 않음. 필요 시 /admin/mode/on 사용)
        resp = JSONResponse(body)
        try:
            access_cookie = settings.auth_access_cookie_name or "access_token"
            refresh_cookie = settings.auth_refresh_cookie_name or "refresh_token"
            cookie_path = settings.auth_cookie_path or "/"
            cookie_domain = settings.auth_cookie_domain or None
            # admin_mode 쿠키와 동일 키 사용 중이므로 항상 삭제해 일관 보안 유지
            resp.delete_cookie(access_cookie, path=cookie_path, domain=cookie_domain)
            resp.delete_cookie(refresh_cookie, path=cookie_path, domain=cookie_domain)
            resp.delete_cookie("session", path="/")
        except Exception:
            pass
        return resp
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
    """로그아웃 처리: 서버가 설정한 HttpOnly 쿠키도 제거합니다.

    프런트에서는 localStorage/sessionStorage의 토큰을 지우고, 이 엔드포인트는
    remember-me 쿠키(access_token/refresh_token)를 안전하게 삭제합니다.
    """
    access_cookie = settings.auth_access_cookie_name or "access_token"
    refresh_cookie = settings.auth_refresh_cookie_name or "refresh_token"
    cookie_path = settings.auth_cookie_path or "/"
    cookie_domain = settings.auth_cookie_domain or None
    resp = JSONResponse({"message": "로그아웃되었습니다"})
    resp.delete_cookie(access_cookie, path=cookie_path, domain=cookie_domain)
    resp.delete_cookie(refresh_cookie, path=cookie_path, domain=cookie_domain)
    # 호환 키
    resp.delete_cookie("session", path="/")
    return resp


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 반환"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "name": current_user.name,
        "phone": current_user.phone,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }


# ========================
# 이메일 인증 시스템
# ========================

def to_utc_aware(dt):
    """naive/aware datetime을 UTC aware로 변환"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/send-verification-email")
def send_verification_email(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """이메일 인증 코드 전송"""
    
    # 사용자 확인
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "해당 이메일로 등록된 사용자가 없습니다")
    
    # 기존 미사용 토큰 삭제
    db.query(EmailVerification).filter(
        EmailVerification.user_id == user.id,
        EmailVerification.used_at.is_(None)
    ).delete()
    
    # 새 토큰 생성
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes)
    
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=email,
        expires_at=expires_at
    )
    
    db.add(verification)
    db.commit()
    
    # 이메일 전송
    try:
        html, text = build_verification_email(token)
        send_email(
            to=email,
            subject="이메일 인증",
            html=html,
            text=text
        )
        return {"message": "인증 이메일을 발송했습니다"}
    except Exception as e:
        logger.error(f"이메일 전송 실패: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "이메일 전송에 실패했습니다")


@router.get("/verify-email/redirect")
def verify_email_redirect(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    flow: str | None = None,
    return_to: str | None = None,
):
    """이메일 인증 링크 처리 - 성공/실패 페이지로 리디렉트"""
    
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == token,
        EmailVerification.used_at.is_(None)
    ).first()
    
    if not verification:
        return RedirectResponse(url=settings.verify_fail_url)
    
    # 만료 확인
    now_utc = datetime.now(timezone.utc)
    expires_utc = to_utc_aware(verification.expires_at)
    
    if now_utc > expires_utc:
        return RedirectResponse(url=settings.verify_fail_url)
    
    # 인증 처리
    verification.used_at = now_utc
    user = verification.user
    if user:
        user.email_verified = True
        user.is_active = True
    
    db.commit()

    # Determine redirect URL
    dest = settings.verify_success_url
    try:
        from urllib.parse import quote_plus
        if flow == "login":
            base = (settings.front_base_url or '').strip().rstrip('/')
            if not base:
                # derive from request if not configured
                xf_proto = request.headers.get('x-forwarded-proto')
                xf_host = request.headers.get('x-forwarded-host')
                base = (f"{xf_proto}://{xf_host}" if xf_proto and xf_host else str(request.base_url).rstrip('/'))
            dest = f"{base}/login?verified=1"
            if return_to:
                dest += f"&return_to={quote_plus(return_to)}"
        elif return_to:
            sep = '&' if ('?' in dest) else '?'
            dest = f"{dest}{sep}return_to={quote_plus(return_to)}"
    except Exception:
        pass
    return RedirectResponse(url=dest)


@router.post("/verify-email")
def verify_email_api(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """API 방식 이메일 인증"""
    
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == token,
        EmailVerification.used_at.is_(None)
    ).first()
    
    if not verification:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "유효하지 않은 인증 토큰입니다")
    
    # 만료 확인
    now_utc = datetime.now(timezone.utc)
    expires_utc = to_utc_aware(verification.expires_at)
    
    if now_utc > expires_utc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "인증 토큰이 만료되었습니다")
    
    # 인증 처리
    verification.used_at = now_utc
    user = verification.user
    if user:
        user.email_verified = True
        user.is_active = True
    
    db.commit()
    return {"message": "이메일 인증이 완료되었습니다"}


# ========================
# 비밀번호 찾기 시스템
# ========================

@router.post("/request-password-reset")
def request_password_reset(
    payload: dict = Body(...), 
    db: Session = Depends(get_db)
):
    """
    비밀번호 재설정 요청
    Body: { username, name, identification_number, email }
    모든 정보가 일치하면 이메일로 재설정 링크 발송
    """
    username = (payload.get("username") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    identification = (payload.get("identification_number") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    
    if not (username and name and identification and email):
        raise HTTPException(400, "username, name, identification_number, email을 모두 입력해 주세요")

    # 사용자 확인
    user = db.query(User).filter(
        User.username == username, 
        User.name == name, 
        User.email == email
    ).first()
    
    if not user:
        raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")

    # 주민번호 확인
    identification_ok = False
    if user.identification_fingerprint:
        identification_ok = (user.identification_fingerprint == id_fingerprint(identification))
    else:
        try:
            identification_ok = (user.get_identification_number() == identification)
        except Exception:
            identification_ok = False
    
    if not identification_ok:
        raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")

    # 기존 미사용 토큰 삭제
    db.query(EmailVerification).filter(
        EmailVerification.user_id == user.id,
        EmailVerification.used_at.is_(None)
    ).delete()

    # 새 토큰 생성
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes)
    
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=user.email,
        expires_at=expires_at
    )
    
    db.add(verification)
    db.commit()

    # 이메일 전송
    try:
        html, text = build_password_reset_email(token, user.username)
        send_email(
            to=user.email,
            subject="[Challengers] 비밀번호 재설정",
            html=html,
            text=text
        )
        return {"message": "비밀번호 재설정 메일을 보냈습니다. 메일함을 확인해 주세요."}
    except Exception as e:
        logger.error(f"비밀번호 재설정 메일 전송 실패: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "이메일 전송에 실패했습니다")


@router.post("/request-password-reset-by-login")
def request_password_reset_by_login(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """아이디 또는 이메일만으로 비밀번호 재설정 메일 발송 (소셜 병합 플로우 등 최소 입력용)
    Body: { login, flow?, return_to? }
    """
    login = (payload.get("login") or "").strip().lower()
    flow = (payload.get("flow") or None)
    return_to = (payload.get("return_to") or None)
    if not login:
        raise HTTPException(400, "login이 필요합니다")

    user = db.query(User).filter(or_(User.username == login, User.email == login)).first()
    if not user:
        raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")

    # 기존 미사용 토큰 삭제
    db.query(EmailVerification).filter(
        EmailVerification.user_id == user.id,
        EmailVerification.used_at.is_(None)
    ).delete()

    # 새 토큰 생성
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes)
    
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=user.email,
        expires_at=expires_at
    )
    db.add(verification)
    db.commit()

    # 이메일 전송 (flow/return_to 지원)
    try:
        html, text = build_password_reset_email(token, user.username, flow=flow, return_to=return_to)
        send_email(
            to=user.email,
            subject="비밀번호 재설정",
            html=html,
            text=text
        )
        # 마스킹된 이메일도 함께 반환하여 프런트에 안내 표시
        def _mask_email(addr: str) -> str:
            if not addr:
                return ''
            try:
                local, dom = addr.split('@', 1)
            except ValueError:
                return addr
            def m(s: str) -> str:
                if len(s) <= 2:
                    return s[0] + '*'
                return s[:2] + '*' * max(1, len(s)-3) + s[-1]
            parts = dom.split('.')
            head = parts[0]
            tail = '.' + '.'.join(parts[1:]) if len(parts) > 1 else ''
            return f"{m(local)}@{m(head)}{tail}"

        return {
            "message": "비밀번호 재설정 메일을 보냈습니다.",
            "sent_to": user.email,
            "sent_to_masked": _mask_email(user.email),
        }
    except Exception as e:
        logger.error(f"비밀번호 재설정 메일 전송 실패: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "이메일 전송에 실패했습니다")


@router.get("/password-reset/redirect")
def password_reset_redirect(token: str):
    """비밀번호 재설정 링크 클릭 시 프론트엔드로 리디렉트"""
    # 프론트엔드 URL에 토큰을 포함하여 리디렉트
    frontend_url = f"{settings.front_base_url}/login?reset_token={token}"
    return RedirectResponse(url=frontend_url, status_code=303)


@router.get("/verify-remaining")
def verify_remaining(login: str, db: Session = Depends(get_db)):
    """해당 로그인(아이디/이메일)에 대해 사용 가능한 인증/재설정 토큰의 남은 시간을 반환"""
    user = db.query(User).filter(or_(User.username == login.lower(), User.email == login.lower())).first()
    if not user:
        return {"seconds_left": 0}
    ver = db.query(EmailVerification).filter(
        EmailVerification.user_id == user.id,
        EmailVerification.used_at.is_(None)
    ).order_by(EmailVerification.expires_at.desc()).first()
    if not ver:
        return {"seconds_left": 0}
    now_utc = datetime.now(timezone.utc)
    exp = to_utc_aware(ver.expires_at)
    left = int((exp - now_utc).total_seconds())
    return {"seconds_left": max(0, left)}


@router.post("/send-verification-by-login")
def send_verification_by_login(payload: dict = Body(...), db: Session = Depends(get_db)):
    """아이디/이메일로 이메일 인증 메일 발송(로그인 화면용)"""
    login = (payload.get("login") or "").strip().lower()
    if not login:
        raise HTTPException(400, "login이 필요합니다")
    user = db.query(User).filter(or_(User.username == login, User.email == login)).first()
    if not user:
        raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")
    try:
        from app.services.email import EmailService
        EmailService.send_verification_email(db, user)
        return {"message": "인증 이메일이 발송되었습니다"}
    except Exception as e:
        logger.error(f"인증 메일 발송 실패: {e}")
        raise HTTPException(500, "이메일 발송에 실패했습니다")


@router.post("/reset-password")
def reset_password(
    payload: dict = Body(...), 
    db: Session = Depends(get_db)
):
    """
    비밀번호 재설정 실행
    Body: { token, new_password }
    """
    token = (payload.get("token") or "").strip()
    new_password = payload.get("new_password") or ""
    
    if not token or not new_password:
        raise HTTPException(400, "token과 new_password가 필요합니다")
    
    if not validate_password_strength(new_password):
        requirements = get_password_requirements()
        raise HTTPException(400, {
            "message": "비밀번호가 요구사항을 충족하지 않습니다", 
            "requirements": requirements
        })

    # 토큰 확인
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == token,
        EmailVerification.used_at.is_(None)
    ).first()
    
    if not verification:
        raise HTTPException(404, "유효하지 않은 토큰입니다")
    
    # 만료 확인
    now_utc = datetime.now(timezone.utc)
    expires_utc = to_utc_aware(verification.expires_at)
    
    if now_utc > expires_utc:
        raise HTTPException(400, "만료된 토큰입니다")

    # 사용자 확인
    user = db.query(User).get(verification.user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")

    # 비밀번호 변경
    user.set_password(new_password)
    verification.used_at = now_utc
    
    # token_version 업데이트로 기존 토큰들 무효화
    user.token_version = (user.token_version or 0) + 1
    
    db.commit()
    return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요."}


@router.get("/check-duplicates")
def check_duplicates(
    db: Session = Depends(get_db),
    username: str | None = Query(default=None),
    email: str | None = Query(default=None),
    phone: str | None = Query(default=None),
    identification_number: str | None = Query(default=None),
):
    """
    중복 확인
    - username: 소문자 비교
    - email: 소문자 비교
    - phone: 010-11자리 → fingerprint 우선, fallback으로 plain 컬럼 비교
    - identification_number: 13자리 숫자 → fingerprint 우선, fallback으로 복호화 비교
    """
    import re
    from ..security import id_fingerprint
    
    taken = {"username": False, "email": False, "phone": False, "identification_number": False}

    if username:
        taken["username"] = db.query(User.id).filter(User.username == username.lower()).first() is not None

    if email:
        taken["email"] = db.query(User.id).filter(User.email == email.lower()).first() is not None

    if phone:
        s = re.sub(r"\D+", "", phone or "")
        if re.fullmatch(r"010\d{8}", s):
            try:
                fp = id_fingerprint(s)
                if db.query(User.id).filter(User.phone_fingerprint == fp).first() is not None:
                    taken["phone"] = True
                else:
                    norm = f"010-{s[3:7]}-{s[7:11]}"
                    exists_plain = db.query(User.id).filter(User.phone == norm).first() is not None
                    if exists_plain:
                        taken["phone"] = True
            except Exception:
                pass

    if identification_number:
        s = re.sub(r"\D+", "", identification_number or "")
        if re.fullmatch(r"\d{13}", s):
            try:
                fp = id_fingerprint(s)
                taken["identification_number"] = db.query(User.id).filter(User.identification_fingerprint == fp).first() is not None
            except Exception:
                pass

    return {"taken": taken}


@router.get("/identity/last")
def get_last_identity(request: Request):
    """최근 소셜 식별 정보 반환 (세션 키 호환)

    우선 최신 키('pending_social'/'last_social_identity')를 확인하고,
    없으면 구 버전 키 패턴('_social_*_data')를 조회해 반환합니다.
    """
    try:
        # 1) 신규 키 우선
        data = request.session.get("pending_social") or request.session.get("last_social_identity")
        if data and isinstance(data, dict):
            return data

        # 2) 구버전 키 호환: _social_*_data
        for key in list(request.session.keys()):
            if key.startswith("_social_") and key.endswith("_data"):
                social_data = request.session.get(key)
                if social_data and isinstance(social_data, dict):
                    # 가능한 경우 표준 키로도 저장해 후속 요청에서 일관되게 참조
                    try:
                        request.session["last_social_identity"] = social_data
                    except Exception:
                        pass
                    return social_data
        return {}
    except Exception:
        return {}


@router.post("/send-email-verification")
def send_email_verification(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """이메일 인증 발송"""
    # 템플릿에서 user_id를 보내는 경우와 email을 직접 보내는 경우 모두 지원
    email = payload.get("email")
    user_id = payload.get("user_id")
    
    if email:
        # 이메일이 직접 제공된 경우
        target_email = email
    elif user_id:
        # user_id가 제공된 경우 해당 사용자의 이메일 찾기
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "사용자를 찾을 수 없습니다")
        target_email = user.email
    else:
        raise HTTPException(400, "이메일 또는 user_id가 필요합니다")
    
    try:
        from app.services.email import EmailService
        # 실제 사용자가 있는 경우 해당 사용자로, 없으면 이메일로만 발송
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                EmailService.send_verification_email(db, user)
            else:
                EmailService.send_verification_email_direct(db, target_email)
        else:
            EmailService.send_verification_email_direct(db, target_email)
        return {"message": "인증 이메일이 발송되었습니다"}
    except Exception as e:
        logger.error(f"이메일 인증 발송 실패: {str(e)}")
        raise HTTPException(500, "이메일 발송에 실패했습니다")
