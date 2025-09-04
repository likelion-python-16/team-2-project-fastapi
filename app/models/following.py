# models/following.py
from sqlalchemy import (
    Column, Integer, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base

class Following(Base):
    __tablename__ = "followings"
    
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following_relations")
    following = relationship("User", foreign_keys=[following_id], back_populates="follower_relations")
    
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_follow_pair"),
        Index("ix_follow_follower", "follower_id"),
        Index("ix_follow_following", "following_id"),
        Index("ix_follow_created", "created_at"),  # 최신 팔로우 조회용
    )