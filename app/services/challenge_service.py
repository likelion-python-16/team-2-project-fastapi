# app/services/challenge_service.py
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status

from app.models.challenge import Challenge, ChallengeStatus, ChallengeMode, PaymentType
from app.models.user import User
from app.models.participation import Participation, ParticipationRole
from app.models.tag import Tag, ChallengeTag
from app.schemas.challenge import (
    ChallengeCreate, 
    ChallengeUpdate, 
    ChallengeResponse,
    ChallengeListItem,
    ChallengeStatistics,
    PaymentInfoResponse
)
from app.utils.logging import logger


class ChallengeService:
    """챌린지 관련 비즈니스 로직을 담당하는 서비스"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_challenge(self, creator: User, challenge_data: ChallengeCreate) -> ChallengeResponse:
        """챌린지 생성"""
        # 1. 사용자 권한 확인
        self._check_user_can_create_challenge(creator)
        
        # 2. 데이터 검증
        self._validate_challenge_data(challenge_data)
        
        # 3. 챌린지 생성
        db_challenge = self._create_challenge_record(creator.id, challenge_data)
        
        # 4. 태그 연결
        if challenge_data.tags:
            self._attach_tags(db_challenge.id, challenge_data.tags)
        
        # 5. 생성자를 매니저로 자동 등록
        self._add_creator_as_manager(db_challenge.id, creator.id)
        
        logger.info(f"챌린지 생성: {db_challenge.title} (ID: {db_challenge.id}) by {creator.username}")
        
        return self._build_challenge_response(db_challenge)

    def get_challenge(self, challenge_id: int, current_user: Optional[User] = None) -> ChallengeResponse:
        """챌린지 상세 조회"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 비공개 챌린지 접근 권한 확인
        if not challenge.is_public and not self._user_can_access_challenge(challenge, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 챌린지에 접근할 권한이 없습니다"
            )
        
        return self._build_challenge_response(challenge)

    def get_challenges(
        self, 
        skip: int = 0, 
        limit: int = 20,
        status_filter: Optional[ChallengeStatus] = None,
        mode_filter: Optional[ChallengeMode] = None,
        payment_filter: Optional[PaymentType] = None,
        creator_id: Optional[int] = None
    ) -> List[ChallengeListItem]:
        """챌린지 목록 조회 (필터링 지원)"""
        query = self.db.query(Challenge).filter(Challenge.is_deleted == False)
        
        # 필터 적용
        if status_filter:
            query = query.filter(Challenge.status == status_filter)
        if mode_filter:
            query = query.filter(Challenge.mode == mode_filter)
        if payment_filter:
            query = query.filter(Challenge.payment_type == payment_filter)
        if creator_id:
            query = query.filter(Challenge.creator_id == creator_id)
        
        # 공개 챌린지만 (관리자가 아닌 경우)
        query = query.filter(Challenge.is_public == True)
        
        challenges = query.order_by(Challenge.created_at.desc()).offset(skip).limit(limit).all()
        
        return [self._build_challenge_list_item(c) for c in challenges]

    def update_challenge(
        self, 
        challenge_id: int, 
        update_data: ChallengeUpdate, 
        current_user: User
    ) -> ChallengeResponse:
        """챌린지 수정"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 권한 확인
        if not self._user_can_edit_challenge(challenge, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="챌린지를 수정할 권한이 없습니다"
            )
        
        # 상태 변경 가능성 확인
        if update_data.status and not self._can_change_status(challenge, update_data.status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 상태에서 해당 상태로 변경할 수 없습니다"
            )
        
        # 업데이트 실행
        self._update_challenge_fields(challenge, update_data)
        
        # 태그 업데이트
        if update_data.tags is not None:
            self._update_challenge_tags(challenge.id, update_data.tags)
        
        logger.info(f"챌린지 수정: {challenge.title} (ID: {challenge.id}) by {current_user.username}")
        
        return self._build_challenge_response(challenge)

    def delete_challenge(self, challenge_id: int, current_user: User) -> bool:
        """챌린지 삭제 (소프트 삭제)"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 권한 확인
        if not self._user_can_delete_challenge(challenge, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="챌린지를 삭제할 권한이 없습니다"
            )
        
        # 진행 중인 챌린지는 삭제 불가
        if challenge.status in [ChallengeStatus.active]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="진행 중인 챌린지는 삭제할 수 없습니다"
            )
        
        # 소프트 삭제
        challenge.is_deleted = True
        challenge.deleted_at = datetime.utcnow()
        challenge.status = ChallengeStatus.cancelled
        
        self.db.commit()
        logger.info(f"챌린지 삭제: {challenge.title} (ID: {challenge.id}) by {current_user.username}")
        
        return True

    def start_challenge(self, challenge_id: int, current_user: User) -> ChallengeResponse:
        """챌린지 시작"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 권한 확인
        if not self._user_can_manage_challenge(challenge, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="챌린지를 시작할 권한이 없습니다"
            )
        
        # 시작 가능한 상태인지 확인
        if challenge.status != ChallengeStatus.recruiting:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="모집 중인 챌린지만 시작할 수 있습니다"
            )
        
        # 최소 참가자 수 확인
        if challenge.current_participants < challenge.min_participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"최소 참가자 수({challenge.min_participants}명)가 부족합니다"
            )
        
        challenge.status = ChallengeStatus.active
        self.db.commit()
        
        logger.info(f"챌린지 시작: {challenge.title} (ID: {challenge.id})")
        return self._build_challenge_response(challenge)

    def complete_challenge(self, challenge_id: int, current_user: User) -> ChallengeResponse:
        """챌린지 완료"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 권한 확인
        if not self._user_can_manage_challenge(challenge, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="챌린지를 완료할 권한이 없습니다"
            )
        
        # 완료 가능한 상태인지 확인
        if challenge.status != ChallengeStatus.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="진행 중인 챌린지만 완료할 수 있습니다"
            )
        
        challenge.status = ChallengeStatus.completed
        challenge.completed_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"챌린지 완료: {challenge.title} (ID: {challenge.id})")
        return self._build_challenge_response(challenge)

    def get_challenge_statistics(self, challenge_id: int) -> ChallengeStatistics:
        """챌린지 통계 정보 조회"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        # 참가자 통계
        participants_query = self.db.query(Participation).filter(
            Participation.challenge_id == challenge_id
        )
        
        total_participants = participants_query.count()
        active_participants = participants_query.filter(Participation.is_active == True).count()
        
        # 진행 상황 계산
        duration_days = self._calculate_duration_days(challenge)
        remaining_days = self._calculate_remaining_days(challenge)
        progress_percentage = self._calculate_progress_percentage(challenge)
        
        return ChallengeStatistics(
            challenge_id=challenge.id,
            total_participants=total_participants,
            active_participants=active_participants,
            current_participants=challenge.current_participants,
            max_participants=challenge.max_participants,
            duration_days=duration_days,
            remaining_days=remaining_days,
            progress_percentage=progress_percentage,
            status=challenge.status.value,
            computed_status=challenge.status.value,  # 계산된 상태가 있다면 여기서 처리
            payment_required=challenge.payment_type != PaymentType.free
        )

    def get_payment_info(self, challenge_id: int) -> PaymentInfoResponse:
        """챌린지 결제 정보 조회"""
        challenge = self._get_challenge_by_id(challenge_id)
        
        available_options = []
        if challenge.payment_type in [PaymentType.entry_fee, PaymentType.both]:
            available_options.append("entry_fee")
        if challenge.payment_type in [PaymentType.monthly_fee, PaymentType.both]:
            available_options.append("monthly_fee")
        
        return PaymentInfoResponse(
            challenge_id=challenge.id,
            payment_type=challenge.payment_type,
            entry_fee=challenge.entry_fee,
            monthly_fee=challenge.monthly_fee,
            is_payment_required=challenge.payment_type != PaymentType.free,
            available_options=available_options
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

    def _check_user_can_create_challenge(self, user: User) -> None:
        """사용자가 챌린지 생성 가능한지 확인"""
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 계정은 챌린지를 생성할 수 없습니다"
            )
        
        # 추가 제한사항 (예: 생성 개수 제한, 레벨 제한 등)
        active_challenges = self.db.query(Challenge).filter(
            Challenge.creator_id == user.id,
            Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active]),
            Challenge.is_deleted == False
        ).count()
        
        if active_challenges >= 5:  # 최대 5개까지
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="동시에 진행할 수 있는 챌린지는 최대 5개입니다"
            )

    def _validate_challenge_data(self, data: ChallengeCreate) -> None:
        """챌린지 데이터 유효성 검증"""
        # 날짜 검증
        if data.start_date and data.start_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="시작일은 오늘 이후여야 합니다"
            )

    def _create_challenge_record(self, creator_id: int, data: ChallengeCreate) -> Challenge:
        """챌린지 DB 레코드 생성"""
        db_challenge = Challenge(
            title=data.title,
            description=data.description,
            creator_id=creator_id,
            start_date=data.start_date,
            end_date=data.end_date,
            payment_type=data.payment_type,
            entry_fee=data.entry_fee or 0,
            monthly_fee=data.monthly_fee or 0,
            min_participants=data.min_participants or 1,
            max_participants=data.max_participants,
            total_rounds=data.total_rounds,
            min_participation_rate=data.min_participation_rate or 80,
            use_reward=data.use_reward or False,
            reward_description=data.reward_description,
            mode=data.mode,
            default_zoom_link=data.default_zoom_link,
            same_place_for_all_rounds=data.same_place_for_all_rounds or False,
            default_place_name=data.default_place_name,
            default_address=data.default_address,
            default_latitude=data.default_latitude,
            default_longitude=data.default_longitude,
            require_approval=data.require_approval or False,
            is_public=data.is_public or True,
            status=ChallengeStatus.draft,
            current_participants=0
        )
        
        self.db.add(db_challenge)
        self.db.commit()
        self.db.refresh(db_challenge)
        
        return db_challenge

    def _attach_tags(self, challenge_id: int, tag_names: List[str]) -> None:
        """챌린지에 태그 연결"""
        for tag_name in tag_names:
            tag = self.db.query(Tag).filter(Tag.name == tag_name.strip().lower()).first()
            if not tag:
                tag = Tag(name=tag_name.strip().lower())
                self.db.add(tag)
                self.db.commit()
                self.db.refresh(tag)
            
            # 중복 체크
            existing_link = self.db.query(ChallengeTag).filter(
                ChallengeTag.challenge_id == challenge_id,
                ChallengeTag.tag_id == tag.id
            ).first()
            
            if not existing_link:
                challenge_tag = ChallengeTag(challenge_id=challenge_id, tag_id=tag.id)
                self.db.add(challenge_tag)
        
        self.db.commit()

    def _add_creator_as_manager(self, challenge_id: int, creator_id: int) -> None:
        """챌린지 생성자를 매니저로 등록"""
        participation = Participation(
            user_id=creator_id,
            challenge_id=challenge_id,
            role=ParticipationRole.manager,
            is_active=True,
            is_approved=True,
            joined_at=datetime.utcnow(),
            approved_at=datetime.utcnow()
        )
        
        self.db.add(participation)
        
        # 참가자 수 증가
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        challenge.current_participants += 1
        
        self.db.commit()

    def _user_can_access_challenge(self, challenge: Challenge, user: Optional[User]) -> bool:
        """사용자가 챌린지에 접근할 수 있는지 확인"""
        if not user:
            return False
        
        # 생성자이거나 참가자인 경우
        return (challenge.creator_id == user.id or 
                self._user_is_participant(challenge.id, user.id))

    def _user_can_edit_challenge(self, challenge: Challenge, user: User) -> bool:
        """사용자가 챌린지를 수정할 수 있는지 확인"""
        return challenge.creator_id == user.id

    def _user_can_delete_challenge(self, challenge: Challenge, user: User) -> bool:
        """사용자가 챌린지를 삭제할 수 있는지 확인"""
        return challenge.creator_id == user.id or user.is_admin

    def _user_can_manage_challenge(self, challenge: Challenge, user: User) -> bool:
        """사용자가 챌린지를 관리할 수 있는지 확인 (시작/완료 등)"""
        return challenge.creator_id == user.id

    def _user_is_participant(self, challenge_id: int, user_id: int) -> bool:
        """사용자가 챌린지 참가자인지 확인"""
        return self.db.query(Participation).filter(
            Participation.challenge_id == challenge_id,
            Participation.user_id == user_id,
            Participation.is_active == True
        ).first() is not None

    def _can_change_status(self, challenge: Challenge, new_status: ChallengeStatus) -> bool:
        """상태 변경이 가능한지 확인"""
        current = challenge.status
        
        valid_transitions = {
            ChallengeStatus.draft: [ChallengeStatus.recruiting, ChallengeStatus.cancelled],
            ChallengeStatus.recruiting: [ChallengeStatus.active, ChallengeStatus.cancelled],
            ChallengeStatus.active: [ChallengeStatus.completed, ChallengeStatus.cancelled],
            ChallengeStatus.completed: [ChallengeStatus.closed],
            ChallengeStatus.cancelled: [],
            ChallengeStatus.closed: []
        }
        
        return new_status in valid_transitions.get(current, [])

    def _update_challenge_fields(self, challenge: Challenge, update_data: ChallengeUpdate) -> None:
        """챌린지 필드 업데이트"""
        update_dict = update_data.model_dump(exclude_unset=True, exclude={'tags'})
        
        for field, value in update_dict.items():
            if hasattr(challenge, field):
                setattr(challenge, field, value)
        
        self.db.commit()

    def _update_challenge_tags(self, challenge_id: int, new_tags: List[str]) -> None:
        """챌린지 태그 업데이트"""
        # 기존 태그 연결 삭제
        self.db.query(ChallengeTag).filter(ChallengeTag.challenge_id == challenge_id).delete()
        
        # 새 태그 연결
        if new_tags:
            self._attach_tags(challenge_id, new_tags)

    def _build_challenge_response(self, challenge: Challenge) -> ChallengeResponse:
        """Challenge 모델을 ChallengeResponse로 변환"""
        response = ChallengeResponse.model_validate(challenge)
        
        # 태그 조회
        tags = self.db.query(Tag.name).join(ChallengeTag).filter(
            ChallengeTag.challenge_id == challenge.id
        ).all()
        response.tags = [tag.name for tag in tags]
        
        return response

    def _build_challenge_list_item(self, challenge: Challenge) -> ChallengeListItem:
        """Challenge 모델을 ChallengeListItem으로 변환"""
        return ChallengeListItem.model_validate(challenge)

    def _calculate_duration_days(self, challenge: Challenge) -> int:
        """챌린지 기간 계산"""
        if challenge.start_date and challenge.end_date:
            return (challenge.end_date - challenge.start_date).days
        return 0

    def _calculate_remaining_days(self, challenge: Challenge) -> int:
        """남은 일수 계산"""
        if challenge.end_date:
            remaining = (challenge.end_date - date.today()).days
            return max(0, remaining)
        return 0

    def _calculate_progress_percentage(self, challenge: Challenge) -> float:
        """진행률 계산"""
        duration = self._calculate_duration_days(challenge)
        if duration <= 0:
            return 0.0
        
        elapsed_days = duration - self._calculate_remaining_days(challenge)
        return min(100.0, (elapsed_days / duration) * 100.0)


# ==================== Service Factory ====================

def get_challenge_service(db: Session) -> ChallengeService:
    """ChallengeService 인스턴스 생성 (의존성 주입용)"""
    return ChallengeService(db)