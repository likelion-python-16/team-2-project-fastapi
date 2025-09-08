from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    reported_id: int = Field(..., description="신고 대상 사용자 ID")
    comment_text: str = Field(..., min_length=1, description="신고 대상 댓글/메시지 텍스트")
    challenge_id: Optional[int] = Field(None, description="관련 챌린지 ID(선택)")
    reason: Optional[str] = Field(None, description="신고 사유(선택)")
    details: Optional[str] = Field(None, description="추가 설명(선택)")


class ReportAutoEvalOut(BaseModel):
    auto_decision: str
    auto_confidence: int  # 0~100
    toxic_score: int      # 0~100
    rule_flag: bool
    reporter_trust: int   # 0~100
    multi_report_count: int


class ReportOut(BaseModel):
    id: int
    reporter_id: int
    reported_id: int
    challenge_id: Optional[int]
    reason: Optional[str]
    details: Optional[str]
    created_at: datetime

    auto_eval: ReportAutoEvalOut

    class Config:
        orm_mode = True

