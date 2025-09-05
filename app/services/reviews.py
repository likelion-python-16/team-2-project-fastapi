from datetime import datetime, time, timedelta, timezone
from sqlalchemy import select, func, and_, or_, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewStatus
from app.models.challenge import Challenge              # end_date(Date)
from app.models.challenge_round import ChallengeRound   # processing_at(Date), finish_time(Time)
from app.models.user import User

# 있을 수도/없을 수도 있는 모델: try-import
try:
    from app.models.participation import Participation
except Exception:
    Participation = None

try:
    from app.models.attendance import RoundAttendance
except Exception:
    RoundAttendance = None



from app.core.config import REVIEW_DEADLINE_DAYS, REVIEW_EDIT_WINDOW_HOURS

# ── 내부 유틸 ────────────────────────────────────────────────────────────────
def _as_aware(dt: datetime) -> datetime:
    # 서버 naive datetime이면 UTC 부여(필요시 프로젝트 TZ로 교체)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ── 챌린지 종료 시각 계산 ───────────────────────────────────────────────────
async def _get_challenge_end_at(db: AsyncSession, challenge_id: int) -> datetime | None:
    # 1) Challenge.end_date(날짜) 있으면 그 날 23:59:59 를 종료시각으로
    q = await db.execute(select(Challenge.end_date).where(Challenge.id == challenge_id))
    end_date = q.scalar_one_or_none()
    if end_date:
        end_dt = datetime.combine(end_date, time(23, 59, 59))
        return _as_aware(end_dt)

    # 2) 없다면 라운드의 (processing_at + finish_time) 중 가장 늦은 시각
    q2 = await db.execute(
        select(func.max(ChallengeRound.processing_at)).where(ChallengeRound.challenge_id == challenge_id)
    )
    last_date = q2.scalar_one_or_none()
    if last_date:
        q3 = await db.execute(
            select(func.max(ChallengeRound.finish_time)).where(
                ChallengeRound.challenge_id == challenge_id,
                ChallengeRound.processing_at == last_date,
            )
        )
        last_finish = q3.scalar_one_or_none() or time(23, 59, 59)
        end_dt = datetime.combine(last_date, last_finish)
        return _as_aware(end_dt)

    return None


# ── 유저가 챌린지를 완료했는지 판정 (실행 우선, 존재 컬럼만 활용) ───────────────
async def _user_completed_challenge(db: AsyncSession, user_id: int, challenge_id: int) -> bool:
    # 라운드 수(기준치)
    q_rounds = await db.execute(
        select(func.count()).select_from(ChallengeRound).where(ChallengeRound.challenge_id == challenge_id)
    )
    rounds_cnt = q_rounds.scalar() or 0

    # 1) Participation 기반 (가장 명확)
    if Participation is not None:
        conds = [Participation.user_id == user_id, Participation.challenge_id == challenge_id]
        completion_or = []
        if hasattr(Participation, "is_completed"):
            completion_or.append(getattr(Participation, "is_completed") == True)  # noqa: E712
        if hasattr(Participation, "status"):
            completion_or.append(getattr(Participation, "status").in_(["completed", "success", "done"]))
        where_clause = and_(*conds, or_(*completion_or)) if completion_or else and_(*conds)
        q = await db.execute(select(func.count()).select_from(Participation).where(where_clause))
        if (q.scalar() or 0) > 0:
            return True

    # 2) RoundAttendance 기반: 전 회차 출석/완료(존재 시)
    if RoundAttendance is not None and rounds_cnt > 0:
        flags = []
        if hasattr(RoundAttendance, "is_present"):
            flags.append(getattr(RoundAttendance, "is_present") == True)
        if hasattr(RoundAttendance, "status"):
            flags.append(getattr(RoundAttendance, "status").in_(["present", "completed", "success"]))
        where_flag = or_(*flags) if flags else literal(True)

        q = await db.execute(
            select(func.count()).select_from(RoundAttendance).where(
                RoundAttendance.user_id == user_id,
                RoundAttendance.challenge_id == challenge_id,
                where_flag,
            )
        )
        attended = q.scalar() or 0
        if attended >= rounds_cnt:
            return True

    # 3) 최소 완화: 참여 레코드만 존재해도 완료로 취급 (마감 로직 때문에 너무 타이트하면 작성 못함)
    if Participation is not None:
        q = await db.execute(
            select(func.count()).select_from(Participation).where(
                Participation.user_id == user_id, Participation.challenge_id == challenge_id
            )
        )
        if (q.scalar() or 0) > 0:
            return True

    return False


# ── 비즈니스 검증 & CRUD ────────────────────────────────────────────────────
async def validate_can_create_review(db: AsyncSession, user_id: int, challenge_id: int):
    end_at = await _get_challenge_end_at(db, challenge_id)
    if not end_at:
        raise ValueError("챌린지를 찾을 수 없거나 종료시각을 알 수 없습니다.")

    now = datetime.now(timezone.utc)
    if now < end_at:
        raise PermissionError("챌린지가 아직 종료되지 않았습니다.")
    if now > end_at + timedelta(days=REVIEW_DEADLINE_DAYS):
        raise PermissionError(f"리뷰 작성 기한({REVIEW_DEADLINE_DAYS}일)이 지났습니다.")

    if not await _user_completed_challenge(db, user_id, challenge_id):
        raise PermissionError("챌린지를 완료한 유저만 리뷰를 작성할 수 있습니다.")

    # 유저×챌린지 중복 방지(서비스 레벨 이중 방어)
    exists_q = await db.execute(
        select(func.count()).select_from(Review).where(
            Review.user_id == user_id, Review.challenge_id == challenge_id
        )
    )
    if (exists_q.scalar() or 0) > 0:
        raise PermissionError("같은 챌린지에는 리뷰를 1회만 작성할 수 있습니다.")


async def create_review(db: AsyncSession, user_id: int, challenge_id: int, payload) -> Review:
    await validate_can_create_review(db, user_id, challenge_id)
    review = Review(
        user_id=user_id,
        challenge_id=challenge_id,
        round_id=getattr(payload, "round_id", None),
        rating=float(payload.rating),
        comment=getattr(payload, "comment", None),
        images_json=getattr(payload, "images", None),
        status=ReviewStatus.visible,
        target_user_id=getattr(payload, "target_user_id", None),
    )
    db.add(review)
    try:
        await db.commit()
        await db.refresh(review)
        
        # 매너점수 업데이트 (리뷰 대상자가 있는 경우)
        if review.target_user_id:
            await update_manner_score_from_review(db, review.target_user_id, review.rating)
            
    except IntegrityError:
        await db.rollback()
        raise PermissionError("이미 해당 챌린지에 리뷰를 작성했습니다.")
    return review


async def get_review(db: AsyncSession, review_id: int) -> Review | None:
    q = await db.execute(select(Review).where(Review.id == review_id, Review.status != ReviewStatus.deleted))
    return q.scalar_one_or_none()


async def validate_can_edit_review(review: Review, current_user_id: int):
    if review.user_id != current_user_id:
        raise PermissionError("본인 리뷰만 수정할 수 있습니다.")
    now = datetime.now(timezone.utc)
    if (now - review.created_at) > timedelta(hours=REVIEW_EDIT_WINDOW_HOURS):
        raise PermissionError("작성 후 24시간이 지나 수정할 수 없습니다.")


async def update_review(db: AsyncSession, review_id: int, current_user_id: int, payload) -> Review:
    review = await get_review(db, review_id)
    if not review:
        raise ValueError("리뷰를 찾을 수 없습니다.")
    await validate_can_edit_review(review, current_user_id)

    if getattr(payload, "rating", None) is not None:
        review.rating = float(payload.rating)
    if hasattr(payload, "comment"):
        review.comment = payload.comment
    if hasattr(payload, "images"):
        review.images_json = payload.images

    await db.commit()
    await db.refresh(review)
    return review


async def list_reviews_by_challenge(
    db: AsyncSession, challenge_id: int, page: int = 1, size: int = 10, order: str = "-created_at"
):
    base = select(Review).where(Review.challenge_id == challenge_id, Review.status == ReviewStatus.visible)

    if order == "-helpful":
        base = base.order_by(Review.helpful_count.desc(), Review.id.desc())
    elif order == "rating":
        base = base.order_by(Review.rating.asc(), Review.id.desc())
    elif order == "-rating":
        base = base.order_by(Review.rating.desc(), Review.id.desc())
    else:
        base = base.order_by(Review.id.desc())  # 최신순

    total_q = await db.execute(
        select(func.count()).select_from(Review).where(
            Review.challenge_id == challenge_id, Review.status == ReviewStatus.visible
        )
    )
    total = total_q.scalar() or 0

    q = await db.execute(base.limit(size).offset((page - 1) * size))
    items = q.scalars().all()
    return total, items

def get_reviewed_target_ids(db: Session, author_id: int, challenge_id: int) -> set[int]:
    """
    특정 author(로그인 유저)가 특정 challenge에서 이미 리뷰한 target_id들의 집합.
    """
    rows = db.execute(
        select(Review.target_user_id).where(
            Review.user_id == author_id,
            Review.challenge_id == challenge_id,
        )
    ).all()
    return {r[0] for r in rows}


async def update_manner_score_from_review(db: AsyncSession, target_user_id: int, rating: float):
    """리뷰 별점을 기반으로 매너점수 업데이트"""
    user_q = await db.execute(select(User).where(User.id == target_user_id))
    user = user_q.scalar_one_or_none()
    
    if user:
        score_change = user.calculate_manner_score_from_rating(rating)
        user.update_manner_score(score_change)
        await db.commit()