# app/schemas/challenge.py
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


# -----------------------------
# Enums (새 모델과 일치하도록 수정)
# -----------------------------
class ChallengeMode(str, Enum):
    online = "online"
    offline = "offline"
    hybrid = "hybrid"


class ChallengeStatus(str, Enum):
    draft = "draft"              # ✅ 추가
    recruiting = "recruiting"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    closed = "closed"            # ✅ 추가


class PaymentType(str, Enum):
    """✅ 새로운 결제 방식 Enum"""
    free = "free"               # 무료
    entry_fee = "entry_fee"     # 일회성 참가비
    monthly_fee = "monthly_fee"  # 월 정기결제
    both = "both"               # 참가비 + 월회비 선택 가능


# -----------------------------
# Create Schema (완전 수정)
# -----------------------------
class ChallengeCreate(BaseModel):
    # 기본 정보
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # ✅ 새로운 결제 시스템
    payment_type: PaymentType = PaymentType.free
    entry_fee: Optional[int] = 0
    monthly_fee: Optional[int] = 0

    # 참가 인원
    min_participants: Optional[int] = 1
    max_participants: Optional[int] = None

    # 회차/참여율 (max_participation_rate 제거)
    total_rounds: Optional[int] = None
    min_participation_rate: Optional[int] = 80

    # ✅ 리워드 (reward → reward_description)
    use_reward: Optional[bool] = False
    reward_description: Optional[str] = None

    # 모드/기본 링크
    mode: ChallengeMode = ChallengeMode.online  # 기본값 online으로 변경
    default_zoom_link: Optional[str] = None

    # ✅ 간소화된 장소 정보
    same_place_for_all_rounds: Optional[bool] = False
    default_place_name: Optional[str] = None
    default_address: Optional[str] = None  # road_address 통합
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None

    # 기본 설정
    require_approval: Optional[bool] = False
    is_public: Optional[bool] = True

    # 태그(카테고리)
    tags: Optional[List[str]] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "title": "30일 운동 챌린지",
                "description": "매일 30분 운동하기",
                "start_date": "2025-01-01",
                "end_date": "2025-01-30",
                "payment_type": "entry_fee",
                "entry_fee": 10000,
                "monthly_fee": 0,
                "min_participants": 5,
                "max_participants": 20,
                "total_rounds": 30,
                "min_participation_rate": 80,
                "use_reward": True,
                "reward_description": "완주자에게 기프티콘 증정",
                "mode": "hybrid",
                "default_zoom_link": None,
                "same_place_for_all_rounds": True,
                "default_place_name": "탄천종합운동장",
                "default_address": "경기도 성남시 분당구 탄천로 215",
                "default_latitude": 37.1234,
                "default_longitude": 127.1234,
                "require_approval": False,
                "is_public": True,
                "tags": ["건강", "운동", "습관형성"],
            }
        },
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        if len(v.strip()) < 2:
            raise ValueError("Title must be at least 2 characters long")
        if len(v.strip()) > 200:
            raise ValueError("Title cannot exceed 200 characters")
        return v.strip()

    @field_validator("entry_fee")
    @classmethod
    def validate_entry_fee(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Entry fee cannot be negative")
        if v is not None and v > 1000000:  # 100만원 제한
            raise ValueError("Entry fee cannot exceed 1,000,000 KRW")
        return v

    @field_validator("monthly_fee")
    @classmethod
    def validate_monthly_fee(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Monthly fee cannot be negative")
        if v is not None and v > 100000:  # 10만원 제한
            raise ValueError("Monthly fee cannot exceed 100,000 KRW")
        return v

    @field_validator("min_participation_rate")
    @classmethod
    def validate_min_rate(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Participation rate must be between 0 and 100")
        return v

    @field_validator("min_participants")
    @classmethod
    def validate_min_participants(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Minimum participants must be at least 1")
        return v

    @field_validator("max_participants")
    @classmethod
    def validate_max_participants(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Maximum participants must be at least 1")
        return v

    @model_validator(mode="after")
    def validate_cross_fields(self):
        # 날짜 검증
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be ≤ end_date")

        # 참가자 수 검증
        if (self.min_participants is not None and self.max_participants is not None 
            and self.max_participants < self.min_participants):
            raise ValueError("max_participants must be ≥ min_participants")

        # 리워드 검증
        if self.use_reward and not (self.reward_description and self.reward_description.strip()):
            raise ValueError("Reward description is required when use_reward is True")

        # ✅ 결제 타입별 검증
        if self.payment_type == PaymentType.entry_fee:
            if not self.entry_fee or self.entry_fee == 0:
                raise ValueError("Entry fee must be > 0 when payment_type is entry_fee")
        elif self.payment_type == PaymentType.monthly_fee:
            if not self.monthly_fee or self.monthly_fee == 0:
                raise ValueError("Monthly fee must be > 0 when payment_type is monthly_fee")
        elif self.payment_type == PaymentType.both:
            if ((not self.entry_fee or self.entry_fee == 0) and 
                (not self.monthly_fee or self.monthly_fee == 0)):
                raise ValueError("At least one fee must be > 0 when payment_type is both")

        return self


# -----------------------------
# Update Schema (완전 수정)
# -----------------------------
class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[ChallengeStatus] = None

    # ✅ 새로운 결제 시스템
    payment_type: Optional[PaymentType] = None
    entry_fee: Optional[int] = None
    monthly_fee: Optional[int] = None

    # 참가 인원
    min_participants: Optional[int] = None
    max_participants: Optional[int] = None

    # 회차/참여율 (max_participation_rate 제거)
    total_rounds: Optional[int] = None
    min_participation_rate: Optional[int] = None

    # ✅ 리워드 (reward → reward_description)
    use_reward: Optional[bool] = None
    reward_description: Optional[str] = None

    # 모드/기본 링크
    mode: Optional[ChallengeMode] = None
    default_zoom_link: Optional[str] = None

    # ✅ 간소화된 장소 정보
    same_place_for_all_rounds: Optional[bool] = None
    default_place_name: Optional[str] = None
    default_address: Optional[str] = None  # road_address 통합
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None

    # 기본 설정
    require_approval: Optional[bool] = None
    is_public: Optional[bool] = None

    # 태그
    tags: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Title cannot be empty")
            if len(v.strip()) < 2:
                raise ValueError("Title must be at least 2 characters long")
            if len(v.strip()) > 200:
                raise ValueError("Title cannot exceed 200 characters")
            return v.strip()
        return v

    @field_validator("entry_fee")
    @classmethod
    def validate_entry_fee(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Entry fee cannot be negative")
        if v is not None and v > 1000000:
            raise ValueError("Entry fee cannot exceed 1,000,000 KRW")
        return v

    @field_validator("monthly_fee")
    @classmethod
    def validate_monthly_fee(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Monthly fee cannot be negative")
        if v is not None and v > 100000:
            raise ValueError("Monthly fee cannot exceed 100,000 KRW")
        return v

    @field_validator("min_participation_rate")
    @classmethod
    def validate_min_rate(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Participation rate must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def validate_cross_fields(self):
        # 날짜 검증
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be ≤ end_date")

        # 참가자 수 검증
        if (self.min_participants is not None and self.max_participants is not None 
            and self.max_participants < self.min_participants):
            raise ValueError("max_participants must be ≥ min_participants")

        # 리워드 검증
        if self.use_reward is True and (
            self.reward_description is None or self.reward_description.strip() == ""
        ):
            raise ValueError("Reward description is required when use_reward is True")

        return self


# -----------------------------
# Response Schemas (완전 수정)
# -----------------------------
class ChallengeResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    creator_id: int

    # 일정
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # 상태
    status: ChallengeStatus = ChallengeStatus.draft
    computed_status: Optional[str] = None  # 계산된 상태
    
    # 타임스탬프
    created_at: datetime
    updated_at: datetime

    # ✅ 새로운 결제 시스템
    payment_type: PaymentType
    entry_fee: int
    monthly_fee: int

    # 참가자 관리
    min_participants: int
    max_participants: Optional[int] = None
    current_participants: int = 0

    # 회차/참여율 (max_participation_rate 제거)
    total_rounds: Optional[int] = None
    min_participation_rate: int

    # ✅ 리워드 시스템 (reward → reward_description)
    use_reward: bool
    reward_description: Optional[str] = None

    # ✅ 완료 & 정산 (is_closed → is_settlement_completed)
    completed_at: Optional[datetime] = None
    is_settlement_completed: bool = False
    settlement_completed_at: Optional[datetime] = None

    # 소프트 삭제
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # 진행 방식
    mode: ChallengeMode
    default_zoom_link: Optional[str] = None

    # ✅ 간소화된 장소 정보
    same_place_for_all_rounds: bool = False
    default_place_name: Optional[str] = None
    default_address: Optional[str] = None  # road_address 통합
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None

    # 기본 설정
    require_approval: bool = False
    is_public: bool = True

    # 태그
    tags: Optional[List[str]] = None

    # ✅ 계산된 필드들 (선택사항)
    duration_days: Optional[int] = None
    remaining_days: Optional[int] = None
    progress_percentage: Optional[float] = None
    payment_required: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class ChallengeOut(ChallengeResponse):
    """ChallengeResponse의 별칭 (호환성)"""
    pass


class ChallengeListItem(BaseModel):
    """목록 조회용 간소화된 스키마"""
    id: int
    title: str
    description: Optional[str] = None
    creator_id: int
    
    # 일정 & 상태
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: ChallengeStatus
    computed_status: Optional[str] = None
    
    # 기본 정보
    payment_type: PaymentType
    entry_fee: int
    monthly_fee: int
    current_participants: int
    max_participants: Optional[int] = None
    mode: ChallengeMode
    is_public: bool
    
    # 타임스탬프
    created_at: datetime
    
    # 계산된 필드
    duration_days: Optional[int] = None
    remaining_days: Optional[int] = None
    progress_percentage: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ChallengeItem(BaseModel):
    """검색 결과용 최소한의 스키마"""
    id: int
    title: str
    description: Optional[str] = None
    creator_id: int
    status: str  # string으로 두면 Enum/str 모두 수용
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 결제 관련 스키마 (새로 추가)
# -----------------------------
class PaymentInfoResponse(BaseModel):
    """결제 정보 응답"""
    challenge_id: int
    payment_type: PaymentType
    entry_fee: int
    monthly_fee: int
    is_payment_required: bool
    
    # 결제 옵션별 상세 정보
    available_options: List[str] = []  # ["entry_fee", "monthly_fee"]
    
    model_config = ConfigDict(from_attributes=True)


class PaymentCalculationRequest(BaseModel):
    """결제 금액 계산 요청"""
    payment_cycle: str  # "entry_fee" or "monthly_fee"


class PaymentCalculationResponse(BaseModel):
    """결제 금액 계산 응답"""
    challenge_id: int
    payment_cycle: str
    amount: int
    currency: str = "KRW"
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 통계 관련 스키마 (새로 추가)
# -----------------------------
class ChallengeStatistics(BaseModel):
    """챌린지 통계 정보"""
    challenge_id: int
    
    # 참가자 통계
    total_participants: int
    active_participants: int
    current_participants: int
    max_participants: Optional[int] = None
    
    # 진행 상황
    duration_days: int
    remaining_days: int
    progress_percentage: float
    
    # 상태 정보
    status: str
    computed_status: str
    payment_required: bool
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 검색 응답 (기존 유지)
# -----------------------------
class DualSearchResponse(BaseModel):
    query: str
    matched_challenges: List[ChallengeItem] = []
    recommended_by_tag_challenges: List[ChallengeItem] = []
    predicted_tag: Optional[str] = None
    predicted_score: Optional[float] = None


# -----------------------------
# 기타 응답 스키마
# -----------------------------
class ChallengeActionResponse(BaseModel):
    """챌린지 액션 응답 (시작/완료 등)"""
    message: str
    challenge_id: Optional[int] = None
    status: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ChallengeDeleteResponse(BaseModel):
    """챌린지 삭제 응답"""
    message: str
    deleted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 태그가 포함된 응답 (라우터에서 사용)
# -----------------------------
class ChallengeResponseWithTags(ChallengeResponse):
    """태그가 포함된 챌린지 응답 (라우터 호환용)"""
    tags: List[str] = []
    
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 유틸리티 함수들
# -----------------------------
def create_challenge_response_with_computed_fields(
    challenge, 
    tags: Optional[List[str]] = None
) -> dict:
    """
    Challenge 모델로부터 계산된 필드들을 포함한 응답 생성
    라우터에서 사용하기 위한 헬퍼 함수
    """
    response_data = ChallengeResponse.model_validate(challenge).model_dump()
    
    # 계산된 필드들 추가
    try:
        response_data['computed_status'] = challenge.get_computed_status().value
        response_data['duration_days'] = challenge.get_duration_days()
        response_data['remaining_days'] = challenge.get_remaining_days()
        response_data['progress_percentage'] = challenge.get_progress_percentage()
        response_data['payment_required'] = challenge.is_payment_required()
    except AttributeError:
        # 메서드가 없는 경우 기본값 설정
        response_data['computed_status'] = response_data.get('status')
        response_data['duration_days'] = None
        response_data['remaining_days'] = None
        response_data['progress_percentage'] = None
        response_data['payment_required'] = challenge.payment_type != PaymentType.free
    
    # 태그 추가
    if tags:
        response_data['tags'] = tags
    
    return response_data


# -----------------------------
# 호환성을 위한 별칭들
# -----------------------------
# 기존 코드와의 호환성을 위해 유지
ChallengeCreateRequest = ChallengeCreate
ChallengeUpdateRequest = ChallengeUpdate