from sqlalchemy import (
    Column, Integer, String, Text, Date, Time, DateTime, Float,
    Enum, ForeignKey, UniqueConstraint, Index, func,Numeric,CheckConstraint
)
from sqlalchemy.orm import relationship
from .base import Base

class ChallengeRound(Base):
    __tablename__ = "challenge_rounds"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # FK
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    
    # 기본 정보
    mode = Column(Enum('online', 'offline'), nullable=False)  # online/offline
    round = Column(Integer, nullable=False, comment="회차 번호(1,2,3,...)")       # 회차 번호(1,2,3,...)
    processing_at = Column(Date,nullable=False, comment="라운드 진행 날짜(YYYY-MM-DD)")  # 라운드 진행 날짜(YYYY-MM-DD)
    start_time = Column(Time,nullable=False, comment="시작 시간")
    finish_time = Column(Time,nullable=False, comment="종료 시간")
    description = Column(Text, comment="회차 설명")
    url = Column(Text, comment="안내/참고 URL")   # 안내/참고 URL
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(),nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(),nullable=False)
    
    # 오프라인용 위치(선택)
    lat = Column(Numeric(9, 6), comment="위도")
    lon = Column(Numeric(9, 6), comment="경도")
    geofence_radius_m = Column(Float, comment="지오펜스 반경 (미터)")  # 미지정 시 서비스 로직에서 기본값(예: 100m)
    
    # 온라인용(선택)
    zoom_meeting_id = Column(String(255), comment="줌 미팅 ID")
    
    # 관계
    challenge = relationship("Challenge", back_populates="rounds")
    pictures = relationship(
        "RoundPicture",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    proofs = relationship(
        "Proof",
        back_populates="round",
        cascade="all, delete-orphan"
    )
    qrcodes = relationship(
        "QRCode",
        back_populates="round",
        cascade="all, delete-orphan"
    )
    attendances = relationship(
        "RoundAttendance",
        back_populates="round",
        cascade="all, delete-orphan"
    )
    reviews = relationship("Review", back_populates="round", cascade="all, delete-orphan")



    __table_args__ = (
        UniqueConstraint("challenge_id", "round", name="uq_challenge_roundnum"),
        Index("ix_round_challenge_round", "challenge_id", "round"),
        Index("ix_round_processing", "processing_at"),
        Index("ix_round_mode", "mode"),
        Index("idx_round_geo", "lat", "lon"),
        Index("ix_round_challenge_processing", "challenge_id", "processing_at"),
        CheckConstraint("round >= 1", name="ck_round_ge_1"),
        CheckConstraint("geofence_radius_m IS NULL OR geofence_radius_m >= 0", name="ck_radius_nonneg"),
        CheckConstraint("start_time < finish_time", name="ck_time_order"),
        {'mysql_engine': 'InnoDB'},
    )