import enum
from datetime import date, datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Date, Boolean, ForeignKey, DateTime, 
    Enum as SAEnum, Float, CheckConstraint, Index
)
from sqlalchemy.orm import relationship, validates
from .base import Base, TimestampMixin

# ============= 핵심 Enum만 유지 =============
class ChallengeStatus(str, enum.Enum):
    """챌린지 상태"""
    draft = "draft"              # 임시저장
    recruiting = "recruiting"    # 모집 중
    active = "active"           # 진행 중
    completed = "completed"      # 완료
    cancelled = "cancelled"      # 취소됨
    closed = "closed"           # 정산 완료

class ChallengeMode(str, enum.Enum):
    """진행 방식"""
    online = "online"           # 온라인
    offline = "offline"         # 오프라인
    hybrid = "hybrid"           # 혼합

class PaymentType(str, enum.Enum):
    """결제 방식"""
    free = "free"               # 무료
    entry_fee = "entry_fee"     # 일회성 참가비
    monthly_fee = "monthly_fee"  # 월 정기결제
    both = "both"               # 참가비 + 월회비 선택 가능

# ============= 간소화된 Challenge 모델 =============
class Challenge(Base, TimestampMixin):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    # ============= 기본 정보 =============
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ============= 일정 =============
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    
    # ============= 상태 =============
    status = Column(
        SAEnum(ChallengeStatus, name="challenge_status_enum"),
        default=ChallengeStatus.draft,
        nullable=False,
        index=True
    )
    
    # ============= 참가자 관리 =============
    min_participants = Column(Integer, nullable=False, default=1)
    max_participants = Column(Integer, nullable=True)  # NULL = 무제한
    current_participants = Column(Integer, default=0, nullable=False)  # 성능용 캐시
    
    # ============= 결제 시스템 =============
    payment_type = Column(
        SAEnum(PaymentType, name="payment_type_enum"),
        default=PaymentType.free,
        nullable=False
    )
    entry_fee = Column(Integer, default=0, nullable=False, comment="원")
    monthly_fee = Column(Integer, default=0, nullable=False, comment="원")
    
    # ============= 진행 방식 =============
    mode = Column(
        SAEnum(ChallengeMode, name="challenge_mode_enum"),
        nullable=False,
        default=ChallengeMode.online
    )
    
    # 회차 시스템
    total_rounds = Column(Integer, nullable=True)
    min_participation_rate = Column(Integer, default=80, nullable=False, comment="%")
    
    # ============= 장소 정보 (간소화) =============
    # 온라인
    default_zoom_link = Column(Text, nullable=True)
    
    # 오프라인
    default_place_name = Column(String(200), nullable=True)
    default_address = Column(String(300), nullable=True)
    default_latitude = Column(Float, nullable=True)
    default_longitude = Column(Float, nullable=True)
    
    same_place_for_all_rounds = Column(Boolean, default=False, nullable=False)

    default_map_url = Column(String(512), nullable=True)

    # ============= 리워드 시스템 =============
    use_reward = Column(Boolean, default=False, nullable=False)
    reward_description = Column(Text, nullable=True)
    
    # ============= 커버 이미지 =============
    cover_image_url = Column(Text, nullable=True)
    
    # ============= 기본 설정 =============
    require_approval = Column(Boolean, default=False, comment="참가 승인 필요")
    is_public = Column(Boolean, default=True, nullable=False)
    
    # ============= 완료 & 정산 =============
    completed_at = Column(DateTime, nullable=True)
    is_settlement_completed = Column(Boolean, default=False)
    settlement_completed_at = Column(DateTime, nullable=True)
    
    # ============= 소프트 삭제 =============
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # ============= 관계 정의 (기존 유지) =============
    creator = relationship("User", back_populates="created_challenges", foreign_keys=[creator_id])
    deleter = relationship("User", foreign_keys=[deleted_by])
    
    participations = relationship("Participation", back_populates="challenge", cascade="all, delete-orphan")
    rounds = relationship("ChallengeRound", back_populates="challenge", cascade="all, delete-orphan")
    round_managers = relationship("RoundManager", back_populates="challenge", cascade="all, delete-orphan")
    
    payments = relationship("Payment", back_populates="challenge")
    refunds = relationship("Refund", back_populates="challenge")
    
    invitations = relationship("Invitation", back_populates="challenge", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="challenge", cascade="all, delete-orphan")
    
    # 태그 시스템 (카테고리 대신 사용)
    challenge_tags = relationship("ChallengeTag", back_populates="challenge", cascade="all, delete-orphan")
    
    chat_rooms = relationship("ChatRoom", back_populates="challenge")
    proofs = relationship("Proof", back_populates="challenge")
    reports = relationship("Report", back_populates="challenge")
    point_histories = relationship("PointHistory", back_populates="challenge")
    penalties = relationship("PenaltyHistory", back_populates="challenge")
    embeddings = relationship("ChallengeEmbedding", back_populates="challenge", cascade="all, delete-orphan")
    
    # ============= 제약 조건 =============
    __table_args__ = (
        # 체크 제약 조건
        CheckConstraint("min_participants > 0", name="ck_challenge_min_participants_positive"),
        CheckConstraint("max_participants IS NULL OR max_participants >= min_participants", name="ck_challenge_max_participants_valid"),
        CheckConstraint("end_date >= start_date", name="ck_challenge_date_range_valid"),
        CheckConstraint("entry_fee >= 0", name="ck_challenge_entry_fee_positive"),
        CheckConstraint("monthly_fee >= 0", name="ck_challenge_monthly_fee_positive"),
        CheckConstraint("min_participation_rate >= 0 AND min_participation_rate <= 100", name="ck_challenge_participation_rate_range"),
        CheckConstraint("current_participants >= 0", name="ck_challenge_current_participants_positive"),
        
        # 핵심 인덱스만 유지
        Index("ix_challenge_status_date", "status", "start_date"),
        Index("ix_challenge_creator_status", "creator_id", "status"),
        Index("ix_challenge_payment_type", "payment_type"),
        Index("ix_challenge_participants", "current_participants", "max_participants"),
        Index("ix_challenge_public", "is_public", "is_deleted"),
    )
    
    # ============= 검증 메서드 =============
    @validates('min_participation_rate')
    def validate_participation_rate(self, _, value):
        if value is not None:
            return max(0, min(100, int(value)))
        return value
    
    @validates('title')
    def validate_title(self, _, value):
        if value:
            return value.strip()[:200]
        return value
    
    # ============= 핵심 비즈니스 로직만 유지 =============
    
    def get_computed_status(self) -> ChallengeStatus:
        """현재 상태 자동 계산"""
        today = date.today()
        
        if self.is_deleted:
            return ChallengeStatus.cancelled
        
        if self.is_settlement_completed:
            return ChallengeStatus.closed
            
        if self.completed_at or (self.end_date and today > self.end_date):
            return ChallengeStatus.completed
        
        if today < self.start_date:
            return ChallengeStatus.recruiting
        
        if self.start_date <= today <= self.end_date:
            if self.current_participants >= self.min_participants:
                return ChallengeStatus.active
            else:
                return ChallengeStatus.recruiting
        
        return self.status
    
    def can_join(self, user_id: int) -> tuple[bool, str]:
        """참가 가능 여부 확인"""
        # 이미 참가했는지 확인
        if any(p.user_id == user_id and p.is_active_participant() for p in self.participations):
            return False, "이미 참가한 챌린지입니다."
        
        # 상태 확인
        computed_status = self.get_computed_status()
        if computed_status not in [ChallengeStatus.recruiting]:
            return False, "참가 접수가 마감되었습니다."
        
        # 최대 인원 확인
        if self.max_participants and self.current_participants >= self.max_participants:
            return False, "참가 인원이 마감되었습니다."
        
        return True, "참가 가능합니다."
    
    def is_payment_required(self) -> bool:
        """결제 필요 여부"""
        return self.payment_type != PaymentType.free
    
    def get_payment_amount(self, payment_cycle: str) -> int:
        """결제 금액 반환"""
        if payment_cycle == "entry_fee":
            return self.entry_fee
        elif payment_cycle == "monthly_fee":
            return self.monthly_fee
        return 0
    
    def increment_participants(self):
        """참가자 수 증가"""
        self.current_participants += 1
    
    def decrement_participants(self):
        """참가자 수 감소"""
        if self.current_participants > 0:
            self.current_participants -= 1
    
    def can_start(self) -> bool:
        """시작 가능 여부"""
        return (
            self.current_participants >= self.min_participants and
            date.today() >= self.start_date and
            self.status == ChallengeStatus.recruiting
        )
    
    def start_challenge(self):
        """챌린지 시작"""
        if self.can_start():
            self.status = ChallengeStatus.active
            return True
        return False
    
    def complete_challenge(self):
        """챌린지 완료"""
        if self.status == ChallengeStatus.active:
            self.status = ChallengeStatus.completed
            self.completed_at = datetime.now(timezone.utc)
            return True
        return False
    
    def soft_delete(self, deleted_by_id: int):
        """소프트 삭제"""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by_id
        self.status = ChallengeStatus.cancelled
    
    def get_duration_days(self) -> int:
        """챌린지 기간"""
        return (self.end_date - self.start_date).days + 1
    
    def get_remaining_days(self) -> int:
        """남은 일 수"""
        today = date.today()
        if today > self.end_date:
            return 0
        elif today < self.start_date:
            return (self.end_date - self.start_date).days + 1
        else:
            return (self.end_date - today).days + 1
    
    def get_progress_percentage(self) -> float:
        """진행률 (%)"""
        total_days = self.get_duration_days()
        if total_days <= 0:
            return 100.0
        
        today = date.today()
        if today < self.start_date:
            return 0.0
        elif today > self.end_date:
            return 100.0
        else:
            passed_days = (today - self.start_date).days + 1
            return (passed_days / total_days) * 100.0
    
    def __repr__(self) -> str:
        return f"<Challenge(id={self.id}, title='{self.title}', status={self.status})>"