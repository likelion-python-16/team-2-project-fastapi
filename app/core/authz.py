#core.autz.py
from sqlalchemy.orm import Session
from app.models.challenge import Challenge
from app.models.participation import Participation, ParticipationRole
from app.models.round_manager import RoundManager

def is_challenge_owner(db: Session, challenge_id: int, user_id: int) -> bool:
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    return bool(ch and ch.creator_id == user_id)

def is_challenge_manager(db: Session, challenge_id: int, user_id: int) -> bool:
    # 참고: 현재 정책상 편집 권한엔 사용하지 않지만, 다른 곳에서 쓸 수 있으니 유지
    p = (db.query(Participation)
         .filter(Participation.challenge_id == challenge_id,
                 Participation.user_id == user_id,
                 Participation.role == ParticipationRole.manager,
                 Participation.is_active == True)
         .first())
    return p is not None

def is_round_manager(db: Session, challenge_id: int, round_id: int, user_id: int) -> bool:
    rm = (db.query(RoundManager)
          .filter(RoundManager.challenge_id == challenge_id,
                  RoundManager.round_id == round_id,
                  RoundManager.user_id == user_id)
          .first())
    return rm is not None

def can_edit_round(db: Session, challenge_id: int, round_id: int | None, user_id: int) -> bool:
    # ✅ creator는 항상 허용
    if is_challenge_owner(db, challenge_id, user_id):
        return True
    # ✅ 회차 생성은 creator만 가능 (round_id=None)
    if round_id is None:
        return False
    # ✅ 해당 회차의 round_manager만 편집 가능
    return is_round_manager(db, challenge_id, round_id, user_id)
