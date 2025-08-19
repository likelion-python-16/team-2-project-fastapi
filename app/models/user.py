from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin
from ..security import hash_password, verify_password, encrypt_str, decrypt_str


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # PK
    id = Column(Integer, primary_key=True, index=True)

    # 필수/고유
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=True)

    # 인증
    password_hash = Column(String(255), nullable=False)

    # 프로필
    name = Column(String(30), nullable=True)  # 회원가입에서 선택사항이므로 nullable 허용
    gender = Column(String(10), nullable=True)
    profile_image = Column(String(255), nullable=True)
    introduction = Column(Text, nullable=True)

    # 연락/지역
    phone_number = Column(String(20), nullable=True, index=True)  # ← phone -> phone_number로 통일
    region_living = Column(String(50), nullable=True)
    region_active = Column(String(50), nullable=True, index=True)

    # 개인식별(암호화 저장)
    identification_number = Column(String(255), nullable=True)

    # 상태/집계
    manner_score = Column(Float, default=0.0, nullable=False, index=True)
    total_points = Column(Integer, default=0, nullable=False, index=True)
    penalty_total = Column(Integer, default=0, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    token_version = Column(Integer, nullable=False, default=0, server_default="0", index=True)

    # 관계
    notifications = relationship(
        "Notification",
        back_populates="user",
        foreign_keys="Notification.user_id",
    )
    payments = relationship(
        "Payment",
        back_populates="user",
        foreign_keys="Payment.user_id",
    )
    refunds = relationship(
        "Refund",
        back_populates="user",
        foreign_keys="Refund.user_id",
    )
    point_exchange_requests = relationship(
        "PointExchangeRequest",
        back_populates="user",
        foreign_keys="PointExchangeRequest.user_id",
    )
    uploaded_round_pictures = relationship(
        "RoundPicture",
        back_populates="uploader",
        foreign_keys="RoundPicture.uploaded_by",
    )
    created_challenges = relationship(
        "Challenge",
        back_populates="creator",
        foreign_keys="Challenge.creator_id",
    )
    participations = relationship(
        "Participation",
        back_populates="user",
    )

    # 확장 관계
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

    # ----- 메서드들 -----
    # 비밀번호
    def set_password(self, plain_password: str) -> None:
        if not plain_password or len(plain_password.strip()) == 0:
            raise ValueError("비밀번호는 비어있을 수 없습니다")
        self.password_hash = hash_password(plain_password)

    def verify_password(self, plain_password: str) -> bool:
        if not plain_password:
            return False
        return verify_password(plain_password, self.password_hash)

    # 식별번호(암호화)
    def set_identification_number(self, plain_number: Optional[str]) -> None:
        if plain_number is None:
            self.identification_number = None
        else:
            self.identification_number = encrypt_str(plain_number)

    def get_identification_number(self) -> Optional[str]:
        if not self.identification_number:
            return None
        try:
            return decrypt_str(self.identification_number)
        except Exception:
            return None

    # 유틸
    def is_email_verified(self) -> bool:
        return self.email is not None and self.is_active

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


# 인덱스
Index("idx_user_region_manner", User.region_active, User.manner_score)
Index("idx_user_active_points", User.is_active, User.total_points)
Index("idx_user_email_active", User.email, User.is_active)
