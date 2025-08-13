from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
from ..security import hash_password, verify_password, encrypt_str, decrypt_str

class User(Base):
    __tablename__ = "users"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # 필수 필드들
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(30), nullable=False)
    
    # 타임스탬프
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 선택 필드들
    phone = Column(String(20), nullable=True)
    identification_number = Column(String(255), nullable=True)  # 암호화 저장
    gender = Column(String(10), nullable=True)
    region_living = Column(String(50), nullable=True)
    region_active = Column(String(50), nullable=True, index=True)
    profile_image = Column(String(255), nullable=True)
    introduction = Column(Text, nullable=True)
    
    # 기본값이 있는 필드들
    manner_score = Column(Float, default=0.0, nullable=False, index=True)
    total_points = Column(Integer, default=0, nullable=False, index=True)
    penalty_total = Column(Integer, default=0, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # 관계 설정
    notifications = relationship(
        "Notification",
        back_populates="user",
        foreign_keys="Notification.user_id",
        overlaps="notifications"
    )
    
    payments = relationship(
        "Payment",
        back_populates="user", 
        foreign_keys="Payment.user_id",
        overlaps="payments"
    )
    
    refunds = relationship(
        "Refund",
        back_populates="user",
        foreign_keys="Refund.user_id",
        overlaps="refunds"
    )
    
    point_exchange_requests = relationship(
        "PointExchangeRequest",
        back_populates="user",
        foreign_keys="PointExchangeRequest.user_id",
        overlaps="point_exchange_requests"
    )
    
    uploaded_round_pictures = relationship(
        "RoundPicture",
        back_populates="uploader",
        foreign_keys="RoundPicture.uploaded_by",
        overlaps="uploader"
    )
    created_challenges = relationship(
    "Challenge", 
    back_populates="creator",
    foreign_keys="Challenge.creator_id",
    overlaps="creator"
    )

    participations = relationship(
    "Participation", 
    back_populates="user"
    )
    # User 모델에 추가해야 할 relationship들
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
    # 비밀번호 메서드
    def set_password(self, plain_password: str) -> None:
        """평문 비밀번호를 해시하여 저장"""
        if not plain_password or len(plain_password.strip()) == 0:
            raise ValueError("비밀번호는 비어있을 수 없습니다")
        self.password_hash = hash_password(plain_password)
    
    def verify_password(self, plain_password: str) -> bool:
        """비밀번호 검증"""
        if not plain_password:
            return False
        return verify_password(plain_password, self.password_hash)
    
    # 식별번호 메서드 (암호화)
    def set_identification_number(self, plain_number: Optional[str]) -> None:
        """식별번호 암호화하여 저장"""
        if plain_number is None:
            self.identification_number = None
        else:
            self.identification_number = encrypt_str(plain_number)
    
    def get_identification_number(self) -> Optional[str]:
        """식별번호 복호화하여 반환"""
        if not self.identification_number:
            return None
        try:
            return decrypt_str(self.identification_number)
        except Exception:
            return None
    
    # 유틸리티 메서드들
    def is_email_verified(self) -> bool:
        """이메일 인증 여부 확인"""
        return self.email is not None and self.is_active
    
    def can_exchange_points(self) -> bool:
        """포인트 교환 가능 여부"""
        return self.is_active and self.penalty_total < 3
    
    def get_display_name(self) -> str:
        """표시용 이름 반환"""
        return self.name if self.name else self.username
    
    def update_manner_score(self, score_change: float) -> None:
        """매너 점수 업데이트 (0-100 범위 유지)"""
        new_score = self.manner_score + score_change
        self.manner_score = max(0.0, min(100.0, new_score))
    
    def add_points(self, points: int) -> None:
        """포인트 추가"""
        if points > 0:
            self.total_points += points
    
    def deduct_points(self, points: int) -> bool:
        """포인트 차감 (잔액 부족시 False 반환)"""
        if points <= 0:
            return False
        if self.total_points >= points:
            self.total_points -= points
            return True
        return False
    
    def add_penalty(self) -> None:
        """패널티 추가"""
        self.penalty_total += 1
        if self.penalty_total >= 5:  # 5회 이상시 비활성화
            self.is_active = False
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', name='{self.name}')>"

# 인덱스들
Index("idx_user_region_manner", User.region_active, User.manner_score)
Index("idx_user_active_points", User.is_active, User.total_points)
Index("idx_user_email_active", User.email, User.is_active)