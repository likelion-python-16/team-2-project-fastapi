from datetime import date, timedelta, datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.models.user import User
from app.models.challenge import Challenge, ChallengeStatus  # ★ Enum 함께 임포트
from app.models.tag import UserTag, ChallengeTag
from app.models.challenge_round import ChallengeRound
from app.security import get_current_user_optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/home", tags=["Home"])


# --- 카드 응답 스키마 ---
class ChallengeCard(BaseModel):
    id: int
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None
    status: str
    fee_type: str
    participation_fee: int
    fee: int
    total_rounds: Optional[int] = None
    thumbnail_url: Optional[str] = None

    class Config:
        from_attributes = True

class HomeSectionsResponse(BaseModel):
    recommended: List[ChallengeCard] = []
    recommended_notice: Optional[str] = None
    followings: List[ChallengeCard] = []
    latest: List[ChallengeCard] = []
    ending_soon: List[ChallengeCard] = []
    latest_has_next: bool = False

# --- 여러 챌린지의 회차 수 한번에 가져오기 ---
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

# --- 모델 -> 카드 변환 ---
def _to_card(ch: Challenge, rounds_count: Optional[int] = None) -> ChallengeCard:
    # ★ 결제 방식에 따른 금액 표시 개선
    entry_fee_val = getattr(ch, "entry_fee", 0) or 0
    monthly_fee_val = getattr(ch, "monthly_fee", 0) or 0
    payment_type = getattr(ch, "payment_type", "free")
    
    # 레거시 필드도 지원
    part_fee_val = (
        getattr(ch, "participation_fee", None)
        or entry_fee_val
        or 0
    )
    fee_val = (
        getattr(ch, "fee", None)
        or monthly_fee_val
        or 0
    )
    
    # 결제 타입별 표시
    if payment_type == "free":
        fee_type = "무료"
    elif payment_type == "entry_fee":
        fee_type = f"입장비 {entry_fee_val:,}원"
    elif payment_type == "monthly_fee":
        fee_type = f"월회비 {monthly_fee_val:,}원"
    elif payment_type == "both":
        fee_type = f"입장비 {entry_fee_val:,}원 + 월회비 {monthly_fee_val:,}원"
    else:
        fee_type = "유료" if (fee_val > 0 or part_fee_val > 0) else "무료"

    # 총 회차: 명시된 total_rounds > 집계값
    total_rounds = (
        getattr(ch, "total_rounds", None) if getattr(ch, "total_rounds", None) not in (None, 0)
        else rounds_count
    )

    # ★ Enum 안전 처리: 문자열로 직렬화
    status_str = ch.status.value if hasattr(ch.status, "value") else str(ch.status)

    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        start_date=ch.start_date,
        end_date=ch.end_date,
        created_at=getattr(ch, "created_at", None),
        status=status_str,
        fee_type=fee_type,
        participation_fee=int(part_fee_val or 0),
        fee=int(fee_val or 0),
        total_rounds=total_rounds,
        thumbnail_url=getattr(ch, "thumbnail_url", None),
    )

@router.get("/recommended", summary="추천 챌린지")
def get_recommended_challenges(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """태그 기반 추천 챌린지 목록 반환"""
    try:
        from app.services.challenge_recommender import get_challenge_recommender
        
        recommender = get_challenge_recommender(db)
        
        if current_user:
            # 로그인한 사용자: 태그 기반 추천
            recommendations = recommender.get_tag_based_recommendations(current_user.id, limit=10)
            notice = None
            
            # 관심 태그 확인
            user_tags_count = db.query(UserTag).filter(UserTag.user_id == current_user.id).count()
            if user_tags_count == 0:
                notice = "💡 마이페이지에서 관심사를 설정하시면 더 정확한 추천을 받을 수 있어요!"
            elif any(r.get('tag_match_count', 0) > 0 for r in recommendations):
                notice = f"🎯 {current_user.username}님의 관심사에 맞는 챌린지를 추천했어요!"
        else:
            # 비로그인 사용자: 인기 챌린지
            recommendations = recommender.get_trending_challenges(limit=10)
            notice = "🔥 지금 인기있는 챌린지들이에요! 로그인하면 관심사 맞춤 추천을 받을 수 있어요."
        
        # 챌린지 카드 형태로 변환
        challenges = []
        for rec in recommendations:
            challenge = rec['challenge']
            
            # 추천 이유 텍스트 생성
            reasons = rec.get('reasons', [])
            recommendation_text = ' • '.join(reasons) if reasons else ''
            
            challenges.append({
                "id": challenge.id,
                "title": challenge.title,
                "description": challenge.description,
                "created_at": challenge.created_at.isoformat() if challenge.created_at else None,
                "current_participants": challenge.current_participants or 0,
                "payment_type": getattr(challenge, 'payment_type', 'free'),
                "entry_fee": getattr(challenge, 'entry_fee', 0),
                "monthly_fee": getattr(challenge, 'monthly_fee', 0),
                "recommendation_score": rec.get('similarity_score', 0),
                "recommendation_reasons": recommendation_text,
                "matched_tags": rec.get('matched_tags', [])
            })
        
        return {
            "success": True,
            "challenges": challenges,
            "notice": notice,
            "user_has_tags": current_user and user_tags_count > 0 if current_user else False
        }
    except Exception as e:
        # 오류 시 기본 인기 챌린지 반환
        try:
            challenges = db.query(Challenge).filter(
                Challenge.is_deleted == False,
                Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active])
            ).order_by(Challenge.current_participants.desc()).limit(10).all()
            
            return {
                "success": True,
                "challenges": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "description": c.description,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "current_participants": c.current_participants or 0,
                        "recommendation_reasons": "인기 챌린지"
                    } for c in challenges
                ],
                "notice": "⚠️ 추천 시스템에 일시적 문제가 있어 인기 챌린지를 보여드려요.",
                "error": str(e)
            }
        except Exception:
            return {"success": False, "challenges": [], "error": str(e)}

@router.get("/following", summary="팔로잉 챌린지")  
def get_following_challenges(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """팔로잉 중인 사용자들의 챌린지 목록"""
    try:
        if not current_user:
            return {"success": False, "challenges": [], "error": "로그인이 필요합니다"}
            
        # 간단히 최신 챌린지들 반환 (실제로는 팔로잉 로직 구현 필요)
        challenges = db.query(Challenge).filter(
            Challenge.is_deleted == False,
            Challenge.status == ChallengeStatus.active
        ).order_by(Challenge.created_at.desc()).limit(5).all()
        
        return {
            "success": True,
            "challenges": [
                {
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "creator_id": c.creator_id,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "status": c.status.value if hasattr(c.status, 'value') else c.status,
                    "mode": c.mode.value if hasattr(c.mode, 'value') else c.mode,
                    "payment_type": c.payment_type.value if hasattr(c.payment_type, 'value') else c.payment_type,
                    "entry_fee": getattr(c, 'entry_fee', 0) or 0,
                    "monthly_fee": getattr(c, 'monthly_fee', 0) or 0,
                    "current_participants": getattr(c, 'current_participants', 0) or 0,
                    "max_participants": getattr(c, 'max_participants', None),
                    "cover_image_url": getattr(c, 'cover_image_url', None),
                } for c in challenges
            ]
        }
    except Exception as e:
        return {"success": False, "challenges": [], "error": str(e)}

@router.get("/sections", response_model=HomeSectionsResponse, summary="홈 페이지 3구역 데이터")
def get_home_sections(
    latest_page: int = 1,
    latest_page_size: int = 12,   # 3x4
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    1) 추천: 로그인 + 선호태그(UserTag) 기준 최신 생성순, 최대 6 (3x2)
    2) 팔로워 챌린지: 로그인 + 내가 팔로우한 유저들의 최신 챌린지, 최대 6 (3x2)
    3) 최신 챌린지: 페이지네이션(12), created_at DESC
    4) 마감 임박: 종료일 3일 이내 + recruiting, 최대 10
    """

    # -----------------------------
    # 1) 태그 기반 추천 챌린지 (개선된 버전)
    # -----------------------------
    from app.services.challenge_recommender import get_challenge_recommender
    
    recommended_cards: List[ChallengeCard] = []
    recommended_notice: Optional[str] = None
    
    try:
        recommender = get_challenge_recommender(db)
        
        if current_user:
            # 로그인한 사용자: 태그 기반 추천
            recommendations = recommender.get_tag_based_recommendations(current_user.id, limit=6)
            
            # 관심 태그 확인
            user_tags_count = db.query(UserTag).filter(UserTag.user_id == current_user.id).count()
            if user_tags_count == 0:
                recommended_notice = "💡 마이페이지에서 관심사를 설정하면 맞춤 추천을 받을 수 있어요!"
            elif any(r.get('tag_match_count', 0) > 0 for r in recommendations):
                recommended_notice = f"🎯 {current_user.username}님 관심사 맞춤 추천"
        else:
            # 비로그인 사용자: 인기 챌린지
            recommendations = recommender.get_trending_challenges(limit=6)
            recommended_notice = "🔥 인기 챌린지 (로그인 시 맞춤 추천)"
        
        # ChallengeCard로 변환
        rec_challenges = [rec['challenge'] for rec in recommendations]
        rec_ids = [c.id for c in rec_challenges]
        rec_counts = get_round_counts(db, rec_ids)
        recommended_cards = [_to_card(c, rec_counts.get(c.id)) for c in rec_challenges]
        
    except Exception as e:
        # 오류 시 기본 최신 챌린지로 폴백
        recommended_rows = (
            db.query(Challenge)
            .filter(Challenge.is_deleted == False, Challenge.status == ChallengeStatus.recruiting)
            .order_by(desc(Challenge.created_at))
            .limit(6)
            .all()
        )
        rec_ids = [c.id for c in recommended_rows]
        rec_counts = get_round_counts(db, rec_ids)
        recommended_cards = [_to_card(c, rec_counts.get(c.id)) for c in recommended_rows]
        recommended_notice = "⚠️ 추천 시스템 일시 오류"

    # -----------------------------
    # 2) 팔로우한 사람이 만든 챌린지 (최신순)
    # -----------------------------
    follow_cards: List[ChallengeCard] = []
    if current_user:
        from app.models.following import Following  # 순환 임포트 회피

        followee_ids_subq = (
            db.query(Following.following_id)
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
    latest_base = db.query(Challenge).order_by(desc(Challenge.created_at))

    latest_rows = (
        latest_base
        .offset((max(latest_page, 1) - 1) * latest_page_size)
        .limit(latest_page_size + 1)  # 다음 페이지 여부 확인
        .all()
    )
    latest_has_next = len(latest_rows) > latest_page_size
    latest_rows = latest_rows[:latest_page_size]

    l_ids = [c.id for c in latest_rows]
    l_counts = get_round_counts(db, l_ids)
    latest_cards = [_to_card(c, l_counts.get(c.id)) for c in latest_rows]

    # -----------------------------
    # 4) 마감 임박 (3일 이내 + recruiting)
    # -----------------------------
    today = date.today()
    within_3 = today + timedelta(days=3)
    ending_rows = (
        db.query(Challenge)
        .filter(
            # ★ Enum 비교는 Enum 값으로 (문자열 리터럴 대신)
            Challenge.status == ChallengeStatus.recruiting,
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
