# models/chat.py
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

class ChatRoom(Base, TimestampMixin):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    # DM 방 지원을 위해 NULL 허용 (챌린지 미연동 방)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=True)
    creator_id   = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    # 관계
    challenge = relationship("Challenge", back_populates="chat_rooms", lazy="joined")
    creator   = relationship("User", back_populates="chat_rooms_created", lazy="joined", foreign_keys=[creator_id])
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan", lazy="selectin")
    participants = relationship("ChatParticipant", back_populates="room", cascade="all, delete-orphan", lazy="selectin")
    
    __table_args__ = (
        Index("ix_chatroom_challenge", "challenge_id"),
        Index("ix_chatroom_creator", "creator_id"),
        Index("ix_chatroom_created", "created_at"),  # 생성 시간 조회용
    )

class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id   = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    content  = Column(Text, nullable=False)
    file_url = Column(String(255), nullable=True)
    is_read  = Column(Boolean, default=False, nullable=False)
    
    # 관계
    room   = relationship("ChatRoom", back_populates="messages", lazy="joined")
    sender = relationship("User", back_populates="chat_messages_sent", lazy="joined", foreign_keys=[sender_id])
    
    __table_args__ = (
        Index("ix_chatmsg_room_created", "room_id", "created_at"),
        Index("ix_chatmsg_sender", "sender_id"),
        Index("ix_chatmsg_is_read", "is_read"),  # 읽음 상태 조회용
    )

class ChatParticipant(Base):
    __tablename__ = "chat_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 관계
    room = relationship("ChatRoom", back_populates="participants", lazy="joined")
    user = relationship("User", back_populates="chat_participations", lazy="joined")
    
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_chat_participant"),
        Index("ix_chatpart_room", "room_id"),
        Index("ix_chatpart_user", "user_id"),
        Index("ix_chatpart_joined", "joined_at"),  # 참가 시간 조회용
    )
