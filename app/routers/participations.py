# app/routers/participations.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.security import get_current_user, get_current_user_optional
from app.services.participation_service import ParticipationService
from app.schemas.participation import (
    ParticipationCreate,
    ParticipationApproval,
    ParticipationResponse,
    ParticipationWithUser,
    MyParticipation,
    ParticipantStats,
    LeaveResponse,
)

# ✅ 인증 의존성: auth 라우터에서 가져옴


router = APIRouter(prefix="/participations", tags=["Participation"])

# --- DI: Service 생성 ---
def get_participation_service(db: Session = Depends(get_db)) -> ParticipationService:
    return ParticipationService(db)

# 1) 참가 신청
@router.post("/join", response_model=ParticipationResponse, status_code=status.HTTP_201_CREATED)
def join_challenge(
    payload: ParticipationCreate,
    current_user: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.join_challenge(current_user, payload)

# 2) 승인/거부 (승인 필요한 챌린지용)
#    participation_id는 "user_id:challenge_id" 형식의 문자열 (서비스 내부 parse 사용)
@router.post("/{participation_id}/approve", response_model=ParticipationResponse)
def approve_participation(
    participation_id: str,
    payload: ParticipationApproval,
    approver: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.approve_participation(participation_id, payload, approver)

# 3) 결제 완료 콜백/처리
@router.post("/{challenge_id}/payment/complete", response_model=ParticipationResponse)
def complete_payment(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    """
    결제 성공 직후(또는 PG 웹훅 후) 호출하여 해당 사용자의 participation을 활성화합니다.
    """
    return service.complete_payment(user_id=current_user.id, challenge_id=challenge_id)

# 4) 결제 실패 처리
@router.post("/{challenge_id}/payment/fail", response_model=ParticipationResponse)
def payment_fail(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.handle_payment_failure(current_user.id, challenge_id)

# 5) 자발적 탈퇴
@router.post("/{challenge_id}/leave", response_model=LeaveResponse)
def leave_challenge(
    challenge_id: int,
    reason: Optional[str] = Body(default=None, embed=True),
    current_user: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.leave_challenge(challenge_id, current_user, reason)

# 6) 강제 퇴출 (관리 권한 필요)
@router.post("/{challenge_id}/kick/{target_user_id}", response_model=ParticipationResponse)
def kick_participant(
    challenge_id: int,
    target_user_id: int,
    reason: str = Body(..., embed=True),
    kicker: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.kick_participant(challenge_id, target_user_id, kicker, reason)

# 7) 진행률(출석수) 업데이트
@router.patch("/{challenge_id}/progress/{user_id}", response_model=ParticipationResponse)
def update_progress(
    challenge_id: int,
    user_id: int,
    new_attendance_count: int = Body(..., embed=True),
    _actor: User = Depends(get_current_user),  # 호출자 인증만
    service: ParticipationService = Depends(get_participation_service),
):
    return service.update_participation_progress(challenge_id, user_id, new_attendance_count)

# 8) 참가자 목록 조회 (공개 챌린지 또는 접근권한 필요)
@router.get("/{challenge_id}/members", response_model=List[ParticipationWithUser])
def get_members(
    challenge_id: int,
    # 공개 접근 허용을 위해 optional 인증 사용
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.get_participants(challenge_id, current_user)

# 9) 승인 대기 목록 (승인 권한 필요)
@router.get("/{challenge_id}/approvals/pending", response_model=List[ParticipationWithUser])
def get_pending(
    challenge_id: int,
    approver: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.get_pending_approvals(challenge_id, approver)

# 10) 내 참가 목록
@router.get("/me", response_model=List[MyParticipation])
def my_participations(
    current_user: User = Depends(get_current_user),
    service: ParticipationService = Depends(get_participation_service),
):
    return service.get_my_participations(current_user)

# 11) 챌린지 참가 통계
@router.get("/{challenge_id}/stats", response_model=ParticipantStats)
def participant_stats(
    challenge_id: int,
    _user: User = Depends(get_current_user),  # 인증만 필요
    service: ParticipationService = Depends(get_participation_service),
):
    return service.get_participant_stats(challenge_id)
