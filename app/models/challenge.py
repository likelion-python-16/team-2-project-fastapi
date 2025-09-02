from sqlalchemy import Column, Integer, String, Text, Date, Boolean, ForeignKey, DateTime, func, Enum, Float
from sqlalchemy.orm import relationship
from .base import Base
from app.models.round_manager import RoundManager  # 필요시 상대 import 대신 문자열로도 가능
from datetime import date
# ✅ 추가: SAEnum 별칭 import (기존 Enum과 충돌 방지)
from sqlalchemy import Enum as SAEnum

class Challenge(Base):
    __tablename__ = "challenges"
    
    # 기존 필드들
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    # ✅ 교체: String(20) -> SAEnum (ENUM 제약 + DEFAULT)
    status = Column(
        SAEnum("recruiting", "active", "completed", "cancelled", name="challenge_status_enum"),
        nullable=False,
        server_default="recruiting",
        comment="챌린지 상태",
    )
    created_at = Column(DateTime, default=func.now())
    # ✅ 추가: updated_at (onupdate)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
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

    max_participation_rate = Column(Integer, nullable=True, comment="최대 참여율 (%)")

    # 🖼 대표(커버) 이미지
    cover_image_url = Column(String(255), nullable=True)
    cover_round_picture_id = Column(Integer, ForeignKey("round_pictures.id", ondelete="SET NULL"), nullable=True)

    def get_status(self, current_count: int = 0) -> str:
        today = date.today()

        # 삭제된 경우 → 종료
        if getattr(self, "is_deleted", False):
            return "completed"

        # 종료일이 있고, 오늘이 종료일 이후 → 종료
        if self.end_date and today > self.end_date:
            return "completed"

        # 시작일이 있고, 오늘이 시작일 이전 → 모집중
        if self.start_date and today < self.start_date:
            return "recruiting"

        # 시작일이 있고, 오늘이 시작일 이후(포함)
        if self.start_date and today >= self.start_date:
            # 최소 인원 미달이면 계속 모집중
            if self.min_participants and current_count < self.min_participants:
                return "recruiting"
            # 종료일이 없거나 오늘이 종료일 이내 → 진행중
            if (self.end_date is None) or (today <= self.end_date):
                return "active"
            
        # 기본값
        return "recruiting"



    # 모드 & 기본값
    mode = Column(Enum("online", "offline", "hybrid", name="challenge_mode_enum"),
              nullable=False, server_default="hybrid")
    default_zoom_link = Column(Text, nullable=True)
    default_place_name = Column(String(255), nullable=True)
    default_road_address = Column(String(255), nullable=True)
    default_address = Column(String(255), nullable=True)

    same_place_for_all_rounds = Column(Boolean, default=False, nullable=False, comment="모든 회차 동일 장소 여부")

    default_map_url = Column(String(512), nullable=True)
    default_latitude = Column(Float, nullable=True)
    default_longitude = Column(Float, nullable=True)
    default_place_id = Column(String(64), nullable=True, comment="네이버 placeId (검색/앱 링크용)")
    
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

    # 회차-매니저 위임 관계
    round_managers = relationship(
        "RoundManager",
        back_populates="challenge",
        cascade="all, delete-orphan"
    )

    # 라운드 사진 중 하나를 대표로 지정한 경우 관계
    cover_round_picture = relationship("RoundPicture", foreign_keys=[cover_round_picture_id])
