from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_, or_, case, distinct

from app.core.database import get_db
from app.core.deps import get_current_user_dual
from app.models.user import User
from app.models.challenge import Challenge, ChallengeStatus  # ★ Enum 함께 임포트
from app.models.tag import UserTag, ChallengeTag
from app.models.challenge_round import ChallengeRound
from app.models.participation import Participation
from app.security import get_current_user_optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/home", tags=["Home"])

# Enhanced response models
class UserStats(BaseModel):
    """사용자 통계 정보"""
    total_challenges: int = 0
    active_participations: int = 0
    completed_challenges: int = 0
    success_rate: float = 0.0
    
    class Config:
        from_attributes = True

class TrendingTag(BaseModel):
    """인기 태그 정보"""
    tag_id: int
    tag_name: str
    usage_count: int
    recent_challenges: int
    
    class Config:
        from_attributes = True


# --- 카드 응답 스키마 ---
class ChallengeCard(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None
    status: str
    fee_type: str
    participation_fee: int
    fee: int
    total_rounds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    current_participants: int = 0
    max_participants: Optional[int] = None
    creator_name: Optional[str] = None
    creator_id: Optional[int] = None
    mode: Optional[str] = None
    tags: List[str] = []
    is_participating: Optional[bool] = None
    days_until_start: Optional[int] = None
    days_until_end: Optional[int] = None
    progress_percentage: Optional[float] = None

    class Config:
        from_attributes = True

class HomeSectionsResponse(BaseModel):
    recommended: List[ChallengeCard] = []
    recommended_notice: Optional[str] = None
    followings: List[ChallengeCard] = []
    latest: List[ChallengeCard] = []
    ending_soon: List[ChallengeCard] = []
    trending: List[ChallengeCard] = []
    user_participating: List[ChallengeCard] = []
    latest_has_next: bool = False
    user_stats: Optional[UserStats] = None
    trending_tags: List[TrendingTag] = []

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

# --- 모델 -> 카드 변환 (Enhanced) ---
def _to_card(ch: Challenge, rounds_count: Optional[int] = None, current_user: Optional[User] = None, db: Optional[Session] = None) -> ChallengeCard:
    # ★ 모델 컬럼명이 프로젝트마다 달라 충돌 방지 (entry_fee/monthly_fee 지원)
    part_fee_val = (
        getattr(ch, "participation_fee", None)
        or getattr(ch, "entry_fee", None)
        or 0
    )
    fee_val = (
        getattr(ch, "fee", None)
        or getattr(ch, "monthly_fee", None)
        or 0
    )
    fee_type = "유료" if (fee_val > 0 or part_fee_val > 0) else "무료"

    # 총 회차: 명시된 total_rounds > 집계값
    total_rounds = (
        getattr(ch, "total_rounds", None) if getattr(ch, "total_rounds", None) not in (None, 0)
        else rounds_count
    )

    # ★ Enum 안전 처리: 문자열로 직렬화
    status_str = ch.status.value if hasattr(ch.status, "value") else str(ch.status)
    
    # Enhanced fields calculation
    today = date.today()
    days_until_start = (ch.start_date - today).days if ch.start_date and ch.start_date > today else None
    days_until_end = (ch.end_date - today).days if ch.end_date and ch.end_date > today else None
    
    # Progress calculation
    progress_percentage = None
    if ch.start_date and ch.end_date:
        if today >= ch.start_date:
            total_duration = (ch.end_date - ch.start_date).days
            if total_duration > 0:
                elapsed = (min(today, ch.end_date) - ch.start_date).days
                progress_percentage = min(100.0, (elapsed / total_duration) * 100)
    
    # Get creator info
    creator_name = None
    creator_id = None
    if hasattr(ch, 'creator') and ch.creator:
        creator_name = ch.creator.username
        creator_id = ch.creator.id
    
    # Check if current user is participating
    is_participating = None
    if current_user and db:
        participation = db.query(Participation).filter(
            Participation.user_id == current_user.id,
            Participation.challenge_id == ch.id,
            Participation.status != "cancelled"
        ).first()
        is_participating = participation is not None
    
    # Get tags
    tags = []
    if hasattr(ch, 'challenge_tags') and ch.challenge_tags:
        # Tag model uses column 'tag' (not 'name')
        tags = [getattr(ct.tag, 'tag', None) for ct in ch.challenge_tags if getattr(ct, 'tag', None)]
        tags = [t for t in tags if t]
    
    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        description=getattr(ch, 'description', None),
        start_date=ch.start_date,
        end_date=ch.end_date,
        created_at=getattr(ch, "created_at", None),
        status=status_str,
        fee_type=fee_type,
        participation_fee=int(part_fee_val or 0),
        fee=int(fee_val or 0),
        total_rounds=total_rounds,
        thumbnail_url=getattr(ch, "thumbnail_url", None),
        cover_image_url=getattr(ch, "cover_image_url", None),
        current_participants=getattr(ch, 'current_participants', 0),
        max_participants=getattr(ch, 'max_participants', None),
        creator_name=creator_name,
        creator_id=creator_id,
        mode=getattr(ch, 'mode', None),
        tags=tags,
        is_participating=is_participating,
        days_until_start=days_until_start,
        days_until_end=days_until_end,
        progress_percentage=progress_percentage
    )

# Enhanced recommended challenges with ML-like features
@router.get("/recommended", summary="추천 챌린지")
def get_recommended_challenges(
    limit: int = Query(10, ge=1, le=50, description="추천 챌린지 개수"),
    include_tags: bool = Query(True, description="태그 정보 포함"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_dual),
):
    """향상된 추천 챌린지 목록 반환"""
    try:
        query = db.query(Challenge)
        
        if include_tags:
            query = query.options(
                joinedload(Challenge.challenge_tags).joinedload(ChallengeTag.tag),
                joinedload(Challenge.creator)
            )
        
        # Enhanced recommendation logic
        if current_user:
            # Get user's preferred tags
            user_tag_ids = db.query(UserTag.tag_id).filter(
                UserTag.user_id == current_user.id
            ).subquery()

            # Preferred by user's tags (less restrictive):
            # - Always exclude soft-deleted
            # - Show matches regardless of status/public, but de-prioritize non-public/non-recruiting in ordering
            preferred_challenges = (
                query.join(ChallengeTag, ChallengeTag.challenge_id == Challenge.id)
                .filter(
                    ChallengeTag.tag_id.in_(user_tag_ids),
                    Challenge.is_deleted == False,
                )
            )

            # Popular challenges (high participation) — keep public only
            popular_challenges = query.filter(
                Challenge.is_deleted == False,
                Challenge.is_public == True,
                Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active]),
                Challenge.current_participants >= 5,
            )

            # Combine and limit results (distinct by id). Favor recruiting/active and public first, then by participants & recency.
            visibility_rank = case(
                (
                    and_(Challenge.is_public == True, Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active])),
                    0
                ),
                else_=1
            )
            challenges = (
                preferred_challenges.union(popular_challenges)
                .order_by(visibility_rank, desc(Challenge.current_participants), desc(Challenge.created_at))
                .distinct(Challenge.id)
                .limit(limit)
                .all()
            )
        else:
            # For non-authenticated users, show popular challenges
            challenges = query.filter(
                Challenge.is_deleted == False,
                Challenge.is_public == True,
                Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active])
            ).order_by(
                desc(Challenge.current_participants),
                desc(Challenge.created_at)
            ).limit(limit).all()
        
        return {
            "success": True,
            "challenges": [
                _to_card(c, current_user=current_user, db=db).__dict__
                for c in challenges
            ],
            "total": len(challenges),
            "personalized": current_user is not None
        }
    except Exception as e:
        return {"success": False, "challenges": [], "error": str(e)}

# Legacy endpoint for backward compatibility
@router.get("/recommended/legacy", summary="추천 챌린지 (레거시)")
def get_recommended_challenges_legacy(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """추천 챌린지 목록 반환 (레거시)"""
    try:
        challenges = db.query(Challenge).filter(
            Challenge.is_deleted == False,
            Challenge.status == ChallengeStatus.active
        ).order_by(Challenge.created_at.desc()).limit(10).all()
        
        return {
            "success": True,
            "challenges": [
                {
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "created_at": c.created_at.isoformat() if c.created_at else None
                } for c in challenges
            ]
        }
    except Exception as e:
        return {"success": False, "challenges": [], "error": str(e)}

# Enhanced following challenges with real follow logic
@router.get("/following", summary="팔로잉 챌린지")  
def get_following_challenges(
    limit: int = Query(20, ge=1, le=50, description="챌린지 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    status_filter: Optional[str] = Query(None, description="상태 필터"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_dual),
):
    """팔로잉 중인 사용자들의 실제 챌린지 목록"""
    try:
        if not current_user:
            return {"success": False, "challenges": [], "error": "로그인이 필요합니다"}
        
        from app.models.following import Following  # 순환 임포트 방지
        
        # Get following user IDs
        following_ids = db.query(Following.following_id).filter(
            Following.follower_id == current_user.id
        ).subquery()
        
        # Query challenges from followed users
        query = db.query(Challenge).options(
            joinedload(Challenge.creator),
            joinedload(Challenge.challenge_tags).joinedload(ChallengeTag.tag)
        ).filter(
            Challenge.creator_id.in_(following_ids),
            Challenge.is_deleted == False,
            Challenge.is_public == True
        )
        
        # Apply status filter if provided
        if status_filter and hasattr(ChallengeStatus, status_filter):
            query = query.filter(Challenge.status == getattr(ChallengeStatus, status_filter))
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination
        challenges = query.order_by(
            desc(Challenge.created_at)
        ).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "challenges": [
                _to_card(c, current_user=current_user, db=db).__dict__
                for c in challenges
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": total > (offset + limit)
        }
    except Exception as e:
        return {"success": False, "challenges": [], "error": str(e)}

# Legacy endpoint for backward compatibility
@router.get("/following/legacy", summary="팔로잉 챌린지 (레거시)")
def get_following_challenges_legacy(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """팔로잉 중인 사용자들의 챌린지 목록 (레거시)"""
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
                    "created_at": c.created_at.isoformat() if c.created_at else None
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
    # 1) 추천(선호태그 기반)
    # -----------------------------
    recommended_rows: List[Challenge] = []
    recommended_notice: Optional[str] = None

    if current_user:
        # 먼저 "선호 태그가 존재하는지"는 간단 쿼리로 체크 (★ exists 오류 수정)
        user_has_tags = (
            db.query(UserTag.tag_id)
              .filter(UserTag.user_id == current_user.id)
              .first()
            is not None
        )

        if user_has_tags:
            # 태그 ID 서브쿼리 (IN 필터용)
            user_tag_ids_subq = (
                db.query(UserTag.tag_id)
                .filter(UserTag.user_id == current_user.id)
                .subquery()
            )
            recommended_rows = (
                db.query(Challenge)
                .join(ChallengeTag, ChallengeTag.challenge_id == Challenge.id)
                .filter(ChallengeTag.tag_id.in_(user_tag_ids_subq))
                .order_by(desc(Challenge.created_at))
                .limit(6)
                .all()
            )
        else:
            recommended_notice = "추천 기능을 위해 ‘선호 태그’를 등록해 주세요."
    else:
        recommended_notice = "추천 기능을 위해 ‘선호 태그’를 등록해 주세요."

    rec_ids = [c.id for c in recommended_rows]
    rec_counts = get_round_counts(db, rec_ids)
    recommended_cards = [_to_card(c, rec_counts.get(c.id), current_user, db) for c in recommended_rows]

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
        follow_cards = [_to_card(c, f_counts.get(c.id), current_user, db) for c in follow_rows]

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
    latest_cards = [_to_card(c, l_counts.get(c.id), current_user, db) for c in latest_rows]

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
    ending_cards = [_to_card(c, e_counts.get(c.id), current_user, db) for c in ending_rows]
    
    # -----------------------------
    # 5) 트렌딩 챌린지 (참가자 수 기준)
    # -----------------------------
    trending_rows = (
        db.query(Challenge)
        .filter(
            Challenge.is_deleted == False,
            Challenge.is_public == True,
            Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active])
        )
        .order_by(desc(Challenge.current_participants), desc(Challenge.created_at))
        .limit(6)
        .all()
    )
    t_ids = [c.id for c in trending_rows]
    t_counts = get_round_counts(db, t_ids)
    trending_cards = [_to_card(c, t_counts.get(c.id), current_user, db) for c in trending_rows]
    
    # -----------------------------
    # 6) 사용자 참여 중인 챌린지
    # -----------------------------
    user_participating_cards = []
    user_stats = None
    trending_tags = []
    
    if current_user:
        # 참여 중인 챌린지
        participating_rows = (
            db.query(Challenge)
            .join(Participation, Participation.challenge_id == Challenge.id)
            .filter(
                Participation.user_id == current_user.id,
                Participation.status != "cancelled",
                Challenge.is_deleted == False
            )
            .order_by(desc(Challenge.created_at))
            .limit(6)
            .all()
        )
        up_ids = [c.id for c in participating_rows]
        up_counts = get_round_counts(db, up_ids)
        user_participating_cards = [_to_card(c, up_counts.get(c.id), current_user, db) for c in participating_rows]
        
        # 사용자 통계
        total_created = db.query(Challenge).filter(
            Challenge.creator_id == current_user.id,
            Challenge.is_deleted == False
        ).count()
        
        active_participations = db.query(Participation).filter(
            Participation.user_id == current_user.id,
            Participation.status == "active"
        ).count()
        
        completed_participations = db.query(Participation).filter(
            Participation.user_id == current_user.id,
            Participation.status == "completed"
        ).count()
        
        total_participations = db.query(Participation).filter(
            Participation.user_id == current_user.id,
            Participation.status != "cancelled"
        ).count()
        
        success_rate = (completed_participations / total_participations * 100) if total_participations > 0 else 0
        
        user_stats = UserStats(
            total_challenges=total_created,
            active_participations=active_participations,
            completed_challenges=completed_participations,
            success_rate=round(success_rate, 1)
        )
    
    # 트렌딩 태그 (최근 30일)
    from app.models.tag import Tag
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    trending_tag_data = (
        db.query(
            Tag.id,
            Tag.tag,
            func.count(ChallengeTag.id).label('usage_count'),
            func.count(case([
                (Challenge.created_at >= thirty_days_ago, ChallengeTag.id)
            ])).label('recent_challenges')
        )
        .join(ChallengeTag, ChallengeTag.tag_id == Tag.id)
        .join(Challenge, Challenge.id == ChallengeTag.challenge_id)
        .filter(
            Challenge.is_deleted == False,
            Challenge.is_public == True
        )
        .group_by(Tag.id, Tag.tag)
        .order_by(desc('recent_challenges'), desc('usage_count'))
        .limit(10)
        .all()
    )
    
    trending_tags = [
        TrendingTag(
            tag_id=tag_data.id,
            tag_name=getattr(tag_data, 'tag', None),
            usage_count=tag_data.usage_count,
            recent_challenges=tag_data.recent_challenges,
        )
        for tag_data in trending_tag_data
    ]

    return HomeSectionsResponse(
        recommended=recommended_cards,
        recommended_notice=recommended_notice,
        followings=follow_cards,
        latest=latest_cards,
        ending_soon=ending_cards,
        trending=trending_cards,
        user_participating=user_participating_cards,
        latest_has_next=latest_has_next,
        user_stats=user_stats,
        trending_tags=trending_tags
    )

# New enhanced endpoints
@router.get("/trending", summary="트렌딩 챌린지")
def get_trending_challenges(
    limit: int = Query(20, ge=1, le=50, description="챌린지 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    time_range: str = Query("week", regex="^(day|week|month)$", description="기간 (day/week/month)"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_dual),
):
    """트렌딩 챌린지 (참가자 수, 활동도 기준)"""
    try:
        # Calculate time filter
        time_filters = {
            "day": datetime.now() - timedelta(days=1),
            "week": datetime.now() - timedelta(days=7), 
            "month": datetime.now() - timedelta(days=30)
        }
        since_date = time_filters.get(time_range, time_filters["week"])
        
        query = db.query(Challenge).options(
            joinedload(Challenge.creator),
            joinedload(Challenge.challenge_tags).joinedload(ChallengeTag.tag)
        ).filter(
            Challenge.is_deleted == False,
            Challenge.is_public == True,
            Challenge.created_at >= since_date,
            Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active])
        )
        
        total = query.count()
        
        challenges = query.order_by(
            desc(Challenge.current_participants),
            desc(Challenge.created_at)
        ).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "challenges": [
                _to_card(c, current_user=current_user, db=db).__dict__
                for c in challenges
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "time_range": time_range,
            "has_more": total > (offset + limit)
        }
    except Exception as e:
        return {"success": False, "challenges": [], "error": str(e)}
