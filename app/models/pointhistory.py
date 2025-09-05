import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class PointHistoryType(str, enum.Enum):
    gain = "gain"
    use = "use"
    refund = "refund"
    challenge_reward = "challenge_reward"     # 챌린지 완주 보상
    withdrawal = "withdrawal"                 # 포인트 환급

class PointHistory(Base, TimestampMixin):
    __tablename__ = "point_histories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True)
    description = Column(String(255), nullable=False)
    point_amount = Column(Integer, nullable=False)
    type = Column(SAEnum(PointHistoryType, name="point_history_type_enum"), nullable=False)
    
    # TimestampMixin이 created_at, updated_at을 제공하므로 중복 제거
    total_earned_point = Column(Integer, nullable=True)  # 트랜잭션 직후 누적 포인트(스냅샷)
    
    # 관계
    user = relationship("User", back_populates="point_histories")
    challenge = relationship("Challenge", back_populates="point_histories")
    
    __table_args__ = (
        Index("ix_ph_user_created", "user_id", "created_at"),
        Index("ix_ph_type", "type"),
        Index("ix_ph_challenge", "challenge_id"),  # 챌린지별 포인트 내역 조회용
        Index("ix_ph_amount", "point_amount"),  # 포인트 양별 조회용 (큰 거래 추적)
    )