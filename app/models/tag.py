from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class Tag(Base, TimestampMixin):
    """
    태그 마스터
    - tag: 실제 태그 텍스트 (UNIQUE, NOT NULL)
    - embedding: 벡터/임베딩(JSON) 저장 가능
    - embedding_updated_at: 임베딩 최신화 시각
    """
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String(255), nullable=False, unique=True)
    icon_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    embedding = Column(JSON, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_updated_at = Column(DateTime, nullable=True)
    
    # 관계
    user_tags = relationship("UserTag", back_populates="tag", cascade="all, delete-orphan")
    challenge_tags = relationship("ChallengeTag", back_populates="tag", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_tag_active", "is_active"),
        Index("ix_tag_text", "tag"),
    )

class UserTag(Base):
    """
    유저-태그 연결(다대다 조인 테이블)
    - (tag_id, user_id) 유니크
    """
    __tablename__ = "user_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    selected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    tag = relationship("Tag", back_populates="user_tags", lazy="joined")
    user = relationship("User", back_populates="user_tags", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint("tag_id", "user_id", name="uq_user_tag_pair"),
        Index("ix_user_tag_user", "user_id"),
        Index("ix_user_tag_tag", "tag_id"),
    )

class ChallengeTag(Base):
    """
    챌린지-태그 연결(다대다 조인 테이블)
    - (tag_id, challenge_id) 유니크
    """
    __tablename__ = "challenge_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    selected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    tag = relationship("Tag", back_populates="challenge_tags", lazy="joined")
    challenge = relationship("Challenge", back_populates="challenge_tags", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint("tag_id", "challenge_id", name="uq_challenge_tag_pair"),
        Index("ix_ch_tag_challenge", "challenge_id"),
        Index("ix_ch_tag_tag", "tag_id"),
    )