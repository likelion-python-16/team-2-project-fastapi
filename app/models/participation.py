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
    moderator = "moderator"  # 부관리자 (신규)

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
    
    # ============= 기본 정보 =============
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
    
    # ============= 시간 정보 =============
    joined_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        index=True,
        comment="참가 신청 시간"
    )
    activated_at = Column(
        DateTime, 
        nullable=True,
        comment="실제 참가 시작 시간 (결제 완료 후)"
    )
    completed_at = Column(DateTime, nullable=True, comment="완료 시간")
    left_at = Column(DateTime, nullable=True, comment="탈퇴 시간")
    
    # ============= 결제 관련 정보 =============
    payment_cycle = Column(
        SAEnum(PaymentCycle, name="payment_cycle_enum"),
        nullable=True,
        comment="선택한 결제 방식 (챌린지가 multiple 옵션일 때)"
    )
    next_payment_date = Column(
        Date, 
        nullable=True,
        index=True,
        comment="다음 결제 예정일 (월회비용)"
    )
    payment_failed_count = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="연속 결제 실패 횟수"
    )
    total_paid_amount = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="총 결제 금액"
    )
    
    # ============= 진행률 & 통계 =============
    progress_rate = Column(
        Float, 
        default=0.0, 
        nullable=False,
        comment="진행률 (0-100%)"
    )
    attendance_count = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="총 출석 횟수"
    )
    total_rounds = Column(
        Integer, 
        nullable=True,
        comment="참가한 시점의 총 회차 수 (변경 추적용)"
    )
    
    # ============= 탈퇴 관련 =============
    leave_type = Column(
        SAEnum(LeaveType, name="leave_type_enum"),
        nullable=True,
        comment="탈퇴 사유"
    )
    leave_reason = Column(Text, nullable=True, comment="상세 탈퇴 사유")
    kicked_by = Column(
        Integer, 
        ForeignKey("users.id"), 
        nullable=True,
        comment="퇴출 처리한 관리자 ID"
    )
    
    # ============= 기타 설정 =============
    is_notification_enabled = Column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="알림 수신 여부"
    )
    auto_payment_enabled = Column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="자동 결제 활성화 여부"
    )
    
    # 참가 시점 메모/동기
    join_motivation = Column(Text, nullable=True, comment="참가 동기/목표")
    
    # ============= 관계 =============
    user = relationship("User", back_populates="participations", foreign_keys=[user_id])
    challenge = relationship("Challenge", back_populates="participations")
    kicker = relationship("User", foreign_keys=[kicked_by])
    
    # 결제 관련
    payments = relationship(
        "Payment", 
        primaryjoin="and_(Payment.user_id==Participation.user_id, "
                   "Payment.challenge_id==Participation.challenge_id)",
        overlaps="user,challenge,payments"
    )
    
    # ============= 제약 조건 =============
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_participation_user_challenge"),
        
        # 인덱스
        Index("ix_participation_user", "user_id"),
        Index("ix_participation_challenge", "challenge_id"),
        Index("ix_participation_status_role", "status", "role"),
        Index("ix_participation_joined_status", "joined_at", "status"),
        Index("ix_participation_next_payment", "next_payment_date"),
        Index("ix_participation_progress", "progress_rate"),
        
        # 체크 제약 조건
        CheckConstraint(
            "progress_rate >= 0 AND progress_rate <= 100", 
            name="ck_participation_progress_range"
        ),
        CheckConstraint(
            "attendance_count >= 0", 
            name="ck_participation_attendance_positive"
        ),
        CheckConstraint(
            "payment_failed_count >= 0", 
            name="ck_participation_payment_failed_positive"
        ),
        CheckConstraint(
            "total_paid_amount >= 0",
            name="ck_participation_total_paid_positive"
        )
    )
    
    # ============= 비즈니스 로직 메서드 =============
    
    @validates('progress_rate')
    def validate_progress_rate(self, key, value):
        """진행률 검증"""
        if value is not None:
            return max(0.0, min(100.0, float(value)))
        return value
    
    def is_active_participant(self) -> bool:
        """활성 참가자인지 확인"""
        return self.status == ParticipationStatus.active
    
    def can_make_payment(self) -> bool:
        """결제 가능 상태인지 확인"""
        return (
            self.status in [ParticipationStatus.active, ParticipationStatus.payment_pending] 
            and self.auto_payment_enabled 
            and self.payment_failed_count < 3
        )
    
    def is_manager_role(self) -> bool:
        """관리자 권한이 있는지 확인"""
        return self.role in [ParticipationRole.creator, ParticipationRole.manager, ParticipationRole.moderator]
    
    def calculate_participation_rate(self) -> float:
        """참여율 계산"""
        if not self.total_rounds or self.total_rounds == 0:
            return 0.0
        return (self.attendance_count / self.total_rounds) * 100
    
    def update_progress(self, new_attendance_count: int):
        """진행률 업데이트"""
        self.attendance_count = max(0, new_attendance_count)
        if self.total_rounds:
            self.progress_rate = self.calculate_participation_rate()
    
    def activate_participation(self):
        """참가 활성화 (결제 완료 후 호출)"""
        if self.status == ParticipationStatus.payment_pending:
            self.status = ParticipationStatus.active
            self.activated_at = datetime.now(timezone.utc)
            self.payment_failed_count = 0
    
    def pause_participation(self, reason: str = None):
        """참가 일시 정지"""
        if self.status == ParticipationStatus.active:
            self.status = ParticipationStatus.paused
            if reason:
                self.leave_reason = reason
    
    def resume_participation(self):
        """참가 재개"""
        if self.status == ParticipationStatus.paused:
            self.status = ParticipationStatus.active
    
    def complete_participation(self):
        """챌린지 완료 처리"""
        if self.status == ParticipationStatus.active:
            self.status = ParticipationStatus.completed
            self.completed_at = datetime.now(timezone.utc)
            self.progress_rate = 100.0
    
    def cancel_participation(self, leave_type: LeaveType, reason: str = None, kicked_by_id: int = None):
        """참가 취소/퇴출 처리"""
        if leave_type == LeaveType.kicked:
            self.status = ParticipationStatus.expelled
            self.kicked_by = kicked_by_id
        else:
            self.status = ParticipationStatus.cancelled
        
        self.leave_type = leave_type
        self.leave_reason = reason
        self.left_at = datetime.now(timezone.utc)
        self.auto_payment_enabled = False
    
    def handle_payment_failure(self):
        """결제 실패 처리"""
        self.payment_failed_count += 1
        
        if self.payment_failed_count >= 3:
            self.status = ParticipationStatus.payment_failed
            self.auto_payment_enabled = False
            self.cancel_participation(
                LeaveType.payment_failure, 
                f"연속 {self.payment_failed_count}회 결제 실패"
            )
    
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
        role: ParticipationRole = ParticipationRole.participant,
        payment_cycle: PaymentCycle = None,
        join_motivation: str = None
    ) -> 'Participation':
        """새 참가 생성"""
        participation = Participation(
            user_id=user_id,
            challenge_id=challenge_id,
            role=role,
            payment_cycle=payment_cycle,
            join_motivation=join_motivation,
            status=ParticipationStatus.pending if payment_cycle != PaymentCycle.free else ParticipationStatus.active
        )
        
        # 무료 참가인 경우 즉시 활성화
        if payment_cycle == PaymentCycle.free:
            participation.activate_participation()
        
        return participation
    
    @staticmethod
    def get_active_participants(challenge_id: int) -> int:
        """활성 참가자 수 조회"""
        from sqlalchemy.orm import object_session
        # 실제 사용 시에는 session을 파라미터로 받아야 함
        pass
    
    @staticmethod
    def check_payment_due_participants(target_date: date = None) -> list:
        """결제 예정 참가자 조회"""
        if not target_date:
            target_date = date.today()
        # 실제 구현 시 session 쿼리 로직
        pass