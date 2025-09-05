from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint, Index, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base

class RoundManager(Base):
    __tablename__ = "round_managers"
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(Integer, ForeignKey("challenge_rounds.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),   # ✅ UPDATE 시 자동 갱신
        nullable=False,
    )

    challenge = relationship("Challenge")
    round = relationship("ChallengeRound")
    user = relationship("User")

    __table_args__ = (
        # ✅ 라운드당 1명
        UniqueConstraint("challenge_id", "round_id", name="uq_round_manager_one_per_round"),
        # ✅ 마이그레이션과 동일한 인덱스 구성
        Index("ix_rm_ch_round", "challenge_id", "round_id"),
        Index("ix_rm_user", "user_id"),
    )