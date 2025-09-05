import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey,
    Index, Enum as SAEnum, CheckConstraint
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class WithdrawalStatus(str, enum.Enum):
    """환급 신청 상태"""
    pending = "pending"          # 신청 대기
    reviewing = "reviewing"      # 검토 중
    approved = "approved"        # 승인됨
    completed = "completed"      # 환급 완료
    rejected = "rejected"        # 거부됨
    cancelled = "cancelled"      # 신청 취소

class WithdrawalMethod(str, enum.Enum):
    """환급 방법"""
    bank_transfer = "bank_transfer"   # 계좌이체
    toss_pay = "toss_pay"            # 토스페이
    kakao_pay = "kakao_pay"          # 카카오페이

class PointWithdrawal(Base, TimestampMixin):
    """포인트 환급 신청"""
    __tablename__ = "point_withdrawals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 환급 정보
    point_amount = Column(Integer, nullable=False)  # 환급할 포인트
    withdrawal_amount = Column(Integer, nullable=False)  # 실제 환급 금액 (수수료 차감 후)
    fee_amount = Column(Integer, default=0, nullable=False)  # 수수료
    
    # 환급 방법
    method = Column(SAEnum(WithdrawalMethod, name="withdrawal_method_enum"), nullable=False)
    
    # 계좌 정보 (암호화 저장 권장)
    bank_name = Column(String(50), nullable=True)
    account_number = Column(String(100), nullable=True)
    account_holder = Column(String(50), nullable=True)
    
    # 상태 관리
    status = Column(SAEnum(WithdrawalStatus, name="withdrawal_status_enum"), 
                   default=WithdrawalStatus.pending, nullable=False)
    
    # 타임스탬프
    requested_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 처리 정보
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 관리자 ID
    rejection_reason = Column(Text, nullable=True)
    admin_memo = Column(Text, nullable=True)
    transaction_id = Column(String(100), nullable=True)  # 은행 거래 ID
    
    # 관계
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    __table_args__ = (
        CheckConstraint("point_amount >= 10000", name="ck_withdrawal_min_points"),
        CheckConstraint("withdrawal_amount > 0", name="ck_withdrawal_amount_positive"),
        CheckConstraint("fee_amount >= 0", name="ck_fee_amount_positive"),
        Index("ix_withdrawal_user_status", "user_id", "status"),
        Index("ix_withdrawal_status_date", "status", "requested_at"),
    )
    
    def approve(self, reviewer_id: int, memo: Optional[str] = None):
        """환급 신청 승인"""
        self.status = WithdrawalStatus.approved
        self.reviewed_by = reviewer_id
        self.reviewed_at = datetime.now(timezone.utc)
        if memo:
            self.admin_memo = memo
    
    def reject(self, reviewer_id: int, reason: str, memo: Optional[str] = None):
        """환급 신청 거부"""
        self.status = WithdrawalStatus.rejected
        self.reviewed_by = reviewer_id
        self.reviewed_at = datetime.now(timezone.utc)
        self.rejection_reason = reason
        if memo:
            self.admin_memo = memo
    
    def complete(self, transaction_id: Optional[str] = None):
        """환급 완료 처리"""
        self.status = WithdrawalStatus.completed
        self.completed_at = datetime.now(timezone.utc)
        if transaction_id:
            self.transaction_id = transaction_id
    
    def cancel(self):
        """신청 취소 (사용자가 취소하거나 시스템에서 취소)"""
        if self.status == WithdrawalStatus.pending:
            self.status = WithdrawalStatus.cancelled
    
    def calculate_withdrawal_amount(self, fee_rate: float = 0.01):
        """환급 금액 계산 (수수료 차감)"""
        self.fee_amount = int(self.point_amount * fee_rate)
        self.withdrawal_amount = self.point_amount - self.fee_amount
        return self.withdrawal_amount
    
    @property
    def can_cancel(self) -> bool:
        """취소 가능 여부"""
        return self.status in [WithdrawalStatus.pending, WithdrawalStatus.reviewing]
    
    @property
    def is_pending(self) -> bool:
        """대기 상태인지"""
        return self.status == WithdrawalStatus.pending
    
    def __repr__(self) -> str:
        return f"<PointWithdrawal(id={self.id}, user_id={self.user_id}, amount={self.point_amount}, status={self.status})>"