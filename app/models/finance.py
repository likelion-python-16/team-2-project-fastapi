import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Text,
    Enum as SAEnum, DECIMAL, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin  # Base / TimestampMixin은 base.py에 이미 있음

# -------------------------
# Enums (상태값 통일)
# -------------------------
class PaymentStatus(str, enum.Enum):
    pending   = "pending"     # 결제 대기
    paid      = "paid"        # 결제 완료
    cancelled = "cancelled"   # 결제 취소
    refunded  = "refunded"    # 환불 완료(부분/전체 후 집계상태)

class RefundStatus(str, enum.Enum):
    pending    = "pending"     # 환불 요청 접수
    processing = "processing"  # 게이트웨이/PG 처리 중
    succeeded  = "succeeded"   # 환불 성공
    failed     = "failed"      # 환불 실패

class PointExchangeStatus(str, enum.Enum):
    pending  = "pending"   # 환전 요청
    approved = "approved"  # 관리자 승인
    rejected = "rejected"  # 관리자 거절
    paid     = "paid"      # 현금 지급 완료

# -------------------------
# Payment
# -------------------------
class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    user_id      = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False)

    amount       = Column(DECIMAL(12, 2), nullable=False)
    currency     = Column(String(3), default="KRW", nullable=False)
    payment_type = Column(String(20), nullable=False)   # 예: card, vbank, bank_transfer
    status       = Column(SAEnum(PaymentStatus, name="payment_status_enum"), default=PaymentStatus.pending, nullable=False)

    toss_payment_id        = Column(String(100), nullable=False)
    idempotency_key        = Column(String(64), nullable=True)   # 요청 중복 방지용(선택)
    planner_id_at_payment  = Column(Integer, nullable=True)      # 결제 시점의 플래너 ID 스냅샷

    # 관계
    user      = relationship("User", back_populates="payments", foreign_keys=[user_id])
    challenge = relationship("Challenge", back_populates="payments")

    __table_args__ = (
        UniqueConstraint('toss_payment_id', name='uq_payment_toss'),
        UniqueConstraint('idempotency_key', name='uq_payment_idem'),
        Index('ix_payment_user_created', 'user_id', 'created_at'),
        Index('ix_payment_status', 'status'),
        Index('ix_payment_challenge', 'challenge_id'),
        Index('ix_payment_amount', 'amount'),  # 금액별 조회용
    )

# -------------------------
# Refund
# -------------------------
class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)

    user_id      = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False)

    amount        = Column(DECIMAL(12, 2), nullable=False)
    currency      = Column(String(3), default="KRW", nullable=False)
    reason        = Column(String(100), nullable=False)
    processed_at  = Column(DateTime, nullable=True)

    refund_status = Column(SAEnum(RefundStatus, name="refund_status_enum"), default=RefundStatus.pending, nullable=False)
    toss_refund_id = Column(String(100), nullable=True)
    error_msg     = Column(Text, nullable=True)

    # 관계
    user      = relationship("User", back_populates="refunds")
    challenge = relationship("Challenge", back_populates="refunds")

    __table_args__ = (
        UniqueConstraint('toss_refund_id', name='uq_refund_toss'),
        Index('ix_refund_user_processed', 'user_id', 'processed_at'),
        Index('ix_refund_status', 'refund_status'),
        Index('ix_refund_challenge', 'challenge_id'),
        Index('ix_refund_amount', 'amount'),  # 금액별 조회용
    )

# -------------------------
# PointExchangeRequest
# -------------------------
class PointExchangeRequest(Base, TimestampMixin):
    __tablename__ = "point_exchange_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    point_amount = Column(Integer, nullable=False)        # 요청 포인트
    cash_amount  = Column(DECIMAL(12, 2), nullable=False) # 환전 금액(정책 반영 후)
    status       = Column(SAEnum(PointExchangeStatus, name="point_exchange_status_enum"), default=PointExchangeStatus.pending, nullable=False)

    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # 관계
    user = relationship("User", back_populates="point_exchange_requests")

    __table_args__ = (
        Index('ix_px_user_requested', 'user_id', 'requested_at'),
        Index('ix_px_status', 'status'),
        Index('ix_px_amount', 'point_amount'),  # 포인트 금액별 조회용
    )