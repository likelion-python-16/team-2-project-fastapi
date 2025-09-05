import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

# --- ENUMs ---
class ReportStatus(str, enum.Enum):
    pending      = "pending"
    under_review = "under_review"
    resolved     = "resolved"
    rejected     = "rejected"
    cancelled    = "cancelled"

class PenaltySource(str, enum.Enum):
    bad_language      = "bad_language"       # 나쁜말, 욕설
    report            = "report"             # 신고로 인한 벌점
    frequent_kick     = "frequent_kick"      # 많은 강퇴
    frequent_leave    = "frequent_leave"     # 잦은 자진 퇴출

# --- Report ---
class Report(Base, TimestampMixin):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    reporter_id  = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reported_id  = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True)
    
    reason  = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    status = Column(SAEnum(ReportStatus, name="report_status_enum"), default=ReportStatus.pending, nullable=False)
    
    is_false_report = Column(Boolean, default=False, nullable=False)
    penalty_given   = Column(Boolean, default=False, nullable=False)
    penalty_score   = Column(Integer, default=0, nullable=False)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    
    # 관계
    reporter  = relationship("User", foreign_keys=[reporter_id], back_populates="reports_made", lazy="joined")
    reported  = relationship("User", foreign_keys=[reported_id], back_populates="reports_received", lazy="joined")
    challenge = relationship("Challenge", back_populates="reports", lazy="joined")
    proofs = relationship("ReportProof", back_populates="report", cascade="all, delete-orphan", lazy="selectin")
    
    __table_args__ = (
        Index("ix_report_reporter", "reporter_id"),
        Index("ix_report_reported", "reported_id"),
        Index("ix_report_challenge", "challenge_id"),
        Index("ix_report_status", "status"),
        Index("ix_report_created", "created_at"),  # 최신 신고 조회용
    )

class ReportProof(Base):
    __tablename__ = "report_proofs"
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    file_url  = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    report = relationship("Report", back_populates="proofs", lazy="joined")
    
    __table_args__ = (
        Index("ix_reportproof_report", "report_id"),
        Index("ix_reportproof_uploaded", "uploaded_at"),  # 업로드 시간 조회용
    )

class PenaltyHistory(Base):
    __tablename__ = "penalty_histories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True)
    
    source_type = Column(SAEnum(PenaltySource, name="penalty_source_enum"), nullable=False)
    reason      = Column(String(255), nullable=False)
    score       = Column(Integer, nullable=False)
    given_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    user      = relationship("User", back_populates="penalties", lazy="joined")
    challenge = relationship("Challenge", back_populates="penalties", lazy="joined")
    
    __table_args__ = (
        Index("ix_penalty_user", "user_id"),
        Index("ix_penalty_challenge", "challenge_id"),
        Index("ix_penalty_given_at", "given_at"),
        Index("ix_penalty_source", "source_type"),
        Index("ix_penalty_score", "score"),  # 점수별 조회용
    )


# ──────────────────────────────────────────────────────────────────────────────
# ML Auto-evaluation log for reports
# 신고 자동판정 로그(1차 판정) — 본체 Report와 분리해 안전하게 확장
class AutoDecision(str, enum.Enum):
    true = "true"      # 정당 신고
    false = "false"    # 거짓 신고
    review = "review"  # 보류 → 휴먼 검수


class ReportAutoEval(Base):
    __tablename__ = "report_auto_evals"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)

    # 평가 대상 텍스트(PII 마스킹 전 원문은 저장하지 않음 권장 → 여기서는 마스킹된 텍스트를 저장)
    comment_text = Column(Text, nullable=False)
    comment_hash = Column(String(64), nullable=False, index=True)  # 동일 댓글 중복신고 집계용

    # 1차 자동판정 피처들
    toxic_score = Column(Integer, nullable=False, default=0)           # 0~100 scale 저장(정수)
    rule_flag = Column(Boolean, nullable=False, default=False)
    reporter_trust = Column(Integer, nullable=False, default=50)       # 0~100 scale 저장(정수)
    multi_report_count = Column(Integer, nullable=False, default=1)

    # 가중 합산 결과
    auto_decision = Column(SAEnum(AutoDecision, name="report_auto_decision_enum"), nullable=False)
    auto_confidence = Column(Integer, nullable=False, default=0)       # 0~100 scale 저장(정수)
    decided_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # 관계
    report = relationship("Report", lazy="joined")

    __table_args__ = (
        Index("ix_report_auto_eval_report", "report_id"),
        Index("ix_report_auto_eval_decided_at", "decided_at"),
        Index("ix_report_auto_eval_decision", "auto_decision"),
    )
