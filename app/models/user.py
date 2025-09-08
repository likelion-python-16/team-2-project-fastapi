from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Enum, Integer, String, Boolean, Float, Text, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
from ..security import hash_password, verify_password, encrypt_str, decrypt_str
from app.models.round_manager import RoundManager
from sqlalchemy.orm import relationship

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
    
    # 기본값이 있는 필드들
    manner_score = Column(Float, default=30.0, nullable=False, index=True)
    total_points = Column(Integer, default=0, nullable=False, index=True)
    penalty_total = Column(Integer, default=0, nullable=False)
    warning_count = Column(Integer, default=0, nullable=False)  # 경고 횟수
    is_review_banned = Column(Boolean, default=False, nullable=False)  # 리뷰 작성 금지
    is_admin = Column(Boolean, default=False, nullable=False)
    is_superadmin = Column(Boolean, default=False, nullable=False)

    # ★ 엄격모드: 기본 비활성/미인증
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    email_verified = Column(Boolean, default=False, nullable=False, index=True)

    # 소프트 삭제
    is_deleted = Column(Boolean, default=False, nullable=False, server_default='0', index=True)
    deleted_at = Column(DateTime, nullable=True)

    token_version = Column(Integer, nullable=False, server_default='0')
    
    # 소셜 로그인 관련 필드
    provider = Column(String(50), nullable=True)
    provider_id = Column(String(100), nullable=True)

    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id", overlaps="notifications")
    payments = relationship("Payment", back_populates="user", foreign_keys="Payment.user_id", overlaps="payments")
    refunds = relationship("Refund", back_populates="user", foreign_keys="Refund.user_id", overlaps="refunds")
    uploaded_round_pictures = relationship("RoundPicture", back_populates="uploader", foreign_keys="RoundPicture.uploaded_by", overlaps="uploader")
    created_challenges = relationship("Challenge", back_populates="creator", foreign_keys="Challenge.creator_id", overlaps="creator")
    participations = relationship("Participation", back_populates="user", foreign_keys="Participation.user_id")
    kicked_participations = relationship("Participation", foreign_keys="Participation.kicked_by")
    managed_rounds = relationship("RoundManager", back_populates="user", cascade="all, delete-orphan")

    user_tags = relationship("UserTag", back_populates="user")
    following_relations = relationship("Following", foreign_keys="Following.follower_id", back_populates="follower")
    follower_relations = relationship("Following", foreign_keys="Following.following_id", back_populates="following")
    invitations_sent = relationship("Invitation", foreign_keys="Invitation.inviter_id", back_populates="inviter")
    invitations_received = relationship("Invitation", foreign_keys="Invitation.invitee_id", back_populates="invitee")
    invitations_reviewed = relationship("Invitation", foreign_keys="Invitation.reviewed_by", back_populates="reviewer")
    point_histories = relationship("PointHistory", back_populates="user")
    # reviews 관계는 Review 모델에서 정의하므로 여기서는 제거
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
        """주민등록번호(13자리) 저장: 형식 검증 후 암호화 + 지문 생성
        - YYMMDD + (7번째: 1~8) 제약
        - 월 십의 자리(3번째)는 0/1, 일 십의 자리(5번째)는 0/1/2/3
        - 유효 월(1~12), 유효 일(1~31)
        """
        import re as _re
        if plain_number is None or str(plain_number).strip() == "":
            self.identification_number = None
            self.identification_fingerprint = None
            return
        # 숫자만 추출 및 기본 형식 검증
        n = _re.sub(r"\D+", "", str(plain_number))
        if not _re.fullmatch(r"\d{13}", n):
            raise ValueError("식별번호는 13자리 숫자여야 합니다")
        # 월/일 자릿수 제약 (월 십의 자리: 0/1, 일 십의 자리: 0~3)
        if n[2] not in ("0", "1"):
            raise ValueError("월의 십의 자리는 0 또는 1이어야 합니다")
        if n[4] not in ("0", "1", "2", "3"):
            raise ValueError("일의 십의 자리는 0-3이어야 합니다")
        # 유효 월/일
        m = int(n[2:4]); d = int(n[4:6])
        if not (1 <= m <= 12):
            raise ValueError("월은 01-12여야 합니다")
        if not (1 <= d <= 31):
            raise ValueError("일은 01-31이어야 합니다")
        # 7번째(성별/세기) 제약: 1~8
        if n[6] not in "12345678":
            raise ValueError("7번째 자리는 1-8이어야 합니다")

        # 저장: 암호화 + fingerprint (정규화된 13자리 기준)
        self.identification_number = encrypt_str(n)
        try:
            from ..security import id_fingerprint
            self.identification_fingerprint = id_fingerprint(n)
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
        """매너 점수 업데이트 (30-100 범위 유지)"""
        new_score = self.manner_score + score_change
        self.manner_score = max(30.0, min(100.0, new_score))
    
    def calculate_manner_score_from_rating(self, rating: float) -> float:
        """리뷰 별점을 기준으로 매너점수 변화량 계산"""
        if rating >= 4.5:
            return 2.0
        elif rating >= 4.0:
            return 1.5
        elif rating >= 3.5:
            return 1.0
        elif rating >= 3.0:
            return 0.5
        elif rating >= 2.5:
            return 0.0
        elif rating >= 2.0:
            return -0.5
        elif rating >= 1.5:
            return -1.0
        else:
            return -1.5

    def apply_report_penalty(self) -> str:
        """신고 승인시 제재 적용 (1회 경고, 2회 리뷰 금지)"""
        self.warning_count += 1
        self.update_manner_score(-3.0)  # 매너점수 3점 차감
        
        if self.warning_count >= 2:
            self.is_review_banned = True
            return "리뷰 작성 금지"
        else:
            return "1회 경고"
    
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

    # 이메일 인증 토큰들
    email_verifications = relationship(
        "EmailVerification",
        back_populates="user",
        passive_deletes=True,
    )

Index("idx_user_region_manner", User.region_active, User.manner_score)
Index("idx_user_active_points", User.is_active, User.total_points)
Index("idx_user_email_active", User.email, User.is_active)
UniqueConstraint(User.provider, User.provider_id, name="uq_user_provider_pid")