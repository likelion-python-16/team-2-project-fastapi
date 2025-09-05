# app/routers/users_mypage_more.py
from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, func, desc, true
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.security import get_current_user
# Simple pagination helper  
def pagination_params(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    skip = (page - 1) * limit
    return {"page": page, "limit": limit, "skip": skip}

from app.models.user import User
from app.models.report import Report, ReportProof
from app.models.payment import Payment, Refund
from app.models.pointhistory import PointHistory
from app.models.participation import Participation
from app.models.challenge import Challenge  # 프로젝트 경로에 맞게 유지

from app.schemas.mypage_more import (
    ReportListOut, ReportItem, ReportProofItem,
    PaymentListOut, PaymentItem,
    PointHistoryListOut, PointHistorySummary, PointHistoryItem,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# -------------------------
# F-1-14: 내 신고 내역 (+첨부)
# -------------------------
@router.get("/me/reports", response_model=ReportListOut)
def my_reports(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    total = db.execute(
        select(func.count()).select_from(Report).where(Report.reporter_id == me.id)
    ).scalar_one()

    if not total:
        return ReportListOut(items=[], total=0, skip=pg["skip"], limit=pg["limit"])

    reports = db.execute(
        select(Report)
        .where(Report.reporter_id == me.id)
        .order_by(desc(Report.created_at), desc(Report.id))
        .offset(pg["skip"]).limit(pg["limit"])
    ).scalars().all()

    rep_ids = [r.id for r in reports]
    proofs_by_report: dict[int, list[ReportProofItem]] = {}
    if rep_ids:
        proofs = db.execute(
            select(ReportProof)
            .where(ReportProof.report_id.in_(rep_ids))
            .order_by(ReportProof.id.asc())
        ).scalars().all()
        for p in proofs:
            proofs_by_report.setdefault(p.report_id, []).append(
                ReportProofItem.model_validate(p, from_attributes=True)
            )

    items: list[ReportItem] = []
    for r in reports:
        item = ReportItem.model_validate(r, from_attributes=True)
        item.proofs = proofs_by_report.get(r.id, [])
        items.append(item)

    return ReportListOut(items=items, total=total, skip=pg["skip"], limit=pg["limit"])


# -------------------------
# F-1-15: 결제 내역
# -------------------------
@router.get("/me/payments", response_model=PaymentListOut)
def my_payments(
    status: Optional[str] = Query(None, description="paid/pending/cancelled/refunded 등"),
    payment_type: Optional[str] = Query(None, description="fee/deposit 등"),
    date_from: Optional[datetime] = Query(None, description="ISO datetime (inclusive)"),
    date_to: Optional[datetime] = Query(None, description="ISO datetime (inclusive)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    cond = [Payment.user_id == me.id]
    if status:
        cond.append(Payment.status == status)
    if payment_type:
        cond.append(Payment.payment_type == payment_type)
    if date_from:
        cond.append(Payment.created_at >= date_from)
    if date_to:
        cond.append(Payment.created_at <= date_to)

    where_clause = and_(*cond)

    total = db.execute(
        select(func.count()).select_from(Payment).where(where_clause)
    ).scalar_one()

    items: list[PaymentItem] = []
    if total:
        rows = db.execute(
            select(Payment)
            .where(where_clause)
            .order_by(desc(Payment.created_at), desc(Payment.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        items = [PaymentItem.model_validate(r, from_attributes=True) for r in rows]

    return PaymentListOut(items=items, total=total, skip=pg["skip"], limit=pg["limit"])


# -------------------------
# F-1-15b: 환불 내역
# -------------------------
@router.get("/me/refunds", response_model=PaymentListOut)
def my_refunds(
    status: Optional[str] = Query(None, description="환불 상태: pending/success/completed/failed"),
    date_from: Optional[datetime] = Query(None, description="ISO datetime (inclusive)"),
    date_to: Optional[datetime] = Query(None, description="ISO datetime (inclusive)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    """사용자 환불 내역"""
    from sqlalchemy import text
    
    # 조건 빌드
    where_conditions = ["user_id = :user_id"]
    params = {"user_id": me.id}
    
    if status:
        where_conditions.append("status = :status")
        params["status"] = status
    
    if date_from:
        where_conditions.append("created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_conditions.append("created_at <= :date_to")
        params["date_to"] = date_to
    
    where_clause = " AND ".join(where_conditions)
    
    # 총 개수 조회
    count_query = f"SELECT COUNT(*) as total FROM refunds WHERE {where_clause}"
    total_result = db.execute(text(count_query), params)
    total = total_result.fetchone()[0]
    
    print(f"DEBUG: Refunds query - user_id={me.id}, status={status}, total={total}")  # 디버깅
    
    items = []
    if total > 0:
        # 데이터 조회
        data_query = f"""
        SELECT id, user_id, challenge_id, payment_id, refund_amount, status, 
               refund_reason, processed_at, requested_at, created_at, updated_at
        FROM refunds 
        WHERE {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
        """
        params.update({"limit": pg["limit"], "offset": pg["skip"]})
        
        rows = db.execute(text(data_query), params)
        
        # PaymentItem 형태로 변환
        for row in rows:
            item = PaymentItem(
                id=row.id,
                amount=int(row.refund_amount),
                status=row.status,
                payment_type="refund",
                method="card",  # 기본값
                created_at=row.created_at
            )
            items.append(item)

    print(f"DEBUG: Refunds result - items={len(items)}")  # 디버깅
    return PaymentListOut(items=items, total=total, skip=pg["skip"], limit=pg["limit"])


# -------------------------
# F-1-16: 포인트 내역
# -------------------------
@router.get("/me/points/history", response_model=PointHistoryListOut)
def my_point_history(
    kind: Literal["all", "earn", "spend"] = Query("all"),
    legacy_type: Optional[str] = Query(None, alias="type"),   # 기존 프론트 호환
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    if legacy_type:
        t = legacy_type.lower()
        if t in ("use", "spend"):
            kind = "spend"
        elif t in ("gain", "earn"):
            kind = "earn"

    conds = [PointHistory.user_id == me.id]
    if kind == "earn":
        conds.append(PointHistory.point_amount > 0)
    elif kind == "spend":
        conds.append(PointHistory.point_amount < 0)
    if start:
        conds.append(PointHistory.created_at >= start)
    if end:
        conds.append(PointHistory.created_at <= end)

    where_clause = and_(*conds) if conds else true()

    total = db.execute(
        select(func.count()).select_from(PointHistory).where(where_clause)
    ).scalar_one()

    items: list[PointHistoryItem] = []
    if total:
        rows = db.execute(
            select(PointHistory)
            .where(where_clause)
            .order_by(desc(PointHistory.created_at), desc(PointHistory.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        items = [PointHistoryItem.model_validate(r, from_attributes=True) for r in rows]

    earned_sum = db.execute(
        select(func.coalesce(func.sum(PointHistory.point_amount), 0))
        .where(and_(PointHistory.user_id == me.id, PointHistory.point_amount > 0))
    ).scalar_one()

    spent_sum_raw = db.execute(
        select(func.coalesce(func.sum(PointHistory.point_amount), 0))
        .where(and_(PointHistory.user_id == me.id, PointHistory.point_amount < 0))
    ).scalar_one()

    db.refresh(me)

    summary = PointHistorySummary(
        total_points=int(me.total_points or 0),
        earned_sum=int(earned_sum or 0),
        spent_sum=abs(int(spent_sum_raw or 0)),
    )

    return PointHistoryListOut(
        summary=summary,
        items=items,
        total=total,
        skip=pg["skip"],
        limit=pg["limit"],
        kind=kind,
    )



# -------------------------
# F-1-18: 참여한 챌린지 목록
# -------------------------
@router.get("/me/participations")
def my_participations(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    return list_user_participations(me.id, db, me, pg)


@router.get("/{user_id}/participations")
def list_user_participations(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    if user_id != me.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    conds = [
        Participation.user_id == me.id,
        Participation.is_active == 1,
    ]

    total = db.execute(
        select(func.count()).select_from(Participation).where(and_(*conds))
    ).scalar_one()

    items = []
    if total:
        rows = db.execute(
            select(
                Participation.id.label("participation_id"),
                Participation.joined_at.label("joined_at"),
                Participation.status.label("participation_status"),
                Participation.role.label("role"),
                Challenge.id.label("challenge_id"),
                Challenge.title.label("title"),
                Challenge.status.label("challenge_status"),
                Challenge.start_date.label("start_date"),
                Challenge.end_date.label("end_date"),
            )
            .join(Challenge, Challenge.id == Participation.challenge_id)
            .where(and_(*conds))
            .order_by(desc(Challenge.start_date), desc(Challenge.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).all()

        items = [dict(r._mapping) for r in rows]

    return {"items": items, "total": total, "skip": pg["skip"], "limit": pg["limit"]}
