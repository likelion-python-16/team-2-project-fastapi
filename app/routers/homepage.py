from datetime import date, timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.models.user import User
from app.models.challenge import Challenge
from app.models.tag import Tag, UserTag, ChallengeTag
from app.models.challenge_round import ChallengeRound

from app.security import verify_token
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/v1/home", tags=["Home"])

# --- optional current user (security.py 변경 없이) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = verify_token(token)
    if not payload or "sub" not in payload:
        return None
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        return None
    return user

# --- 카드 응답 스키마 ---
class ChallengeCard(BaseModel):
    id: int
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None       # 등록일 표시용 (프론트에서 사용)
    status: str
    fee_type: str
    participation_fee: int
    fee: int
    total_rounds: Optional[int] = None          # ✅ 총 회차 (추가)
    thumbnail_url: Optional[str] = None

    class Config:
        from_attributes = True

class HomeSectionsResponse(BaseModel):
    recommended: List[ChallengeCard] = []
    recommended_notice: Optional[str] = None
    followings: List[ChallengeCard] = []        # 로그인 사용 시 팔로우 섹션
    latest: List[ChallengeCard] = []
    ending_soon: List[ChallengeCard] = []
    latest_has_next: bool = False               # 프론트 Prev/Next 판정용

# --- 헬퍼: 여러 챌린지의 회차수 한번에 가져오기 ---
def get_round_counts(db: Session, challenge_ids: List[int]) -> Dict[int, int]:
    if not challenge_ids:
        return {}
    rows = (
        db.query(ChallengeRound.challenge_id, func.count(ChallengeRound.id))
        .filter(ChallengeRound.challenge_id.in_(challenge_ids))
        .group_by(ChallengeRound.challenge_id)
        .all()
    )
    return {cid: cnt for cid, cnt in rows}

# --- 헬퍼: 모델 -> 카드 변환 ---
def _to_card(ch: Challenge, rounds_count: Optional[int] = None) -> ChallengeCard:
    fee_val = (ch.fee or 0)
    part_fee_val = (ch.participation_fee or 0)
    fee_type = "유료" if (fee_val > 0 or part_fee_val > 0) else "무료"

    # total_rounds 우선순위: 명시된 total_rounds > 집계된 rounds_count
    total_rounds = ch.total_rounds if getattr(ch, "total_rounds", None) not in (None, 0) else rounds_count

    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        start_date=ch.start_date,
        end_date=ch.end_date,
        created_at=getattr(ch, "created_at", None),
        status=ch.status,
        fee_type=fee_type,
        participation_fee=part_fee_val,
        fee=fee_val,
        total_rounds=total_rounds,
        thumbnail_url=getattr(ch, "thumbnail_url", None),
    )

@router.get("/sections", response_model=HomeSectionsResponse, summary="홈 페이지 3구역 데이터")
def get_home_sections(
    latest_page: int = 1,
    latest_page_size: int = 12,   # 3x4
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    1) 추천 챌린지: 로그인 + 선호태그(UserTag) 기준 최신 생성순, 최대 6 (3x2)
       - 선호태그 없으면 안내문 표시
    2) 팔로잉 챌린지: 로그인 + 내가 팔로우한 유저들이 만든 챌린지 최신 생성순, 최대 6 (3x2)
       - 로그인 안 했으면 프론트에서 '로그인 필요' 배지 표시(이미 JS 처리)
    3) 최신 챌린지: 페이지네이션(페이지당 12), created_at DESC
    4) 마감 임박: 종료일 3일 이내 + recruiting, 최대 10 (프론트에선 6만 쓰기도 함)
    ※ 모든 카드에 total_rounds 채워서 반환
    """

    # -----------------------------
    # 1) 추천(선호태그 기반)
    # -----------------------------
    recommended_rows: List[Challenge] = []
    recommended_notice: Optional[str] = None

    if current_user:
        user_tag_ids_subq = (
            db.query(UserTag.tag_id).filter(UserTag.user_id == current_user.id).subquery()
        )
        user_has_tags = db.query(user_tag_ids_subq.exists()).scalar()
        if user_has_tags:
            recommended_rows = (
                db.query(Challenge)
                .join(ChallengeTag, ChallengeTag.challenge_id == Challenge.id)
                .filter(ChallengeTag.tag_id.in_(user_tag_ids_subq))
                .order_by(desc(Challenge.created_at))
                .limit(6)  # 3x2
                .all()
            )
        else:
            recommended_notice = "추천 기능을 위해 ‘선호 태그’를 등록해 주세요."
    else:
        recommended_notice = "추천 기능을 위해 ‘선호 태그’를 등록해 주세요."

    # 회차수 집계 & 매핑
    rec_ids = [c.id for c in recommended_rows]
    rec_counts = get_round_counts(db, rec_ids)
    recommended_cards = [_to_card(c, rec_counts.get(c.id)) for c in recommended_rows]

    # -----------------------------
    # 2) 팔로우한 사람이 만든 챌린지 (최신순)
    #    이 섹션은 별도 엔드포인트도 있지만, 홈에 함께 싣고 싶다면 여기서도 제공 가능
    # -----------------------------
    follow_cards: List[ChallengeCard] = []
    if current_user:
        # following 테이블: (follower_id -> followee_id)
        # 모델명이 Following이라면 import: from app.models.following import Following
        from app.models.following import Following  # 루프 상단 import를 피하기 위해 여기서 import

        followee_ids_subq = (
            db.query(Following.followee_id)
            .filter(Following.follower_id == current_user.id)
            .subquery()
        )
        follow_rows = (
            db.query(Challenge)
            .filter(Challenge.creator_id.in_(followee_ids_subq))
            .order_by(desc(Challenge.created_at))
            .limit(6)
            .all()
        )
        f_ids = [c.id for c in follow_rows]
        f_counts = get_round_counts(db, f_ids)
        follow_cards = [_to_card(c, f_counts.get(c.id)) for c in follow_rows]

    # -----------------------------
    # 3) 최신 챌린지 (페이지네이션)
    # -----------------------------
    latest_base = (
        db.query(Challenge)
        .order_by(desc(Challenge.created_at))
    )

    latest_rows = (
        latest_base
        .offset((max(latest_page,1) - 1) * latest_page_size)
        .limit(latest_page_size + 1)  # 다음 페이지 유무 확인 위해 +1
        .all()
    )
    latest_has_next = len(latest_rows) > latest_page_size
    latest_rows = latest_rows[:latest_page_size]

    l_ids = [c.id for c in latest_rows]
    l_counts = get_round_counts(db, l_ids)
    latest_cards = [_to_card(c, l_counts.get(c.id)) for c in latest_rows]

    # -----------------------------
    # 4) 마감 임박 (3일 이내, recruiting)
    # -----------------------------
    today = date.today()
    within_3 = today + timedelta(days=3)
    ending_rows = (
        db.query(Challenge)
        .filter(
            Challenge.status == "recruiting",
            Challenge.end_date.isnot(None),
            Challenge.end_date >= today,
            Challenge.end_date <= within_3,
        )
        .order_by(Challenge.end_date.asc(), Challenge.created_at.desc())
        .limit(10)
        .all()
    )
    e_ids = [c.id for c in ending_rows]
    e_counts = get_round_counts(db, e_ids)
    ending_cards = [_to_card(c, e_counts.get(c.id)) for c in ending_rows]

    return HomeSectionsResponse(
        recommended=recommended_cards,
        recommended_notice=recommended_notice,
        followings=follow_cards,
        latest=latest_cards,
        ending_soon=ending_cards,
        latest_has_next=latest_has_next,
    )