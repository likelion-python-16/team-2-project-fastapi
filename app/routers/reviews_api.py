from __future__ import annotations
from typing import List, Optional
from functools import lru_cache
from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.config import settings
from datetime import datetime, timedelta, timezone, date
from app.security import get_current_user
from app.models.user import User
from app.models.review import Review, ReviewHelpful, ReviewStatus
from app.models.notification import Notification, NotificationEvent
from app.models.challenge import Challenge
from app.models.challenge_round import ChallengeRound
from app.models.participation import Participation
from app.schemas.reviews import ReviewCreate, ReviewUpdate, ReviewOut, ReviewList

router = APIRouter(tags=["Reviews"])  # prefix 는 main.py 에서 /api/v1 로 묶음
logger = logging.getLogger(__name__)


# ---- helpers ---------------------------------------------------------------
def _to_review_out(m: Review) -> ReviewOut:
    return ReviewOut(
        id=m.id,
        user_id=m.user_id,
        challenge_id=m.challenge_id,
        round_id=m.round_id,
        rating=float(m.rating or 0),
        comment=m.comment,
        helpful_count=int(m.helpful_count or 0),
        status=m.status.value if hasattr(m.status, "value") else str(m.status),
        images=(m.images_json if isinstance(m.images_json, list) else (m.images_json or None)),
        created_at=m.created_at,
        updated_at=m.updated_at,
        target_user_id=getattr(m, 'target_user_id', None),
        target_user_name=(getattr(m, 'target_user', None).name if getattr(m, 'target_user', None) is not None else None),
    )


# ---- profanity check (LOL list) --------------------------------------------
@lru_cache(maxsize=1)
def _load_lol_banned_words() -> list[str]:
    """리그오브레전드 필터 리스트를 여러 후보 경로에서 탐색하여 로드.
    우선순위:
      1) 프로젝트 루트/team-2-project-fastapi/리그오브레전드_필터링리스트_2020.txt
      2) 워크스페이스 루트/리그오브레전드_필터링리스트_2020.txt (프로젝트 폴더 바깥)
      3) 프로젝트 루트/data/리그오브레전드_필터링리스트_2020.txt
    """
    here = Path(__file__).resolve()
    project_root = here.parents[2]  # .../team-2-project-fastapi
    ws_root = project_root.parent   # .../ (workspace root)
    candidates = [
        project_root / "리그오브레전드_필터링리스트_2020.txt",
        ws_root / "리그오브레전드_필터링리스트_2020.txt",
        project_root / "data" / "리그오브레전드_필터링리스트_2020.txt",
        project_root / "data" / "lol_profanity_ko.txt",
    ]
    words: list[str] = []
    for path in candidates:
        try:
            if path.exists():
                data = path.read_text(encoding="utf-8", errors="ignore")
                for line in data.splitlines():
                    w = (line or "").strip()
                    if not w or w.startswith("#"):
                        continue
                    words.append(w)
                break
        except Exception:
            continue
    if not words:
        # 최소 안전망: 한국어 상용 금칙어 몇 개(요청 케이스 대응)
        words = [
            "병신", "씨발", "좆", "개새", "개새끼", "꺼져", "fuck", "bitch", "idiot"
        ]
    return words


def _contains_banned(text: str) -> tuple[bool, list[str]]:
    t = (text or "").strip()
    if not t:
        return False, []
    t_low = t.lower()
    hits: list[str] = []
    for w in _load_lol_banned_words():
        if not w:
            continue
        wl = w.lower()
        if wl in t_low:
            hits.append(w)
            if len(hits) >= 10:
                break
    return (len(hits) > 0), hits


class ProfanityCheckIn(BaseModel):
    text: str


@router.post("/moderation/profanity-check")
def profanity_check(payload: ProfanityCheckIn):
    blocked, matches = _contains_banned(payload.text)
    return {"blocked": blocked, "matched": matches, "count": len(matches)}


def _ensure_challenge_exists(db: Session, challenge_id: int) -> None:
    if not db.query(Challenge.id).filter(Challenge.id == challenge_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다")


def _recompute_manner_score(db: Session, target_user_id: int) -> None:
    """리뷰 평균을 30~100 스케일로 환산해 매너점수 갱신.
    - 1★ → 30점, 5★ → 100점 선형 매핑
    - 리뷰가 없으면 30점 유지
    """
    avg_cnt = db.query(func.avg(Review.rating), func.count(Review.id)).filter(
        Review.target_user_id == target_user_id,
        Review.status != ReviewStatus.deleted,
    ).first()
    avg_rating = float(avg_cnt[0] or 0.0)
    cnt = int(avg_cnt[1] or 0)
    score = 30.0 if cnt == 0 else (30.0 + (max(1.0, min(5.0, avg_rating)) - 1.0) / 4.0 * 70.0)
    u = db.query(User).filter(User.id == target_user_id).first()
    if u is not None:
        u.manner_score = max(0.0, min(100.0, round(score)))
        db.commit()


# ---- endpoints -------------------------------------------------------------
@router.post("/challenges/{challenge_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    challenge_id: int,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_challenge_exists(db, challenge_id)

    # 서버 측 욕설/금칙어 차단 (프론트 우회 방지)
    text_for_check = (payload.comment or "").strip()
    blocked, _matches = _contains_banned(text_for_check)
    if blocked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="욕설 사용시 리뷰쓰기가 불가능합니다.")

    # 한 유저가 같은 대상자에게 한 챌린지에서 1회 제한
    exists = db.query(Review.id).filter(
        Review.user_id == current_user.id, 
        Review.challenge_id == challenge_id,
        Review.target_user_id == payload.target_id
    ).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 해당 대상에게 리뷰를 작성했습니다")

    # 마감/개시 검증 (종료 후 ~ n일 이내) - 테스트를 위해 임시 비활성화
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다")
    # 테스트를 위해 날짜 검증 비활성화
    # if ch.end_date:
    #     today = date.today()
    #     if today < ch.end_date:
    #         raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="챌린지가 아직 종료되지 않았습니다")
    #     if today > (ch.end_date + timedelta(days=settings.review_deadline_days)):
    #         raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"리뷰 작성 기한({settings.review_deadline_days}일)이 지났습니다")

    m = Review(
        user_id=current_user.id,
        target_user_id=payload.target_id,  # 리뷰 대상자
        challenge_id=challenge_id,
        round_id=payload.round_id,
        rating=float(payload.rating),
        comment=payload.comment,
        images_json=payload.images,
        status=ReviewStatus.visible,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    # 매너점수 업데이트 (리뷰 대상자가 있는 경우)
    if payload.target_id:
        try:
            _recompute_manner_score(db, int(payload.target_id))
        except Exception:
            pass
    # 알림 생성(작성자/대상자)
    try:
        logger.info(f"Creating notifications for review {m.id}")
        db.add(Notification(
            user_id=current_user.id,
            title="✍️ 리뷰 작성 완료",
            content=f"대상 ID {payload.target_id}에게 {float(payload.rating)}점 리뷰를 작성했습니다.",
            event_type=NotificationEvent.review_created,
            target_type="review",
            target_id=m.id,
        ))
        if payload.target_id:
            logger.info(f"Creating notification for target user {payload.target_id}")
            db.add(Notification(
                user_id=int(payload.target_id),
                title="⭐ 새로운 리뷰 도착",
                content=f"{current_user.name or current_user.username}님이 {float(payload.rating)}점 리뷰를 남겼습니다.",
                event_type=NotificationEvent.review_received,
                target_type="review",
                target_id=m.id,
            ))
        db.commit()
        logger.info("Notifications created successfully")
    except Exception as e:
        logger.error(f"Failed to create notifications: {e}")
        db.rollback()
    
    return _to_review_out(m)


@router.get("/challenges/{challenge_id}/reviews", response_model=ReviewList)
def list_reviews(
    challenge_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    order: str = Query("-created_at", description="-helpful | rating | -rating | -created_at"),
    db: Session = Depends(get_db),
):
    _ensure_challenge_exists(db, challenge_id)

    q = db.query(Review).filter(Review.challenge_id == challenge_id, Review.status == ReviewStatus.visible)
    if order == "-helpful":
        q = q.order_by(Review.helpful_count.desc(), Review.id.desc())
    elif order == "rating":
        q = q.order_by(Review.rating.asc(), Review.id.desc())
    elif order == "-rating":
        q = q.order_by(Review.rating.desc(), Review.id.desc())
    else:
        q = q.order_by(Review.id.desc())

    total = db.query(func.count()).select_from(Review).filter(
        Review.challenge_id == challenge_id, Review.status == ReviewStatus.visible
    ).scalar() or 0

    items = q.limit(size).offset((page - 1) * size).all()
    return ReviewList(total=int(total), items=[_to_review_out(m) for m in items])


@router.get("/me/challenges/completed")
def my_completed_challenges(
    challenge_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """완료된 챌린지 목록.

    - query.challenge_id 가 주어지면 '연결 여부와 무관하게' 해당 챌린지의 완료 여부만 판단해 반환(테스트 편의)
    - 아니면 로그인 사용자가 '참여했거나 생성한' 챌린지 중 완료된 것만 반환
    완료 판단: end_date <= 오늘 OR status == 'completed'
    """
    today = date.today()
    if challenge_id:
        ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        rows = []
        if ch and ((ch.end_date is not None and ch.end_date <= today) or (ch.status == "completed")):
            rows = [ch]
    else:
        q = (
            db.query(Challenge)
            .outerjoin(Participation, Participation.challenge_id == Challenge.id)
            .filter(
                (Participation.user_id == current_user.id) | (Challenge.creator_id == current_user.id)
            )
            .filter(
                ((Challenge.end_date.isnot(None)) & (Challenge.end_date <= today)) |
                (Challenge.status == "completed")
            )
            .order_by(Challenge.end_date.desc(), Challenge.created_at.desc())
            .distinct(Challenge.id)
        )
        rows = q.all()
    def to_dict(c: Challenge):
        return {
            "id": c.id,
            "title": c.title,
            "start_date": c.start_date,
            "end_date": c.end_date,
            "status": c.status,
            "created_at": getattr(c, "created_at", None),
        }
    return {"items": [to_dict(c) for c in rows]}


@router.post("/challenges/{challenge_id}/force-complete")
def force_complete_challenge_for_me(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """개발 편의용: 현재 사용자 기준으로 챌린지를 테스트 완료 상태로 강제 설정.

    - settings.debug 가 True 일 때만 허용
    - end_date = 어제, status = 'completed'
    - creator_id 가 비어 있으면 현재 사용자로 설정
    - 참여 레코드가 없으면 1건 생성
    """
    if not settings.debug:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="개발 모드에서만 사용할 수 있습니다")

    ch: Challenge | None = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다")

    ch.end_date = date.today() - timedelta(days=1)
    ch.status = "completed"
    if not getattr(ch, "creator_id", None):
        ch.creator_id = current_user.id

    exists = (
        db.query(Participation.id)
        .filter(Participation.user_id == current_user.id, Participation.challenge_id == challenge_id)
        .first()
    )
    if not exists:
        db.add(Participation(user_id=current_user.id, challenge_id=challenge_id, status="active", is_active=True))

    db.commit()
    db.refresh(ch)
    return {
        "id": ch.id,
        "title": ch.title,
        "end_date": ch.end_date,
        "status": ch.status,
        "creator_id": ch.creator_id,
        "linked": True,
    }


@router.patch("/reviews/{review_id}", response_model=ReviewOut)
def update_review(
    review_id: int,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m: Optional[Review] = db.query(Review).filter(Review.id == review_id, Review.status != ReviewStatus.deleted).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="리뷰를 찾을 수 없습니다")
    if m.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="본인 리뷰만 수정할 수 있습니다")

    # 수정 가능 시간 제한
    if m.created_at:
        now = datetime.now(timezone.utc)
        created = m.created_at if m.created_at.tzinfo else m.created_at.replace(tzinfo=timezone.utc)
        gap = now - created
        edit_window_hours = getattr(settings, 'review_edit_window_hours', 24)  # 기본값 24시간
        if gap > timedelta(hours=edit_window_hours):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"작성 후 {edit_window_hours}시간이 지나 수정할 수 없습니다")

    if payload.rating is not None:
        m.rating = float(payload.rating)
    if payload.comment is not None:
        m.comment = payload.comment
    if payload.images is not None:
        m.images_json = payload.images

    db.commit()
    db.refresh(m)
    # 대상자 매너 점수 재계산
    try:
        if getattr(m, 'target_user_id', None):
            _recompute_manner_score(db, int(m.target_user_id))
    except Exception:
        pass
    return _to_review_out(m)


@router.delete("/reviews/{review_id}")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """리뷰 삭제"""
    m: Optional[Review] = db.query(Review).filter(Review.id == review_id, Review.status != ReviewStatus.deleted).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="리뷰를 찾을 수 없습니다")
    if m.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="본인 리뷰만 삭제할 수 있습니다")

    # 소프트 삭제 처리
    m.status = ReviewStatus.deleted
    m.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    # 대상자 매너 점수 재계산
    try:
        if getattr(m, 'target_user_id', None):
            _recompute_manner_score(db, int(m.target_user_id))
    except Exception:
        pass
    return {"message": "리뷰가 삭제되었습니다", "review_id": review_id}


@router.post("/reviews/{review_id}/helpful")
def toggle_helpful(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m: Optional[Review] = db.query(Review).filter(Review.id == review_id, Review.status == ReviewStatus.visible).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="리뷰를 찾을 수 없습니다")
    if m.user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="본인 리뷰에는 표시할 수 없습니다")

    existing = db.query(ReviewHelpful).filter(
        ReviewHelpful.review_id == review_id, ReviewHelpful.user_id == current_user.id
    ).first()
    if existing:
        db.delete(existing)
        m.helpful_count = max(0, int(m.helpful_count or 0) - 1)
        db.commit()
        return {"helpful": False, "helpful_count": m.helpful_count}
    else:
        db.add(ReviewHelpful(review_id=review_id, user_id=current_user.id))
        m.helpful_count = int(m.helpful_count or 0) + 1
        db.commit()
        return {"helpful": True, "helpful_count": m.helpful_count}


@router.get("/challenges/{challenge_id}/reviews/mine")
def has_my_review(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = db.query(Review).filter(Review.challenge_id == challenge_id, Review.user_id == current_user.id, Review.status != ReviewStatus.deleted).first()
    return {"has": bool(m), "review": (_to_review_out(m) if m else None)}


@router.get("/challenges/{challenge_id}/reviews/my-reviewed-users")
def my_reviewed_users(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내가 리뷰한 사용자들의 target_user_id 목록 반환"""
    reviews = db.query(Review.target_user_id).filter(
        Review.challenge_id == challenge_id,
        Review.user_id == current_user.id,
        Review.target_user_id.isnot(None),
        Review.status != ReviewStatus.deleted
    ).all()
    
    reviewed_user_ids = [r[0] for r in reviews if r[0] is not None]
    return {"reviewed_user_ids": reviewed_user_ids}


@router.get("/reviews/my", response_model=ReviewList)
def my_reviews(
    challenge_id: int | None = Query(default=None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Review).filter(Review.user_id == current_user.id, Review.status != ReviewStatus.deleted)
    if challenge_id:
        q = q.filter(Review.challenge_id == challenge_id)
    total = q.count()
    items = q.order_by(Review.id.desc()).limit(size).offset((page-1)*size).all()
    return ReviewList(total=int(total), items=[_to_review_out(m) for m in items])


@router.get("/reviews/received", response_model=ReviewList)
def received_reviews(
    challenge_id: int | None = Query(default=None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내가 받은 리뷰들 조회"""
    q = db.query(Review).filter(Review.target_user_id == current_user.id, Review.status == ReviewStatus.visible)
    if challenge_id:
        q = q.filter(Review.challenge_id == challenge_id)
    total = q.count()
    items = q.order_by(Review.id.desc()).limit(size).offset((page-1)*size).all()
    return ReviewList(total=int(total), items=[_to_review_out(m) for m in items])
