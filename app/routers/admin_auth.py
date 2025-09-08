from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.security import create_access_token, verify_password, hash_password, id_fingerprint, normalize_phone, get_current_user
from app.core.deps import get_current_user_from_cookie

router = APIRouter(prefix="/admin", tags=["admin-auth"])

# Template setup
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent  # app/routers -> app
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _issue_cookie_token(user: User, admin_mode: bool, minutes: int | None = None) -> str:
    payload = {
        "sub": str(user.id),
        "admin_mode": bool(admin_mode),
        "tv": int(getattr(user, "token_version", 0) or 0),
    }
    expire_min = minutes if minutes is not None else settings.jwt_access_token_expire_minutes
    return create_access_token(payload, expires_delta=timedelta(minutes=expire_min))


@router.get("/choice", response_class=HTMLResponse)
def admin_login_choice_page(
    request: Request,
    status: str = None,
    user_id: int = None,
    db: Session = Depends(get_db),
):
    """관리자 로그인 선택 페이지.

    status=check 이고 user_id가 있으면 최근 관리자 신청 상태를 표시.
    """
    context = {"request": request}
    if status == "check" and user_id:
        from app.models.admin_request import AdminRequest
        from app.models.user import User as _U
        try:
            user = db.query(_U).filter(_U.id == user_id).first()
            if user:
                admin_request = (
                    db.query(AdminRequest)
                    .filter(AdminRequest.user_id == user_id)
                    .order_by(AdminRequest.created_at.desc())
                    .first()
                )
                if admin_request:
                    if admin_request.status == "pending":
                        context.update({
                            "status_message": "관리자 신청이 검토 중입니다",
                            "status_type": "pending",
                            "message_detail": "신청해주신 관리자 권한이 현재 검토 중입니다. 승인까지 조금만 기다려 주세요.",
                        })
                    elif admin_request.status == "rejected":
                        context.update({
                            "status_message": "관리자 신청이 거절되었습니다",
                            "status_type": "rejected",
                            "message_detail": "신청하신 관리자 권한이 거절되었습니다. 자세한 사항은 관리자에게 문의해주세요.",
                        })
                    elif admin_request.status == "approved":
                        context.update({
                            "status_message": "관리자 권한이 승인되었습니다",
                            "status_type": "approved",
                            "message_detail": "관리자 권한이 승인되었습니다. 다시 로그인해주세요.",
                        })
                else:
                    context.update({
                        "status_message": "관리자가 아니신가요?",
                        "status_type": "no_request",
                        "message_detail": "관리자 권한 신청을 통해 관리자로 등록하실 수 있습니다.",
                    })
        except Exception:
            context.update({
                "status_message": "관리자가 아니신가요?",
                "status_type": "error",
                "message_detail": "관리자 권한 확인 중 오류가 발생했습니다.",
            })
    return templates.TemplateResponse("admin_login_choice.html", context)


@router.get("/login", response_class=HTMLResponse)
def admin_login_page(request: Request, db: Session = Depends(get_db)):
    # 이미 관리자로 로그인되어 있으면 로그아웃 처리
    try:
        from app.core.deps import get_current_user_from_cookie
        current_user = get_current_user_from_cookie(request, db)
        if current_user:
            # 이미 로그인되어 있으면 자동 로그아웃 (관리자든 일반 유저든)
            response = RedirectResponse(url="/admin/login", status_code=303)
            try:
                response.delete_cookie(
                    key=(settings.auth_access_cookie_name or "access_token"),
                    path=(settings.auth_cookie_path or "/"),
                    domain=(settings.auth_cookie_domain or None),
                )
            except Exception:
                response.delete_cookie("access_token", path="/")
            return response
    except Exception:
        pass
    
    # superadmin이 존재하면 회원가입 비활성화
    from app.models.user import User
    try:
        superadmin_exists = db.query(User).filter(User.is_superadmin == True).first() is not None
    except Exception:
        superadmin_exists = False
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "admin_signup_enabled": not superadmin_exists}
    )


@router.get("/check-admin")
def check_admin(login: str, db: Session = Depends(get_db)):
    """Check if a given login (username or email) belongs to an admin user.
    Returns: { exists: bool, is_admin: bool }
    """
    from app.models.user import User
    login = (login or "").strip().lower()
    if not login:
        return {"exists": False, "is_admin": False}
    q = db.query(User).filter((User.username == login) | (User.email == login)).first()
    if not q:
        return {"exists": False, "is_admin": False}
    return {"exists": True, "is_admin": bool(getattr(q, "is_admin", False))}


@router.post("/login")
def admin_login(
    request: Request,
    response: Response,
    login: str = Form(..., description="username or email"),
    password: str = Form(...),
    password_confirm: str = Form(None),
    ident: str = Form(None, description="주민번호"),
    phone: str = Form(None, description="휴대전화"),
    db: Session = Depends(get_db),
):
    login = (login or "").strip()
    # admin_signup_enabled 플래그 (superadmin 존재 시 비활성화)
    try:
        superadmin_exists = db.query(User).filter(User.is_superadmin == True).first() is not None
    except Exception:
        superadmin_exists = False
    admin_signup_enabled = not superadmin_exists

    if not login or not password:
        # 폼 에러는 페이지 내 빨간 문구로 표시
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "아이디/비밀번호를 입력하세요", "admin_signup_enabled": admin_signup_enabled},
            status_code=200,
        )

    # find by username or email
    user: Optional[User] = (
        db.query(User)
        .filter((User.username == login) | (User.email == login))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        # 실패 시에도 같은 페이지에서 빨간 문구 표시
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다", "admin_signup_enabled": admin_signup_enabled},
            status_code=200,
        )
    if password_confirm is not None and password_confirm != password:
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "비밀번호 확인이 일치하지 않습니다", "admin_signup_enabled": admin_signup_enabled},
            status_code=200,
        )
    if not user.is_admin:
        # 관리자가 아닌 계정은 신청 상태 안내 페이지로 이동
        return RedirectResponse(url=f"/admin/choice?status=check&user_id={user.id}", status_code=303)

    # 관리자 로그인은 아이디/비밀번호만으로 가능하도록 변경
    # 추가 정보 검증은 생략

    # 관리자 모드 토큰은 기본 30분 권장
    token = _issue_cookie_token(user, admin_mode=True, minutes=min(settings.jwt_access_token_expire_minutes, 30))
    secure_flag = not settings.debug  # dev=False, prod=True
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        key=(settings.auth_access_cookie_name or "access_token"),
        value=token,
        httponly=settings.auth_cookie_http_only,
        secure=(settings.auth_cookie_secure if settings.auth_cookie_secure is not None else secure_flag),
        samesite=(settings.auth_cookie_samesite or "lax"),
        max_age=settings.jwt_access_token_expire_minutes * 60,
        path=(settings.auth_cookie_path or "/"),
        domain=(settings.auth_cookie_domain or None),
    )
    return resp


@router.get("/signup", response_class=HTMLResponse)
def admin_signup_page(request: Request, db: Session = Depends(get_db)):
    # superadmin이 존재하면 회원가입 차단
    try:
        superadmin_exists = db.query(User).filter(User.is_superadmin == True).first() is not None
    except Exception:
        superadmin_exists = False
    if superadmin_exists:
        return RedirectResponse(url="/admin/login?info=signup_disabled", status_code=303)
    return templates.TemplateResponse("admin_signup.html", {"request": request})


@router.post("/signup")
def admin_signup(
    request: Request,
    response: Response,
    username: str = Form(...),
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    phone: str = Form(..., description="휴대전화"),
    ident: str = Form(..., description="주민번호"),
    also_user: int = Form(0, description="일반 회원 정보도 입력 진행 여부 (0|1)"),
    db: Session = Depends(get_db),
):
    username = (username or "").strip().lower()
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not username or not email or not password or not name or not phone or not ident:
        return templates.TemplateResponse(
            "admin_signup.html",
            {"request": request, "error": "필수 항목을 모두 입력하세요"},
            status_code=200,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            "admin_signup.html",
            {"request": request, "error": "비밀번호 확인이 일치하지 않습니다"},
            status_code=200,
        )
    # 중복 계정 검사(대소문자 무시)
    exists = (
        db.query(User.id)
        .filter((func.lower(User.username) == username) | (func.lower(User.email) == email))
        .first()
    )
    if exists:
        return templates.TemplateResponse(
            "admin_signup.html",
            {"request": request, "error": "이미 존재하는 아이디 또는 이메일입니다"},
            status_code=200,
        )

    # 전화번호/주민번호 중복 검사 (fingerprint 기준 + 레거시 plain)
    try:
        p_norm = normalize_phone(phone)
        if p_norm and len(p_norm) == 11 and p_norm.startswith('010'):
            p_fp = id_fingerprint(p_norm)
            dup_phone = db.query(User.id).filter((User.phone_fingerprint == p_fp) | (User.phone == phone)).first() is not None
            if dup_phone:
                return templates.TemplateResponse(
                    "admin_signup.html",
                    {"request": request, "error": "이미 등록된 전화번호입니다"},
                    status_code=200,
                )
    except Exception:
        pass

    try:
        ident_digits = normalize_phone(ident)  # 숫자만
        if ident_digits and len(ident_digits) == 13:
            i_fp = id_fingerprint(ident_digits)
            dup_ident = db.query(User.id).filter((User.identification_fingerprint == i_fp)).first() is not None
            if dup_ident:
                return templates.TemplateResponse(
                    "admin_signup.html",
                    {"request": request, "error": "이미 등록된 주민번호입니다"},
                    status_code=200,
                )
    except Exception:
        pass

    # superadmin이 존재하면 회원가입 차단
    try:
        superadmin_exists = db.query(User).filter(User.is_superadmin == True).first() is not None
    except Exception:
        superadmin_exists = False
    if superadmin_exists:
        return RedirectResponse(url="/admin/login?info=signup_disabled", status_code=303)

    # 첫 관리자는 자동으로 슈퍼관리자가 됨
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        name=name,
        is_admin=True,
        is_superadmin=True,  # 첫 관리자는 슈퍼관리자
        is_active=True,
        email_verified=True,  # admin은 이메일 인증 과정 없이 바로 인증됨
        introduction="",
    )
    # 추가 정보 저장
    try:
        # 전화/주민번호 유효성은 모델 setter에서 정규화/검증 수행
        user.set_phone(phone)
        user.set_identification_number(ident)
    except Exception:
        pass
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _issue_cookie_token(user, admin_mode=True, minutes=min(settings.jwt_access_token_expire_minutes, 30))
    secure_flag = not settings.debug
    # also_user 체크: 일반 회원 추가 정보 입력 플로우 허용 쿠키 + step2 이동
    allow_steps = str(also_user or 0) == '1'
    next_url = "/admin/signup2" if allow_steps else "/admin"
    resp = RedirectResponse(url=next_url, status_code=303)
    resp.set_cookie(
        key=(settings.auth_access_cookie_name or "access_token"),
        value=token,
        httponly=settings.auth_cookie_http_only,
        secure=(settings.auth_cookie_secure if settings.auth_cookie_secure is not None else secure_flag),
        samesite=(settings.auth_cookie_samesite or "lax"),
        max_age=settings.jwt_access_token_expire_minutes * 60,
        path=(settings.auth_cookie_path or "/"),
        domain=(settings.auth_cookie_domain or None),
    )
    if allow_steps:
        # 서버 가드 우회를 위한 한시 쿠키
        resp.set_cookie(
            key="allow_signup_steps",
            value="1",
            httponly=True,
            secure=(settings.auth_cookie_secure if settings.auth_cookie_secure is not None else secure_flag),
            samesite=(settings.auth_cookie_samesite or "lax"),
            max_age=60 * 30,
            path=(settings.auth_cookie_path or "/"),
            domain=(settings.auth_cookie_domain or None),
        )
    return resp


@router.post("/mode/on")
def admin_mode_on(
    request: Request,
    response: Response,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    # 현재 로그인한 사용자(쿠키) 재검증 + is_admin 확인 후 admin_mode 켜기
    me = get_current_user_from_cookie(request, db)
    if not me:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    if not me.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 없습니다")
    if not verify_password(password, me.password_hash):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")

    token = _issue_cookie_token(me, admin_mode=True, minutes=min(settings.jwt_access_token_expire_minutes, 30))
    secure_flag = not settings.debug
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        key=(settings.auth_access_cookie_name or "access_token"),
        value=token,
        httponly=settings.auth_cookie_http_only,
        secure=(settings.auth_cookie_secure if settings.auth_cookie_secure is not None else secure_flag),
        samesite=(settings.auth_cookie_samesite or "lax"),
        max_age=60 * 30,
        path=(settings.auth_cookie_path or "/"),
        domain=(settings.auth_cookie_domain or None),
    )
    return resp


@router.post("/mode/off")
def admin_mode_off(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    # 요구사항: 관리자 모드 종료 시 일반 로그인도 유지하지 않고 완전 로그아웃 상태로 홈 이동
    resp = RedirectResponse(url="/home", status_code=303)
    try:
        resp.delete_cookie(
            key=(settings.auth_access_cookie_name or "access_token"),
            path=(settings.auth_cookie_path or "/"),
            domain=(settings.auth_cookie_domain or None),
        )
        resp.delete_cookie(
            key=(settings.auth_refresh_cookie_name or "refresh_token"),
            path=(settings.auth_cookie_path or "/"),
            domain=(settings.auth_cookie_domain or None),
        )
        resp.delete_cookie("session", path="/")
    except Exception:
        # 최소한 access_token 제거 시도
        resp.delete_cookie("access_token", path="/")
    return resp


# -------- 관리자 권한 신청 (로그인 필요) --------
@router.get("/request")
def admin_request(db: Session = Depends(get_db), request: Request = None):
    from app.core.deps import get_current_user_from_cookie
    from app.models.admin_request import AdminRequest
    me = get_current_user_from_cookie(request, db)
    if not me:
        # 로그인 후 다시 돌아오도록 유도
        return RedirectResponse(url="/login?return_to=/admin/request", status_code=303)
    # 이미 관리자인 경우 바로 대시보드로
    if getattr(me, "is_admin", False):
        return RedirectResponse(url="/admin", status_code=303)
    # 기존 보류중 요청 있으면 재사용
    pend = db.query(AdminRequest).filter(AdminRequest.user_id == me.id, AdminRequest.status == "pending").first()
    if not pend:
        pend = AdminRequest(user_id=me.id, status="pending")
        db.add(pend)
        db.commit()
        try:
            from app.models.admin_audit_log import AdminAuditLog
            db.add(AdminAuditLog(user_id=me.id, action='applied'))
            db.commit()
        except Exception:
            pass
    return RedirectResponse(url="/admin/requested", status_code=303)


@router.post("/logout")
def admin_logout(request: Request):
    """관리자 로그아웃: 인증 쿠키 제거 후 홈으로 이동."""
    resp = RedirectResponse(url="/home", status_code=303)
    cookie_key = settings.auth_access_cookie_name or "access_token"
    refresh_key = settings.auth_refresh_cookie_name or "refresh_token"
    for name in (cookie_key, "session", refresh_key):
        try:
            resp.delete_cookie(
                key=name,
                path=(settings.auth_cookie_path or "/"),
                domain=(settings.auth_cookie_domain or None),
            )
        except Exception:
            try:
                resp.delete_cookie(key=name, path="/")
            except Exception:
                pass
    return resp


@router.post("/request-by-credential")
def admin_request_by_credential(
    login: str = Form(..., description="username or email"),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Allow creating an admin request by verifying credentials without session.
    Returns JSON {ok:bool, detail?:str}
    """
    from app.models.user import User
    from app.models.admin_request import AdminRequest

    login = (login or "").strip()
    if not login or not password:
        raise HTTPException(status_code=400, detail="아이디/비밀번호를 입력하세요")
    user = (
        db.query(User)
        .filter((User.username == login) | (User.email == login))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")
    if user.is_admin:
        return {"ok": False, "detail": "이미 관리자 계정입니다"}

    pend = db.query(AdminRequest).filter(AdminRequest.user_id == user.id, AdminRequest.status == "pending").first()
    if not pend:
        pend = AdminRequest(user_id=user.id, status="pending")
        db.add(pend)
        db.commit()
        try:
            from app.models.admin_audit_log import AdminAuditLog
            db.add(AdminAuditLog(user_id=user.id, action='applied'))
            db.commit()
        except Exception:
            pass
    return {"ok": True}


@router.get("/signup-request", response_class=HTMLResponse)
def admin_signup_request_page(request: Request):
    return templates.TemplateResponse("admin_signup_request.html", {"request": request})


# 신규: 기존 계정으로 관리자 신청 (1단계)
@router.get("/signup-request1", response_class=HTMLResponse)
def admin_signup_request1_page(request: Request):
    return templates.TemplateResponse("admin_signup_request1.html", {"request": request})


@router.post("/signup-request1")
def admin_signup_request1_submit(
    request: Request,
    login: str = Form(..., description="username or email"),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """기존 계정/비밀번호로 본인 확인 후 관리자 신청 생성, 완료 페이지로 리다이렉트."""
    from app.models.user import User
    from app.models.admin_request import AdminRequest

    login = (login or "").strip()
    if not login or not password:
        return templates.TemplateResponse(
            "admin_signup_request1.html",
            {"request": request, "error": "아이디/비밀번호를 입력하세요"},
            status_code=200,
        )
    user = (
        db.query(User)
        .filter((User.username == login) | (User.email == login))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "admin_signup_request1.html",
            {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다"},
            status_code=200,
        )
    if user.is_admin:
        return templates.TemplateResponse(
            "admin_signup_request1.html",
            {"request": request, "error": "이미 관리자 계정입니다"},
            status_code=200,
        )
    pend = db.query(AdminRequest).filter(AdminRequest.user_id == user.id, AdminRequest.status == "pending").first()
    if not pend:
        pend = AdminRequest(user_id=user.id, status="pending")
        db.add(pend)
        db.commit()
    return RedirectResponse(url="/admin/requested", status_code=303)


@router.post("/signup-request")
def admin_signup_request(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    phone: str | None = Form(None),
    ident: str | None = Form(None),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    from app.models.admin_request import AdminRequest
    
    username = (username or "").strip()
    email = (email or "").strip().lower()
    name = (name or "").strip()
    
    if not username or not email or not password or not name:
        return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "필수 항목을 모두 입력하세요"}, status_code=200)
    if password != password_confirm:
        return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "비밀번호 확인이 일치하지 않습니다"}, status_code=200)
    
    # 중복 계정 확인
    exists = db.query(User).filter((func.lower(User.username) == username.lower()) | (func.lower(User.email) == email.lower())).first()
    if exists:
        return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "이미 존재하는 아이디 또는 이메일입니다"}, status_code=200)

    # 전화/주민번호 필수 및 중복 검사
    try:
        p_norm = normalize_phone(phone or "")
        if not (p_norm and len(p_norm) == 11 and p_norm.startswith('010')):
            return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "전화번호는 010으로 시작하는 11자리여야 합니다"}, status_code=200)
        p_fp = id_fingerprint(p_norm)
        if db.query(User.id).filter((User.phone_fingerprint == p_fp) | (User.phone == phone)).first() is not None:
            return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "이미 등록된 전화번호입니다"}, status_code=200)
    except Exception:
        pass
    try:
        ident_digits = normalize_phone(ident or "")
        if not (ident_digits and len(ident_digits) == 13):
            return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "주민등록번호 형식이 올바르지 않습니다"}, status_code=200)
        i_fp = id_fingerprint(ident_digits)
        if db.query(User.id).filter(User.identification_fingerprint == i_fp).first() is not None:
            return templates.TemplateResponse("admin_signup_request2.html", {"request": request, "error": "이미 등록된 주민번호입니다"}, status_code=200)
    except Exception:
        pass
    
    # 새 사용자 생성 (비활성 상태로)
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        name=name,
        is_admin=False,
        is_superadmin=False,
        # 일반 회원 권한 즉시 사용 가능하도록 활성화
        is_active=True,
        email_verified=True,
        introduction="",
    )
    # 선택 입력: 전화/주민번호 저장 (모델 setter에서 검증/정규화)
    try:
        if phone:
            user.set_phone(phone)
    except Exception:
        pass
    try:
        if ident:
            user.set_identification_number(ident)
    except Exception:
        pass
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 관리자 권한 요청 생성
    admin_request = AdminRequest(user_id=user.id, status="pending")
    db.add(admin_request)
    db.commit()
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=user.id, action='applied'))
        db.commit()
    except Exception:
        pass

    # 추가 단계 플로우 항상 진행: 한시 쿠키 설정 후 2단계로 이동
    resp = RedirectResponse(url="/admin/signup-request2_2", status_code=303)
    secure_flag = not settings.debug
    # 신규 생성 사용자로 로그인 쿠키 발급 (후속 단계에서 프로필 저장 가능하게)
    try:
        login_token = _issue_cookie_token(user, admin_mode=False)
        resp.set_cookie(
            key=(settings.auth_access_cookie_name or "access_token"),
            value=login_token,
            httponly=settings.auth_cookie_http_only,
            secure=secure_flag,
            samesite=(settings.auth_cookie_samesite or "lax"),
            max_age=settings.jwt_access_token_expire_minutes * 60,
            path=(settings.auth_cookie_path or "/"),
            domain=(settings.auth_cookie_domain or None),
        )
    except Exception:
        pass
    resp.set_cookie(
        key="allow_signup_steps",
        value="1",
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=60*30,
        path="/",
    )
    return resp


# 신규: 신규 가입 + 관리자 신청 (2단계) 화면
@router.get("/signup-request2", response_class=HTMLResponse)
def admin_signup_request2_page(request: Request):
    return templates.TemplateResponse("admin_signup_request2.html", {"request": request})

# Added step pages for admin and request flows
@router.get("/signup2", response_class=HTMLResponse)
def admin_signup_step2_page(request: Request):
    return templates.TemplateResponse("admin_signup2.html", {"request": request})

@router.post("/signup2")
def admin_signup_step2_save(
    request: Request,
    gender: Optional[str] = Form(None),
    region_living: Optional[str] = Form(None),
    region_active: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """관리자 가입 2단계 저장: 성별/거주/활동지역.
    - 쿠키(access_token) 기반 현재 사용자 식별 후 업데이트
    """
    me = get_current_user_from_cookie(request, db)
    if not me:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    # 업데이트
    if gender:
        try:
            me.gender = gender if gender in ("male","female","other") else me.gender
        except Exception:
            pass
    if region_living is not None:
        me.region_living = (region_living or "").strip()
    if region_active is not None:
        me.region_active = (region_active or "").strip()
    db.commit()
    return {"ok": True}

@router.get("/signup3", response_class=HTMLResponse)
def admin_signup_step3_page(request: Request):
    return templates.TemplateResponse("admin_signup3.html", {"request": request})

@router.post("/signup3")
async def admin_signup_step3_save(
    request: Request,
    db: Session = Depends(get_db),
):
    """관리자 가입 3단계 저장: 프로필 이미지/소개/선택 태그.
    - JSON 또는 폼 전송을 모두 지원
    body: { profile_image?, introduction?, selected_tags?: [str] }
    """
    me = get_current_user_from_cookie(request, db)
    if not me:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    # 파라미터 파싱 (JSON 우선)
    profile_image = None
    introduction = None
    selected_tags = []
    try:
        data = await request.json()
        profile_image = (data.get("profile_image") or None)
        introduction = (data.get("introduction") or None)
        st = data.get("selected_tags") or []
        if isinstance(st, list):
            selected_tags = [str(t).strip() for t in st if isinstance(t, str) and t.strip()]
    except Exception:
        form = await request.form()
        profile_image = form.get("profile_image")
        introduction = form.get("introduction")
        st = form.getlist("selected_tags") if hasattr(form, "getlist") else []
        selected_tags = [str(t).strip() for t in st if isinstance(t, str) and t.strip()]

    # 업데이트: 이미지/소개
    if profile_image is not None:
        me.profile_image = profile_image.strip()
    if introduction is not None:
        me.introduction = introduction.strip()
    db.commit()

    # 태그 연결 (있을 때만)
    if selected_tags:
        from app.models.tag import Tag, UserTag
        # existing only: 존재하는 태그만 연결
        existing = db.query(Tag).filter(Tag.tag.in_(selected_tags), Tag.is_active == True).all()
        tag_map = {t.tag: t for t in existing}
        for name in selected_tags:
            tag = tag_map.get(name)
            if not tag:
                continue
            exists = db.query(UserTag).filter(UserTag.user_id == me.id, UserTag.tag_id == tag.id).first()
            if not exists:
                db.add(UserTag(user_id=me.id, tag_id=tag.id))
        db.commit()

    return {"ok": True}

@router.get("/signup-request2_2", response_class=HTMLResponse)
def admin_signup_request2_step2_page(request: Request):
    return templates.TemplateResponse("admin_signup_request2_2.html", {"request": request})

@router.get("/signup-request2_3", response_class=HTMLResponse)
def admin_signup_request2_step3_page(request: Request):
    return templates.TemplateResponse("admin_signup_request2_3.html", {"request": request})


# Bearer token 기반 admin 모드 전환 (API용)
@router.post("/mode/enable")
def enable_admin_mode_api(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bearer token 인증을 통한 관리자 모드 활성화"""
    if not (current_user.is_admin or current_user.is_superadmin):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    # 관리자 모드 쿠키 토큰 발급
    admin_token = _issue_cookie_token(current_user, admin_mode=True)
    response.set_cookie(
        key=(settings.auth_access_cookie_name or "access_token"),
        value=admin_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        httponly=settings.auth_cookie_http_only,
        secure=settings.auth_cookie_secure,
        samesite=(settings.auth_cookie_samesite or "lax"),
        path=(settings.auth_cookie_path or "/"),
        domain=(settings.auth_cookie_domain or None),
    )
    
    return {"detail": "관리자 모드가 활성화되었습니다"}
