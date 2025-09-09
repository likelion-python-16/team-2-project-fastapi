# app/schemas/participation.py
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from enum import Enum

# 모델의 Enum들을 import
from app.models.participation import (
    ParticipationRole, ParticipationStatus, PaymentCycle, LeaveType
)

# -----------------------------
# Request Schemas
# -----------------------------
class ParticipationCreate(BaseModel):
    """챌린지 참가 신청"""
    challenge_id: int
    payment_cycle: Optional[PaymentCycle] = None  # both 타입일 때 선택
    message: Optional[str] = None  # 참가 동기/메시지
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "challenge_id": 1,
                "payment_cycle": "entry_fee",
                "message": "열심히 참여하겠습니다!"
            }
        }
    )
    
    @field_validator("challenge_id")
    @classmethod
    def validate_challenge_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Challenge ID must be positive")
        return v


class ParticipationUpdate(BaseModel):
    """참가 정보 수정 (관리자용)"""
    role: Optional[ParticipationRole] = None
    is_notification_enabled: Optional[bool] = None
    auto_payment_enabled: Optional[bool] = None
    join_motivation: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ParticipationApproval(BaseModel):
    """참가 승인/거부 (챌린지 생성자용)"""
    approved: bool
    rejection_reason: Optional[str] = None
    
    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: Optional[str], info) -> Optional[str]:
        if not info.data.get("approved") and not v:
            raise ValueError("Rejection reason is required when not approved")
        return v


class KickParticipantRequest(BaseModel):
    """참가자 강제 퇴출 요청"""
    target_user_id: int
    reason: str
    
    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v.strip()


# -----------------------------
# Response Schemas  
# -----------------------------
class ParticipationResponse(BaseModel):
    """참가 정보 응답 - 모델 구조와 일치"""
    user_id: int
    challenge_id: int
    role: ParticipationRole
    status: ParticipationStatus
    
    # 시간 정보
    joined_at: datetime
    activated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
    
    # 결제 관련
    payment_cycle: Optional[PaymentCycle] = None
    next_payment_date: Optional[date] = None
    payment_failed_count: int = 0
    total_paid_amount: int = 0
    
    # 진행률 & 통계
    progress_rate: float = 0.0
    attendance_count: int = 0
    total_rounds: Optional[int] = None
    
    # 탈퇴 관련
    leave_type: Optional[LeaveType] = None
    leave_reason: Optional[str] = None
    kicked_by: Optional[int] = None
    
    # 기타 설정
    is_notification_enabled: bool = True
    auto_payment_enabled: bool = True
    join_motivation: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ParticipationWithUser(ParticipationResponse):
    """유저 정보가 포함된 참가 정보"""
    user: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)


class ParticipationWithChallenge(ParticipationResponse):
    """챌린지 정보가 포함된 참가 정보"""
    challenge: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)


class ParticipationListItem(BaseModel):
    """목록 조회용 간소화된 참가 정보"""
    user_id: int
    challenge_id: int
    role: ParticipationRole
    status: ParticipationStatus
    joined_at: datetime
    progress_rate: float = 0.0
    
    # 추가 필드
    user_nickname: Optional[str] = None
    challenge_title: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 특수 목적 Schemas
# -----------------------------
class ParticipantStats(BaseModel):
    """참가자 통계"""
    challenge_id: int
    total_participants: int
    active_participants: int
    pending_approvals: int
    payment_pending: int = 0
    completed_participants: int = 0
    
    # 역할별
    creators_count: int = 0
    managers_count: int = 0
    moderators_count: int = 0
    participants_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class MyParticipation(BaseModel):
    """내 참가 현황 - status 기반"""
    user_id: int
    challenge_id: int
    challenge_title: str
    challenge_status: str
    
    # 참가 정보
    role: ParticipationRole
    status: ParticipationStatus
    joined_at: datetime
    progress_rate: float = 0.0
    
    # 결제 정보
    payment_cycle: Optional[PaymentCycle] = None
    total_paid_amount: int = 0
    
    # 챌린지 관련
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    current_participants: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class ParticipationProgress(BaseModel):
    """참가자 진행 상황"""
    user_id: int
    challenge_id: int
    progress_rate: float
    attendance_count: int
    total_rounds: Optional[int] = None
    
    # 계산된 필드
    participation_rate: Optional[float] = None
    remaining_rounds: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# Action Response Schemas
# -----------------------------
class ParticipationActionResponse(BaseModel):
    """참가 관련 액션 응답"""
    message: str
    user_id: Optional[int] = None
    challenge_id: Optional[int] = None
    status: Optional[ParticipationStatus] = None
    
    model_config = ConfigDict(from_attributes=True)


class LeaveResponse(BaseModel):
    """챌린지 탈퇴 응답"""
    message: str
    left_at: datetime
    leave_type: LeaveType
    refund_amount: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class PaymentCompleteResponse(BaseModel):
    """결제 완료 응답"""
    message: str
    user_id: int
    challenge_id: int
    activated_at: datetime
    payment_cycle: PaymentCycle
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 일괄 처리용 Schemas
# -----------------------------
class BulkApprovalRequest(BaseModel):
    """일괄 승인/거부 요청"""
    participation_ids: List[str]  # "user_id:challenge_id" 형태
    approved: bool
    rejection_reason: Optional[str] = None
    
    @field_validator("participation_ids")
    @classmethod
    def validate_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one participation required")
        if len(v) > 50:
            raise ValueError("Cannot process more than 50 participations at once")
        
        # "user_id:challenge_id" 형태 검증
        for pid in v:
            if ":" not in pid:
                raise ValueError("Invalid participation ID format")
            try:
                user_id, challenge_id = pid.split(":")
                int(user_id), int(challenge_id)
            except (ValueError, IndexError):
                raise ValueError(f"Invalid participation ID: {pid}")
        
        return v


class BulkApprovalResponse(BaseModel):
    """일괄 처리 응답"""
    total_requested: int
    successful: int
    failed: int
    errors: List[str] = []
    
    model_config = ConfigDict(from_attributes=True)


class BulkProgressUpdateRequest(BaseModel):
    """일괄 진행률 업데이트 요청 (출석 체크용)"""
    updates: List[dict]  # [{"user_id": int, "attendance_count": int}, ...]
    
    @field_validator("updates")
    @classmethod
    def validate_updates(cls, v: List[dict]) -> List[dict]:
        if not v:
            raise ValueError("At least one update required")
        if len(v) > 100:
            raise ValueError("Cannot process more than 100 updates at once")
        
        for update in v:
            if not isinstance(update.get("user_id"), int) or update["user_id"] <= 0:
                raise ValueError("Invalid user_id")
            if not isinstance(update.get("attendance_count"), int) or update["attendance_count"] < 0:
                raise ValueError("Invalid attendance_count")
        
        return v


# -----------------------------
# 검색 및 필터 Schemas
# -----------------------------
class ParticipationFilter(BaseModel):
    """참가자 목록 필터"""
    status: Optional[ParticipationStatus] = None
    role: Optional[ParticipationRole] = None
    payment_cycle: Optional[PaymentCycle] = None
    min_progress_rate: Optional[float] = None
    max_progress_rate: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaymentDueParticipant(BaseModel):
    """결제 예정 참가자"""
    user_id: int
    challenge_id: int
    user_name: str
    challenge_title: str
    next_payment_date: date
    payment_cycle: PaymentCycle
    amount_due: int
    payment_failed_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 상태별 응답 Schemas
# -----------------------------
class PendingParticipation(BaseModel):
    """승인 대기 참가"""
    user_id: int
    challenge_id: int
    user_name: str
    user_email: str
    challenge_title: str
    joined_at: datetime
    join_motivation: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ActiveParticipation(BaseModel):
    """활성 참가"""
    user_id: int
    challenge_id: int
    role: ParticipationRole
    activated_at: datetime
    progress_rate: float
    attendance_count: int
    payment_cycle: Optional[PaymentCycle] = None
    
    model_config = ConfigDict(from_attributes=True)


class CompletedParticipation(BaseModel):
    """완료된 참가"""
    user_id: int
    challenge_id: int
    completed_at: datetime
    final_progress_rate: float
    total_attendance: int
    total_paid_amount: int
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 호환성 별칭
# -----------------------------
ParticipationOut = ParticipationResponse
ParticipationCreateRequest = ParticipationCreate
ParticipationUpdateRequest = ParticipationUpdate

# 복합키 처리용 헬퍼
def create_participation_id(user_id: int, challenge_id: int) -> str:
    """복합키를 문자열 ID로 변환"""
    return f"{user_id}:{challenge_id}"

def parse_participation_id(participation_id: str) -> tuple[int, int]:
    """문자열 ID를 복합키로 변환"""
    try:
        user_id, challenge_id = participation_id.split(":")
        return int(user_id), int(challenge_id)
    except (ValueError, IndexError):
        raise ValueError(f"Invalid participation ID format: {participation_id}")