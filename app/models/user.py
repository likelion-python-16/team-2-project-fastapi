from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Enum, Integer, String, Boolean, Float, Text, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
from ..security import hash_password, verify_password, encrypt_str, decrypt_str
from app.models.round_manager import RoundManager

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # (레거시) 평문 정규화 저장 컬럼 — 가급적 비워두길 권장
    phone = Column(String(20), unique=True, index=True, nullable=True)

    # 신규: 암호화 + 지문
    phone_encrypted = Column(String(255), nullable=True)
    phone_fingerprint = Column(String(64), unique=True, nullable=True, index=True)

    identification_number = Column(String(255), nullable=True)
    identification_fingerprint = Column(String(64), unique=True, nullable=True, index=True)

    gender = Column(
        Enum("male", "female", "other", name="gender_enum"),
        nullable=False,
        server_default="other"
    )

    region_living = Column(String(50), nullable=False, server_default='')
    region_active = Column(String(50), nullable=False, server_default='', index=True)
    profile_image = Column(String(255), nullable=False, server_default='')
    introduction = Column(Text, nullable=False)

    manner_score = Column(Float, default=0.0, nullable=False, index=True)
    total_points = Column(Integer, default=0, nullable=False, index=True)
    penalty_total = Column(Integer, default=0, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # ★ 엄격모드: 기본 비활성/미인증
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    email_verified = Column(Boolean, default=False, nullable=False, index=True)

    token_version = Column(Integer, nullable=False, server_default='0')

    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id", overlaps="notifications")
    payments = relationship("Payment", back_populates="user", foreign_keys="Payment.user_id", overlaps="payments")
    refunds = relationship("Refund", back_populates="user", foreign_keys="Refund.user_id", overlaps="refunds")
    point_exchange_requests = relationship("PointExchangeRequest", back_populates="user", foreign_keys="PointExchangeRequest.user_id", overlaps="point_exchange_requests")
    uploaded_round_pictures = relationship("RoundPicture", back_populates="uploader", foreign_keys="RoundPicture.uploaded_by", overlaps="uploader")
    created_challenges = relationship("Challenge", back_populates="creator", foreign_keys="Challenge.creator_id", overlaps="creator")
    participations = relationship("Participation", back_populates="user")
    managed_rounds = relationship("RoundManager", back_populates="user", cascade="all, delete-orphan")

    user_tags = relationship("UserTag", back_populates="user")
    following_relations = relationship("Following", foreign_keys="Following.follower_id", back_populates="follower")
    follower_relations = relationship("Following", foreign_keys="Following.following_id", back_populates="following")
    invitations_sent = relationship("Invitation", foreign_keys="Invitation.inviter_id", back_populates="inviter")
    invitations_received = relationship("Invitation", foreign_keys="Invitation.invitee_id", back_populates="invitee")
    invitations_reviewed = relationship("Invitation", foreign_keys="Invitation.reviewed_by", back_populates="reviewer")
    point_histories = relationship("PointHistory", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    helpful_given = relationship("ReviewHelpful", back_populates="user")
    qrcodes = relationship("QRCode", back_populates="user")
    round_attendances = relationship("RoundAttendance", back_populates="user", foreign_keys="RoundAttendance.user_id")
    proofs = relationship("Proof", back_populates="user", foreign_keys="Proof.user_id")
    verified_appeals = relationship("Appeal", back_populates="verifier", foreign_keys="Appeal.verified_by")
    admin_notices = relationship("AdminNotice", back_populates="author")
    reports_made = relationship("Report", foreign_keys="Report.reporter_id", back_populates="reporter")
    reports_received = relationship("Report", foreign_keys="Report.reported_id", back_populates="reported")
    penalties = relationship("PenaltyHistory", back_populates="user")
    chat_rooms_created = relationship("ChatRoom", back_populates="creator", foreign_keys="ChatRoom.creator_id")
    chat_messages_sent = relationship("ChatMessage", back_populates="sender", foreign_keys="ChatMessage.sender_id")
    chat_participations = relationship("ChatParticipant", back_populates="user")

    def set_password(self, plain_password: str) -> None:
        if not plain_password or len(plain_password.strip()) == 0:
            raise ValueError("비밀번호는 비어있을 수 없습니다")
        self.password_hash = hash_password(plain_password)
    
    def verify_password(self, plain_password: str) -> bool:
        if not plain_password:
            return False
        return verify_password(plain_password, self.password_hash)

    def set_identification_number(self, plain_number: Optional[str]) -> None:
        if plain_number is None:
            self.identification_number = None
            self.identification_fingerprint = None
        else:
            self.identification_number = encrypt_str(plain_number)
            try:
                from ..security import id_fingerprint
                self.identification_fingerprint = id_fingerprint(plain_number)
            except Exception:
                self.identification_fingerprint = None
    
    def get_identification_number(self) -> Optional[str]:
        if not self.identification_number:
            return None
        try:
            return decrypt_str(self.identification_number)
        except Exception:
            return None

    def set_phone(self, plain_phone: Optional[str]) -> None:
        if not plain_phone:
            self.phone = None
            self.phone_encrypted = None
            self.phone_fingerprint = None
            return
        self.phone = None
        try:
            self.phone_encrypted = encrypt_str(plain_phone)
        except Exception:
            self.phone_encrypted = None
        from ..security import id_fingerprint, normalize_phone
        normalized = normalize_phone(plain_phone)
        self.phone_fingerprint = id_fingerprint(normalized)

    def get_phone(self) -> Optional[str]:
        if not self.phone_encrypted:
            return None
        try:
            return decrypt_str(self.phone_encrypted)
        except Exception:
            return None
    
    def is_email_verified(self) -> bool:
        return bool(self.email_verified)
    
    def can_exchange_points(self) -> bool:
        return self.is_active and self.penalty_total < 3
    
    def get_display_name(self) -> str:
        return self.name if self.name else self.username
    
    def update_manner_score(self, score_change: float) -> None:
        new_score = self.manner_score + score_change
        self.manner_score = max(0.0, min(100.0, new_score))
    
    def add_points(self, points: int) -> None:
        if points > 0:
            self.total_points += points
    
    def deduct_points(self, points: int) -> bool:
        if points <= 0:
            return False
        if self.total_points >= points:
            self.total_points -= points
            return True
        return False
    
    def add_penalty(self) -> None:
        self.penalty_total += 1
        if self.penalty_total >= 5:
            self.is_active = False
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', name='{self.name}')>"

Index("idx_user_region_manner", User.region_active, User.manner_score)
Index("idx_user_active_points", User.is_active, User.total_points)
Index("idx_user_email_active", User.email, User.is_active)
