# app/schemas/mypage_more.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_serializer


# -------------------------
# F-1-14 신고/첨부
# -------------------------
class ReportProofItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: int
    file_url: Optional[str] = None
    created_at: datetime


class ReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    # 가변 기본값 방지
    proofs: List[ReportProofItem] = Field(default_factory=list)


class ReportListOut(BaseModel):
    items: List[ReportItem]
    total: int
    skip: int
    limit: int


# -------------------------
# F-1-15 결제 내역
# -------------------------
class PaymentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    status: str
    payment_type: Optional[str] = None
    method: Optional[str] = Field(default="unknown")
    created_at: datetime


class PaymentListOut(BaseModel):
    items: List[PaymentItem]
    total: int
    skip: int
    limit: int


# -------------------------
# F-1-16 포인트 내역
#   - DB: point_amount, description, type(enum)
#   - API 응답: delta, memo, type  ← 프론트(mypage.js) 기대값
# -------------------------
class PointHistoryItem(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,  # validation_alias 사용
    )

    id: int
    # enum -> 문자열로 직렬화
    type: str

    # DB의 point_amount -> 응답 필드 delta 로 노출
    delta: int = Field(validation_alias="point_amount")
    # DB의 description -> 응답 필드 memo 로 노출
    memo: Optional[str] = Field(default=None, validation_alias="description")

    created_at: datetime

    # enum 객체가 들어와도 'use' / 'gain' 등의 값만 나오도록 보장
    @field_serializer("type")
    def _serialize_type(self, v):
        return getattr(v, "value", v)


class PointHistorySummary(BaseModel):
    total_points: int
    earned_sum: int
    spent_sum: int


class PointHistoryListOut(BaseModel):
    summary: PointHistorySummary
    items: List[PointHistoryItem]
    total: int
    skip: int
    limit: int
    kind: Literal["all", "earn", "spend"]


# -------------------------
# F-1-17 포인트 전환(환급) 내역
# -------------------------
class PointExchangeItem(BaseModel):
    id: int
    status: str
    # 💡 DB: cash_amount / point_amount → 응답: amount / points 로 매핑
    amount: float = Field(alias="cash_amount")    # 현금 액수
    points: int = Field(alias="point_amount")     # 포인트 수량
    requested_at: datetime
    processed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,   # alias 역방향 채우기도 허용
    }



class PointExchangeListOut(BaseModel):
    items: List[PointExchangeItem]
    total: int
    skip: int
    limit: int
