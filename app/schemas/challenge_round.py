# app/schemas/challenge_round.py (새 파일 생성)

from pydantic import BaseModel, field_validator
from datetime import date, time, datetime
from typing import Optional
from enum import Enum

class RoundMode(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"

class ChallengeRoundCreate(BaseModel):
    challenge_id: int
    mode: RoundMode
    round: int
    processing_at: date
    start_time: Optional[time] = None
    finish_time: Optional[time] = None
    description: Optional[str] = None
    url: Optional[str] = None
    
    # 오프라인용 위치 정보
    lat: Optional[float] = None
    lon: Optional[float] = None
    geofence_radius_m: Optional[float] = None
    
    # 온라인용
    zoom_meeting_id: Optional[str] = None

    @field_validator('round')
    @classmethod
    def validate_round(cls, v):
        if v <= 0:
            raise ValueError('Round must be positive')
        return v
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v, values):
        if v and 'mode' in values and values['mode'] == RoundMode.OFFLINE:
            raise ValueError('URL is not needed for offline rounds')
        return v
    
    @field_validator('lat', 'lon')
    @classmethod
    def validate_coordinates(cls, v, values):
        if v is not None and 'mode' in values and values['mode'] == RoundMode.ONLINE:
            raise ValueError('Coordinates are not needed for online rounds')
        return v

class ChallengeRoundUpdate(BaseModel):
    mode: Optional[RoundMode] = None
    processing_at: Optional[date] = None
    start_time: Optional[time] = None
    finish_time: Optional[time] = None
    description: Optional[str] = None
    url: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    geofence_radius_m: Optional[float] = None
    zoom_meeting_id: Optional[str] = None

class ChallengeRoundResponse(BaseModel):
    id: int
    challenge_id: int
    mode: str
    round: int
    processing_at: date
    start_time: Optional[time]
    finish_time: Optional[time]
    description: Optional[str]
    url: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    geofence_radius_m: Optional[float]
    zoom_meeting_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True