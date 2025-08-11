from sqlalchemy import Column, Integer, String, Text, Date, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base

class Challenge(Base):
    __tablename__ = "challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # 🔗 Relationships
    creator = relationship("User", back_populates="created_challenges")
    participants = relationship("ChallengeParticipant", back_populates="challenge")