# app/routers/users_mypage.py  (F-1-10, 11, 15, 16)

from fastapi import APIRouter, Depends, Query
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, desc, literal

from app.db.session import get_db
from app.deps.auth import get_current_user
from app.deps.pagination import pagination_params

from app.models.user import User
from app.models.following import Following
from app.models.finance import Payment, Refund
from app.models.pointhistory import PointHistory, PointHistoryType

from app.schemas.finance import SpendSummaryOut, PaymentOut, PaymentListOut
from app.schemas.user import UserBrief, FollowListOut
from app.schemas.point import PointHistoryOut, PointHistoryListOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])

# -----------------------------
# F-1-10: 지금까지 쓴 금액 요약
# -----------------------------
@router.get("/me/spend/summary", response_model=SpendSummaryOut)
def my_spend_summary(
    include_deposit: bool = False,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    pay_type_cond = literal(True) if include_deposit else (Payment.payment_type == "fee")

    total_paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            and_(
                Payment.user_id == me.id,
                Payment.status == "paid",
                pay_type_cond,
            )
        )
    ).scalar_one()

    total_refunded = db.execute(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            and_(
                Refund.user_id == me.id,
                Refund.processed_at.isnot(None),   # 또는 Refund.status == "processed"
            )
        )
    ).scalar_one()

    return SpendSummaryOut(
        total_paid=int(total_paid or 0),
        total_refunded=int(total_refunded or 0),
        net_spent=int(total_paid or 0) - int(total_refunded or 0),
    )

# -----------------------------
# F-1-15: 결제 내역
# -----------------------------
@router.get("/me/payments", response_model=PaymentListOut)
def my_payments(
    status: Optional[str] = Query(None, description="예: paid / pending / cancelled / refunded"),
    payment_type: Optional[str] = Query(None, description="예: fee / deposit"),
    date_from: Optional[str] = Query(None, description="ISO8601 시작(>=)"),
    date_to: Optional[str] = Query(None, description="ISO8601 종료(<)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),     # {skip, limit}
):
    conds = [Payment.user_id == me.id]
    if status:
        conds.append(Payment.status == status)
    if payment_type:
        conds.append(Payment.payment_type == payment_type)
    if date_from:
        conds.append(Payment.created_at >= date_from)
    if date_to:
        conds.append(Payment.created_at < date_to)

    total = db.execute(
        select(func.count()).select_from(Payment).where(and_(*conds))
    ).scalar_one()

    items = []
    if total:
        rows = db.execute(
            select(Payment)
            .where(and_(*conds))
            .order_by(desc(Payment.created_at), desc(Payment.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        items = [PaymentOut.model_validate(r, from_attributes=True) for r in rows]

    return PaymentListOut(items=items, total=int(total or 0), skip=pg["skip"], limit=pg["limit"])

# -----------------------------
# F-1-16: 포인트 내역
# -----------------------------
@router.get("/me/points", response_model=PointHistoryListOut)
def my_point_history(
    type: Optional[PointHistoryType] = Query(None, description="gain/use/refund"),
    challenge_id: Optional[int] = Query(None, description="특정 챌린지 필터"),
    date_from: Optional[str] = Query(None, description="ISO8601 시작(>=)"),
    date_to: Optional[str] = Query(None, description="ISO8601 종료(<)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    conds = [PointHistory.user_id == me.id]
    if type is not None:
        conds.append(PointHistory.type == type)
    if challenge_id is not None:
        conds.append(PointHistory.challenge_id == challenge_id)
    if date_from:
        conds.append(PointHistory.created_at >= date_from)
    if date_to:
        conds.append(PointHistory.created_at < date_to)

    total = db.execute(
        select(func.count()).select_from(PointHistory).where(and_(*conds))
    ).scalar_one()

    items = []
    if total:
        rows = db.execute(
            select(PointHistory)
            .where(and_(*conds))
            .order_by(desc(PointHistory.created_at), desc(PointHistory.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        items = [PointHistoryOut.model_validate(r, from_attributes=True) for r in rows]

    current_points = int(me.total_points or 0)

    return PointHistoryListOut(
        items=items,
        total=int(total or 0),
        skip=pg["skip"],
        limit=pg["limit"],
        current_points=current_points,
    )

# -----------------------------
# F-1-11: 팔로우/팔로워
# -----------------------------
@router.get("/me/following", response_model=FollowListOut)
def my_following(
    only_active: bool = Query(True, description="활성 사용자만"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    total = db.execute(
        select(func.count())
        .select_from(Following)
        .join(User, User.id == Following.following_id)
        .where(and_(Following.follower_id == me.id, (User.is_active == True) if only_active else True))  # noqa: E712
    ).scalar_one()

    users = []
    if total:
        rows = db.execute(
            select(User)
            .join(Following, Following.following_id == User.id)
            .where(and_(Following.follower_id == me.id, (User.is_active == True) if only_active else True))  # noqa: E712
            .order_by(desc(Following.created_at), desc(User.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        users = [UserBrief.model_validate(u, from_attributes=True) for u in rows]

    return FollowListOut(items=users, total=int(total or 0), skip=pg["skip"], limit=pg["limit"])

@router.get("/me/followers", response_model=FollowListOut)
def my_followers(
    only_active: bool = Query(True, description="활성 사용자만"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    pg: dict = Depends(pagination_params),
):
    total = db.execute(
        select(func.count())
        .select_from(Following)
        .join(User, User.id == Following.follower_id)
        .where(and_(Following.following_id == me.id, (User.is_active == True) if only_active else True))  # noqa: E712
    ).scalar_one()

    users = []
    if total:
        rows = db.execute(
            select(User)
            .join(Following, Following.follower_id == User.id)
            .where(and_(Following.following_id == me.id, (User.is_active == True) if only_active else True))  # noqa: E712
            .order_by(desc(Following.created_at), desc(User.id))
            .offset(pg["skip"]).limit(pg["limit"])
        ).scalars().all()
        users = [UserBrief.model_validate(u, from_attributes=True) for u in rows]

    return FollowListOut(items=users, total=int(total or 0), skip=pg["skip"], limit=pg["limit"])

