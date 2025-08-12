from sqlalchemy import Column, Integer, String, Text, Date, Time, DateTime, Float, ForeignKey, func, Enum
from sqlalchemy.orm import relationship
from .base import Base

class ChallengeRound(Base):
    __tablename__ = "challenge_rounds"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    mode = Column(Enum('online', 'offline'), nullable=False)
    round = Column(Integer, nullable=False, comment="회차 번호")
    processing_at = Column(Date, comment="진행 날짜")
    start_time = Column(Time, comment="시작 시간")
    finish_time = Column(Time, comment="종료 시간")
    description = Column(Text, comment="회차 설명")
    url = Column(Text, comment="온라인 링크")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 위치 정보 (오프라인용)
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    geofence_radius_m = Column(Float, comment="지오펜스 반경 (미터)")
    zoom_meeting_id = Column(String(255), comment="줌 미팅 ID")
    
    # 🔗 Relationships
    challenge = relationship("Challenge", back_populates="rounds")
    attendances = relationship("RoundAttendance", back_populates="round")
    
    # Unique constraint: 한 챌린지의 같은 회차는 유일해야 함
    __table_args__ = (
        {'mysql_engine': 'InnoDB'},
    )