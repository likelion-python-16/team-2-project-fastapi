from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import re, secrets
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.models.user import User
from app.models.email_verification import EmailVerification
from app.schemas.auth import SignUpIn, LoginIn, TokenOut, RefreshTokenIn
from app.security import (
    create_access_token,
    create_refresh_token,
    validate_password_strength,
    get_password_requirements,
)
from app.services.mailer import send_email, build_verification_email, build_password_reset_email
from app.security import id_fingerprint, normalize_phone, validate_password_strength
from app.utils.logging import logger
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

DEFAULT_PROFILE_IMAGE = "/static/pictures/defaultprofile.jpeg"

# ========================
# naive/aware 보정 유틸
# ========================
def to_utc_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:               # naive -> aware(UTC)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)   # aware -> UTC 정규화

# ------------------------
# 중복 확인
# ------------------------
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
    taken = {"username": False, "email": False, "phone": False, "identification_number": False}

    if username:
        taken["username"] = db.query(User.id).filter(User.username == username.lower()).first() is not None

    if email:
        taken["email"] = db.query(User.id).filter(User.email == email.lower()).first() is not None

    if phone:
        s = re.sub(r"\D+", "", phone or "")
        if re.fullmatch(r"010\d{8}", s):
            # fingerprint 우선
            try:
                fp = id_fingerprint(s)
                if db.query(User.id).filter(User.phone_fingerprint == fp).first() is not None:
                    taken["phone"] = True
                else:
                    # 레거시 plain 컬럼도 체크
                    norm = f"010-{s[3:7]}-{s[7:11]}"
                    exists_plain = db.query(User.id).filter(User.phone == norm).first() is not None
                    if exists_plain:
                        taken["phone"] = True
                    else:
                        # fallback 2: 암호화 컬럼 복호화 비교( fingerprint/plain 모두 없는 레거시 데이터 대비 )
                        try:
                            users = db.query(User).filter(User.phone_encrypted.isnot(None)).limit(5000).all()
                            for u in users:
                                try:
                                    p = u.get_phone()
                                    if p and re.sub(r"\D+", "", p) == s:
                                        taken["phone"] = True
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            pass
            except Exception:
                pass

    if identification_number:
        d = re.sub(r"\D+", "", identification_number or "")
        if re.fullmatch(r"\d{13}", d):
            # fingerprint 우선
            try:
                fp = id_fingerprint(d)
                found = db.query(User.id).filter(User.identification_fingerprint == fp).first()
                if found is not None:
                    taken["identification_number"] = True
                else:
                    # fallback: 복호화 비교(지문이 없는 레거시 데이터 대비)
                    candidates = db.query(User).filter(User.identification_number.isnot(None)).limit(5000).all()
                    for u in candidates:
                        try:
                            plain = u.get_identification_number()
                            if plain and re.sub(r"\D+", "", plain) == d:
                                taken["identification_number"] = True
                                break
                        except Exception:
                            continue
            except Exception:
                pass

    return {"taken": taken}

# ------------------------
# 회원가입
# ------------------------
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpIn, db: Session = Depends(get_db)):
    if not validate_password_strength(payload.password):
        requirements = get_password_requirements()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "비밀번호가 요구사항을 충족하지 않습니다", "requirements": requirements},
        )

    username = payload.username.lower()
    email = str(payload.email).lower()

    # 중복 항목 개별 확인
    dup_username = db.query(User.id).filter(User.username == username).first() is not None
    dup_email = db.query(User.id).filter(User.email == email).first() is not None
    dup_phone = False
    if payload.phone:
        try:
            # 우선 fingerprint 기준으로 중복 확인 (신규 저장 정책)
            digits = normalize_phone(payload.phone)
            if digits and len(digits) == 11 and digits.startswith('010'):
                fp = id_fingerprint(digits)
                if db.query(User.id).filter(User.phone_fingerprint == fp).first() is not None:
                    dup_phone = True
                else:
                    # 레거시: plain 컬럼(010-1234-5678)도 확인
                    dup_phone = db.query(User.id).filter(User.phone == payload.phone).first() is not None
        except Exception:
            # 포맷/지문 오류 시엔 보수적으로 plain만 확인
            dup_phone = db.query(User.id).filter(User.phone == payload.phone).first() is not None
    if dup_username or dup_email or dup_phone:
        detail = {
            "message": "중복된 항목이 있습니다",
            "fields": {"username": dup_username, "email": dup_email, "phone": dup_phone}
        }
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail)

    try:
        profile_image_value = (payload.profile_image or "").strip() or DEFAULT_PROFILE_IMAGE
        user = User(
            username=username,
            email=email,
            name=(payload.name or username),
            phone=None,  # 전화번호는 set_phone에서 암호화/지문 처리
            gender=(payload.gender or "other"),
            region_living=(payload.region_living or ""),
            region_active=(payload.region_active or ""),
            profile_image=profile_image_value,
            introduction=(payload.introduction or ""),
            email_verified=False,
            is_active=False,
        )
        user.set_password(payload.password)
        user.set_identification_number(payload.identification_number)
        # 전화번호 암호화 저장 + fingerprint
        try:
            if payload.phone:
                user.set_phone(payload.phone)
        except Exception:
            pass

        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 태그 처리: introduction이 JSON 형태면 파싱해서 UserTag 테이블에 저장
        intro_data = payload.introduction or ""
        if intro_data:
            try:
                import json
                from app.models.tag import Tag, UserTag
                parsed = json.loads(intro_data)
                if isinstance(parsed, dict) and 'interests' in parsed:
                    keywords = parsed.get('interests', {}).get('keywords', [])
                    # bio만 introduction에 저장
                    user.introduction = parsed.get('bio', '').strip()
                    
                    # 태그들을 UserTag 테이블에 저장
                    for keyword in keywords:
                        if keyword and isinstance(keyword, str):
                            keyword = keyword.strip()
                            # 태그가 존재하지 않으면 생성
                            tag = db.query(Tag).filter(Tag.tag == keyword).first()
                            if not tag:
                                tag = Tag(tag=keyword, is_active=True)
                                db.add(tag)
                                db.commit()
                                db.refresh(tag)
                            
                            # 중복 방지: 이미 연결되어 있지 않으면 UserTag 생성
                            existing = db.query(UserTag).filter(UserTag.user_id == user.id, UserTag.tag_id == tag.id).first()
                            if not existing:
                                user_tag = UserTag(user_id=user.id, tag_id=tag.id)
                                db.add(user_tag)
                    
                    db.commit()
            except (json.JSONDecodeError, Exception):
                # JSON 파싱 실패 시 그냥 텍스트로 저장
                pass
        
        logger.info(f"회원가입(미인증) 생성: user_id={user.id}, username={user.username}")

        # 정책: 이메일 인증 요구 여부
        if settings.require_email_verification:
            # 인증 메일 + 토큰(만료시간)
            token = secrets.token_urlsafe(48)
            ev = EmailVerification(
                user_id=user.id,
                token=token,
                sent_to=user.email.lower(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes),
            )
            db.add(ev)
            db.commit()

            html, text = build_verification_email(token)
            send_email(user.email, "[Challengers] 이메일 인증", html, text)

            return {
                "message": "가입이 완료되었습니다. 이메일 인증을 완료하면 로그인할 수 있어요.",
                "verify": {"sent_to": user.email},
            }
        else:
            # 인증 없이 즉시 활성화 + 토큰 발급
            user.email_verified = True
            user.is_active = True
            db.commit(); db.refresh(user)
            claims = {"sub": user.username, "user_id": user.id, "tv": (user.token_version or 0)}
            access_token = create_access_token(data=claims)
            refresh_token = create_refresh_token(data=claims)
            return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    except IntegrityError as e:
        db.rollback()
        logger.warning(f"회원가입 DB 무결성 오류: {str(e)}")
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용 중인 사용자명/이메일/전화번호가 있습니다")
    except ValueError as e:
        db.rollback()
        logger.error(f"회원가입 검증 오류: {str(e)}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"회원가입 오류: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "서버 오류가 발생했습니다")

# ------------------------
# 이메일 인증 처리 (used_at 플래그 사용)
# ------------------------
@router.get("/verify-email/redirect")
def verify_email_redirect(token: str, db: Session = Depends(get_db)):
    ver = db.query(EmailVerification).filter_by(token=token).first()
    if not ver:
        return RedirectResponse(settings.verify_fail_url + "?reason=invalid_token", status_code=303)

    # 이미 사용됨
    if ver.used_at:
        return RedirectResponse(settings.verify_fail_url + "?reason=used", status_code=303)

    # 만료 체크
    now_utc = datetime.now(timezone.utc)
    exp_utc = to_utc_aware(ver.expires_at)
    if exp_utc and exp_utc < now_utc:
        return RedirectResponse(settings.verify_fail_url + "?reason=expired", status_code=303)

    user = db.query(User).get(ver.user_id)
    if not user:
        return RedirectResponse(settings.verify_fail_url + "?reason=user_not_found", status_code=303)

    # 이메일이 변경된 경우(토큰 발급 당시 주소와 현재 계정 이메일이 다름) 무효 처리
    current_email = (user.email or "").strip().lower()
    token_email = (ver.sent_to or "").strip().lower()
    if current_email != token_email:
        return RedirectResponse(settings.verify_fail_url + "?reason=email_changed", status_code=303)

    user.email_verified = True
    user.is_active = True
    ver.used_at = now_utc          # ✅ 삭제하지 말고 사용 처리만
    db.commit()

    return RedirectResponse(settings.verify_success_url, status_code=303)

# (토큰 기반 재전송 엔드포인트는 사용하지 않음 – 원상복구)

# ------------------------
# 로그인
# ------------------------
@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        or_(User.username == payload.login, User.email == payload.login)
    ).first()

    if not user or not user.verify_password(payload.password):
        logger.warning(f"로그인 실패 시도: login={payload.login}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다")

    if settings.require_email_verification and not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "EMAIL_NOT_VERIFIED", "message": "이메일 인증이 필요합니다."},
        )
    if not user.is_active:
        # 관리자 권한 신청 중인 상태 확인
        from app.models.admin_request import AdminRequest
        pending_request = db.query(AdminRequest).filter(
            AdminRequest.user_id == user.id,
            AdminRequest.status == "pending"
        ).first()
        
        if pending_request:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, 
                detail="승인 절차 중입니다. 좀 더 기다려주세요."
            )
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="비활성화된 계정입니다.")

    try:
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        db.refresh(user)

        claims = {"sub": user.username, "user_id": user.id, "tv": user.token_version}
        access_token = create_access_token(data=claims)
        refresh_token = create_refresh_token(data=claims)
        logger.info(f"로그인 성공: user_id={user.id}, username={user.username}, tv={user.token_version}")
        
        # JSON 응답에 쿠키도 설정 (듀얼 인증 지원)
        response_data = {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
        response = JSONResponse(content=response_data)
        
        # HttpOnly 쿠키 설정으로 세션 유지
        # 운영(HTTPS)에서는 Secure 쿠키, 로컬 개발에서는 비보안 쿠키
        from app.core.config import settings as _settings
        secure_flag = not _settings.debug
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=secure_flag,
            samesite="lax",
            max_age=settings.jwt_access_token_expire_minutes * 60,
            path="/",
        )
        return response
    except Exception as e:
        db.rollback()
        logger.error(f"로그인 처리/토큰 생성 오류: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "토큰 생성에 실패했습니다")

# ------------------------
# 아이디 찾기
# ------------------------
def _mask_username(username: str) -> str:
    if not username:
        return username
    n = len(username)
    if n <= 2:
        return "*" * n
    if n <= 4:
        return username[0] + ("*" * (n-2)) + username[-1]
    # 기본: 앞2 + *... + 뒤2
    return username[:2] + ("*" * (n-4)) + username[-2:]

def _email_hint(email: str) -> str:
    """이메일 제공자 힌트(도메인 앞부분 2글자 + ***). 예: gmail.com -> gm***, naver.com -> na***"""
    if not email or '@' not in email:
        return None
    try:
        domain = str(email).strip().lower().split('@', 1)[1]
        provider = domain.split('.', 1)[0]
        if not provider:
            return None
        head = provider[:2]
        return f"{head}***"
    except Exception:
        return None

def _email_masked(email: str) -> str | None:
    """전체 이메일 마스킹
    - local: 앞 3글자 + *** + 끝 1글자(길이에 따라 가변)
    - domain: 제공자 앞 2글자 + **** + .com  (예: hotmail.com -> ho****.com, naver.com -> na****.com)
    예) chrislee2@hotmail.com -> chr***2@ho****.com
    """
    if not email or '@' not in email:
        return None
    try:
        email = str(email).strip().lower()
        local, domain = email.split('@', 1)
        parts = domain.split('.')
        provider = parts[0] if parts else ''

        # local masking
        n = len(local)
        if n <= 1:
            local_masked = local + '***'
        elif n == 2:
            local_masked = local[0] + '***'
        elif n == 3:
            local_masked = local[:2] + '*'
        elif n == 4:
            local_masked = local[:2] + '**' + local[-1]
        else:
            local_masked = local[:3] + '***' + local[-1]

        # provider 앞 2글자 + **** + .com 형태로 고정
        head = provider[:2]
        domain_masked = f"{head}****.com"
        return f"{local_masked}@{domain_masked}"
    except Exception:
        return None

@router.post("/match-existing-social")
def match_existing_social(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    소셜 가입 1단계에서 기존 계정 존재 여부 판단용.
    입력:
      - name (선택)
      - phone (선택, 010-11자리)
      - identification (선택, 주민번호 13자리 숫자)

    반환:
      {
        by_name_phone: bool,
        by_name_ident: bool,
        by_phone_ident: bool,
        by_ident_only: bool,
        username_masked: str | null,
        email_hint: str | null,
        email_masked: str | null,
      }
    """
    name = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    ident = (payload.get("identification") or "").strip()

    # normalize phone
    phone_norm = None
    phone_fp = None
    if phone:
        s = normalize_phone(phone)
        if s and len(s) == 11 and s.startswith("010"):
            phone_norm = s
            phone_fp = id_fingerprint(s)

    # normalize identification (13 digits)
    ident_digits = None
    ident_fp = None
    if ident:
        d = normalize_phone(ident)  # 숫자만
        if d and len(d) == 13:
            ident_digits = d
            ident_fp = id_fingerprint(d)

    by_name_phone = False
    by_name_ident = False
    by_phone_ident = False
    by_ident_only = False
    masked = None
    email_hint = None
    email_masked = None

    # name 기반 후보
    candidates = []
    if name:
        candidates = db.query(User).filter(func.lower(User.name) == func.lower(name)).all()

    def _phone_matches(u: User) -> bool:
        if not (phone_norm or phone_fp):
            return False
        # fingerprint 우선
        if getattr(u, 'phone_fingerprint', None) and phone_fp:
            if u.phone_fingerprint == phone_fp:
                return True
        # plain(phone)
        p = (u.phone or '')
        if p:
            if normalize_phone(p) == phone_norm:
                return True
        # decrypt(phone_encrypted)
        try:
            dp = u.get_phone()
            if dp and normalize_phone(dp) == phone_norm:
                return True
        except Exception:
            pass
        return False

    def _ident_matches(u: User) -> bool:
        if not (ident_digits or ident_fp):
            return False
        if getattr(u, 'identification_fingerprint', None) and ident_fp:
            if u.identification_fingerprint == ident_fp:
                return True
        try:
            di = u.get_identification_number()
            if di and normalize_phone(di) == ident_digits:
                return True
        except Exception:
            pass
        return False

    # name + phone
    if candidates and (phone_norm or phone_fp):
        for u in candidates:
            if _phone_matches(u):
                by_name_phone = True
                masked = _mask_username(u.username)
                email_hint = _email_hint(u.email)
                email_masked = _email_masked(u.email)
                break

    # name + identification
    if not masked and candidates and (ident_digits or ident_fp):
        for u in candidates:
            if _ident_matches(u):
                by_name_ident = True
                masked = _mask_username(u.username)
                email_hint = _email_hint(u.email)
                email_masked = _email_masked(u.email)
                break

    # phone + identification (강한 충돌)
    if (phone_norm or phone_fp) and (ident_digits or ident_fp):
        # 후보: 전화로 1차 좁히기
        q = db.query(User)
        if phone_fp:
            q = q.filter(User.phone_fingerprint == phone_fp)
        else:
            # fallback: plain column 비교
            norm_str = f"010-{phone_norm[3:7]}-{phone_norm[7:]}" if phone_norm and len(phone_norm) == 11 else None
            if norm_str:
                q = q.filter(User.phone == norm_str)
        phone_list = q.all()
        found = None
        for u in phone_list:
            if _ident_matches(u):
                by_phone_ident = True
                found = u
                break
        # 안전 범위에서 힌트 제공: 단일 매치 시 마스킹 정보 포함
        if found and not masked:
            try:
                masked = _mask_username(found.username)
                email_hint = _email_hint(getattr(found, 'email', None))
                email_masked = _email_masked(getattr(found, 'email', None))
            except Exception:
                pass

    # identification only (강한 충돌) — 이름/전화 없이 주민번호만 일치
    if (ident_digits or ident_fp) and not (by_name_ident or by_phone_ident):
        cand = None
        if ident_fp:
            cand = db.query(User).filter(User.identification_fingerprint == ident_fp).first()
        if not cand:
            # fallback: 복호화 비교
            users = db.query(User).filter(User.identification_number.isnot(None)).limit(5000).all()
            for u in users:
                try:
                    plain = u.get_identification_number()
                    if plain and normalize_phone(plain) == ident_digits:
                        cand = u; break
                except Exception:
                    continue
        if cand:
            by_ident_only = True
            if not masked:
                masked = _mask_username(cand.username)
                email_hint = _email_hint(getattr(cand, 'email', None))
                email_masked = _email_masked(getattr(cand, 'email', None))

    return {
        "by_name_phone": by_name_phone,
        "by_name_ident": by_name_ident,
        "by_phone_ident": by_phone_ident,
        "username_masked": masked,
        "by_ident_only": by_ident_only,
        "email_hint": email_hint,
        "email_masked": email_masked,
    }

@router.post("/find-username")
def find_username(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    Body: { name, identification, contact }
    - contact: 휴대폰번호 또는 이메일 둘 중 하나
    모두 일치하는 계정의 username을 반환. 없으면 404.
    """
    name = (payload.get("name") or "").strip()
    ident = (payload.get("identification") or "").strip()
    contact = (payload.get("contact") or "").strip().lower()
    if not (name and ident and contact):
        raise HTTPException(400, "name, identification, contact를 모두 입력해 주세요")

    # 이메일/전화 분기
    is_email = '@' in contact
    phone_norm = normalize_phone(contact) if not is_email else None
    phone_fp = id_fingerprint(phone_norm) if phone_norm else None
    ident_digits = normalize_phone(ident)  # 숫자만 추출 (dash 제거)
    if not ident_digits or len(ident_digits) != 13:
        raise HTTPException(400, "주민번호는 13자리 숫자여야 합니다")
    ident_fp = id_fingerprint(ident_digits)

    # 간단 이메일/전화 형식 검증
    if is_email:
        import re as _re
        if not _re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", contact):
            raise HTTPException(400, "이메일 형식이 올바르지 않습니다")
    else:
        if not phone_norm or len(phone_norm) != 11 or not phone_norm.startswith('010'):
            raise HTTPException(400, "전화번호는 010으로 시작하는 11자리여야 합니다")

    # 이름은 대소문자 구분 없이 매칭
    q = db.query(User).filter(func.lower(User.name) == func.lower(name))
    candidates = q.all()
    for u in candidates:
        ok_ident = False
        if u.identification_fingerprint:
            ok_ident = (u.identification_fingerprint == ident_fp)
        else:
            try:
                plain = u.get_identification_number()  # 저장된 값은 숫자 13자리
                ok_ident = (plain == ident_digits)
            except Exception:
                ok_ident = False
        if not ok_ident:
            continue

        # 연락처/이메일 일치 여부 확인
        ok_contact = False
        if is_email:
            ok_contact = (str(u.email or '').strip().lower() == contact)
        else:
            # 우선 fingerprint → plain(phone) → 복호화(phone_encrypted)
            if u.phone_fingerprint and phone_fp:
                ok_contact = (u.phone_fingerprint == phone_fp)
            if not ok_contact:
                db_plain = (u.phone or '')
                if db_plain:
                    ok_contact = (normalize_phone(db_plain) == phone_norm)
            if not ok_contact:
                try:
                    p = u.get_phone()
                    if p:
                        ok_contact = (normalize_phone(p) == phone_norm)
                except Exception:
                    ok_contact = False

        if ok_contact:
            return {"username": _mask_username(u.username)}
    raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")

# ------------------------
# 비밀번호 재설정 요청(메일 발송)
# ------------------------
@router.post("/request-password-reset")
def request_password_reset(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    Body: { username, name, identification, email }
    모두 일치 시 해당 이메일로 재설정 링크 발송.
    """
    username = (payload.get("username") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    ident = (payload.get("identification") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    if not (username and name and ident and email):
        raise HTTPException(400, "username, name, identification, email을 모두 입력해 주세요")

    user = db.query(User).filter(User.username == username, User.name == name, User.email == email).first()
    if not user:
        raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")

    # 주민번호 확인
    ok_ident = False
    if user.identification_fingerprint:
        ok_ident = (user.identification_fingerprint == id_fingerprint(ident))
    else:
        try:
            ok_ident = (user.get_identification_number() == ident)
        except Exception:
            ok_ident = False
    if not ok_ident:
        raise HTTPException(404, "해당 정보를 가진 계정을 찾을 수 없습니다")

    # 토큰 발급 & 메일 발송
    token = secrets.token_urlsafe(48)
    ev = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=user.email,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes),
    )
    db.add(ev); db.commit()
    flow = (payload.get("flow") or "").strip() or None
    return_to = (payload.get("return_to") or "").strip() or None
    # 안전 위하여 내부 경로만 허용 (http, // 등 시작 제거)
    if return_to and not return_to.startswith('/'):
        return_to = None
    html, text = build_password_reset_email(token, user.username, flow, return_to)
    send_email(user.email, "[Challengers] 비밀번호 재설정", html, text)
    return {"message": "비밀번호 재설정 메일을 보냈습니다. 메일함을 확인해 주세요."}

# ------------------------
# 비밀번호 재설정 수행
# ------------------------
@router.post("/reset-password")
def reset_password(payload: dict = Body(...), db: Session = Depends(get_db)):
    token = (payload.get("token") or "").strip()
    new_password = payload.get("new_password") or ""
    if not token or not new_password:
        raise HTTPException(400, "token과 new_password가 필요합니다")
    if not validate_password_strength(new_password):
        raise HTTPException(400, "비밀번호가 요구사항을 충족하지 않습니다")

    ver = db.query(EmailVerification).filter(EmailVerification.token == token).first()
    if not ver:
        raise HTTPException(404, "유효하지 않은 토큰입니다")
    if ver.used_at:
        raise HTTPException(400, "이미 사용된 토큰입니다")
    now_utc = datetime.now(timezone.utc)
    exp_utc = to_utc_aware(ver.expires_at)
    if exp_utc and exp_utc < now_utc:
        raise HTTPException(400, "만료된 토큰입니다")

    user = db.query(User).get(ver.user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")

    user.set_password(new_password)
    ver.used_at = now_utc
    db.commit()
    return {"message": "비밀번호가 변경되었습니다. 로그인해 주세요."}

# ------------------------
# 토큰 갱신 / 로그아웃
# ------------------------
@router.post("/refresh", response_model=TokenOut)
def refresh_token(payload: RefreshTokenIn, db: Session = Depends(get_db)):
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
def logout(request: Request):
    """브라우저 폼에서 호출되는 로그아웃: 쿠키 제거 후 관리자 로그인으로 이동."""
    resp = RedirectResponse(url="/admin/login", status_code=303)
    # access_token 쿠키 제거로 세션 정리
    try:
        resp.delete_cookie("access_token", path="/")
    except Exception:
        pass
    return resp

# ------------------------
# 인증 메일 재전송 (email 직접)
# ------------------------
@router.post("/send-verification")
def resend_verification(
    email: str = Body(..., embed=True, description="가입한 이메일 주소"),
    db: Session = Depends(get_db),
):
    email = (email or "").strip().lower()
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일을 입력하세요")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": "인증 메일이 발송되었습니다. 메일함을 확인하세요."}

    if user.email_verified:
        return {"message": "이미 이메일 인증이 완료된 계정입니다. 로그인해 주세요."}

    # 기존 미사용 토큰은 남겨둬도 무방하나, 여기선 정리
    db.query(EmailVerification).filter(EmailVerification.user_id == user.id).delete()

    token = secrets.token_urlsafe(48)
    ev = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=user.email,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes),
    )
    db.add(ev)
    db.commit()

    html, text = build_verification_email(token)
    send_email(user.email, "[Challengers] 이메일 인증 재전송", html, text)

    now_utc = datetime.now(timezone.utc)
    exp_utc = to_utc_aware(ev.expires_at)
    seconds_left = max(0, int((exp_utc - now_utc).total_seconds())) if exp_utc else 0

    return {
        "message": "인증 메일이 재전송되었습니다. 메일함(스팸함 포함)을 확인하세요.",
        "seconds_left": seconds_left,
        "expires_at": exp_utc.isoformat() if exp_utc else None,
    }

# ------------------------
# 인증 메일 재전송 (login = 아이디 or 이메일)
# ------------------------
@router.post("/send-verification-by-login")
def resend_verification_by_login(
    login: str = Body(..., embed=True, description="아이디 또는 이메일"),
    db: Session = Depends(get_db),
):
    login = (login or "").strip().lower()
    if not login:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "아이디 또는 이메일을 입력하세요")

    user = db.query(User).filter(or_(User.username == login, User.email == login)).first()
    if not user:
        return {"message": "인증 메일이 발송되었습니다. 메일함을 확인하세요."}

    if user.email_verified:
        return {"message": "이미 이메일 인증이 완료된 계정입니다. 로그인해 주세요."}

    db.query(EmailVerification).filter(EmailVerification.user_id == user.id).delete()

    token = secrets.token_urlsafe(48)
    ev = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=user.email,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes),
    )
    db.add(ev)
    db.commit()

    html, text = build_verification_email(token)
    send_email(user.email, "[Challengers] 이메일 인증 재전송", html, text)

    now_utc = datetime.now(timezone.utc)
    exp_utc = to_utc_aware(ev.expires_at)
    seconds_left = max(0, int((exp_utc - now_utc).total_seconds())) if exp_utc else 0

    return {
        "message": "인증 메일이 재전송되었습니다. 메일함(스팸함 포함)을 확인하세요.",
        "seconds_left": seconds_left,
        "expires_at": exp_utc.isoformat() if exp_utc else None,
    }

# ------------------------
# 남은 시간 조회 (login 또는 email 모두 허용)
# ------------------------
@router.get("/verify-remaining")
def verify_remaining(
    login: str | None = Query(default=None, description="아이디 또는 이메일"),
    email: str | None = Query(default=None, description="(하위호환) 이메일"),
    db: Session = Depends(get_db),
):
    key = (login or email or "").strip().lower()
    if not key:
        return {"seconds_left": 0, "expires_at": None}

    user = db.query(User).filter(or_(User.username == key, User.email == key)).first()
    if not user or user.email_verified:
        return {"seconds_left": 0, "expires_at": None}

    ev = (
        db.query(EmailVerification)
        .filter(EmailVerification.user_id == user.id)
        .order_by(EmailVerification.expires_at.desc())
        .first()
    )
    if not ev or not ev.expires_at:
        return {"seconds_left": 0, "expires_at": None}

    now_utc = datetime.now(timezone.utc)
    exp_utc = to_utc_aware(ev.expires_at)
    seconds_left = max(0, int((exp_utc - now_utc).total_seconds())) if exp_utc else 0

    return {"seconds_left": seconds_left, "expires_at": exp_utc.isoformat() if exp_utc else None}

# ------------------------
# ✅ 이메일 수정 + 재전송 (새로 추가된 최종 엔드포인트)
# ------------------------
@router.post("/update-email")
def update_email(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    Body: { login, current_password, new_email }
    login은 아이디 또는 현재 이메일.
    """
    login = (payload.get("login") or "").strip().to_lower() if hasattr(str, "to_lower") else (payload.get("login") or "").strip().lower()
    current_password = payload.get("current_password") or ""
    new_email = (payload.get("new_email") or "").strip().lower()

    if not login or not current_password or not new_email:
        raise HTTPException(400, "login, current_password, new_email이 모두 필요합니다")

    user = db.query(User).filter(or_(User.username == login, User.email == login)).first()
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")

    # 소셜 연동 계정은 이메일 변경 금지(안전 정책)
    if getattr(user, 'provider', None) and getattr(user, 'provider_id', None):
        raise HTTPException(403, "소셜 연동 계정은 이메일을 변경할 수 없습니다")

    if not user.verify_password(current_password):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다")

    if db.query(User.id).filter(User.email == new_email, User.id != user.id).first():
        raise HTTPException(409, "이미 사용 중인 이메일입니다")

    # 이메일 변경
    user.email = new_email
    user.email_verified = False
    user.is_active = False
    db.commit(); db.refresh(user)

    # 새 토큰 발급 및 발송
    # 이전에 발급된 모든 인증 토큰은 무효화(삭제)
    db.query(EmailVerification).filter(EmailVerification.user_id == user.id).delete()
    db.commit()
    token = secrets.token_urlsafe(48)
    ev = EmailVerification(
        user_id=user.id,
        token=token,
        sent_to=user.email.lower(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.email_token_expire_minutes),
    )
    db.add(ev)
    db.commit()

    html, text = build_verification_email(token)
    send_email(user.email, "[Challengers] 이메일 인증", html, text)

    return {"message": "이메일이 변경되었고 인증 메일을 보냈습니다.", "sent_to": user.email}

# ------------------------
# 프론트 URL 유틸 (프록시/배포 환경 대응)
# ------------------------
def _front_base_from_request(request: Request) -> str:
    base = (settings.front_base_url or '').strip().rstrip('/')
    if base:
        return base
    # 헤더로부터 유추 (X-Forwarded-Proto/Host)
    xf_proto = request.headers.get('x-forwarded-proto')
    xf_host = request.headers.get('x-forwarded-host')
    if xf_proto and xf_host:
        return f"{xf_proto}://{xf_host}"
    # 기본: 현재 요청 기준
    u = str(request.base_url).rstrip('/')
    return u

# ------------------------
# 비밀번호 재설정 링크 → 프론트로 리디렉션
# ------------------------
@router.get('/password-reset/redirect')
def password_reset_redirect(token: str, request: Request, flow: str | None = None, return_to: str | None = None):
    base = _front_base_from_request(request)
    from urllib.parse import quote_plus
    parts = []
    if flow:
        parts.append(f"flow={quote_plus(flow)}")
    if return_to:
        # 내부 경로만 허용
        if return_to.startswith('/'):
            parts.append(f"return_to={quote_plus(return_to)}")
    qs = ("&"+"&".join(parts)) if parts else ""
    url = f"{base}/login?reset_token={quote_plus(token)}{qs}"
    return RedirectResponse(url, status_code=303)
