from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class AdminRequest(Base):
    __tablename__ = "admin_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum("pending", "approved", "rejected", name="admin_request_status"), nullable=False, server_default="pending")
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

