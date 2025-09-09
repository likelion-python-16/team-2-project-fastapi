import enum
from datetime import datetime, timezone, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, DateTime, Boolean, String, Text, Date, Float,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from .base import Base, TimestampMixin

# ============= 개선된 Enum 정의 =============
class ParticipationRole(str, enum.Enum):
    """참가 역할"""
    creator = "creator"      # 챌린지 생성자
    participant = "participant"  # 일반 참가자  
    manager = "manager"      # 위임 관리자

class ParticipationStatus(str, enum.Enum):
    """참가 상태 - 생명주기 기반"""
    pending = "pending"          # 대기 중 (결제 전/승인 전)
    payment_pending = "payment_pending"  # 결제 대기 중
    active = "active"            # 활성 참가 중
    paused = "paused"           # 일시 정지 (재개 가능)
    completed = "completed"      # 챌린지 완료
    cancelled = "cancelled"      # 참가 취소 (자발적)
    expelled = "expelled"        # 강제 퇴출
    payment_failed = "payment_failed"  # 결제 실패로 인한 중단

class LeaveType(str, enum.Enum):
    """탈퇴 유형"""
    voluntary = "voluntary"      # 자발적 탈퇴
    kicked = "kicked"           # 강제 퇴출
    payment_failure = "payment_failure"  # 결제 실패
    rule_violation = "rule_violation"    # 규칙 위반
    inactivity = "inactivity"   # 비활성으로 인한 제거

class PaymentCycle(str, enum.Enum):
    """선택한 결제 방식"""
    entry_fee = "entry_fee"     # 일회성 참가비
    monthly = "monthly"         # 월 정기결제
    free = "free"               # 무료 참가

# ============= 개선된 Participation 모델 =============
class Participation(Base, TimestampMixin):
    __tablename__ = "participations"
    
    # ============= 기본 정보 (DB에 실제 존재하는 컬럼만) =============
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), primary_key=True)
    
    # 역할 & 상태
    role = Column(
        SAEnum(ParticipationRole, name="participation_role_enum"),
        default=ParticipationRole.participant,
        nullable=False,
        index=True
    )
    status = Column(
        SAEnum(ParticipationStatus, name="participation_status_enum"), 
        default=ParticipationStatus.pending,
        nullable=False,
        index=True
    )
    
    # 시간 정보
    joined_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        index=True,
        comment="참가 신청 시간"
    )

    # 활성 상태 (DB에 실제 존재)
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="참여 레코드 활성 여부"
    )
    
    # ============= 관계 =============
    user = relationship("User", back_populates="participations", foreign_keys=[user_id])
    challenge = relationship("Challenge", back_populates="participations")
    
    # ============= 제약 조건 =============
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_participation_user_challenge"),
        
        # 인덱스
        Index("ix_participation_user", "user_id"),
        Index("ix_participation_challenge", "challenge_id"),
        Index("ix_participation_status_role", "status", "role"),
        Index("ix_participation_joined_status", "joined_at", "status"),
    )
    
    # ============= 비즈니스 로직 메서드 (간소화) =============
    
    def is_active_participant(self) -> bool:
        """활성 참가자인지 확인"""
        return self.status == ParticipationStatus.active
    
    def is_manager_role(self) -> bool:
        """관리자 권한이 있는지 확인"""
        return self.role in [ParticipationRole.creator, ParticipationRole.manager]
    
    def get_status_display(self) -> str:
        """상태 표시용 텍스트"""
        status_map = {
            ParticipationStatus.pending: "참가 대기",
            ParticipationStatus.payment_pending: "결제 대기",
            ParticipationStatus.active: "참가 중",
            ParticipationStatus.paused: "일시 정지",
            ParticipationStatus.completed: "완료",
            ParticipationStatus.cancelled: "취소",
            ParticipationStatus.expelled: "퇴출",
            ParticipationStatus.payment_failed: "결제 실패"
        }
        return status_map.get(self.status, "알 수 없음")
    
    def __repr__(self) -> str:
        return (
            f"<Participation(user_id={self.user_id}, challenge_id={self.challenge_id}, "
            f"status={self.status}, role={self.role})>"
        )

# ============= 추가 헬퍼 함수들 =============
class ParticipationManager:
    """참가 관련 비즈니스 로직 관리"""
    
    @staticmethod
    def create_participation(
        user_id: int, 
        challenge_id: int, 
        role: ParticipationRole = ParticipationRole.participant
    ) -> 'Participation':
        """새 참가 생성"""
        participation = Participation(
            user_id=user_id,
            challenge_id=challenge_id,
            role=role,
            status=ParticipationStatus.active,  # 간소화: 바로 활성화
            is_active=True
        )
        
        return participation
