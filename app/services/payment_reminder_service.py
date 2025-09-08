# app/services/payment_reminder_service.py
"""
월회비 결제 알림 및 자동 처리 서비스
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.participation import Participation, PaymentCycle, ParticipationStatus
from app.models.challenge import Challenge, ChallengeStatus
from app.models.notification import Notification, NotificationEvent
from app.models.user import User
from app.utils.logging import logger


class PaymentReminderService:
    def __init__(self, db: Session):
        self.db = db
    
    def check_and_send_payment_reminders(self) -> dict:
        """
        월회비 결제 알림 체크 및 발송
        - 매일 실행 예정 (cron 또는 scheduler)
        """
        today = date.today()
        results = {
            "reminder_sent": 0,
            "overdue_processed": 0,
            "errors": []
        }
        
        try:
            # 1. 결제 예정자 알림 (3일 전, 1일 전)
            reminder_count = self._send_upcoming_payment_reminders(today)
            results["reminder_sent"] = reminder_count
            
            # 2. 연체자 처리 (결제일 지난 후 3일)
            overdue_count = self._process_overdue_payments(today)
            results["overdue_processed"] = overdue_count
            
            logger.info(f"월회비 알림 처리 완료: 알림 {reminder_count}건, 연체처리 {overdue_count}건")
            
        except Exception as e:
            logger.error(f"월회비 알림 처리 중 오류: {e}")
            results["errors"].append(str(e))
        
        return results
    
    def _send_upcoming_payment_reminders(self, today: date) -> int:
        """다가오는 결제에 대한 알림 발송"""
        reminder_dates = [
            today + timedelta(days=3),  # 3일 후 결제 예정
            today + timedelta(days=1),  # 1일 후 결제 예정
        ]
        
        sent_count = 0
        
        for reminder_date in reminder_dates:
            days_left = (reminder_date - today).days
            
            # 해당 날짜에 결제 예정인 월회비 참가자 조회
            participants = self.db.query(Participation).join(
                Challenge, Participation.challenge_id == Challenge.id
            ).filter(
                and_(
                    Participation.payment_cycle == PaymentCycle.monthly,
                    Participation.status == ParticipationStatus.active,
                    Participation.next_payment_date == reminder_date,
                    Challenge.status == ChallengeStatus.active,
                    Challenge.is_deleted == False
                )
            ).all()
            
            for participation in participants:
                try:
                    self._send_payment_reminder(participation, days_left)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"결제 알림 발송 실패: user_id={participation.user_id}, challenge_id={participation.challenge_id}, error={e}")
        
        return sent_count
    
    def update_next_payment_after_round_complete(self, participation: Participation, completed_round_id: int) -> None:
        """회차 완료 후 다음 회차 결제일 업데이트"""
        if participation.payment_cycle != PaymentCycle.monthly:
            return
            
        challenge = self.db.query(Challenge).filter(Challenge.id == participation.challenge_id).first()
        if not challenge:
            return
            
        # 완료된 회차 이후의 다음 회차 찾기
        from app.models.challenge_round import ChallengeRound
        
        completed_round = self.db.query(ChallengeRound).filter(ChallengeRound.id == completed_round_id).first()
        if not completed_round:
            return
            
        next_round = self.db.query(ChallengeRound).filter(
            ChallengeRound.challenge_id == challenge.id,
            ChallengeRound.start_date > completed_round.start_date
        ).order_by(ChallengeRound.start_date.asc()).first()
        
        if next_round:
            participation.next_payment_date = next_round.start_date
            logger.info(f"회차 완료 후 다음 결제일 업데이트: user_id={participation.user_id}, completed_round_id={completed_round_id}, next_date={participation.next_payment_date}")
        else:
            # 마지막 회차 완료 - 결제일 제거
            participation.next_payment_date = None
            logger.info(f"마지막 회차 완료 - 결제 스케줄 종료: user_id={participation.user_id}, challenge_id={challenge.id}")
        
        self.db.commit()
    
    def _send_payment_reminder(self, participation: Participation, days_left: int):
        """개별 결제 알림 발송"""
        challenge = self.db.query(Challenge).filter(Challenge.id == participation.challenge_id).first()
        if not challenge:
            return
        
        # 중복 알림 방지 (당일 이미 같은 알림 발송했는지 확인)
        existing_notification = self.db.query(Notification).filter(
            and_(
                Notification.user_id == participation.user_id,
                Notification.type == NotificationEvent.payment_reminder,
                Notification.created_at >= datetime.now(timezone.utc).date(),
                Notification.extra_data.contains(f'"challenge_id":{challenge.id}'),
                Notification.extra_data.contains(f'"days_left":{days_left}')
            )
        ).first()
        
        if existing_notification:
            return  # 이미 발송됨
        
        # 알림 메시지 생성
        if days_left == 1:
            title = "내일 월회비 결제 예정 📅"
            message = f"'{challenge.title}' 월회비 {challenge.monthly_fee:,}원이 내일 결제됩니다."
        else:
            title = f"{days_left}일 후 월회비 결제 예정 📅"
            message = f"'{challenge.title}' 월회비 {challenge.monthly_fee:,}원이 {days_left}일 후 결제됩니다."
        
        # 알림 생성
        notification = Notification(
            user_id=participation.user_id,
            type=NotificationEvent.payment_reminder,
            title=title,
            message=message,
            action_url=f"/pages/challenges/{challenge.id}",
            extra_data={
                "challenge_id": challenge.id,
                "payment_amount": challenge.monthly_fee,
                "payment_date": participation.next_payment_date.isoformat(),
                "days_left": days_left
            }
        )
        
        self.db.add(notification)
        self.db.commit()
        
        logger.info(f"결제 알림 발송: user_id={participation.user_id}, challenge='{challenge.title}', days_left={days_left}")
    
    def _process_overdue_payments(self, today: date) -> int:
        """연체된 결제 처리"""
        overdue_date = today - timedelta(days=3)  # 3일 지난 결제
        
        # 연체된 월회비 참가자 조회
        overdue_participants = self.db.query(Participation).join(
            Challenge, Participation.challenge_id == Challenge.id
        ).filter(
            and_(
                Participation.payment_cycle == PaymentCycle.monthly,
                Participation.status == ParticipationStatus.active,
                Participation.next_payment_date <= overdue_date,
                Challenge.status == ChallengeStatus.active,
                Challenge.is_deleted == False
            )
        ).all()
        
        processed_count = 0
        
        for participation in overdue_participants:
            try:
                self._handle_overdue_payment(participation)
                processed_count += 1
            except Exception as e:
                logger.error(f"연체 처리 실패: user_id={participation.user_id}, challenge_id={participation.challenge_id}, error={e}")
        
        return processed_count
    
    def _handle_overdue_payment(self, participation: Participation):
        """연체된 결제 처리"""
        challenge = self.db.query(Challenge).filter(Challenge.id == participation.challenge_id).first()
        if not challenge:
            return
        
        # 결제 실패 횟수 증가
        participation.payment_failed_count += 1
        
        if participation.payment_failed_count >= 3:
            # 3회 실패 시 자동 탈퇴
            participation.status = ParticipationStatus.payment_failed
            participation.left_at = datetime.now(timezone.utc)
            participation.leave_reason = "월회비 3회 연속 결제 실패로 인한 자동 탈퇴"
            
            # 챌린지 참가자 수 감소
            challenge.current_participants = max(0, challenge.current_participants - 1)
            
            # 탈퇴 알림
            notification = Notification(
                user_id=participation.user_id,
                type=NotificationEvent.participation_removed,
                title="챌린지 자동 탈퇴 알림 ⚠️",
                message=f"'{challenge.title}'에서 월회비 연체로 인해 자동 탈퇴되었습니다. 재참여를 원하시면 다시 신청해주세요.",
                action_url=f"/pages/challenges/{challenge.id}"
            )
            self.db.add(notification)
            
            logger.warning(f"월회비 연체로 자동 탈퇴: user_id={participation.user_id}, challenge='{challenge.title}'")
        else:
            # 다음 결제일 연장 (7일 후)
            participation.next_payment_date = date.today() + timedelta(days=7)
            
            # 연체 알림
            notification = Notification(
                user_id=participation.user_id,
                type=NotificationEvent.payment_reminder,
                title=f"월회비 연체 알림 ({participation.payment_failed_count}/3) ⚠️",
                message=f"'{challenge.title}' 월회비 결제가 연체되었습니다. 7일 내 결제하지 않으면 자동 탈퇴됩니다.",
                action_url=f"/pages/challenges/{challenge.id}",
                extra_data={
                    "challenge_id": challenge.id,
                    "payment_amount": challenge.monthly_fee,
                    "failed_count": participation.payment_failed_count,
                    "next_payment_date": participation.next_payment_date.isoformat()
                }
            )
            self.db.add(notification)
            
            logger.info(f"월회비 연체 알림: user_id={participation.user_id}, failed_count={participation.payment_failed_count}")
        
        self.db.commit()
    
    def set_next_payment_date(self, participation: Participation, challenge: Challenge) -> None:
        """다음 결제일 설정 (월회비 = 회차별 결제)"""
        if participation.payment_cycle != PaymentCycle.monthly:
            return
        
        # 다음 회차의 시작일을 찾기
        from app.models.challenge_round import ChallengeRound
        from sqlalchemy import desc
        
        # 가장 가까운 미래의 회차 찾기
        next_round = self.db.query(ChallengeRound).filter(
            ChallengeRound.challenge_id == challenge.id,
            ChallengeRound.start_date > date.today()
        ).order_by(ChallengeRound.start_date.asc()).first()
        
        if next_round:
            # 다음 회차 시작일을 결제일로 설정
            participation.next_payment_date = next_round.start_date
            logger.info(f"다음 월회비(회차별) 결제일 설정: user_id={participation.user_id}, challenge_id={challenge.id}, next_date={participation.next_payment_date}, round_id={next_round.id}")
        else:
            # 회차가 없으면 챌린지 시작일 기준으로
            if challenge.start_date > date.today():
                participation.next_payment_date = challenge.start_date
                logger.info(f"첫 월회비 결제일을 챌린지 시작일로 설정: user_id={participation.user_id}, challenge_id={challenge.id}, next_date={participation.next_payment_date}")
            else:
                # 챌린지가 이미 시작됐으면 즉시 결제 필요
                participation.next_payment_date = date.today()
                logger.info(f"이미 시작된 챌린지 - 즉시 월회비 결제 필요: user_id={participation.user_id}, challenge_id={challenge.id}")


def get_payment_reminder_service(db: Session) -> PaymentReminderService:
    """PaymentReminderService 의존성 주입"""
    return PaymentReminderService(db)