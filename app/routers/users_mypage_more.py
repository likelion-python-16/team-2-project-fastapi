# app/routers/users_mypage_more.py
from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, func, desc, true
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import get_current_user
from app.deps.pagination import pagination_params

from app.models.user import User
from app.models.report import Report, ReportProof
from app.models.finance import Payment, Refund, PointExchangeRequest
from app.models.pointhistory import PointHistory
from app.models.participation import Participation
from app.models.challenge import Challenge  # 프로젝트 경로에 맞게 유지

from app.schemas.mypage_more import (
    ReportListOut, ReportItem, ReportProofItem,
    PaymentListOut, PaymentItem,
    PointHistoryListOut, PointHistorySummary, PointHistoryItem,
    PointExchangeListOut, PointExchangeItem,
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
# F-1-17: 포인트 전환(환급) 내역
# -------------------------
@router.get("/me/points/exchanges", response_model=PointExchangeListOut)
def my_point_exchanges(
    status: Optional[str] = Query(None, description="requested/processing/succeeded/failed"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    cond = [PointExchangeRequest.user_id == me.id]
    if status:
        cond.append(PointExchangeRequest.status == status)
    where_clause = and_(*cond)

    total = db.execute(
        select(func.count()).select_from(PointExchangeRequest).where(where_clause)
    ).scalar_one()

    items: list[PointExchangeItem] = []
    if total:
        rows = db.execute(
            select(PointExchangeRequest)
            .where(where_clause)
            .order_by(desc(PointExchangeRequest.requested_at), desc(PointExchangeRequest.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        items = [PointExchangeItem.model_validate(r, from_attributes=True) for r in rows]

    return PointExchangeListOut(items=items, total=total, skip=pg["skip"], limit=pg["limit"])


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
