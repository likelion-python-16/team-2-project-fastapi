from datetime import datetime
import enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin

# =========================
# ENUM 정의
# =========================
class QRStatus(str, enum.Enum):
    valid = "valid"
    used = "used"
    expired = "expired"
    revoked = "revoked"

class CheckMethod(str, enum.Enum):
    qr = "qr"
    gps = "gps"
    image = "image"
    manual = "manual"

class AutoDecision(str, enum.Enum):
    _pass = "pass"
    review = "review"
    fail = "fail"

class InitialDecision(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    review = "review"

class InitialDecisionCode(str, enum.Enum):
    late = "late"
    no_gps = "no_gps"
    wrong_place = "wrong_place"
    no_face = "no_face"
    file_invalid = "file_invalid"
    other = "other"

class ProofStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class AppealDecisionCode(str, enum.Enum):
    insufficient_evidence = "insufficient_evidence"
    still_no_gps = "still_no_gps"
    time_mismatch = "time_mismatch"
    face_mismatch = "face_mismatch"
    duplicate = "duplicate"
    other = "other"

class AttendanceStatus(str, enum.Enum):
    pending = "pending"
    present = "present"
    late = "late"
    absent = "absent"
    rejected = "rejected"

class AppealStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"

# =========================
# QRCode
# =========================
class QRCode(Base, TimestampMixin):
    __tablename__ = "qrcodes"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("challenge_rounds.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    qr_token = Column(String(255), nullable=False)
    scanned_at = Column(DateTime, nullable=True)

    # 스키마에서 created_at DEFAULT CURRENT_TIMESTAMP → Mixin과 동일하게 운용
    expires_at = Column(DateTime, nullable=True)
    jti = Column(String(64), nullable=True)

    status = Column(SAEnum(QRStatus, name="qr_status_enum"), default=QRStatus.valid, nullable=False)

    # 관계
    user = relationship("User", back_populates="qrcodes", lazy="joined", foreign_keys=[user_id])
    round = relationship("ChallengeRound", back_populates="qrcodes", lazy="joined", foreign_keys=[round_id])
    attendance = relationship(  # 1:1 매핑(사실상)
        "RoundAttendance",
        back_populates="qr",
        uselist=False,
        primaryjoin="QRCode.id==RoundAttendance.qr_id"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "round_id", name="uq_qr_user_round"),
        Index("ix_qr_round_status", "round_id", "status"),
        Index("ix_qr_user", "user_id"),
        Index("ix_qr_token", "qr_token"),
    )


# =========================
# Round_Attendance
# =========================
class RoundAttendance(Base, TimestampMixin):
    __tablename__ = "round_attendances"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(Integer, ForeignKey("challenge_rounds.id", ondelete="CASCADE"), nullable=False)

    is_checked_in = Column(Boolean, default=False, nullable=False)
    is_checked_out = Column(Boolean, default=False, nullable=False)
    checkin_time = Column(DateTime, nullable=True)
    checkout_time = Column(DateTime, nullable=True)

    manually_verified = Column(Boolean, default=False, nullable=False)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    ai_score = Column(Float, nullable=True)

    qr_id = Column(Integer, ForeignKey("qrcodes.id", ondelete="SET NULL"), nullable=True)
    scanned_at = Column(DateTime, nullable=True)

    status = Column(
        SAEnum(AttendanceStatus, name="attendance_status_enum"),
        default=AttendanceStatus.pending,
        nullable=False
    )

    proof_id = Column(Integer, ForeignKey("proofs.id", ondelete="SET NULL"), nullable=True)

    verified_by_meta = Column(Boolean, default=False, nullable=False)
    meta_check_time = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)

    check_method = Column(SAEnum(CheckMethod, name="check_method_enum"), default=CheckMethod.qr, nullable=False)
    auto_decision = Column(SAEnum(AutoDecision, name="auto_decision_enum"), nullable=True)

    initial_decision = Column(SAEnum(InitialDecision, name="initial_decision_enum"),
    default=InitialDecision.review, nullable=False)
    initial_decision_reason = Column(Text, nullable=True)
    initial_decision_code = Column(SAEnum(InitialDecisionCode, name="initial_decision_code_enum"), nullable=True)

    # 관계
    round = relationship("ChallengeRound", back_populates="attendances", lazy="joined")
    verifier = relationship("User", lazy="joined", foreign_keys=[verified_by])
    user = relationship("User", back_populates="round_attendances", lazy="joined", foreign_keys=[user_id])

    qr = relationship("QRCode", back_populates="attendance", lazy="joined", foreign_keys=[qr_id])

    proof = relationship(
        "Proof",
        back_populates="attendances",
        lazy="selectin",
        foreign_keys=[proof_id]
    )

    appeals = relationship(
        "Appeal",
        back_populates="attendance",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "round_id", name="uq_ra_user_round"),
        Index("ix_ra_round_user", "round_id", "user_id"),
        Index("ix_ra_status", "status"),
        Index("ix_ra_checkin", "checkin_time"),
    )


# =========================
# Proof
# =========================
class Proof(Base, TimestampMixin):
    __tablename__ = "proofs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(Integer, ForeignKey("challenge_rounds.id", ondelete="CASCADE"), nullable=False)

    proof_type = Column(String(30), nullable=False)           # 스키마대로 VARCHAR(30)
    file_url = Column(String(255), nullable=True)             # 단일 파일
    exif_data = Column(JSON, nullable=True)                    # EXIF/GPS/촬영시각 등 구조화
    status = Column(SAEnum(ProofStatus, name="proof_status_enum"),
                    default=ProofStatus.pending, nullable=False)

    initial_verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    verified_at = Column(DateTime, nullable=True)

    ai_score = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    explanation_choices = Column(String(255), nullable=True)
    explanation_file_url = Column(String(255), nullable=True)

    files_json = Column(JSON, nullable=True)                  # 다중 파일
    face_compare_score = Column(Float, nullable=True)

    # 관계
    verifier = relationship("User", lazy="joined", foreign_keys=[initial_verified_by])
    user = relationship("User", back_populates="proofs", lazy="joined", foreign_keys=[user_id])
    challenge = relationship("Challenge", back_populates="proofs", lazy="joined")
    round = relationship("ChallengeRound", back_populates="proofs", lazy="joined")

    # RoundAttendance에서 대표 증빙으로 참조 (1:N, viewonly 아님 → RA.proof_id 업데이트 가능)
    attendances = relationship(
        "RoundAttendance",
        back_populates="proof",
        primaryjoin="Proof.id==RoundAttendance.proof_id"
    )

    __table_args__ = (
        Index("ix_proof_round_user_submitted", "round_id", "user_id", "submitted_at"),
        Index("ix_proof_status", "status"),
        Index("ix_proof_challenge", "challenge_id"),
    )


# =========================
# Appeal
# =========================
class Appeal(Base, TimestampMixin):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)

    round_attendance_id = Column(Integer, ForeignKey("round_attendances.id", ondelete="CASCADE"), nullable=False)

    explanation = Column(Text, nullable=True)
    files_url = Column(JSON, nullable=True)

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    appeal_status = Column(String(20), default="pending", nullable=False)  # 스키마대로 String(20)
    note = Column(Text, nullable=True)

    decision_reason = Column(Text, nullable=True)
    decision_code = Column(SAEnum(AppealDecisionCode, name="appeal_decision_code_enum"), nullable=True)
    auto_reason = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    # 관계
    attendance = relationship("RoundAttendance", back_populates="appeals", lazy="joined")
    verifier = relationship("User", back_populates="verified_appeals", lazy="joined", foreign_keys=[verified_by])

    __table_args__ = (
        Index("ix_appeal_ra", "round_attendance_id"),
        Index("ix_appeal_status", "appeal_status"),
        Index("ix_appeal_submitted", "submitted_at"),
    )