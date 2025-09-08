from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Query, Form, Body
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_master_admin
from app.models.admin_request import AdminRequest

router = APIRouter(prefix="", tags=["admin-pages"])  # mount at root for /admin

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
    error: Optional[str] = Query(None),
):
    # If a flow sends us here with user selection required, go to history list page
    if (error or "").strip() == "user_required":
        return RedirectResponse(url="/admin/requests-history", status_code=303)
    # Basic metrics (가벼운 집계)
    from app.models.user import User
    try:
        from app.models.challenge import Challenge
    except ImportError:
        Challenge = None
    try:
        from app.models.payment import Payment, PaymentStatus
    except ImportError:
        Payment = None
        PaymentStatus = None
    try:
        user_count = db.query(User).filter(getattr(User, 'is_superadmin', False) == False).count()
    except Exception:
        user_count = 0
    try:
        challenge_count = db.query(Challenge).count() if Challenge else 0
    except Exception:
        challenge_count = 0
    try:
        admin_count = db.query(User).filter(User.is_admin == True, getattr(User, 'is_superadmin', False) == False).count()
    except Exception:
        admin_count = 0
    total_revenue = 0
    try:
        if Payment and PaymentStatus:
            from sqlalchemy import func
            # completed 또는 success 상태의 결제만 매출로 계산
            total_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
                Payment.status.in_([PaymentStatus.completed, PaymentStatus.success])
            ).scalar() or 0
    except Exception:
        total_revenue = 0

    # Preview lists
    latest_users = []
    latest_challenges = []
    admin_requests = []
    try:
        latest_users = db.query(User).filter(getattr(User, 'is_superadmin', False) == False).order_by(User.id.desc()).limit(8).all()
    except Exception:
        latest_users = []
    try:
        latest_challenges = db.query(Challenge).order_by(Challenge.id.desc()).limit(8).all() if Challenge else []
    except Exception:
        latest_challenges = []
    try:
        from sqlalchemy.orm import joinedload
        from sqlalchemy import func
        from datetime import timedelta
        from app.utils.timezone import now_kst

        # 1) Auto-expire: pending > 24h -> rejected
        try:
            expire_before = now_kst() - timedelta(hours=24)
            stale = (
                db.query(AdminRequest)
                .filter(AdminRequest.status == 'pending', AdminRequest.created_at < expire_before)
                .all()
            )
            if stale:
                now = now_kst()
                for r in stale:
                    r.status = 'rejected'
                    r.reviewed_at = now
                    # keep reviewed_by as None for auto-expire
                db.commit()
        except Exception:
            pass

        # 2) Only latest request per user (keep history, but list current view succinct)
        latest_ids_subq = (
            db.query(func.max(AdminRequest.id).label('max_id'))
            .group_by(AdminRequest.user_id)
            .subquery()
        )
        admin_requests = (
            db.query(AdminRequest)
            .options(joinedload(AdminRequest.user))
            .filter(AdminRequest.id.in_(latest_ids_subq))
            .order_by(AdminRequest.created_at.desc())
            .all()
        )
        # Hide superadmin data for non-super admins only
        if not getattr(current_user, 'is_superadmin', False):
            admin_requests = [r for r in admin_requests if not (getattr(r, 'user', None) and getattr(r.user, 'is_superadmin', False))]
    except Exception:
        admin_requests = []

    ctx = {
        "request": request,
        "admin": current_user,
        "user_count": user_count,
        "challenge_count": challenge_count,
        "admin_count": admin_count,
        "total_revenue": total_revenue,
        "latest_users": latest_users,
        "latest_challenges": latest_challenges,
        "admin_requests": admin_requests,
    }
    return templates.TemplateResponse("admin_dashboard.html", ctx)


@router.get("/admin/user-history", response_class=HTMLResponse)
def admin_user_history(
    request: Request,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    # Superadmins can view other superadmins; others cannot (route guarded by master only)
    if getattr(user, 'is_superadmin', False) and not getattr(current_user, 'is_superadmin', False):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin?error=forbidden", status_code=303)
    # gather admin_requests for user
    reqs = db.query(AdminRequest).filter(AdminRequest.user_id == user_id).order_by(AdminRequest.created_at.asc()).all()
    # gather audit logs
    try:
        from app.models.admin_audit_log import AdminAuditLog
        audits = db.query(AdminAuditLog).filter(AdminAuditLog.user_id == user_id).order_by(AdminAuditLog.created_at.asc()).all()
    except Exception:
        audits = []
    return templates.TemplateResponse("admin_user_history.html", {"request": request, "target": user, "reqs": reqs, "audits": audits})


# -----------------------
# Super Admin: Create Admin
# -----------------------
@router.get("/admin/admins/new", response_class=HTMLResponse)
def admin_create_page(request: Request, current_user = Depends(require_master_admin)):
    return templates.TemplateResponse("admin_admin_create.html", {"request": request, "admin": current_user})


@router.post("/admin/admins/new")
def admin_create(
    request: Request,
    name: str,
    username: str,
    email: str,
    phone: str,
    ident: str,
    password: str,
    password_confirm: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from app.models.user import User
    from app.security import hash_password

    name = (name or "").strip()
    username = (username or "").strip()
    email = (email or "").strip().lower()
    if not all([name, username, email, phone, ident, password, password_confirm]):
        return HTMLResponse("필수 항목 누락", status_code=400)
    if password != password_confirm:
        return HTMLResponse("비밀번호 확인이 일치하지 않습니다", status_code=400)
    exists = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if exists:
        return HTMLResponse("이미 존재하는 사용자입니다", status_code=400)

    u = User(
        name=name,
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_admin=True,
        is_active=True,
        email_verified=True,  # admin은 이메일 인증 과정 없이 바로 인증됨
        introduction="",
    )
    try:
        u.set_phone(phone)
        u.set_identification_number(ident)
    except Exception:
        pass
    db.add(u)
    db.commit()
    return HTMLResponse("관리자 계정이 생성되었습니다. <a href=\"/admin\">대시보드로</a>", status_code=201)


@router.get("/admin/requested", response_class=HTMLResponse)
def admin_requested(request: Request):
    return templates.TemplateResponse("admin_requested.html", {"request": request})


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
):
    from app.models.user import User
    admins: List[User] = (
        db.query(User)
        .filter(User.is_admin == True, getattr(User, 'is_superadmin', False) == False)
        .order_by(User.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "admins": admins}
    )


@router.get("/admin/requests")
def admin_requests_list(
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from sqlalchemy.orm import joinedload
    reqs = (
        db.query(AdminRequest)
        .options(joinedload(AdminRequest.user))
        .order_by(AdminRequest.created_at.desc())
        .limit(200)
        .all()
    )
    # filter out superadmin requests only for non-super admins
    if not getattr(current_user, 'is_superadmin', False):
        reqs = [r for r in reqs if not (getattr(r, 'user', None) and getattr(r.user, 'is_superadmin', False))]
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": getattr(r.user, "username", None) if r.user else None,
            "email": getattr(r.user, "email", None) if r.user else None,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in reqs
    ]

@router.get("/admin/requests-history", response_class=HTMLResponse)
def admin_requests_history(
    request: Request,
    q: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    sort: Optional[str] = Query("time_desc"),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    """Global admin action history page (audit log + pending reminder).

    Supports filtering by user (`q`), action type, and sorting.
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_, func
    from app.models.user import User
    from app.models.admin_audit_log import AdminAuditLog
    from app.models.admin_request import AdminRequest
    from app.utils.timezone import now_kst

    # Base query with relationships
    query = (
        db.query(AdminAuditLog)
        .options(joinedload(AdminAuditLog.user), joinedload(AdminAuditLog.actor))
    )

    # Join user and optionally hide superadmin rows for non-super admins
    try:
        query = query.join(User, User.id == AdminAuditLog.user_id)
        if not getattr(current_user, 'is_superadmin', False):
            query = query.filter(User.is_superadmin == False)
    except Exception:
        pass

    # Filter: search by applicant user fields
    search_query = (q or "").strip()
    if search_query:
        # Re-join User to filter by name/username/email
        query = query.filter(
            or_(
                func.lower(User.name).like(f"%{search_query.lower()}%"),
                func.lower(User.username).like(f"%{search_query.lower()}%"),
                func.lower(User.email).like(f"%{search_query.lower()}%"),
            )
        )

    # Filter: action
    action_filter = (action or "").strip() or None
    if action_filter:
        query = query.filter(AdminAuditLog.action == action_filter)

    # Sorting
    sort_option = (sort or "time_desc").strip() or "time_desc"
    if sort_option == "time_asc":
        query = query.order_by(AdminAuditLog.created_at.asc())
    elif sort_option == "name_asc":
        query = query.order_by(func.lower(User.name).asc(), AdminAuditLog.created_at.desc())
    elif sort_option == "name_desc":
        query = query.order_by(func.lower(User.name).desc(), AdminAuditLog.created_at.desc())
    else:
        query = query.order_by(AdminAuditLog.created_at.desc())

    rows = query.limit(500).all()

    # Pending request remaining time map (seconds left until 24h)
    pending_left_map: dict[int, int] = {}
    try:
        from datetime import timedelta
        now = now_kst()
        pendings = db.query(AdminRequest).filter(AdminRequest.status == 'pending').all()
        for p in pendings:
            try:
                if not p.created_at:
                    continue
                elapsed = now - p.created_at
                remaining = max(0, int((timedelta(hours=24) - elapsed).total_seconds()))
                pending_left_map[p.user_id] = remaining
            except Exception:
                continue
    except Exception:
        pending_left_map = {}

    ctx = {
        "request": request,
        "rows": rows,
        "search_query": search_query,
        "action_filter": action_filter,
        "sort_option": sort_option,
        "pending_left_map": pending_left_map,
    }
    return templates.TemplateResponse("admin_requests_history.html", ctx)


@router.post("/admin/requests/{request_id}/approve")
def admin_request_approve(
    request_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return {"ok": False, "detail": "요청을 찾을 수 없습니다"}
    from app.models.user import User
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return {"ok": False, "detail": "대상 사용자를 찾을 수 없습니다"}
    # Promote by flag and activate account
    user.is_admin = True
    user.is_active = True  # 승인 시 활성화
    user.email_verified = True  # admin 승인 시 이메일도 인증됨으로 처리
    req.status = "approved"
    req.reviewed_by = current_user.id
    from app.utils.timezone import now_kst
    req.reviewed_at = now_kst()
    db.commit()
    return {"ok": True, "request_id": req.id, "user_id": user.id, "is_admin": True}


@router.post("/admin/requests/{request_id}/reject")
def admin_request_reject(
    request_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return {"ok": False, "detail": "요청을 찾을 수 없습니다"}
    req.status = "rejected"
    req.reviewed_by = current_user.id
    from app.utils.timezone import now_kst
    req.reviewed_at = now_kst()
    db.commit()
    return {"ok": True, "request_id": req.id, "status": "rejected"}


@router.post("/admin/users/{user_id}/promote")
def admin_promote_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
):
    from app.models.user import User
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return {"ok": False, "detail": "사용자를 찾을 수 없습니다"}
    target.is_admin = True
    db.commit()
    return {"ok": True, "user_id": target.id, "is_admin": True}


@router.post("/admin/users/{user_id}/demote")
def admin_demote_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
):
    if current_user.id == user_id:
        return {"ok": False, "detail": "자기 자신은 강등할 수 없습니다"}
    from app.models.user import User
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return {"ok": False, "detail": "사용자를 찾을 수 없습니다"}
    target.is_admin = False
    db.commit()
    return {"ok": True, "user_id": target.id, "is_admin": False}


# PATCH variant (권장): REST 관례상 부분 수정으로 강등 처리
@router.patch("/admin/users/{user_id}/demote")
def admin_demote_user_patch(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    # 자기 자신 강등 금지 (잠금 방지)
    if current_user.id == user_id:
        return {"ok": False, "detail": "자기 자신은 강등할 수 없습니다"}

    from app.models.user import User
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return {"ok": False, "detail": "사용자를 찾을 수 없습니다"}

    changed = bool(target.is_admin)
    target.is_admin = False
    db.commit()

    return {"ok": True, "user_id": target.id, "is_admin": False, "changed": changed}


# ----- 권한 해제(대시보드 토글에서 호출) -----
class RevokeIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=255)
    scope: str = Field("all", pattern="^(all|super_only)$")


@router.post("/admin/users/{user_id}/revoke")
def admin_revoke_user(
    user_id: int,
    data: RevokeIn,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    # 자기 자신 해제 금지
    if current_user.id == user_id:
        return {"ok": False, "detail": "자기 자신은 해제할 수 없습니다"}

    from app.models.user import User
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return {"ok": False, "detail": "대상 사용자를 찾을 수 없습니다"}

    scope = (data.scope or "all").strip()
    if scope == "super_only":
        # 책임관리자 권한만 해제 (관리자 권한 유지)
        target.is_superadmin = False
        target.is_admin = True
        action = "demoted_super_only"
    else:
        # 모든 관리자 권한 해제
        target.is_superadmin = False
        target.is_admin = False
        action = "demoted_all"

    db.commit()

    # 감사 로그 기록
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=target.id, action=action, note=(data.note or '').strip()[:255], actor_id=current_user.id))
        db.commit()
    except Exception:
        pass

    return {"ok": True, "user_id": target.id, "scope": scope}


# 새로운 Form 기반 승인/거절 엔드포인트 (대시보드용)
@router.post("/admin/approve-request")
def admin_approve_request_form(
    request: Request,
    request_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    
    from app.models.user import User
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    
    # 사용자 승인 처리
    user.is_admin = True
    user.is_active = True  # 승인 시 활성화
    user.email_verified = True  # admin 승인 시 이메일도 인증됨으로 처리
    
    req.status = "approved"
    req.reviewed_by = current_user.id
    from app.utils.timezone import now_kst
    req.reviewed_at = now_kst()
    
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=user.id, action='approved', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
    return RedirectResponse(url="/admin?success=approved", status_code=303)


@router.get("/admin/approve-request", response_class=HTMLResponse)
def admin_approve_request_confirm(
    request: Request,
    request_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    return templates.TemplateResponse("admin_approve_confirm.html", {"request": request, "req": req})

@router.get("/admin/reject-request", response_class=HTMLResponse)
def admin_reject_request_confirm(
    request: Request,
    request_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    return templates.TemplateResponse("admin_reject_confirm.html", {"request": request, "req": req})


@router.post("/admin/reject-request")
def admin_reject_request_form(
    request: Request,
    request_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    
    req.status = "rejected"
    req.reviewed_by = current_user.id
    from app.utils.timezone import now_kst
    req.reviewed_at = now_kst()
    
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=req.user_id, action='rejected', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
    return RedirectResponse(url="/admin?success=rejected", status_code=303)

@router.get("/admin/reapprove-request", response_class=HTMLResponse)
def admin_reapprove_request_confirm(
    request: Request,
    request_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    return templates.TemplateResponse("admin_reapprove_confirm.html", {"request": request, "req": req})

@router.post("/admin/reapprove-request")
def admin_reapprove_request_form(
    request_id: int = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    from app.models.user import User
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    # 재승인 처리
    user.is_admin = True
    user.is_active = True
    user.email_verified = True
    req.status = "approved"
    req.reviewed_by = current_user.id
    if note:
        req.note = note[:255]
    try:
        from app.utils.timezone import now_kst
        req.reviewed_at = now_kst()
    except Exception:
        pass
    db.commit()
    # 감사 로그
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=user.id, action='reapproved', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
    return RedirectResponse(url="/admin?success=reapproved", status_code=303)


# ----- 신청 비고 작성/수정 -----
@router.get("/admin/request-note", response_class=HTMLResponse)
def admin_request_note_page(
    request: Request,
    request_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    return templates.TemplateResponse("admin_request_note_edit.html", {"request": request, "req": req})


@router.post("/admin/request-note")
def admin_request_note_save(
    request_id: int = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    # 저장
    req.note = (note or '')[:255]
    db.commit()
    return RedirectResponse(url=f"/admin?success=note_saved#req-{request_id}", status_code=303)


@router.post("/admin/promote-superadmin")
def admin_promote_superadmin_form(
    request: Request,
    user_id: int = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    from app.models.user import User
    
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    # 책임관리자는 관리 권한을 항상 포함
    target.is_admin = True
    target.is_superadmin = True
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=target.id, action='promoted_super', note=(note or '')[:255], actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
    return RedirectResponse(url="/admin?success=promoted", status_code=303)


@router.get("/admin/demote-admin", response_class=HTMLResponse)
def admin_demote_admin_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
    user_id: Optional[int] = Query(None),
):
    from app.models.user import User
    
    # user_id가 없으면 선택 페이지 표시
    if user_id is None:
        # 모든 관리자 목록 가져오기 (자신 제외)
        admins = db.query(User).filter(
            User.is_admin == True,
            getattr(User, 'is_superadmin', False) == False,
            User.id != current_user.id
        ).all()
        
        return templates.TemplateResponse("admin_demote_confirm.html", {
            "request": request, 
            "admin": current_user,
            "target_user": None,
            "admins": admins
        })
    
    # user_id가 있으면 확인 페이지 표시
    if current_user.id == user_id:
        return RedirectResponse(url="/admin?error=self_demote", status_code=303)
    
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    if getattr(target, 'is_superadmin', False):
        return RedirectResponse(url="/admin?error=forbidden", status_code=303)
    
    return templates.TemplateResponse("admin_demote_confirm.html", {
        "request": request, 
        "admin": current_user,
        "target_user": target
    })

@router.post("/admin/demote-admin")
def admin_demote_admin_form(
    request: Request,
    user_id: int = Form(...),
    demote_scope: str = Form("all"),  # 'super_only' | 'all'
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    from app.models.user import User
    
    if current_user.id == user_id:
        return RedirectResponse(url="/admin?error=self_demote", status_code=303)
    
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    
    if demote_scope == "super_only":
        # 책임관리자 권한만 해제 (일반 관리자 권한은 유지)
        target.is_superadmin = False
        target.is_admin = True
    else:
        # 모든 관리자 권한 해제
        target.is_admin = False
        target.is_superadmin = False
    db.commit()
    return RedirectResponse(url="/admin?success=demoted", status_code=303)


@router.get("/admin/points", response_class=HTMLResponse)
def admin_points_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
):
    """관리자 포인트 관리 페이지"""
    return templates.TemplateResponse("admin_points.html", {"request": request, "current_user": current_user})
