from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, func
from sqlalchemy.orm import relationship
from .base import Base

class ChallengeParticipant(Base):
    __tablename__ = "challenge_participants"
    
    participant_id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=func.now())
    status = Column(String(20), default="active")  # active, completed, dropped
    
    # 🔗 Relationships
    challenge = relationship("Challenge", back_populates="participants")
    user = relationship("User", back_populates="participated_challenges")