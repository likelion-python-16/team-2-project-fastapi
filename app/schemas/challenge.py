# app/schemas/challenge.py 업데이트

from pydantic import BaseModel, field_validator, ConfigDict
from datetime import date, datetime
from typing import Optional
from enum import Enum

class ChallengeStatus(str, Enum):
    RECRUITING = "recruiting"  # 모집중
    ACTIVE = "active"         # 진행중
    COMPLETED = "completed"   # 완료
    CANCELLED = "cancelled"   # 취소

class ChallengeCreate(BaseModel):
    # 기본 정보
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # 🆕 결제 관련
    fee: Optional[int] = 0
    participation_fee: Optional[int] = 0
    
    # 🆕 참가자 관리
    min_participants: Optional[int] = None
    max_participants: Optional[int] = None
    
    # 🆕 회차 시스템
    total_rounds: Optional[int] = None
    min_participation_rate: Optional[int] = 80
    
    # 🆕 리워드 시스템
    use_reward: Optional[bool] = False
    reward: Optional[str] = None

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        if len(v.strip()) < 2:
            raise ValueError('Title must be at least 2 characters long')
        return v.strip()
    
    @field_validator('participation_fee')
    @classmethod
    def validate_participation_fee(cls, v):
        if v is not None and v > 10000:
            raise ValueError('Participation fee cannot exceed 10,000 KRW')
        if v is not None and v < 0:
            raise ValueError('Participation fee cannot be negative')
        return v
    
    @field_validator('fee')
    @classmethod
    def validate_fee(cls, v):
        if v is not None and v < 0:
            raise ValueError('Fee cannot be negative')
        return v
    
    @field_validator('min_participation_rate')
    @classmethod
    def validate_participation_rate(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Participation rate must be between 0 and 100')
        return v

class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[ChallengeStatus] = None
    
    # 🆕 업데이트 가능한 필드들
    fee: Optional[int] = None
    participation_fee: Optional[int] = None
    min_participants: Optional[int] = None
    max_participants: Optional[int] = None
    total_rounds: Optional[int] = None
    min_participation_rate: Optional[int] = None
    use_reward: Optional[bool] = None
    reward: Optional[str] = None

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Title cannot be empty')
            if len(v.strip()) < 2:
                raise ValueError('Title must be at least 2 characters long')
            return v.strip()
        return v
    
    @field_validator('participation_fee')
    @classmethod
    def validate_participation_fee(cls, v):
        if v is not None and v > 10000:
            raise ValueError('Participation fee cannot exceed 10,000 KRW')
        if v is not None and v < 0:
            raise ValueError('Participation fee cannot be negative')
        return v

class ChallengeResponse(BaseModel):
    # 기본 정보
    id: int
    title: str
    description: Optional[str]
    creator_id: int
    start_date: Optional[date]
    end_date: Optional[date]
    status: str
    created_at: datetime
    
    # 🆕 추가된 필드들
    fee: int
    participation_fee: int
    min_participants: Optional[int]
    max_participants: Optional[int]
    total_rounds: Optional[int]
    min_participation_rate: int
    use_reward: bool
    reward: Optional[str]
    is_closed: bool
    is_deleted: bool
    
    class Config:
        from_attributes = True

class ChallengeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    thumbnail: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_active: bool

class PaginatedChallenges(BaseModel):
    items: list[ChallengeBrief]
    total: int
    page: int
    size: int