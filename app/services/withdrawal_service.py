from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_

from app.models.user import User
from app.models.point_withdrawal import PointWithdrawal, WithdrawalStatus, WithdrawalMethod
from app.models.pointhistory import PointHistory, PointHistoryType


class WithdrawalService:
    """포인트 환급 서비스"""
    
    MIN_WITHDRAWAL_POINTS = 10000  # 최소 환급 포인트
    DEFAULT_FEE_RATE = 0.01  # 기본 수수료율 1%
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_withdrawal_request(self, 
                                user_id: int,
                                point_amount: int,
                                method: WithdrawalMethod,
                                bank_name: Optional[str] = None,
                                account_number: Optional[str] = None,
                                account_holder: Optional[str] = None) -> Dict:
        """포인트 환급 신청"""
        
        # 사용자 확인
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")
        
        # 환급 자격 확인
        can_withdraw, message = self._can_user_withdraw(user, point_amount)
        if not can_withdraw:
            raise ValueError(message)
        
        # 계좌이체인 경우 계좌 정보 필수
        if method == WithdrawalMethod.bank_transfer:
            if not all([bank_name, account_number, account_holder]):
                raise ValueError("계좌이체 선택 시 은행명, 계좌번호, 예금주명이 필요합니다")
        
        # 환급 신청 생성
        withdrawal = PointWithdrawal(
            user_id=user_id,
            point_amount=point_amount,
            method=method,
            bank_name=bank_name,
            account_number=account_number,
            account_holder=account_holder,
            status=WithdrawalStatus.pending
        )
        
        # 수수료 계산
        withdrawal.calculate_withdrawal_amount(self.DEFAULT_FEE_RATE)
        
        # 포인트 차감 (임시로 예약)
        user.deduct_points(point_amount)
        
        # 데이터베이스에 저장하여 ID 생성
        self.db.add(withdrawal)
        self.db.flush()  # ID 생성을 위한 flush
        
        # 포인트 히스토리 기록
        point_history = PointHistory(
            user_id=user_id,
            description=f"포인트 환급 신청 (신청ID: {withdrawal.id})",
            point_amount=-point_amount,
            type=PointHistoryType.withdrawal,
            total_earned_point=user.total_points
        )
        
        self.db.add(point_history)
        self.db.commit()
        
        return {
            "withdrawal_id": withdrawal.id,
            "point_amount": point_amount,
            "withdrawal_amount": withdrawal.withdrawal_amount,
            "fee_amount": withdrawal.fee_amount,
            "status": withdrawal.status,
            "message": "환급 신청이 완료되었습니다. 검토 후 처리됩니다."
        }
    
    def cancel_withdrawal_request(self, user_id: int, withdrawal_id: int) -> Dict:
        """환급 신청 취소"""
        withdrawal = self.db.query(PointWithdrawal).filter(
            and_(
                PointWithdrawal.id == withdrawal_id,
                PointWithdrawal.user_id == user_id
            )
        ).first()
        
        if not withdrawal:
            raise ValueError("환급 신청을 찾을 수 없습니다")
        
        if not withdrawal.can_cancel:
            raise ValueError("취소할 수 없는 상태입니다")
        
        # 포인트 복구
        user = self.db.query(User).filter(User.id == user_id).first()
        user.add_points(withdrawal.point_amount)
        
        # 신청 취소
        withdrawal.cancel()
        
        # 포인트 히스토리 기록
        point_history = PointHistory(
            user_id=user_id,
            description=f"포인트 환급 신청 취소 (신청ID: {withdrawal_id})",
            point_amount=withdrawal.point_amount,
            type=PointHistoryType.refund,
            total_earned_point=user.total_points
        )
        
        self.db.add(point_history)
        self.db.commit()
        
        return {
            "withdrawal_id": withdrawal_id,
            "status": withdrawal.status,
            "refunded_points": withdrawal.point_amount,
            "message": "환급 신청이 취소되었습니다. 포인트가 복구되었습니다."
        }
    
    def get_user_withdrawals(self, user_id: int, limit: int = 20) -> List[Dict]:
        """사용자 환급 내역 조회"""
        withdrawals = self.db.query(PointWithdrawal).filter(
            PointWithdrawal.user_id == user_id
        ).order_by(PointWithdrawal.requested_at.desc()).limit(limit).all()
        
        return [
            {
                "id": w.id,
                "point_amount": w.point_amount,
                "withdrawal_amount": w.withdrawal_amount,
                "fee_amount": w.fee_amount,
                "method": w.method,
                "status": w.status,
                "requested_at": w.requested_at,
                "reviewed_at": w.reviewed_at,
                "completed_at": w.completed_at,
                "rejection_reason": w.rejection_reason,
                "can_cancel": w.can_cancel
            }
            for w in withdrawals
        ]
    
    def get_withdrawal_details(self, user_id: int, withdrawal_id: int) -> Dict:
        """환급 신청 상세 조회"""
        withdrawal = self.db.query(PointWithdrawal).filter(
            and_(
                PointWithdrawal.id == withdrawal_id,
                PointWithdrawal.user_id == user_id
            )
        ).first()
        
        if not withdrawal:
            raise ValueError("환급 신청을 찾을 수 없습니다")
        
        return {
            "id": withdrawal.id,
            "point_amount": withdrawal.point_amount,
            "withdrawal_amount": withdrawal.withdrawal_amount,
            "fee_amount": withdrawal.fee_amount,
            "method": withdrawal.method,
            "bank_name": withdrawal.bank_name,
            "account_number": withdrawal.account_number,
            "account_holder": withdrawal.account_holder,
            "status": withdrawal.status,
            "requested_at": withdrawal.requested_at,
            "reviewed_at": withdrawal.reviewed_at,
            "completed_at": withdrawal.completed_at,
            "rejection_reason": withdrawal.rejection_reason,
            "admin_memo": withdrawal.admin_memo,
            "transaction_id": withdrawal.transaction_id,
            "can_cancel": withdrawal.can_cancel
        }
    
    def _can_user_withdraw(self, user: User, point_amount: int) -> Tuple[bool, str]:
        """환급 자격 확인"""
        
        # 활성 사용자인지 확인
        if not user.is_active:
            return False, "비활성화된 계정입니다"
        
        # 포인트 교환 자격 확인 (User 모델의 기존 메소드 활용)
        if not user.can_exchange_points():
            return False, "포인트 교환 자격이 없습니다 (계정 비활성화 또는 페널티)"
        
        # 최소 환급 포인트 확인
        if point_amount < self.MIN_WITHDRAWAL_POINTS:
            return False, f"최소 {self.MIN_WITHDRAWAL_POINTS:,}포인트 이상만 환급 가능합니다"
        
        # 보유 포인트 확인
        if user.total_points < point_amount:
            return False, "보유 포인트가 부족합니다"
        
        # 대기 중인 환급 신청 확인
        pending_withdrawal = self.db.query(PointWithdrawal).filter(
            and_(
                PointWithdrawal.user_id == user.id,
                PointWithdrawal.status.in_([
                    WithdrawalStatus.pending, 
                    WithdrawalStatus.reviewing,
                    WithdrawalStatus.approved
                ])
            )
        ).first()
        
        if pending_withdrawal:
            return False, "이미 처리 중인 환급 신청이 있습니다"
        
        return True, "환급 가능"
    
    # 관리자용 메소드들
    def get_pending_withdrawals(self, limit: int = 50) -> List[Dict]:
        """대기 중인 환급 신청 목록 (관리자용)"""
        withdrawals = self.db.query(PointWithdrawal).filter(
            PointWithdrawal.status == WithdrawalStatus.pending
        ).order_by(PointWithdrawal.requested_at.asc()).limit(limit).all()
        
        result = []
        for w in withdrawals:
            user = self.db.query(User).filter(User.id == w.user_id).first()
            result.append({
                "id": w.id,
                "user_id": w.user_id,
                "username": user.username if user else "Unknown",
                "user_name": user.name if user else "Unknown",
                "point_amount": w.point_amount,
                "withdrawal_amount": w.withdrawal_amount,
                "fee_amount": w.fee_amount,
                "method": w.method,
                "bank_name": w.bank_name,
                "account_number": w.account_number,
                "account_holder": w.account_holder,
                "requested_at": w.requested_at,
                "status": w.status
            })
        
        return result
    
    def approve_withdrawal(self, withdrawal_id: int, reviewer_id: int, memo: Optional[str] = None) -> Dict:
        """환급 신청 승인 (관리자용)"""
        withdrawal = self.db.query(PointWithdrawal).filter(
            PointWithdrawal.id == withdrawal_id
        ).first()
        
        if not withdrawal:
            raise ValueError("환급 신청을 찾을 수 없습니다")
        
        if withdrawal.status != WithdrawalStatus.pending:
            raise ValueError("승인할 수 없는 상태입니다")
        
        withdrawal.approve(reviewer_id, memo)
        self.db.commit()
        
        return {
            "withdrawal_id": withdrawal_id,
            "status": withdrawal.status,
            "message": "환급 신청이 승인되었습니다"
        }
    
    def reject_withdrawal(self, withdrawal_id: int, reviewer_id: int, reason: str, memo: Optional[str] = None) -> Dict:
        """환급 신청 거부 (관리자용)"""
        withdrawal = self.db.query(PointWithdrawal).filter(
            PointWithdrawal.id == withdrawal_id
        ).first()
        
        if not withdrawal:
            raise ValueError("환급 신청을 찾을 수 없습니다")
        
        if withdrawal.status != WithdrawalStatus.pending:
            raise ValueError("거부할 수 없는 상태입니다")
        
        # 포인트 복구
        user = self.db.query(User).filter(User.id == withdrawal.user_id).first()
        if user:
            user.add_points(withdrawal.point_amount)
            
            # 포인트 히스토리 기록
            point_history = PointHistory(
                user_id=withdrawal.user_id,
                description=f"환급 신청 거부로 인한 포인트 복구 (신청ID: {withdrawal_id})",
                point_amount=withdrawal.point_amount,
                type=PointHistoryType.refund,
                total_earned_point=user.total_points
            )
            self.db.add(point_history)
        
        withdrawal.reject(reviewer_id, reason, memo)
        self.db.commit()
        
        return {
            "withdrawal_id": withdrawal_id,
            "status": withdrawal.status,
            "reason": reason,
            "message": "환급 신청이 거부되었습니다. 포인트가 복구되었습니다."
        }
    
    def complete_withdrawal(self, withdrawal_id: int, transaction_id: Optional[str] = None) -> Dict:
        """환급 완료 처리 (관리자용)"""
        withdrawal = self.db.query(PointWithdrawal).filter(
            PointWithdrawal.id == withdrawal_id
        ).first()
        
        if not withdrawal:
            raise ValueError("환급 신청을 찾을 수 없습니다")
        
        if withdrawal.status != WithdrawalStatus.approved:
            raise ValueError("승인된 상태에서만 완료 처리 가능합니다")
        
        withdrawal.complete(transaction_id)
        self.db.commit()
        
        return {
            "withdrawal_id": withdrawal_id,
            "status": withdrawal.status,
            "transaction_id": transaction_id,
            "message": "환급이 완료되었습니다"
        }