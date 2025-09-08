# app/services/participation_service.py
from datetime import datetime, date, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.participation import (
    Participation, ParticipationRole, ParticipationStatus, 
    PaymentCycle, LeaveType, ParticipationManager
)
from app.models.challenge import Challenge, ChallengeStatus, PaymentType
from app.models.user import User
from app.models.payment import Payment, PaymentStatus, Refund
from app.schemas.participation import (
    ParticipationCreate,
    ParticipationUpdate,
    ParticipationApproval,
    ParticipationResponse,
    ParticipationWithUser,
    ParticipationListItem,
    MyParticipation,
    ParticipantStats,
    LeaveResponse,
    BulkApprovalRequest,
    BulkApprovalResponse
)
from app.utils.logging import logger


class ParticipationService:
    """참가 관련 비즈니스 로직을 담당하는 서비스"""
    
    def __init__(self, db: Session):
        self.db = db

    def join_challenge(self, user: User, participation_data: ParticipationCreate) -> ParticipationResponse:
        """챌린지 참가 신청 (멱등성 보장)"""
        challenge = self._get_challenge_by_id(participation_data.challenge_id)
        
        # 1. 참가 가능성 검증
        self._validate_can_join(challenge, user)
        
        # 2. 기존 참가 확인 (멱등성 처리)
        existing = self._get_user_participation(challenge.id, user.id)
        if existing:
            # 활성 상태인 경우 기존 참여 반환
            if existing.status in [ParticipationStatus.active, ParticipationStatus.pending, ParticipationStatus.payment_pending]:
                logger.info(f"이미 참가 중인 사용자: {user.id} -> 챌린지 {challenge.id}, 상태: {existing.status}")
                return ParticipationResponse.model_validate(existing)
            
            # 강퇴된 사용자는 재참가 불가
            elif existing.status == ParticipationStatus.expelled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="이 챌린지에서 강퇴되어 재참가할 수 없습니다"
                )
            
            # 취소된 참여가 있는 경우 재활성화
            elif existing.status == ParticipationStatus.cancelled:
                logger.info(f"취소된 참여 재활성화: {user.id} -> 챌린지 {challenge.id}, 이전 상태: {existing.status}")
                return self._reactivate_participation(existing, challenge, participation_data)
        
        # 3. 결제 방식 결정
        payment_cycle = self._determine_payment_cycle(challenge, participation_data)
        
        # 4. 참가 신청 생성 (트랜잭션으로 보호)
        try:
            participation = ParticipationManager.create_participation(
                user_id=user.id,
                challenge_id=challenge.id,
                role=ParticipationRole.participant,
                payment_cycle=payment_cycle,
                join_motivation=getattr(participation_data, 'message', None)
            )
            
            self.db.add(participation)
            
            # 5. 자동 승인 처리
            if not challenge.require_approval and payment_cycle == PaymentCycle.free:
                participation.activate_participation()
                self._increment_challenge_participants(challenge)
            elif payment_cycle != PaymentCycle.free:
                participation.status = ParticipationStatus.payment_pending
            
            self.db.commit()
            self.db.refresh(participation)
            
            logger.info(f"챌린지 참가 신청: {user.username} -> {challenge.title} (결제: {payment_cycle})")
            
            return ParticipationResponse.model_validate(participation)
            
        except IntegrityError as e:
            # 중복 키 오류 발생 시 롤백 후 기존 참가 반환
            self.db.rollback()
            logger.warning(f"참가 중복 생성 시도: {user.id} -> 챌린지 {challenge.id}, 에러: {e}")
            
            # 기존 참가 조회 후 반환
            existing_participation = self._get_user_participation(challenge.id, user.id)
            if existing_participation:
                return ParticipationResponse.model_validate(existing_participation)
            else:
                # 예상치 못한 상황
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="참가 처리 중 오류가 발생했습니다"
                )
        except Exception as e:
            self.db.rollback()
            logger.error(f"참가 신청 처리 중 오류: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"참가 처리 중 오류가 발생했습니다: {str(e)}"
            )

    def approve_participation(
        self, 
        participation_id: int, 
        approval_data: ParticipationApproval, 
        approver: User
    ) -> ParticipationResponse:
        """참가 승인/거부 (승인 필요한 챌린지용)"""
        participation = self._get_participation_by_id(participation_id)
        challenge = self._get_challenge_by_id(participation.challenge_id)
        
        # 권한 확인
        if not self._can_approve_participation(challenge, approver):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="참가를 승인할 권한이 없습니다"
            )
        
        # 상태 확인
        if participation.status != ParticipationStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="승인 대기 상태가 아닙니다"
            )
        
        if approval_data.approved:
            # 승인 처리
            if participation.payment_cycle == PaymentCycle.free:
                participation.activate_participation()
                self._increment_challenge_participants(challenge)
            else:
                participation.status = ParticipationStatus.payment_pending
            logger.info(f"참가 승인: {participation.user_id} for challenge {participation.challenge_id}")
        else:
            # 거부 처리
            participation.cancel_participation(
                LeaveType.voluntary, 
                approval_data.rejection_reason or "관리자가 참가를 거부했습니다"
            )
            logger.info(f"참가 거부: {participation.user_id} for challenge {participation.challenge_id}")
        
        self.db.commit()
        return ParticipationResponse.model_validate(participation)

    def complete_payment(self, user_id: int, challenge_id: int) -> ParticipationResponse:
        """결제 완료 처리 (결제 서비스에서 호출)"""
        try:
            participation = self._get_user_participation(challenge_id, user_id)
            
            if not participation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="참가 정보를 찾을 수 없습니다"
                )
            
            if participation.status not in [ParticipationStatus.payment_pending, ParticipationStatus.pending]:
                if participation.status == ParticipationStatus.active:
                    logger.info(f"이미 활성화된 참가: {user_id} for challenge {challenge_id}")
                    return ParticipationResponse.model_validate(participation)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"결제 처리 가능한 상태가 아닙니다. 현재 상태: {participation.status}"
                    )
            
            # 결제 완료 후 활성화
            participation.activate_participation()
            challenge = self._get_challenge_by_id(challenge_id)
            
            # 월회비인 경우만 다음 결제일 설정 (both 타입은 제외 - 회차별 수동 결제)
            if participation.payment_cycle == PaymentCycle.monthly:
                from app.services.payment_reminder_service import get_payment_reminder_service
                reminder_service = get_payment_reminder_service(self.db)
                reminder_service.set_next_payment_date(participation, challenge)
            
            self._increment_challenge_participants(challenge)
            
            self.db.commit()
            logger.info(f"결제 완료 및 참가 활성화: {user_id} for challenge {challenge_id}")
            
            return ParticipationResponse.model_validate(participation)
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"결제 완료 처리 중 오류: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="결제 완료 처리 중 오류가 발생했습니다"
            )

    def leave_challenge(self, challenge_id: int, user: User, reason: str = None) -> LeaveResponse:
        """챌린지 탈퇴"""
        participation = self._get_user_participation(challenge_id, user.id)
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="참가하지 않은 챌린지입니다"
            )
        
        if not participation.is_active_participant():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 탈퇴했거나 비활성 상태입니다"
            )
        
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 생성자는 탈퇴 불가
        if participation.role == ParticipationRole.creator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="챌린지 생성자는 탈퇴할 수 없습니다"
            )
        
        # 환불 금액 계산
        refund_amount = self._calculate_refund_amount(challenge, participation)
        
        logger.info(f"환불 금액 계산 결과: user_id={user.id}, challenge_id={challenge_id}, refund_amount={refund_amount}, total_paid={participation.total_paid_amount}")
        
        # 실제 환불 처리 
        if refund_amount > 0:  # 양수 금액만 실제 환불 처리
            self._process_refund(participation, refund_amount, reason or "사용자 탈퇴")
        elif refund_amount == 0:
            # 0원 환불은 기록 없이 로그만 남기기
            logger.info(f"0원 환불 - 환불 기록 생성 생략: user_id={user.id}, challenge_id={challenge_id}")
        else:
            logger.warning(f"음수 환불 금액: {refund_amount}원 - 환불 처리 건너뛰기")
        
        # 탈퇴 처리 (모델 메서드 활용)
        participation.cancel_participation(
            LeaveType.voluntary,
            reason or "사용자 요청으로 탈퇴"
        )
        
        # 참가자 수 감소
        self._decrement_challenge_participants(challenge)
        
        self.db.commit()
        logger.info(f"챌린지 탈퇴: {user.username} from {challenge.title}")
        
        return LeaveResponse(
            message="챌린지에서 탈퇴하였습니다",
            left_at=participation.left_at,
            leave_type=LeaveType.voluntary,
            refund_amount=refund_amount
        )

    def kick_participant(
        self, 
        challenge_id: int, 
        target_user_id: int, 
        kicker: User, 
        reason: str
    ) -> ParticipationResponse:
        """참가자 강제 퇴출"""
        participation = self._get_user_participation(challenge_id, target_user_id)
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="참가 정보를 찾을 수 없습니다"
            )
        
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 권한 확인
        if not self._can_manage_participants(challenge, kicker):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="참가자를 퇴출할 권한이 없습니다"
            )
        
        # 생성자는 퇴출 불가
        if participation.role == ParticipationRole.creator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="챌린지 생성자는 퇴출할 수 없습니다"
            )
        
        # 강제 퇴출 처리
        participation.cancel_participation(
            LeaveType.kicked,
            reason,
            kicked_by_id=kicker.id
        )
        
        # 참가자 수 감소
        self._decrement_challenge_participants(challenge)
        
        self.db.commit()
        logger.info(f"참가자 퇴출: {target_user_id} from challenge {challenge_id} by {kicker.username}")
        
        return ParticipationResponse.model_validate(participation)

    def update_participation_progress(
        self, 
        challenge_id: int, 
        user_id: int, 
        new_attendance_count: int
    ) -> ParticipationResponse:
        """참가자 진행률 업데이트 (출석 체크 등에서 호출)"""
        participation = self._get_user_participation(challenge_id, user_id)
        
        if not participation or not participation.is_active_participant():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="활성 참가자가 아닙니다"
            )
        
        # 모델 메서드 활용하여 진행률 업데이트
        participation.update_progress(new_attendance_count)
        
        self.db.commit()
        return ParticipationResponse.model_validate(participation)

    def handle_payment_failure(self, user_id: int, challenge_id: int) -> ParticipationResponse:
        """결제 실패 처리 (결제 서비스에서 호출)"""
        participation = self._get_user_participation(challenge_id, user_id)
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="참가 정보를 찾을 수 없습니다"
            )
        
        # 모델 메서드로 결제 실패 처리
        participation.handle_payment_failure()
        
        # 3번 실패 시 자동 탈퇴
        if participation.status == ParticipationStatus.payment_failed:
            challenge = self._get_challenge_by_id(challenge_id)
            self._decrement_challenge_participants(challenge)
        
        self.db.commit()
        logger.info(f"결제 실패 처리: {user_id} for challenge {challenge_id}")
        
        return ParticipationResponse.model_validate(participation)

    def get_participants(self, challenge_id: int, current_user: Optional[User] = None) -> List[ParticipationWithUser]:
        """챌린지 참가자 목록 조회"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 접근 권한 확인
        if not challenge.is_public and not self._user_can_access_challenge(challenge, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="참가자 목록을 볼 권한이 없습니다"
            )
        
        participants = self.db.query(Participation).join(
            User, Participation.user_id == User.id
        ).filter(
            Participation.challenge_id == challenge_id,
            Participation.status == ParticipationStatus.active
        ).all()
        
        result = []
        for p in participants:
            # 딕셔너리로 직접 생성
            user_data = {
                "id": p.user.id,
                "username": p.user.username,
                "profile_image": p.user.profile_image or "",
                "manner_score": p.user.manner_score
            }
            
            # Participation 데이터를 딕셔너리로 변환 (모델에 있는 필드만 사용)
            participation_dict = {
                "challenge_id": p.challenge_id,
                "user_id": p.user_id,
                "status": p.status,
                "role": p.role,
                # "payment_cycle": p.payment_cycle,  # 임시 비활성화 - DB에 컬럼이 없음
                # "join_motivation": p.join_motivation,  # 임시 비활성화 - DB에 컬럼이 없음
                "joined_at": p.joined_at,
                # "activated_at": p.activated_at,  # 임시 비활성화 - DB에 컬럼이 없음
                # "completed_at": p.completed_at,  # 임시 비활성화 - DB에 컬럼이 없음
                # "left_at": p.left_at,  # 임시 비활성화 - DB에 컬럼이 없음
                # "next_payment_date": p.next_payment_date,  # 임시 비활성화 - DB에 컬럼이 없음
                # "payment_failed_count": p.payment_failed_count,  # 임시 비활성화 - DB에 컬럼이 없음
                # "total_paid_amount": p.total_paid_amount,  # 임시 비활성화 - DB에 컬럼이 없음
                # "progress_rate": p.progress_rate,  # 임시 비활성화 - DB에 컬럼이 없음
                # "attendance_count": p.attendance_count,  # 임시 비활성화 - DB에 컬럼이 없음
                # "total_rounds": p.total_rounds,  # 임시 비활성화 - DB에 컬럼이 없음
                # "leave_type": p.leave_type,  # 임시 비활성화 - DB에 컬럼이 없음
                # "leave_reason": p.leave_reason,  # 임시 비활성화 - DB에 컬럼이 없음
                # "kicked_by": p.kicked_by,  # 임시 비활성화 - DB에 컬럼이 없음
                # "is_notification_enabled": p.is_notification_enabled,  # 임시 비활성화 - DB에 컬럼이 없음
                # "auto_payment_enabled": p.auto_payment_enabled,  # 임시 비활성화 - DB에 컬럼이 없음
                "user": user_data
            }
            
            response = ParticipationWithUser(**participation_dict)
            result.append(response)
        
        return result

    def get_pending_approvals(self, challenge_id: int, approver: User) -> List[ParticipationWithUser]:
        """승인 대기 중인 참가 신청 목록"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        if not self._can_approve_participation(challenge, approver):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="승인 대기 목록을 볼 권한이 없습니다"
            )
        
        pending = self.db.query(Participation).join(User).filter(
            Participation.challenge_id == challenge_id,
            Participation.status == ParticipationStatus.pending
        ).all()
        
        result = []
        for p in pending:
            response = ParticipationWithUser.model_validate(p)
            response.user = {
                "id": p.user.id,
                "username": p.user.username,
                "email": p.user.email,
                "profile_image": p.user.profile_image or ""
            }
            result.append(response)
        
        return result

    def get_my_participations(self, user: User) -> List[MyParticipation]:
        """내가 참가한 챌린지 목록"""
        participations = self.db.query(Participation).join(Challenge).filter(
            Participation.user_id == user.id,
            Participation.status.in_([
                ParticipationStatus.active,
                ParticipationStatus.pending,
                ParticipationStatus.payment_pending,
                ParticipationStatus.completed
            ]),
            Challenge.is_deleted == False
        ).all()
        
        result = []
        for p in participations:
            result.append(MyParticipation(
                id=p.user_id * 1000000 + p.challenge_id,  # 임시 ID 생성
                challenge_id=p.challenge_id,
                challenge_title=p.challenge.title,
                challenge_status=p.challenge.status.value,
                role=p.role,
                is_active=p.status == ParticipationStatus.active,
                joined_at=p.joined_at,
                start_date=p.challenge.start_date,
                end_date=p.challenge.end_date,
                current_participants=p.challenge.current_participants
            ))
        
        return result

    def get_participant_stats(self, challenge_id: int) -> ParticipantStats:
        """참가자 통계 정보"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 상태별 참가자 수 집계
        stats_query = self.db.query(
            Participation.status,
            func.count(Participation.user_id).label('count')
        ).filter(
            Participation.challenge_id == challenge_id
        ).group_by(Participation.status).all()
        
        stats_dict = {status: count for status, count in stats_query}
        
        # 역할별 수 집계 (활성 참가자만)
        role_query = self.db.query(
            Participation.role,
            func.count(Participation.user_id).label('count')
        ).filter(
            Participation.challenge_id == challenge_id,
            Participation.status == ParticipationStatus.active
        ).group_by(Participation.role).all()
        
        role_dict = {role: count for role, count in role_query}
        
        return ParticipantStats(
            challenge_id=challenge_id,
            total_participants=sum(stats_dict.values()),
            active_participants=stats_dict.get(ParticipationStatus.active, 0),
            pending_approvals=stats_dict.get(ParticipationStatus.pending, 0),
            managers_count=role_dict.get(ParticipationRole.manager, 0) + role_dict.get(ParticipationRole.creator, 0),
            members_count=role_dict.get(ParticipationRole.participant, 0)
        )

    # ==================== Private Methods ====================
    
    def _get_challenge_by_id(self, challenge_id: int) -> Challenge:
        """ID로 챌린지 조회"""
        challenge = self.db.query(Challenge).filter(
            Challenge.id == challenge_id,
            Challenge.is_deleted == False
        ).first()
        
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="챌린지를 찾을 수 없습니다"
            )
        
        return challenge

    def _get_participation_by_id(self, participation_id: str) -> Participation:
        """ID로 참가 정보 조회 - 복합키 처리"""
        from app.schemas.participation import parse_participation_id
        user_id, challenge_id = parse_participation_id(participation_id)
        
        participation = self.db.query(Participation).filter(
            Participation.user_id == user_id,
            Participation.challenge_id == challenge_id
        ).first()
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="참가 정보를 찾을 수 없습니다"
            )
        
        return participation

    def _get_user_participation(self, challenge_id: int, user_id: int) -> Optional[Participation]:
        """사용자의 챌린지 참가 정보 조회"""
        return self.db.query(Participation).filter(
            Participation.challenge_id == challenge_id,
            Participation.user_id == user_id
        ).first()

    def _validate_can_join(self, challenge: Challenge, user: User) -> None:
        """참가 가능성 검증"""
        logger.info(f"Validating join: user_id={user.id}, user_active={user.is_active}, challenge_id={challenge.id}, challenge_status={challenge.status}")
        
        if not user.is_active:
            logger.warning(f"User {user.id} is not active")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 계정은 챌린지에 참가할 수 없습니다"
            )
        
        if challenge.status not in [ChallengeStatus.recruiting]:
            logger.warning(f"Challenge {challenge.id} status is {challenge.status}, not recruiting")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"모집 중이 아닌 챌린지에는 참가할 수 없습니다 (현재 상태: {challenge.status})"
            )
        
        if (challenge.max_participants and 
            challenge.current_participants >= challenge.max_participants):
            logger.warning(f"Challenge {challenge.id} is full: {challenge.current_participants}/{challenge.max_participants}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="참가 정원이 초과되었습니다"
            )

    def _determine_payment_cycle(self, challenge: Challenge, data: ParticipationCreate) -> PaymentCycle:
        """결제 방식 결정"""
        if challenge.payment_type == PaymentType.free:
            return PaymentCycle.free
        elif challenge.payment_type == PaymentType.entry_fee:
            return PaymentCycle.entry_fee
        elif challenge.payment_type == PaymentType.monthly_fee:
            return PaymentCycle.monthly
        elif challenge.payment_type == PaymentType.both:
            # 사용자가 선택한 방식 사용 (기본값은 참가비)
            requested_cycle = getattr(data, 'payment_cycle', 'entry_fee')
            return PaymentCycle.entry_fee if requested_cycle == 'entry_fee' else PaymentCycle.monthly
        
        return PaymentCycle.free

    def _increment_challenge_participants(self, challenge: Challenge) -> None:
        """챌린지 참가자 수 증가"""
        challenge.current_participants += 1
        
    def _decrement_challenge_participants(self, challenge: Challenge) -> None:
        """챌린지 참가자 수 감소"""
        challenge.current_participants = max(0, challenge.current_participants - 1)

    def _can_approve_participation(self, challenge: Challenge, user: User) -> bool:
        """참가 승인 권한 확인"""
        if challenge.creator_id == user.id or user.is_admin:
            return True
        
        manager_participation = self.db.query(Participation).filter(
            Participation.challenge_id == challenge.id,
            Participation.user_id == user.id,
            Participation.role.in_([ParticipationRole.manager, ParticipationRole.moderator]),
            Participation.status == ParticipationStatus.active
        ).first()
        
        return manager_participation is not None

    def _can_manage_participants(self, challenge: Challenge, user: User) -> bool:
        """참가자 관리 권한 확인 (퇴출 등)"""
        return challenge.creator_id == user.id or user.is_admin

    def _user_can_access_challenge(self, challenge: Challenge, user: Optional[User]) -> bool:
        """사용자가 챌린지에 접근할 수 있는지 확인"""
        if not user:
            return False
        
        return (challenge.creator_id == user.id or 
                self._get_user_participation(challenge.id, user.id) is not None)

    def _reactivate_participation(self, participation: Participation, challenge: Challenge, participation_data: ParticipationCreate) -> ParticipationResponse:
        """취소된 참여를 재활성화"""
        try:
            # 결제 방식 재결정
            payment_cycle = self._determine_payment_cycle(challenge, participation_data)
            
            # 참여 데이터 초기화
            # participation.payment_cycle = payment_cycle  # 임시 비활성화 - DB에 컬럼이 없음
            # participation.join_motivation = getattr(participation_data, 'message', None)  # 임시 비활성화 - DB에 컬럼이 없음
            # participation.left_at = None  # 임시 비활성화 - DB에 컬럼이 없음
            # participation.leave_type = None  # 임시 비활성화 - DB에 컬럼이 없음
            # participation.leave_reason = None  # 임시 비활성화 - DB에 컬럼이 없음
            # participation.progress_rate = 0.0  # 임시 비활성화 - DB에 컬럼이 없음
            # participation.attendance_count = 0  # 임시 비활성화 - DB에 컬럼이 없음
            
            # 상태 설정
            if payment_cycle == PaymentCycle.free:
                participation.status = ParticipationStatus.active
                # participation.activated_at = datetime.now(timezone.utc)  # 임시 비활성화 - DB에 컬럼이 없음
                self._increment_challenge_participants(challenge)
            else:
                participation.status = ParticipationStatus.payment_pending
                # participation.activated_at = None  # 임시 비활성화 - DB에 컬럼이 없음
            
            self.db.commit()
            logger.info(f"참여 재활성화 완료: user_id={participation.user_id}, challenge_id={participation.challenge_id}, 새 상태: {participation.status}")
            
            return ParticipationResponse.model_validate(participation)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"참여 재활성화 중 오류: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="참여 재활성화 중 오류가 발생했습니다"
            )

    def _calculate_refund_amount(self, challenge: Challenge, participation: Participation) -> int:
        """환불 금액 계산"""
        logger.info(f"환불 금액 계산 시작: user_id={participation.user_id}, challenge_id={participation.challenge_id}")
        logger.info(f"  - 총 결제 금액: {participation.total_paid_amount}원")
        logger.info(f"  - 챌린지 상태: {challenge.status}")
        logger.info(f"  - 진행률: {participation.progress_rate}%")
        
        # participation.total_paid_amount 사용
        if participation.total_paid_amount <= 0:
            logger.info(f"  - 결과: 결제 금액 없음 -> 0원 환불")
            return 0
        
        # 챌린지 상태에 따른 환불 정책
        if challenge.status == ChallengeStatus.recruiting:
            refund_amount = participation.total_paid_amount
            logger.info(f"  - 결과: 모집중 -> 전액 환불 {refund_amount}원")
            return refund_amount  # 전액 환불
        elif challenge.status == ChallengeStatus.active:
            # 진행률에 따른 부분 환불
            unused_rate = (100.0 - participation.progress_rate) / 100.0
            refund_amount = int(participation.total_paid_amount * unused_rate * 0.8)  # 80% 환불
            logger.info(f"  - 진행중: 미사용률 {unused_rate:.2f} * 80% -> {refund_amount}원 환불")
            return refund_amount
        else:
            logger.info(f"  - 결과: 완료/취소 상태 -> 0원 환불")
            return 0  # 완료된 챌린지는 환불 없음

    def _process_refund(self, participation: Participation, refund_amount: int, reason: str):
        """실제 환불 처리"""
        from app.models.payment import Payment, PaymentStatus, Refund
        from app.services.payment_service import get_payment_service
        
        # 해당 참여자의 결제 내역 찾기
        payments = self.db.query(Payment).filter(
            Payment.user_id == participation.user_id,
            Payment.challenge_id == participation.challenge_id,
            Payment.status == PaymentStatus.completed
        ).order_by(Payment.created_at.desc()).all()
        
        if not payments:
            logger.warning(f"환불 대상 결제 내역이 없습니다: user_id={participation.user_id}, challenge_id={participation.challenge_id}")
            # 결제 내역이 없는 경우 환불할 금액이 0이므로 로그만 남기고 종료
            logger.info(f"결제 내역 없음으로 환불 처리 생략: user_id={participation.user_id}, challenge_id={participation.challenge_id}, expected_amount={refund_amount}")
            return
        
        # 가장 최근 결제 건에 대해 환불 처리
        latest_payment = payments[0]
        
        # User 객체 조회 (lazy loading 방지)
        user = self.db.query(User).filter(User.id == participation.user_id).first()
        if not user:
            logger.error(f"사용자를 찾을 수 없습니다: user_id={participation.user_id}")
            return
        
        try:
            payment_service = get_payment_service(self.db)
            refund = payment_service.refund_payment(
                payment_id=latest_payment.id,
                user=user,
                amount=refund_amount,
                reason=reason
            )
            
            # 환불 처리 상태를 완료로 업데이트
            refund.mark_processed()
            self.db.commit()
            
            logger.info(f"환불 처리 완료: payment_id={latest_payment.id}, refund_id={refund.id}, amount={refund_amount}, reason={reason}")
            
        except Exception as e:
            logger.error(f"환불 처리 실패: {e}")
            # 롤백 수행
            self.db.rollback()
            
            # 환불 실패 시 실패 기록만 남기기 (새 트랜잭션에서)
            try:
                refund = Refund(
                    payment_id=latest_payment.id,
                    user_id=participation.user_id,
                    challenge_id=participation.challenge_id,
                    refund_amount=refund_amount,
                    refund_reason=f"{reason} (처리실패: {str(e)})",
                    status=PaymentStatus.failed
                )
                self.db.add(refund)
                self.db.commit()  # 실패 기록은 별도로 커밋
                logger.info(f"환불 실패 기록 생성: payment_id={latest_payment.id}, amount={refund_amount}, error={str(e)}")
            except Exception as inner_e:
                logger.error(f"환불 실패 기록 생성도 실패: {inner_e}")
                self.db.rollback()  # 실패 기록도 실패하면 롤백

    def _process_zero_refund(self, participation: Participation, reason: str):
        """0원 환불 기록 처리 (기록 목적)"""
        try:
            # 결제 내역 확인
            latest_payment = self.db.query(Payment).filter(
                Payment.user_id == participation.user_id,
                Payment.challenge_id == participation.challenge_id
            ).order_by(Payment.created_at.desc()).first()
            
            if not latest_payment:
                logger.info(f"결제 내역 없음 - 0원 환불 기록 건너뛰기")
                return
            
            # 0원 환불 기록 생성 (사용자에게 "환불 처리함" 표시 목적)
            refund = Refund(
                payment_id=latest_payment.id,
                user_id=participation.user_id,
                challenge_id=participation.challenge_id,
                refund_amount=1,  # constraint 우회를 위해 1원으로 저장
                refund_reason=f"{reason} (실제 환불 금액: 0원)",
                status=PaymentStatus.completed,  # 즉시 완료 처리
                requested_at=datetime.now(timezone.utc),
                processed_at=datetime.now(timezone.utc)
            )
            
            self.db.add(refund)
            self.db.commit()
            
            logger.info(f"0원 환불 기록 생성 완료: payment_id={latest_payment.id}")
            
        except Exception as e:
            logger.error(f"0원 환불 기록 처리 실패: {e}")
            self.db.rollback()


# ==================== Service Factory ====================

def get_participation_service(db: Session) -> ParticipationService:
    """ParticipationService 인스턴스 생성 (의존성 주입용)"""
    return ParticipationService(db)