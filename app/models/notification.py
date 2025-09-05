import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class NotificationEvent(str, enum.Enum):
    challenge_deleted = "challenge_deleted"
    creator_delegated = "creator_delegated"
    review_created = "review_created"
    review_updated = "review_updated"
    review_received = "review_received"
    refund_succeeded = "refund_succeeded"
    refund_failed = "refund_failed"
    point_awarded = "point_awarded"
    notice_posted = "notice_posted"
    join_completed = "join_completed"
    challenge_created = "challenge_created"
    challenge_joined = "challenge_joined"
    report_received = "report_received"
    warning_received = "warning_received"

class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    event_type = Column(SAEnum(NotificationEvent, name="notification_event_enum"), nullable=True)
    
    # TimestampMixin이 created_at, updated_at을 제공하므로 중복 제거
    
    # 관계 - 수정된 부분
    user = relationship("User", back_populates="notifications")
    
    __table_args__ = (
        Index("ix_notification_user", "user_id"),
        Index("ix_notification_is_read", "is_read"),
        Index("ix_notification_event", "event_type"),
        Index("ix_notification_created", "created_at"),
        Index("ix_notification_user_read", "user_id", "is_read"),  # 복합 인덱스 추가
        Index("ix_notification_target", "target_type", "target_id"),  # 타겟 조회용
    )