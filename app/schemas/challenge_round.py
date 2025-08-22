# app/schemas/challenge_round.py
from pydantic import BaseModel, field_validator, model_validator
from datetime import date, time, datetime
from typing import Optional,Literal
from enum import Enum

class RoundMode(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"

class ChallengeRoundCreate(BaseModel):
    challenge_id: int
    mode: RoundMode
    round: int
    processing_at: date
    start_time: time
    finish_time: time
    description: str
    url: Optional[str] = None  # online: zoom link
    
    # 온라인(선택)
    zoom_meeting_id: Optional[str] = None

    # 오프라인(B안)
    place_name: Optional[str] = None
    road_address: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    geofence_radius_m: Optional[float] = None


    @field_validator('round')
    @classmethod
    def validate_round(cls, v):
        if v <= 0:
            raise ValueError('Round must be positive')
        return v

    @model_validator(mode="after")
    def validate_mode_fields(self):
        # 시간 검증
        if self.start_time >= self.finish_time:
            raise ValueError("finish_time must be greater than start_time")

        if self.mode == RoundMode.ONLINE:
            # 온라인이면 줌 URL 또는 미팅ID 중 하나는 있어야 함
            if not (self.url or self.zoom_meeting_id):
                raise ValueError("online round requires zoom link (url) or zoom_meeting_id")

        if self.mode == RoundMode.OFFLINE:
            if not self.place_name:
                raise ValueError("offline round requires place_name")
            if not (self.road_address or (self.lat is not None and self.lon is not None)):
                raise ValueError("offline round requires road_address or (lat & lon)")
        return self

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
    place_name: Optional[str] = None
    road_address: Optional[str] = None
    address: Optional[str] = None
    map_url: Optional[str] = None
    mode: Optional[Literal["online", "offline"]] = None

class ChallengeRoundResponse(BaseModel):
    id: int
    challenge_id: int
    mode: str
    round: int
    processing_at: date
    start_time: time            # ← 모델이 NOT NULL이면 응답도 필수로
    finish_time: time           # ← 동일
    description: str           # ← 동일
    url: Optional[str] = None  # online: zoom link / offline: naver map link

    place_name: Optional[str]
    road_address: Optional[str]
    address: Optional[str]
    map_url: Optional[str]

    lat: Optional[float]
    lon: Optional[float]

    geofence_radius_m: Optional[float]
    zoom_meeting_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    # 🆕 참여예상 인원(서버에서 채워서 내려줌)
    planned_count: int

    class Config:
        from_attributes = True