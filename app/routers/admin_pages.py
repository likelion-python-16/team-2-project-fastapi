from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Query, Form
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
    q: Optional[str] = Query(None, description="신청자 검색 (이름/아이디/이메일)"),
):
    # Basic metrics (가벼운 집계)
    from app.models.user import User
    try:
        from app.models.challenge import Challenge
    except ImportError:
        Challenge = None
    try:
        from app.models.finance import Payment, PaymentStatus
    except ImportError:
        Payment = None
        PaymentStatus = None
    try:
        user_count = db.query(User).count()
    except Exception:
        user_count = 0
    try:
        challenge_count = db.query(Challenge).count() if Challenge else 0
    except Exception:
        challenge_count = 0
    try:
        admin_count = db.query(User).filter(User.is_admin == True).count()
    except Exception:
        admin_count = 0
    total_revenue = 0
    try:
        if Payment and PaymentStatus:
            from sqlalchemy import func
            total_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == PaymentStatus.paid).scalar() or 0
    except Exception:
        total_revenue = 0

    # Preview lists
    latest_users = []
    latest_challenges = []
    admin_requests = []
    try:
        # '회원들 조회'에서 현재 사용자와 모든 책임관리자 제외
        latest_users = (
            db.query(User)
            .filter(User.id != current_user.id)
            .filter(User.is_superadmin == False)
            .order_by(User.id.desc())
            .limit(8)
            .all()
        )
    except Exception:
        latest_users = []
    try:
        latest_challenges = db.query(Challenge).order_by(Challenge.id.desc()).limit(8).all() if Challenge else []
    except Exception:
        latest_challenges = []
    try:
        from sqlalchemy.orm import joinedload
        from sqlalchemy import func
        from datetime import datetime, timedelta

        # 1) Auto-expire: pending > 24h -> rejected
        try:
            expire_before = datetime.utcnow() - timedelta(hours=24)
            stale = (
                db.query(AdminRequest)
                .filter(AdminRequest.status == 'pending', AdminRequest.created_at < expire_before)
                .all()
            )
            if stale:
                now = datetime.utcnow()
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
        from app.models.user import User
        qry = (
            db.query(AdminRequest)
            .join(User, User.id == AdminRequest.user_id)
            .options(joinedload(AdminRequest.user))
            .filter(AdminRequest.id.in_(latest_ids_subq))
        )
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            qry = qry.filter(
                (func.lower(User.name).like(like)) |
                (func.lower(User.username).like(like)) |
                (func.lower(User.email).like(like))
            )
        admin_requests = qry.order_by(AdminRequest.created_at.desc()).all()
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
        "search_query": q or "",
    }
    return templates.TemplateResponse("admin_dashboard.html", ctx)


@router.get("/admin/requests-history", response_class=HTMLResponse)
def admin_requests_history(
    request: Request,
    q: str | None = Query(None),
    action: str | None = Query(None),
    status: str | None = Query(None),  # legacy alias: pending/approved/rejected/revoked
    sort: str = Query("time_desc"),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from app.models.user import User
    from app.models.admin_audit_log import AdminAuditLog
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_, asc, desc

    try:
        query = (
            db.query(AdminAuditLog)
            .join(User, User.id == AdminAuditLog.user_id)
            .options(joinedload(AdminAuditLog.user), joinedload(AdminAuditLog.actor))
        )

        # 검색 (이름/아이디/이메일)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(User.name.ilike(like), User.username.ilike(like), User.email.ilike(like))
            )

        # 액션 필터 (status의 레거시 값도 허용)
        alias_map = {
            'pending': 'applied',
            'approved': 'approved',
            'rejected': 'rejected',
            'revoked': 'demoted_all',
        }
        chosen_action = action or (alias_map.get((status or '').lower()) if status else None)
        allowed_actions = {"applied","approved","rejected","reapproved","promoted_super","demoted_super_only","demoted_all","auto_rejected"}
        if chosen_action in allowed_actions:
            query = query.filter(AdminAuditLog.action == chosen_action)

        # 정렬
        if sort == "time_asc":
            query = query.order_by(asc(AdminAuditLog.created_at))
        elif sort == "name_asc":
            query = query.order_by(asc(User.name))
        elif sort == "name_desc":
            query = query.order_by(desc(User.name))
        else:  # time_desc
            query = query.order_by(desc(AdminAuditLog.created_at))

        rows = query.limit(2000).all()
    except Exception:
        rows = []

    # 신청일(최초 applied) 맵 구성: user_id -> datetime
    try:
        from sqlalchemy import func
        applied_pairs = (
            db.query(AdminAuditLog.user_id, func.min(AdminAuditLog.created_at))
              .filter(AdminAuditLog.action == 'applied')
              .group_by(AdminAuditLog.user_id)
              .all()
        )
        applied_map = {uid: ts for (uid, ts) in applied_pairs}
    except Exception:
        applied_map = {}

    # 현재 pending 상태(가장 최근 요청이 pending)인 사용자에 대한 남은 시간 계산
    pending_left_map = {}
    imminent_threshold_sec = 2 * 60 * 60  # 2 hours
    try:
        from app.models.admin_request import AdminRequest
        from sqlalchemy import func as F
        # latest request id per user
        latest_subq = (
            db.query(F.max(AdminRequest.id).label('max_id'))
            .group_by(AdminRequest.user_id)
            .subquery()
        )
        latest_rows = (
            db.query(AdminRequest)
            .filter(AdminRequest.id.in_(latest_subq))
            .all()
        )
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        for r in latest_rows:
            if getattr(r, 'status', None) == 'pending' and getattr(r, 'created_at', None):
                expire_at = r.created_at + timedelta(hours=24)
                seconds_left = int((expire_at - now).total_seconds())
                pending_left_map[r.user_id] = max(-1_000_000, seconds_left)
    except Exception:
        pending_left_map = {}

    return templates.TemplateResponse(
        "admin_requests_history.html",
        {
            "request": request,
            "rows": rows,
            "search_query": q,
            "action_filter": chosen_action or "",
            "sort_option": sort,
            "applied_map": applied_map,
            "pending_left_map": pending_left_map,
            "imminent_threshold_sec": imminent_threshold_sec,
        },
    )


@router.get("/admin/user-history")
def admin_user_history_disabled():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin?info=history_disabled", status_code=303)


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
def admin_requested(request: Request, db: Session = Depends(get_db)):
    """신청자용 진행상황 페이지: 최근 신청의 상태를 보여준다."""
    try:
        from app.core.deps import get_current_user_from_cookie
        me = get_current_user_from_cookie(request, db)
    except Exception:
        me = None

    last_req = None
    if me:
        try:
            last_req = (
                db.query(AdminRequest)
                .filter(AdminRequest.user_id == me.id)
                .order_by(AdminRequest.id.desc())
                .first()
            )
        except Exception:
            last_req = None

    ctx = {"request": request, "me": me, "last_req": last_req}
    return templates.TemplateResponse("admin_requested.html", ctx)


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
):
    from app.models.user import User
    admins: List[User] = db.query(User).filter(User.is_admin == True).order_by(User.id.desc()).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "admins": admins}
    )


@router.get("/admin/requests")
def admin_requests_list(
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    reqs = (
        db.query(AdminRequest)
        .order_by(AdminRequest.created_at.desc())
        .limit(200)
        .all()
    )
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
    was_rejected = (req.status == 'rejected')
    req.status = "approved"
    req.reviewed_by = current_user.id
    from datetime import datetime
    req.reviewed_at = datetime.utcnow()
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        if was_rejected:
            if not getattr(req, 'note', None):
                req.note = '재승인됨'
                db.commit()
            db.add(AdminAuditLog(user_id=user.id, action='reapproved', actor_id=current_user.id))
        else:
            db.add(AdminAuditLog(user_id=user.id, action='approved', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
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
    from datetime import datetime
    req.reviewed_at = datetime.utcnow()
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=req.user_id, action='rejected', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
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


# Inline revoke (권한 해제 토글)
@router.post("/admin/users/{user_id}/revoke")
def admin_revoke_inline(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from app.models.user import User
    from app.models.admin_request import AdminRequest
    from app.models.admin_audit_log import AdminAuditLog
    from datetime import datetime
    note = (payload or {}).get('note') or ''
    scope = (payload or {}).get('scope') or 'all'  # 'super_only' | 'all'
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return {"ok": False, "detail": "사용자를 찾을 수 없습니다"}
    if current_user.id == user_id:
        return {"ok": False, "detail": "자기 자신은 해제할 수 없습니다"}
    if not note.strip():
        return {"ok": False, "detail": "사유가 필요합니다"}
    # 이미 비관리자면 스킵
    if not target.is_admin and not target.is_superadmin:
        return {"ok": True, "changed": False}

    if scope == 'super_only' and target.is_superadmin:
        # 책임관리자 권한만 해제
        target.is_superadmin = False
        target.is_admin = True
        db.add(AdminAuditLog(user_id=target.id, action='demoted_super_only', actor_id=current_user.id, note=(note or '').strip() or None))
    else:
        # 전체 관리자 권한 해제: AdminRequest에 권한 해제 이력 추가 + AuditLog 기록
        target.is_admin = False
        target.is_superadmin = False
        rec = AdminRequest(
            user_id=target.id,
            status='revoked',
            note=(note or '관리자 권한 해제').strip(),
            reviewed_by=current_user.id,
            reviewed_at=datetime.utcnow(),
        )
        db.add(rec)
        db.add(AdminAuditLog(user_id=target.id, action='demoted_all', actor_id=current_user.id, note=(note or '').strip() or None))
    db.commit()
    return {"ok": True, "changed": True}


# 새로운 Form 기반 승인/거절 엔드포인트 (대시보드용)
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


@router.post("/admin/approve-request")
def admin_approve_request_form(
    request: Request,
    request_id: int = Form(...),
    note: str = Form(""),
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
    req.note = note.strip() if note else None
    from datetime import datetime
    req.reviewed_at = datetime.utcnow()
    
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=user.id, action='approved', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
    return RedirectResponse(url="/admin?success=approved", status_code=303)


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
    note: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    # require note
    note_txt = (note or '').strip()
    if not note_txt:
        return templates.TemplateResponse("admin_reject_confirm.html", {"request": request, "req": req, "error": "거절 사유를 입력하세요"}, status_code=200)

    req.status = "rejected"
    req.reviewed_by = current_user.id
    req.note = note_txt
    from datetime import datetime
    req.reviewed_at = datetime.utcnow()
    
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=req.user_id, action='rejected', actor_id=current_user.id, note=note_txt))
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
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/requests-history?error=request_not_found", status_code=303)
    if req.status != 'rejected':
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/requests-history?error=not_rejected", status_code=303)
    return templates.TemplateResponse("admin_reapprove_confirm.html", {"request": request, "req": req})


@router.post("/admin/reapprove-request")
def admin_reapprove_request_form(
    request: Request,
    request_id: int = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin/requests-history?error=request_not_found", status_code=303)
    
    if req.status != 'rejected':
        return RedirectResponse(url="/admin/requests-history?error=not_rejected", status_code=303)
    
    from app.models.user import User
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return RedirectResponse(url="/admin/requests-history?error=user_not_found", status_code=303)
    
    # 사용자 재승인 처리
    user.is_admin = True
    user.is_active = True
    user.email_verified = True
    
    req.status = "approved"
    req.reviewed_by = current_user.id
    req.note = note.strip() if note else "재승인됨"
    from datetime import datetime
    req.reviewed_at = datetime.utcnow()
    
    db.commit()
    # audit
    try:
        from app.models.admin_audit_log import AdminAuditLog
        db.add(AdminAuditLog(user_id=user.id, action='reapproved', actor_id=current_user.id))
        db.commit()
    except Exception:
        pass
    return RedirectResponse(url="/admin/requests-history?success=reapproved", status_code=303)


@router.post("/admin/promote-superadmin")
def admin_promote_superadmin_form(
    request: Request,
    user_id: int = Form(...),
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
        db.add(AdminAuditLog(user_id=target.id, action='promoted_super', actor_id=current_user.id))
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
    note: str = Form(""),
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
    
    from app.models.admin_audit_log import AdminAuditLog
    note_txt = (note or '').strip()
    if not note_txt:
        # Re-render page with error and target loaded
        return templates.TemplateResponse("admin_demote_confirm.html", {
            "request": request,
            "admin": current_user,
            "target_user": target,
            "error": "해제 사유를 입력하세요"
        })
    if demote_scope == "super_only":
        # 책임관리자 권한만 해제 (일반 관리자 권한은 유지)
        target.is_superadmin = False
        target.is_admin = True
        try:
            db.add(AdminAuditLog(user_id=target.id, action='demoted_super_only', actor_id=current_user.id, note=note_txt or None))
        except Exception:
            pass
    else:
        # 모든 관리자 권한 해제: AdminRequest에 권한 해제 기록 추가 + AuditLog
        target.is_admin = False
        target.is_superadmin = False
        
        # AdminRequest에 권한 해제 기록 추가
        from app.models.admin_request import AdminRequest
        from datetime import datetime
        revoke_record = AdminRequest(
            user_id=target.id,
            status="revoked",
            note=(note_txt or '관리자 권한 해제').strip(),
            reviewed_by=current_user.id,
            reviewed_at=datetime.utcnow()
        )
        db.add(revoke_record)
        try:
            from app.models.admin_audit_log import AdminAuditLog
            db.add(AdminAuditLog(user_id=target.id, action='demoted_all', actor_id=current_user.id, note=note_txt or None))
        except Exception:
            pass
    
    db.commit()
    return RedirectResponse(url="/admin?success=demoted", status_code=303)


# Request note edit
@router.get("/admin/request-note", response_class=HTMLResponse)
def admin_request_note_page(
    request: Request,
    request_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    return templates.TemplateResponse("admin_request_note_edit.html", {"request": request, "req": req})


@router.post("/admin/request-note")
def admin_request_note_save(
    request: Request,
    request_id: int = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_master_admin),
):
    from fastapi.responses import RedirectResponse
    req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/admin?error=request_not_found", status_code=303)
    req.note = (note or '').strip() or None
    db.commit()
    return RedirectResponse(url=f"/admin?success=note_saved", status_code=303)
