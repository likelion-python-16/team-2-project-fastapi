from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, Enum, func
from sqlalchemy.orm import relationship
from .base import Base

class ChallengeParticipant(Base):
    __tablename__ = "challenge_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=func.now())
    status = Column(String(20), default="active")  # active, completed, dropped
    is_active = Column(Boolean, default=True)
    role = Column(Enum('planner', 'participant'), default='participant')
    leave_type = Column(String(20), nullable=True)
    
    # 🔗 Relationships
    challenge = relationship("Challenge", back_populates="participants")
    user = relationship("User", back_populates="participated_challenges")
    attendances = relationship("RoundAttendance", back_populates="participant")