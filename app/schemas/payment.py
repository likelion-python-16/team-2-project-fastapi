# app/schemas/payment.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

# 모델의 Enum들을 import
from app.models.payment import PaymentMethodType, PaymentTransactionType, PaymentStatus

# -----------------------------
# Request Schemas
# -----------------------------
class PaymentCreateIn(BaseModel):
    """결제 생성 요청"""
    challenge_id: Optional[int] = None
    amount: int
    transaction_type: PaymentTransactionType
    method: PaymentMethodType
    order_id: str
    order_name: Optional[str] = None
    payment_key: Optional[str] = None
    metadata_json: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "challenge_id": 1,
                "amount": 10000,
                "transaction_type": "entry_fee",
                "method": "card",
                "order_id": "ORDER_20240101_001",
                "order_name": "30일 운동 챌린지 참가비",
                "payment_key": "toss_payment_key_123"
            }
        }
    )
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v > 10000000:  # 1천만원 제한
            raise ValueError("Amount cannot exceed 10,000,000 KRW")
        return v
    
    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("Order ID must be at least 5 characters")
        return v.strip()


class PaymentUpdateStatusIn(BaseModel):
    """결제 상태 업데이트 요청"""
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    cancel_reason: Optional[str] = None


class RefundCreateIn(BaseModel):
    """환불 생성 요청"""
    payment_id: int
    amount: int
    reason: str
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Refund amount must be positive")
        return v
    
    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("Refund reason must be at least 5 characters")
        return v.strip()


class TossWebhookIn(BaseModel):
    """토스 결제 웹훅"""
    orderId: str
    status: str
    paymentKey: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "orderId": "ORDER_20240101_001",
                "status": "DONE",
                "paymentKey": "toss_payment_key_123"
            }
        }
    )


# -----------------------------
# Response Schemas
# -----------------------------
class PaymentOut(BaseModel):
    """결제 정보 응답"""
    id: int
    user_id: int
    challenge_id: Optional[int] = None
    amount: int
    method: PaymentMethodType
    transaction_type: PaymentTransactionType
    status: PaymentStatus
    order_id: str
    order_name: Optional[str] = None
    payment_key: Optional[str] = None
    
    # 상태별 타임스탬프
    created_at: datetime
    approved_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # 실패/취소 정보
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    cancel_reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaymentWithUser(PaymentOut):
    """사용자 정보가 포함된 결제 정보"""
    user: Optional[dict] = None


class PaymentWithChallenge(PaymentOut):
    """챌린지 정보가 포함된 결제 정보"""
    challenge: Optional[dict] = None


class RefundOut(BaseModel):
    """환불 정보 응답"""
    id: int
    payment_id: int
    amount: int
    reason: str
    status: PaymentStatus
    requested_by: int
    
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaymentSummary(BaseModel):
    """결제 요약 정보"""
    user_id: int
    total_payments: int
    total_amount: int
    completed_payments: int
    failed_payments: int
    cancelled_payments: int
    total_refunds: int
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 호환성 별칭
# -----------------------------
PaymentCreateRequest = PaymentCreateIn
PaymentResponse = PaymentOut
RefundCreateRequest = RefundCreateIn
RefundResponse = RefundOut