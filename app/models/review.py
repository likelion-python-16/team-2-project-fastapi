# models/review.py
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, JSON,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum, Boolean
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class ReviewStatus(str, enum.Enum):
    visible = "visible"
    hidden = "hidden"
    deleted = "deleted"

class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # 리뷰 작성자
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # 리뷰 대상자
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(Integer, ForeignKey("challenge_rounds.id", ondelete="CASCADE"), nullable=True)
    comment = Column(Text, nullable=True)
    rating = Column(Float, nullable=False)
    helpful_count = Column(Integer, default=0, nullable=False)
    status = Column(
        SAEnum(ReviewStatus, name="review_status_enum"),
        default=ReviewStatus.visible,
        nullable=False
    )
    images_json = Column(JSON, nullable=True)
    
    # 관계
    user = relationship("User", lazy="joined", foreign_keys=[user_id])
    target_user = relationship("User", lazy="joined", foreign_keys=[target_user_id])
    challenge = relationship("Challenge", back_populates="reviews", lazy="joined")
    round = relationship("ChallengeRound", back_populates="reviews", lazy="joined")
    helpfuls = relationship(
        "ReviewHelpful",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    __table_args__ = (
        # 유저-챌린지, 유저-라운드 각각 1회만 리뷰 가능
        UniqueConstraint("user_id", "challenge_id", name="uq_review_user_challenge"),
        UniqueConstraint("user_id", "round_id", name="uq_review_user_round"),
        Index("ix_review_challenge", "challenge_id"),
        Index("ix_review_round", "round_id"),
        Index("ix_review_status", "status"),
        Index("ix_review_rating", "rating"),  # 평점별 조회용
        Index("ix_review_helpful_count", "helpful_count"),  # 인기 리뷰 조회용
    )

class ReviewHelpful(Base):
    """
    리뷰 '도움됐어요' 기록 테이블.
    - (review_id, user_id) 유니크 → 한 유저가 같은 리뷰에 중복 눌림 방지
    - Review.helpful_count 는 서비스 로직에서 증감(트랜잭션으로 관리)
    """
    __tablename__ = "review_helpfuls"
    
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    review = relationship("Review", back_populates="helpfuls", lazy="joined")
    user = relationship("User", back_populates="helpful_given", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_helpful_review_user"),
        Index("ix_helpful_review", "review_id"),
        Index("ix_helpful_user", "user_id"),
        Index("ix_helpful_created", "created_at"),  # 최근 도움 표시 조회용
    )