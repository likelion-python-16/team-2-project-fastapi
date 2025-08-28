# app/services/payment_service.py
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Depends, HTTPException, status
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.payment import (
    Payment, Refund, PaymentStatus, 
    PaymentMethodType, PaymentTransactionType
)
from app.models.challenge import Challenge
from app.models.user import User
from app.utils.logging import logger

class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def create_payment(
        self, user: User, challenge: Challenge | None,
        amount: int, transaction_type: str | PaymentTransactionType, 
        method: str | PaymentMethodType, order_id: str, order_name: str,
        payment_key: str | None = None, metadata_json: str | None = None,
    ) -> Payment:
        try:
            # Enum 타입 확인 및 변환
            if isinstance(transaction_type, str):
                transaction_type = PaymentTransactionType(transaction_type)
            if isinstance(method, str):
                method = PaymentMethodType(method)
                
            payment = Payment(
                user_id=user.id,
                challenge_id=challenge.id if challenge else None,
                amount=amount,
                transaction_type=transaction_type,
                method=method,
                order_id=order_id,
                order_name=order_name,
                payment_key=payment_key,
                metadata_json=metadata_json,
                status=PaymentStatus.pending
            )
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)
            logger.info(f"결제 생성 완료: payment_id={payment.id}, user_id={user.id}, challenge_id={challenge.id if challenge else None}")
            return payment
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"결제 생성 중 DB 오류: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"결제 생성 중 오류가 발생했습니다: {str(e)}"
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"결제 생성 중 오류: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="결제 생성 중 오류가 발생했습니다"
            )

    def approve_payment(self, payment_id: int) -> Payment:
        try:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise HTTPException(status_code=404, detail="결제를 찾을 수 없습니다")
            
            payment.status = PaymentStatus.completed
            payment.approved_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info(f"결제 승인 완료: payment_id={payment.id}")
            return payment
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"결제 승인 중 DB 오류: {e}")
            raise HTTPException(status_code=500, detail="결제 승인 중 오류가 발생했습니다")
        except Exception as e:
            self.db.rollback()
            logger.error(f"결제 승인 중 오류: {e}")
            raise HTTPException(status_code=500, detail="결제 승인 중 오류가 발생했습니다")

    def fail_payment(self, payment_id: int, code: str, message: str) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="결제를 찾을 수 없습니다")
        
        payment.status = PaymentStatus.failed
        payment.failure_code = code
        payment.failure_message = message
        self.db.commit()
        return payment

    def cancel_payment(self, payment_id: int, reason: str) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="결제를 찾을 수 없습니다")
        
        payment.status = PaymentStatus.cancelled
        payment.cancel_reason = reason
        payment.cancelled_at = datetime.utcnow()
        self.db.commit()
        return payment

    def refund_payment(self, payment_id: int, user: User, amount: int, reason: str) -> Refund:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="결제를 찾을 수 없습니다")
        
        if payment.amount < amount:
            raise HTTPException(status_code=400, detail="환불 금액이 결제 금액을 초과합니다")
        
        refund = Refund(
            payment_id=payment_id,
            user_id=user.id,
            challenge_id=payment.challenge_id,
            refund_amount=amount,
            refund_reason=reason,
            status=PaymentStatus.pending
        )
        
        self.db.add(refund)
        self.db.commit()
        self.db.refresh(refund)
        return refund

    def get_user_payments(self, user_id: int, challenge_id: int = None) -> list[Payment]:
        query = self.db.query(Payment).filter(Payment.user_id == user_id)
        
        if challenge_id:
            query = query.filter(Payment.challenge_id == challenge_id)
        
        return query.order_by(Payment.created_at.desc()).all()

def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db)