from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.pointhistory import PointHistoryType  # ← enum 재사용

class PointHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    description: str
    point_amount: int
    type: PointHistoryType           # "gain" | "use" | "refund"
    challenge_id: Optional[int] = None
    created_at: datetime             # TimestampMixin 제공 필드

class PointHistoryListOut(BaseModel):
    items: list[PointHistoryOut]
    total: int
    skip: int
    limit: int
    current_points: int              # User.total_points 표시용

class PointExchangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    points: int                 # 요청 포인트
    status: str                 # 예: requested / approved / rejected / processed
    requested_at: datetime
    processed_at: datetime | None = None

class PointExchangeListOut(BaseModel):
    items: list[PointExchangeOut]
    total: int
    skip: int
    limit: int

class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount: int
    status: str | None = None
    processed_at: datetime | None = None
    created_at: datetime

class RefundListOut(BaseModel):
    items: list[RefundOut]
    total: int
    skip: int
    limit: int