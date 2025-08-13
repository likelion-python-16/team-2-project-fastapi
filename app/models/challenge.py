# app/models/challenge.py 업데이트

from sqlalchemy import Column, Integer, String, Text, Date, Boolean, ForeignKey, DateTime, func, Enum
from sqlalchemy.orm import relationship
from .base import Base

class Challenge(Base):
    __tablename__ = "challenges"
    
    # 기존 필드들
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(String(20), default="recruiting")
    created_at = Column(DateTime, default=func.now())
    
    # 🆕 1단계: 핵심 필드들 (결제/참가 관련)
    fee = Column(Integer, default=0, comment="회비 (원)")
    participation_fee = Column(Integer, default=0, comment="참가비 (원)")
    min_participants = Column(Integer, nullable=True, comment="최소 참가자 수")
    max_participants = Column(Integer, nullable=True, comment="최대 참가자 수")
    
    # 🆕 리워드 시스템
    use_reward = Column(Boolean, default=False, comment="리워드 사용 여부")
    reward = Column(Text, nullable=True, comment="리워드 내용")
    
    # 🆕 회차 시스템
    total_rounds = Column(Integer, nullable=True, comment="총 회차 수")
    min_participation_rate = Column(Integer, default=80, comment="최소 참여율 (%)")
    
    # 🆕 정산 시스템
    is_closed = Column(Boolean, default=False, comment="정산 완료 여부")
    
    # 🆕 소프트 삭제
    is_deleted = Column(Boolean, default=False, comment="삭제 여부")
    deleted_at = Column(DateTime, nullable=True, comment="삭제 시간")
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="삭제한 유저")
    
    # 🔗 Relationships (foreign_keys 명시)
    creator = relationship("User", back_populates="created_challenges", foreign_keys="Challenge.creator_id")
    deleter = relationship("User", foreign_keys="Challenge.deleted_by")

    # 참가 관련
    participations = relationship("Participation", back_populates="challenge")

    # 라운드 관련
    rounds = relationship("ChallengeRound", back_populates="challenge")

    # 결제 관련
    payments = relationship("Payment", back_populates="challenge")
    refunds = relationship("Refund", back_populates="challenge")

    # 초대 관련
    invitations = relationship("Invitation", back_populates="challenge")

    # 포인트 관련
    point_histories = relationship("PointHistory", back_populates="challenge")

    # 리뷰 관련
    reviews = relationship("Review", back_populates="challenge")

    # 태그 관련
    challenge_tags = relationship("ChallengeTag", back_populates="challenge")

    # 임베딩 관련
    embeddings = relationship("ChallengeEmbedding", back_populates="challenge", cascade="all, delete-orphan")

    proofs = relationship("Proof", back_populates="challenge")

    # Challenge 모델에 추가
    reports = relationship("Report", back_populates="challenge")
    penalties = relationship("PenaltyHistory", back_populates="challenge")

    chat_rooms = relationship("ChatRoom", back_populates="challenge")