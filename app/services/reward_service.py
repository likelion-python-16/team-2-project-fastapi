from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.user import User
from app.models.challenge import Challenge, ChallengeStatus
from app.models.participation import Participation, ParticipationStatus
from app.models.payment import Payment, PaymentStatus
from app.models.pointhistory import PointHistory, PointHistoryType
from app.core.database import get_db


class RewardService:
    """챌린지 완주 보상 시스템"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def complete_challenge_and_distribute_rewards(self, challenge_id: int) -> Dict:
        """챌린지 완료 및 보상 분배"""
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise ValueError("챌린지를 찾을 수 없습니다")
        
        if challenge.status != ChallengeStatus.completed:
            raise ValueError("완료된 챌린지가 아닙니다")
        
        # 완주자 찾기
        completers = self._get_challenge_completers(challenge_id)
        if not completers:
            return {"message": "완주자가 없습니다", "completers": 0, "total_rewards": 0}
        
        # 총 참가비 계산
        total_entry_fees = self._calculate_total_entry_fees(challenge_id)
        if total_entry_fees <= 0:
            return {"message": "분배할 참가비가 없습니다", "completers": len(completers), "total_rewards": 0}
        
        # 포인트 분배 계산
        reward_per_person = total_entry_fees // len(completers)
        
        # 포인트 분배 실행
        total_distributed = 0
        reward_details = []
        
        for user_id in completers:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and user.is_active:
                # 포인트 지급
                user.add_points(reward_per_person)
                
                # 포인트 히스토리 기록
                point_history = PointHistory(
                    user_id=user_id,
                    challenge_id=challenge_id,
                    description=f"{challenge.title} 완주 보상",
                    point_amount=reward_per_person,
                    type=PointHistoryType.challenge_reward,
                    total_earned_point=user.total_points
                )
                self.db.add(point_history)
                
                total_distributed += reward_per_person
                reward_details.append({
                    "user_id": user_id,
                    "username": user.username,
                    "reward_points": reward_per_person
                })
        
        # 챌린지 상태를 closed로 변경 (정산 완료)
        challenge.status = ChallengeStatus.closed
        
        self.db.commit()
        
        return {
            "message": "보상 분배 완료",
            "challenge_id": challenge_id,
            "challenge_title": challenge.title,
            "completers": len(completers),
            "total_entry_fees": total_entry_fees,
            "reward_per_person": reward_per_person,
            "total_distributed": total_distributed,
            "remaining_amount": total_entry_fees - total_distributed,
            "reward_details": reward_details
        }
    
    def _get_challenge_completers(self, challenge_id: int) -> List[int]:
        """챌린지 완주자 목록 조회"""
        # 참가자 중 완료 상태인 사용자들
        completers = self.db.query(Participation.user_id).filter(
            and_(
                Participation.challenge_id == challenge_id,
                Participation.status == ParticipationStatus.completed
            )
        ).all()
        
        return [completer[0] for completer in completers]
    
    def _calculate_total_entry_fees(self, challenge_id: int) -> int:
        """총 참가비 계산"""
        # 성공적으로 결제된 참가비 합계
        total = self.db.query(func.sum(Payment.amount)).filter(
            and_(
                Payment.challenge_id == challenge_id,
                Payment.status.in_([PaymentStatus.success, PaymentStatus.completed])
            )
        ).scalar()
        
        return total or 0
    
    def get_challenge_reward_info(self, challenge_id: int) -> Dict:
        """챌린지 보상 정보 조회"""
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise ValueError("챌린지를 찾을 수 없습니다")
        
        # 현재 참가자 수
        total_participants = self.db.query(func.count(Participation.user_id)).filter(
            and_(
                Participation.challenge_id == challenge_id,
                Participation.status.in_([ParticipationStatus.active, ParticipationStatus.completed])
            )
        ).scalar() or 0
        
        # 완주자 수
        completers_count = len(self._get_challenge_completers(challenge_id))
        
        # 총 참가비
        total_entry_fees = self._calculate_total_entry_fees(challenge_id)
        
        # 예상 보상 (완주자가 있다면)
        expected_reward_per_person = 0
        if completers_count > 0:
            expected_reward_per_person = total_entry_fees // completers_count
        
        return {
            "challenge_id": challenge_id,
            "challenge_title": challenge.title,
            "challenge_status": challenge.status,
            "total_participants": total_participants,
            "completers_count": completers_count,
            "total_entry_fees": total_entry_fees,
            "expected_reward_per_person": expected_reward_per_person,
            "completion_rate": round((completers_count / total_participants * 100), 2) if total_participants > 0 else 0
        }
    
    def can_distribute_rewards(self, challenge_id: int) -> Tuple[bool, str]:
        """보상 분배 가능 여부 확인"""
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            return False, "챌린지를 찾을 수 없습니다"
        
        if challenge.status == ChallengeStatus.closed:
            return False, "이미 정산이 완료된 챌린지입니다"
        
        if challenge.status != ChallengeStatus.completed:
            return False, "완료된 챌린지만 보상 분배가 가능합니다"
        
        completers = self._get_challenge_completers(challenge_id)
        if not completers:
            return False, "완주자가 없어 보상을 분배할 수 없습니다"
        
        total_entry_fees = self._calculate_total_entry_fees(challenge_id)
        if total_entry_fees <= 0:
            return False, "분배할 참가비가 없습니다"
        
        return True, "보상 분배 가능"
    
    def get_user_challenge_rewards(self, user_id: int, limit: int = 20) -> List[Dict]:
        """사용자의 챌린지 보상 내역 조회"""
        rewards = self.db.query(
            PointHistory.id,
            PointHistory.challenge_id,
            PointHistory.description,
            PointHistory.point_amount,
            PointHistory.created_at,
            Challenge.title.label("challenge_title")
        ).join(
            Challenge, PointHistory.challenge_id == Challenge.id
        ).filter(
            and_(
                PointHistory.user_id == user_id,
                PointHistory.type == PointHistoryType.challenge_reward
            )
        ).order_by(PointHistory.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": reward.id,
                "challenge_id": reward.challenge_id,
                "challenge_title": reward.challenge_title,
                "description": reward.description,
                "point_amount": reward.point_amount,
                "received_at": reward.created_at
            }
            for reward in rewards
        ]