from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.models.point_withdrawal import WithdrawalStatus, WithdrawalMethod


class WithdrawalRequest(BaseModel):
    """환급 신청 요청"""
    point_amount: int = Field(..., ge=10000, description="환급할 포인트 (최소 10,000)")
    method: WithdrawalMethod = Field(..., description="환급 방법")
    bank_name: Optional[str] = Field(None, max_length=50, description="은행명")
    account_number: Optional[str] = Field(None, max_length=100, description="계좌번호")
    account_holder: Optional[str] = Field(None, max_length=50, description="예금주명")
    
    @model_validator(mode='after')
    def validate_bank_info(self):
        if self.method == WithdrawalMethod.bank_transfer:
            if not self.bank_name or not self.bank_name.strip():
                raise ValueError("계좌이체 선택 시 은행명은 필수입니다")
            if not self.account_number or not self.account_number.strip():
                raise ValueError("계좌이체 선택 시 계좌번호는 필수입니다")
            if not self.account_holder or not self.account_holder.strip():
                raise ValueError("계좌이체 선택 시 예금주명은 필수입니다")
        return self


class WithdrawalResponse(BaseModel):
    """환급 신청 응답"""
    withdrawal_id: int
    point_amount: int
    withdrawal_amount: int
    fee_amount: int
    status: WithdrawalStatus
    message: str


class WithdrawalDetail(BaseModel):
    """환급 신청 상세 정보"""
    id: int
    point_amount: int
    withdrawal_amount: int
    fee_amount: int
    method: WithdrawalMethod
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    status: WithdrawalStatus
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    admin_memo: Optional[str] = None
    transaction_id: Optional[str] = None
    can_cancel: bool
    
    class Config:
        from_attributes = True


class WithdrawalListItem(BaseModel):
    """환급 신청 목록 항목"""
    id: int
    point_amount: int
    withdrawal_amount: int
    fee_amount: int
    method: WithdrawalMethod
    status: WithdrawalStatus
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    can_cancel: bool
    
    class Config:
        from_attributes = True


class WithdrawalAdminDetail(BaseModel):
    """관리자용 환급 신청 상세"""
    id: int
    user_id: int
    username: str
    user_name: str
    point_amount: int
    withdrawal_amount: int
    fee_amount: int
    method: WithdrawalMethod
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    requested_at: datetime
    status: WithdrawalStatus


class WithdrawalReview(BaseModel):
    """환급 신청 검토 요청"""
    memo: Optional[str] = Field(None, max_length=500, description="관리자 메모")


class WithdrawalRejection(WithdrawalReview):
    """환급 신청 거부 요청"""
    reason: str = Field(..., max_length=500, description="거부 사유")


class WithdrawalCompletion(BaseModel):
    """환급 완료 요청"""
    transaction_id: Optional[str] = Field(None, max_length=100, description="거래 ID")


class RewardInfo(BaseModel):
    """챌린지 보상 정보"""
    challenge_id: int
    challenge_title: str
    challenge_status: str
    total_participants: int
    completers_count: int
    total_entry_fees: int
    expected_reward_per_person: int
    completion_rate: float


class RewardDistributionResult(BaseModel):
    """보상 분배 결과"""
    message: str
    challenge_id: int
    challenge_title: str
    completers: int
    total_entry_fees: int
    reward_per_person: int
    total_distributed: int
    remaining_amount: int
    reward_details: list


class UserRewardHistory(BaseModel):
    """사용자 보상 내역"""
    id: int
    challenge_id: int
    challenge_title: str
    description: str
    point_amount: int
    received_at: datetime
    
    class Config:
        from_attributes = True