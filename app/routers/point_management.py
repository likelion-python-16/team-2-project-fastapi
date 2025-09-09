from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_from_cookie, require_admin
from app.models.user import User
from app.services.withdrawal_service import WithdrawalService
from app.services.reward_service import RewardService
from app.schemas.point_withdrawal import (
    WithdrawalRequest, WithdrawalResponse, WithdrawalDetail, WithdrawalListItem,
    WithdrawalAdminDetail, WithdrawalReview, WithdrawalRejection, WithdrawalCompletion,
    RewardInfo, RewardDistributionResult, UserRewardHistory
)

router = APIRouter(prefix="/points", tags=["Point Management"])


# 사용자용 포인트 환급 API
@router.post("/withdraw", response_model=WithdrawalResponse)
async def create_withdrawal_request(
    request: WithdrawalRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """포인트 환급 신청"""
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    service = WithdrawalService(db)
    try:
        result = service.create_withdrawal_request(
            user_id=current_user.id,
            point_amount=request.point_amount,
            method=request.method,
            bank_name=request.bank_name,
            account_number=request.account_number,
            account_holder=request.account_holder
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/withdrawals", response_model=List[WithdrawalListItem])
async def get_my_withdrawals(
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """내 환급 신청 목록 조회"""
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    service = WithdrawalService(db)
    return service.get_user_withdrawals(current_user.id, limit)


@router.get("/withdrawals/{withdrawal_id}", response_model=WithdrawalDetail)
async def get_withdrawal_detail(
    withdrawal_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """환급 신청 상세 조회"""
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    service = WithdrawalService(db)
    try:
        return service.get_withdrawal_details(current_user.id, withdrawal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/withdrawals/{withdrawal_id}/cancel")
async def cancel_withdrawal_request(
    withdrawal_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """환급 신청 취소"""
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    service = WithdrawalService(db)
    try:
        result = service.cancel_withdrawal_request(current_user.id, withdrawal_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rewards/history", response_model=List[UserRewardHistory])
async def get_my_reward_history(
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """내 챌린지 보상 내역 조회"""
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    service = RewardService(db)
    return service.get_user_challenge_rewards(current_user.id, limit)


# 관리자용 환급 관리 API
@router.get("/admin/withdrawals/pending", response_model=List[WithdrawalAdminDetail])
async def get_pending_withdrawals(
    limit: int = Query(50, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """대기 중인 환급 신청 목록 (관리자용)"""
    service = WithdrawalService(db)
    return service.get_pending_withdrawals(limit)


@router.post("/admin/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: int,
    review: WithdrawalReview,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """환급 신청 승인 (관리자용)"""
    service = WithdrawalService(db)
    try:
        result = service.approve_withdrawal(withdrawal_id, current_user.id, review.memo)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: int,
    rejection: WithdrawalRejection,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """환급 신청 거부 (관리자용)"""
    service = WithdrawalService(db)
    try:
        result = service.reject_withdrawal(
            withdrawal_id, current_user.id, rejection.reason, rejection.memo
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/withdrawals/{withdrawal_id}/complete")
async def complete_withdrawal(
    withdrawal_id: int,
    completion: WithdrawalCompletion,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """환급 완료 처리 (관리자용)"""
    service = WithdrawalService(db)
    try:
        result = service.complete_withdrawal(withdrawal_id, completion.transaction_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 챌린지 보상 관리 API
@router.get("/admin/challenges/{challenge_id}/reward-info", response_model=RewardInfo)
async def get_challenge_reward_info(
    challenge_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """챌린지 보상 정보 조회 (관리자용)"""
    service = RewardService(db)
    try:
        return service.get_challenge_reward_info(challenge_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/admin/challenges/{challenge_id}/distribute-rewards", response_model=RewardDistributionResult)
async def distribute_challenge_rewards(
    challenge_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """챌린지 완주 보상 분배 (관리자용)"""
    service = RewardService(db)
    try:
        # 보상 분배 가능 여부 확인
        can_distribute, message = service.can_distribute_rewards(challenge_id)
        if not can_distribute:
            raise HTTPException(status_code=400, detail=message)
        
        result = service.complete_challenge_and_distribute_rewards(challenge_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/challenges/{challenge_id}/can-distribute")
async def check_can_distribute_rewards(
    challenge_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """보상 분배 가능 여부 확인 (관리자용)"""
    service = RewardService(db)
    can_distribute, message = service.can_distribute_rewards(challenge_id)
    return {
        "can_distribute": can_distribute,
        "message": message
    }