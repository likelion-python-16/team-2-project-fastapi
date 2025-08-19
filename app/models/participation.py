import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, DateTime, Boolean, String,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class ParticipationRole(str, enum.Enum):
    creator = "creator"
    participant = "participant"
    manager = "manager"  # 🆕 위임 관리자 역할 추가

class Participation(Base, TimestampMixin):
    __tablename__ = "participations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(20), default="active", nullable=False)   # 예: active, left, kicked 등 자유롭게 사용
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(
        SAEnum(ParticipationRole, name="participation_role_enum"),
        default=ParticipationRole.participant,
        nullable=False
    )
    leave_type = Column(String(20), nullable=True)   # 예: voluntary, kicked 등 자유 입력
    
    # 관계
    user = relationship("User", back_populates="participations")
    challenge = relationship("Challenge", back_populates="participations")
    
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_participation_user_challenge"),
        Index("ix_participation_user", "user_id"),
        Index("ix_participation_challenge", "challenge_id"),
        Index("ix_participation_status", "status"),
        Index("ix_participation_role", "role"),
        Index("ix_participation_active", "is_active"),
        Index("ix_participation_joined", "joined_at"),  # 참가 시간 순 조회용
    )