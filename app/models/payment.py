# app/models/payment.py
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SAEnum,
    CheckConstraint, Index, ForeignKeyConstraint
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

# ===== Enums =====
class PaymentMethodType(str, enum.Enum):
    card = "card"
    bank_transfer = "bank_transfer"
    toss_pay = "toss_pay"
    kakao_pay = "kakao_pay"
    point = "point"

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    refunded = "refunded"
    partial_refunded = "partial_refunded"

class PaymentTransactionType(str, enum.Enum):
    entry_fee = "entry_fee"
    monthly_fee = "monthly_fee"
    penalty = "penalty"
    etc = "etc"

# ===== Payment =====
class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    # 핵심 FK
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=True, index=True)

    # Participation(복합 PK: user_id + challenge_id)에 매핑 (nullable 허용)
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        Index("ix_payment_user_status", "user_id", "status"),
        Index("ix_payment_challenge_type", "challenge_id", "transaction_type"),
        ForeignKeyConstraint(
            ["user_id", "challenge_id"],
            ["participations.user_id", "participations.challenge_id"],
            name="fk_payment_participation",
            use_alter=True,
        ),
    )

    # 결제 정보
    method = Column(SAEnum(PaymentMethodType, name="payment_method_type_enum"), nullable=False)
    transaction_type = Column(SAEnum(PaymentTransactionType, name="payment_transaction_type_enum"), nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(SAEnum(PaymentStatus, name="payment_status_enum"), nullable=False, default=PaymentStatus.pending)

    # 주문/연동 정보
    order_id = Column(String(100), unique=True, index=True, nullable=False)
    order_name = Column(String(200), nullable=True)
    payment_key = Column(String(255), unique=True, nullable=True)  # PG 결제키(옵션)

    # 타임스탬프
    requested_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # 부가 정보
    failure_code = Column(String(50), nullable=True)
    failure_message = Column(Text, nullable=True)
    cancel_reason = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    # 관계
    user = relationship("User", back_populates="payments")
    challenge = relationship("Challenge", back_populates="payments")

    # Participation은 조회 편의용(양방향 back_populates 없이, Participation 쪽 정의와 충돌 방지)
    participation = relationship(
        "Participation",
        primaryjoin="and_(Payment.user_id==Participation.user_id, Payment.challenge_id==Participation.challenge_id)",
        viewonly=True,
        overlaps="user,challenge,payments"
    )

    # Refunds(단방향)
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")

    # 비즈니스 헬퍼
    def approve(self):
        self.status = PaymentStatus.completed
        self.approved_at = datetime.now(timezone.utc)

    def fail(self, code: Optional[str] = None, message: Optional[str] = None):
        self.status = PaymentStatus.failed
        self.failed_at = datetime.now(timezone.utc)
        self.failure_code = code
        self.failure_message = message

    def cancel(self, reason: Optional[str] = None):
        if self.status in (PaymentStatus.pending, PaymentStatus.success):
            self.status = PaymentStatus.cancelled
            self.cancelled_at = datetime.now(timezone.utc)
            self.cancel_reason = reason

    def is_successful(self) -> bool:
        return self.status in (PaymentStatus.success, PaymentStatus.completed)

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, order_id='{self.order_id}', status={self.status})>"

class PaymentMethod(Base, TimestampMixin):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    method = Column(SAEnum(PaymentMethodType, name="payment_method_type_enum"), nullable=False)
    display_name = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    # 관계: User <-> PaymentMethod (User 모델의 payment_methods 와 짝)
    user = relationship("User")

# ===== Refund =====
class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=True, index=True)

    refund_amount = Column(Integer, nullable=False)
    refund_reason = Column(Text, nullable=True)

    # 환불 상태는 PaymentStatus 재사용(경량화 목적)
    status = Column(SAEnum(PaymentStatus, name="refund_status_enum"), nullable=False, default=PaymentStatus.pending)

    requested_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    # 관계
    payment = relationship("Payment", back_populates="refunds")
    user = relationship("User", back_populates="refunds")
    challenge = relationship("Challenge", back_populates="refunds")

    __table_args__ = (
        CheckConstraint("refund_amount >= 0", name="ck_refund_amount_positive"),
        Index("ix_refund_user_date", "user_id", "requested_at"),
    )

    def mark_processed(self):
        self.status = PaymentStatus.refunded
        self.processed_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<Refund(id={self.id}, payment_id={self.payment_id}, amount={self.refund_amount})>"
