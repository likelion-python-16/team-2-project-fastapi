# models/admin_notice.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class AdminNotice(Base, TimestampMixin):
    __tablename__ = "admin_notices"

    id = Column(Integer, primary_key=True, index=True)
    
    # 작성자 필드 추가
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="작성한 관리자 ID")

    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)

    # TimestampMixin: created_at / updated_at
    is_active = Column(Boolean, default=True, nullable=False)

    # 관계
    author = relationship("User", back_populates="admin_notices", foreign_keys=[author_id])
    
    __table_args__ = (
        Index("ix_admin_notice_active", "is_active"),
        Index("ix_admin_notice_updated", "updated_at"),
        Index("ix_admin_notice_author", "author_id"),  # 작성자별 조회용
    )