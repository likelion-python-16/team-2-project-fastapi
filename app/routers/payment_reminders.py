# app/routers/payment_reminders.py
"""
월회비 결제 알림 관리 API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.services.payment_reminder_service import get_payment_reminder_service
from app.utils.logging import logger

router = APIRouter(prefix="/payment-reminders", tags=["Payment Reminders"])


@router.post("/check")
def check_payment_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    월회비 결제 알림 수동 실행
    - 관리자 또는 시스템에서만 실행 가능
    """
    # 관리자 권한 확인 (필요시)
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    try:
        reminder_service = get_payment_reminder_service(db)
        results = reminder_service.check_and_send_payment_reminders()
        
        logger.info(f"결제 알림 수동 실행: user_id={current_user.id}, results={results}")
        
        return {
            "success": True,
            "message": "결제 알림 처리가 완료되었습니다",
            "results": results
        }
    except Exception as e:
        logger.error(f"결제 알림 수동 실행 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"결제 알림 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/next-payments")
def get_upcoming_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자의 다가오는 월회비 결제 일정 조회"""
    from app.models.participation import Participation, PaymentCycle, ParticipationStatus
    from app.models.challenge import Challenge
    from datetime import date, timedelta
    
    # 사용자의 월회비 참여 내역 조회
    upcoming_payments = db.query(Participation).join(
        Challenge, Participation.challenge_id == Challenge.id
    ).filter(
        Participation.user_id == current_user.id,
        Participation.payment_cycle == PaymentCycle.monthly,
        Participation.status == ParticipationStatus.active,
        Participation.next_payment_date.isnot(None),
        Participation.next_payment_date >= date.today(),
        Challenge.is_deleted == False
    ).all()
    
    result = []
    for participation in upcoming_payments:
        challenge = db.query(Challenge).filter(Challenge.id == participation.challenge_id).first()
        if challenge:
            days_until = (participation.next_payment_date - date.today()).days
            result.append({
                "challenge_id": challenge.id,
                "challenge_title": challenge.title,
                "payment_amount": challenge.monthly_fee,
                "next_payment_date": participation.next_payment_date.isoformat(),
                "days_until": days_until,
                "payment_failed_count": participation.payment_failed_count
            })
    
    # 날짜순 정렬
    result.sort(key=lambda x: x["next_payment_date"])
    
    return {
        "upcoming_payments": result,
        "total_count": len(result)
    }