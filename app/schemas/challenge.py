# app/schemas/challenge.py에 추가할 코드

from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional
from enum import Enum

class ChallengeStatus(str, Enum):
    RECRUITING = "recruiting"  # 모집중
    ACTIVE = "active"         # 진행중
    COMPLETED = "completed"   # 완료
    CANCELLED = "cancelled"   # 취소

class ChallengeCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        if len(v.strip()) < 2:
            raise ValueError('Title must be at least 2 characters long')
        return v.strip()

class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[ChallengeStatus] = None

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

class ChallengeResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    creator_id: int
    start_date: Optional[date]
    end_date: Optional[date]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True