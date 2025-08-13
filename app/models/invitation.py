import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    canceled = "canceled"

class Invitation(Base, TimestampMixin):
    __tablename__ = "invitations"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    inviter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invitee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(InvitationStatus, name="invitation_status_enum"),
                    default=InvitationStatus.pending, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # TimestampMixin이 created_at, updated_at을 제공하므로 중복 제거
    
    # 관계
    challenge = relationship("Challenge", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="invitations_sent")
    invitee = relationship("User", foreign_keys=[invitee_id], back_populates="invitations_received")
    reviewer = relationship("User", foreign_keys=[reviewed_by], back_populates="invitations_reviewed")
    
    __table_args__ = (
        UniqueConstraint("challenge_id", "invitee_id", name="uq_invitation_challenge_invitee"),
        Index("ix_invitation_challenge", "challenge_id"),
        Index("ix_invitation_status", "status"),
        Index("ix_invitation_inviter", "inviter_id"),
        Index("ix_invitation_invitee", "invitee_id"),
        Index("ix_invitation_reviewed", "reviewed_at"),  # 리뷰 상태 조회용
    )