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