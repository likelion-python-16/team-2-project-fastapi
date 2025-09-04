from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, JSON, Index
)
from sqlalchemy.orm import relationship
from .base import Base

class ChallengeEmbedding(Base):
    __tablename__ = "challenge_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    
    # JSON로 저장(엔진 독립적). Postgres면 ARRAY(Float)로 바꿔도 OK.
    embedding = Column(JSON, nullable=False)
    model_name = Column(String(100), nullable=False)
    updated_at = Column(DateTime, 
    default=lambda: datetime.now(timezone.utc), 
    onupdate=lambda: datetime.now(timezone.utc), 
    nullable=False)
    
    # 관계
    challenge = relationship("Challenge", back_populates="embeddings")
    
    __table_args__ = (
        UniqueConstraint("challenge_id", "model_name", name="uq_challenge_embedding_per_model"),
        Index("ix_embedding_challenge", "challenge_id"),
        Index("ix_embedding_model", "model_name"),
        Index("ix_embedding_updated", "updated_at"),
    )