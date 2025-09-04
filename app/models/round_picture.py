from sqlalchemy import (
    Column, Boolean, String, Text, Date, DateTime, Float, Integer,
    Enum, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class RoundPicture(Base, TimestampMixin):
    __tablename__ = "round_pictures"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # FK
    round_id = Column(Integer, ForeignKey("challenge_rounds.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # 파일/공개여부/업로드시각
    file_url = Column(String(255), nullable=False)
    is_public = Column(Boolean, default=True, nullable=False)
    # uploaded_at 은 created_at으로 치환
    
    # 관계
    round = relationship("ChallengeRound", back_populates="pictures")
    uploader = relationship("User", back_populates="uploaded_round_pictures", foreign_keys=[uploaded_by])
    
    __table_args__ = (
        Index("ix_roundpic_round", "round_id"),
        Index("ix_roundpic_public", "is_public"),
        Index("ix_roundpic_uploader", "uploaded_by"),
        Index("ix_roundpic_created", "created_at"),
    )