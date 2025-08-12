from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, Text, func
from sqlalchemy.orm import relationship
from .base import Base

class RoundAttendance(Base):
    __tablename__ = "round_attendances"
    
    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("challenge_rounds.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("challenge_participants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 출석 정보
    status = Column(String(20), default="absent")  # present, absent, late, excused
    attended_at = Column(DateTime, nullable=True)
    proof_image_url = Column(Text, nullable=True, comment="인증 사진")
    proof_description = Column(Text, nullable=True, comment="인증 설명")
    
    # 시스템 정보
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 🔗 Relationships
    round = relationship("ChallengeRound", back_populates="attendances")
    participant = relationship("ChallengeParticipant", back_populates="attendances")
    user = relationship("User")