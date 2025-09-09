# app/routers/challenges.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from typing import List, Optional, Literal
from datetime import date

from app.core.database import get_db
from app.security import get_current_user, get_current_user_optional
from app.utils.logging import logger

# Models
from app.models.user import User
from app.models.challenge import Challenge, ChallengeStatus, ChallengeMode, PaymentType
from app.models.participation import Participation, ParticipationRole
from app.models.challenge_round import ChallengeRound
from app.models.round_manager import RoundManager
from app.models.attendance import RoundAttendance
from app.models.tag import Tag, ChallengeTag
from app.models.notification import Notification, NotificationEvent

# Schemas
from app.schemas.challenge import (
    ChallengeCreate, ChallengeResponse, ChallengeUpdate,
    DualSearchResponse, ChallengeItem
)
from app.schemas.challenge_round import (
    ChallengeRoundCreate, ChallengeRoundUpdate, ChallengeRoundResponse,
)

# Services & AuthZ
from app.services.predictor import predict_category
from app.services.challenge_round_service import auto_create_rounds_on_challenge_create
from app.services.challenge_recommender import get_challenge_recommender
from app.services.enhanced_challenge_search import get_enhanced_challenge_search
from app.core.authz import can_edit_round, is_challenge_owner, is_challenge_manager

router = APIRouter(prefix="/challenges", tags=["challenges"])

# Quick endpoints for frontend compatibility
@router.get("/recommended")
def get_recommended_challenges_simple(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """추천 챌린지 목록 (간단 버전)"""
    try:
        q = (
            db.query(Challenge)
            .filter(
                Challenge.is_deleted == False,
                getattr(Challenge, 'is_public', True) == True,
                Challenge.status.in_([ChallengeStatus.recruiting, ChallengeStatus.active])
            )
        )
        if current_user:
            q = q.filter(Challenge.creator_id != current_user.id)
        challenges = (
            q.order_by(desc(getattr(Challenge, 'created_at', Challenge.id)))
             .limit(10)
             .all()
        )
        
        return {
            "success": True,
            "challenges": [
                {
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "created_at": c.created_at.isoformat() if getattr(c, 'created_at', None) else None,
                    "creator_id": c.creator_id,
                    "mode": c.mode.value if hasattr(c.mode, 'value') else c.mode,
                    "status": c.status.value if hasattr(c.status, 'value') else c.status,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
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

@router.get("/following")
def get_following_challenges_simple(db: Session = Depends(get_db)):
    """팔로잉 챌린지 목록 (간단 버전)"""
    try:
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
                } for c in challenges
            ]
        }
    except Exception as e:
        return {"success": False, "challenges": [], "error": str(e)}

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def get_current_user_id(current_user: User = Depends(get_current_user)) -> int:
    """현재 로그인한 사용자 ID 반환"""
    return current_user.id

def _payment_validation(
    payment_type: PaymentType,
    entry_fee: Optional[int],
    monthly_fee: Optional[int],
) -> None:
    """새로운 결제 시스템 검증"""
    if entry_fee is not None and entry_fee < 0:
        raise HTTPException(400, "Entry fee cannot be negative")
    if monthly_fee is not None and monthly_fee < 0:
        raise HTTPException(400, "Monthly fee cannot be negative")
    if entry_fee is not None and entry_fee > 1000000:  # 100만원 제한
        raise HTTPException(400, "Entry fee cannot exceed 1,000,000 KRW")
    if monthly_fee is not None and monthly_fee > 100000:  # 10만원 제한
        raise HTTPException(400, "Monthly fee cannot exceed 100,000 KRW")
    
    # 결제 타입별 검증
    if payment_type == PaymentType.entry_fee:
        if not entry_fee or entry_fee == 0:
            raise HTTPException(400, "Entry fee must be > 0 when payment_type is entry_fee")
    elif payment_type == PaymentType.monthly_fee:
        if not monthly_fee or monthly_fee == 0:
            raise HTTPException(400, "Monthly fee must be > 0 when payment_type is monthly_fee")
    elif payment_type == PaymentType.both:
        if (not entry_fee or entry_fee == 0) and (not monthly_fee or monthly_fee == 0):
            raise HTTPException(400, "At least one fee must be > 0 when payment_type is both")

def _validate_common_business_rules(
    start_date: Optional[date],
    end_date: Optional[date],
    payment_type: Optional[PaymentType],
    entry_fee: Optional[int],
    monthly_fee: Optional[int],
) -> None:
    """공통 비즈니스 규칙 검증"""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "start_date must be ≤ end_date")
    
    if payment_type:
        _payment_validation(payment_type, entry_fee, monthly_fee)

def _round_has_dependents(r: ChallengeRound) -> bool:
    return bool(
        (getattr(r, "attendances", None) and len(r.attendances) > 0)
        or (getattr(r, "proofs", None) and len(r.proofs) > 0)
        or (getattr(r, "qrcodes", None) and len(r.qrcodes) > 0)
        or (getattr(r, "reviews", None) and len(r.reviews) > 0)
    )

def _reconcile_total_rounds(db: Session, challenge: Challenge, new_total: Optional[int], force: bool = False) -> None:
    if new_total is None:
        return
    existing = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge.id)
        .order_by(ChallengeRound.round.asc())
        .all()
    )
    cur_n = len(existing)
    if new_total == cur_n:
        return

    if new_total > cur_n:
        base_mode = existing[-1].mode if cur_n > 0 else (challenge.mode or ChallengeMode.online)
        for i in range(cur_n + 1, new_total + 1):
            db.add(ChallengeRound(challenge_id=challenge.id, round=i, mode=base_mode))
        db.flush()
        return

    # shrink
    to_delete = [r for r in existing if r.round > new_total]
    for r in reversed(to_delete):
        if _round_has_dependents(r) and not force:
            raise HTTPException(409, f"Round {r.round} has dependent data; pass force=true to remove.")
        db.delete(r)
    db.flush()

def _calculate_status(ch: Challenge, db: Session, today: date) -> str:
    """
    새 모델의 get_computed_status() 메서드 활용
    """
    try:
        # 새 모델의 메서드 사용
        computed_status = ch.get_computed_status()
        return computed_status.value if hasattr(computed_status, 'value') else computed_status
    except:
        # fallback: 기존 로직 (수정된 버전)
        participants_count = db.query(Participation).filter(Participation.challenge_id == ch.id).count()
        
        if ch.is_settlement_completed:  # ✅ is_closed → is_settlement_completed
            return "completed"
        if ch.end_date and today > ch.end_date:
            return "completed"
        if ch.start_date and today < ch.start_date:
            return "recruiting"
        if ch.start_date and today >= ch.start_date:
            if participants_count < (ch.min_participants or 1):
                return "recruiting"
            if not ch.end_date or today <= ch.end_date:
                return "active"
        return "recruiting"

def _can_edit_challenge(db: Session, challenge_id: int, me: int) -> bool:
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        return False
    return ch.creator_id == me or is_challenge_manager(db, challenge_id, me)

# ---- tags helpers ----
def _challenge_tags(db: Session, challenge_id: int) -> List[str]:
    rows = (
        db.query(Tag)
        .join(ChallengeTag, ChallengeTag.tag_id == Tag.id)
        .filter(ChallengeTag.challenge_id == challenge_id)
        .order_by(Tag.tag.asc())
        .all()
    )
    return [t.tag for t in rows]

def _with_tags(db: Session, ch: Challenge) -> dict:
    resp = ChallengeResponse.model_validate(ch).model_dump()
    resp["tags"] = _challenge_tags(db, ch.id)
    return resp

def _with_tags_and_participation(db: Session, ch: Challenge, user_id: Optional[int] = None) -> dict:
    """챌린지 정보에 태그와 사용자 참여 상태를 추가"""
    resp = ChallengeResponse.model_validate(ch).model_dump()
    resp["tags"] = _challenge_tags(db, ch.id)
    
    # 사용자 참여 상태 추가
    resp["user_participation"] = None
    if user_id:
        participation = db.query(Participation).filter(
            Participation.challenge_id == ch.id,
            Participation.user_id == user_id
        ).first()
        
        if participation:
            resp["user_participation"] = {
                "status": participation.status.value if hasattr(participation.status, 'value') else participation.status,
                "role": participation.role.value if hasattr(participation.role, 'value') else participation.role,
                "joined_at": participation.joined_at,
                "is_creator": ch.creator_id == user_id
            }
    
    return resp

# Pydantic v2: 응답 모델 확장 (tags 추가)
class ChallengeResponseWithTags(ChallengeResponse):  # type: ignore[misc]
    tags: List[str] = []

# -------------------------------------------------------------------
# Search (with AI tag recommendation)
# -------------------------------------------------------------------
@router.get(
    "/search",
    response_model=DualSearchResponse,
    summary="검색어(선택)+날짜 필터+상태(기본 recruiting)+정렬 + AI 태그 추천"
)
def dual_search(
    q: Optional[str] = Query(None, description="검색어 (선택)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Literal["recruiting", "active", "completed", "cancelled"] = Query(
        "recruiting", alias="status"
    ),
    location: Optional[str] = Query(None, description="장소 검색어 (선택)"),
    start_from: Optional[date] = Query(None), start_to: Optional[date] = Query(None),
    end_from: Optional[date] = Query(None),   end_to: Optional[date] = Query(None),
    sort_by: Literal["created_at", "start_date", "end_date", "title"] = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
):
    def apply_filters(query):
        query = query.filter(Challenge.status == status_filter)
        if start_from is not None:
            query = query.filter(Challenge.start_date >= start_from)
        if start_to is not None:
            query = query.filter(Challenge.start_date <= start_to)
        if end_from is not None:
            query = query.filter(Challenge.end_date >= end_from)
        if end_to is not None:
            query = query.filter(Challenge.end_date <= end_to)
        return query

    def apply_sorting(query):
        col_map = {
            "created_at": getattr(Challenge, "created_at", Challenge.id),
            "start_date": Challenge.start_date,
            "end_date": Challenge.end_date,
            "title": Challenge.title,
        }
        col = col_map.get(sort_by, getattr(Challenge, "created_at", Challenge.id))
        return query.order_by(asc(col) if sort_dir == "asc" else desc(col))

    base = db.query(Challenge).join(User, User.id == Challenge.creator_id)
    
    # 텍스트 검색 (제목, 설명, 작성자)
    if q and q.strip():
        like = f"%{q.strip()}%"
        base = base.filter(or_(
            Challenge.title.ilike(like),
            Challenge.description.ilike(like),
            User.name.ilike(like),
        ))
    
    # 장소 검색 (장소명, 주소)
    if location and location.strip():
        location_like = f"%{location.strip()}%"
        base = base.filter(or_(
            Challenge.default_place_name.ilike(location_like),
            Challenge.default_address.ilike(location_like),
        ))

    base = apply_filters(base)
    base = apply_sorting(base)

    rows: List[Challenge] = (
        base.offset((page - 1) * page_size).limit(page_size).all()
    )
    matched = [ChallengeItem.model_validate(ch) for ch in rows]
    matched_ids = {ch.id for ch in rows}

    predicted_tag = None
    predicted_score = None
    recommended: List[ChallengeItem] = []
    try:
        if q and q.strip():
            tag_name, score = predict_category(q.strip())
            predicted_tag = tag_name
            predicted_score = float(score) if score is not None else None

            tag_obj = db.query(Tag).filter(Tag.tag == tag_name, Tag.is_active == True).first()
            if tag_obj:
                rec = (db.query(Challenge)
                       .join(ChallengeTag, ChallengeTag.challenge_id == Challenge.id)
                       .filter(ChallengeTag.tag_id == tag_obj.id)
                       .filter(~Challenge.id.in_(matched_ids)))
                rec = apply_filters(rec)
                rec = apply_sorting(rec)
                recommended = [ChallengeItem.model_validate(ch) for ch in rec.all()]
    except Exception:
        pass

    return DualSearchResponse(
        query=(q or ""),
        matched_challenges=matched,
        recommended_by_tag_challenges=recommended,
        predicted_tag=predicted_tag,
        predicted_score=predicted_score,
    )

# 새로운 AI 기반 챌린지 추천 API
@router.get("/recommendations")
def get_challenge_recommendations(
    query: str = Query(..., description="추천받을 텍스트 (관심사, 활동 등)"),
    limit: int = Query(default=5, le=20, description="추천 개수"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """AI 기반 챌린지 추천"""
    recommender = get_challenge_recommender(db)
    user_id = current_user.id if current_user else None
    
    try:
        recommendations = recommender.find_similar_challenges(
            query_text=query,
            limit=limit,
            user_id=user_id
        )
        
        # 추천이 부족하면 인기 챌린지로 보완
        if len(recommendations) < limit:
            trending = recommender.get_trending_challenges(limit=limit-len(recommendations))
            recommendations.extend(trending)
        
        # 응답 형태로 변환
        result = []
        for rec in recommendations[:limit]:
            ch = rec['challenge']
            result.append({
                'id': ch.id,
                'title': ch.title,
                'description': ch.description,
                'mode': ch.mode.value if hasattr(ch.mode, 'value') else ch.mode,
                'status': ch.status.value if hasattr(ch.status, 'value') else ch.status,
                'current_participants': ch.current_participants or 0,
                'max_participants': ch.max_participants,
                'start_date': ch.start_date.isoformat() if ch.start_date else None,
                'end_date': ch.end_date.isoformat() if ch.end_date else None,
                'payment_type': ch.payment_type.value if hasattr(ch.payment_type, 'value') else ch.payment_type,
                'entry_fee': ch.entry_fee,
                'monthly_fee': ch.monthly_fee,
                'similarity_score': rec['similarity_score'],
                'participant_count': rec['participant_count'],
                'reasons': rec['reasons']
            })
        
        return {
            'query': query,
            'recommendations': result,
            'total': len(result)
        }
        
    except Exception as e:
        logger.error(f"추천 시스템 오류: {e}")
        # 폴백: 인기 챌린지 반환
        trending = recommender.get_trending_challenges(limit=limit)
        result = []
        for rec in trending:
            ch = rec['challenge']
            result.append({
                'id': ch.id,
                'title': ch.title,
                'description': ch.description,
                'mode': ch.mode.value if hasattr(ch.mode, 'value') else ch.mode,
                'status': ch.status.value if hasattr(ch.status, 'value') else ch.status,
                'current_participants': ch.current_participants or 0,
                'max_participants': ch.max_participants,
                'similarity_score': 1.0,
                'participant_count': rec['participant_count'],
                'reasons': ['인기 챌린지']
            })
        
        return {
            'query': query,
            'recommendations': result,
            'total': len(result),
            'fallback': True
        }

# 새로운 스마트 검색 API (category_keywords.json 활용)
@router.get("/smart-search")
def smart_search_challenges(
    q: Optional[str] = Query(None, description="검색어 (선택)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Literal["recruiting", "active", "completed", "cancelled"] = Query(
        "recruiting", alias="status"
    ),
    location: Optional[str] = Query(None, description="장소 검색어 (선택)"),
    start_from: Optional[date] = Query(None), start_to: Optional[date] = Query(None),
    end_from: Optional[date] = Query(None), end_to: Optional[date] = Query(None),
    sort_by: Literal["created_at", "start_date", "end_date", "title"] = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """스마트 태그 매칭을 활용한 챌린지 검색"""
    try:
        # Enhanced Challenge Search 서비스 사용
        search_service = get_enhanced_challenge_search(db)
        user_id = current_user.id if current_user else None
        
        if q and q.strip():
            # 스마트 검색 실행
            search_result = search_service.smart_search(
                query=q.strip(),
                limit=page_size * 2,  # 충분한 결과를 확보
                user_id=user_id,
                status_filter=status_filter
            )
            
            # 직접 매칭 + 태그 기반 매칭 결합
            matched_challenges = search_result['direct_matches']
            recommended_by_tag_challenges = search_result['tag_based_matches']
            
            return {
                "query": q.strip(),
                "matched_challenges": matched_challenges[:page_size],
                "recommended_by_tag_challenges": recommended_by_tag_challenges[:8],
                "suggested_categories": search_result['suggested_categories'],
                "query_analysis": search_result['query_analysis'],
                "total": len(matched_challenges) + len(recommended_by_tag_challenges)
            }
        else:
            # 빈 검색어일 때는 기본 dual_search 로직 사용
            return dual_search(
                q=q, page=page, page_size=page_size,
                status_filter=status_filter, location=location,
                start_from=start_from, start_to=start_to,
                end_from=end_from, end_to=end_to,
                sort_by=sort_by, sort_dir=sort_dir,
                db=db
            )
            
    except Exception as e:
        logger.error(f"Smart search error: {e}")
        # 폴백: 기본 검색 사용
        return dual_search(
            q=q, page=page, page_size=page_size,
            status_filter=status_filter, location=location,
            start_from=start_from, start_to=start_to,
            end_from=end_from, end_to=end_to,
            sort_by=sort_by, sort_dir=sort_dir,
            db=db
        )

# -------------------------------------------------------------------
# Create / List / Get / Update / Delete / Status
# -------------------------------------------------------------------
@router.post("/")
async def create_challenge(
    challenge_data: ChallengeCreate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    logger.info(f"Creating challenge for user_id: {me}")
    
    # ✅ 새로운 결제 시스템 검증
    _validate_common_business_rules(
        challenge_data.start_date, 
        challenge_data.end_date,
        getattr(challenge_data, 'payment_type', PaymentType.free),
        getattr(challenge_data, 'entry_fee', 0),
        getattr(challenge_data, 'monthly_fee', 0),
    )
    
    # 리워드 검증 (reward → reward_description)
    if getattr(challenge_data, 'use_reward', False) and not getattr(challenge_data, 'reward_description', None):
        raise HTTPException(400, "Reward description is required when use_reward is True")

    # ✅ 새 모델에 맞게 챌린지 생성
    new_challenge = Challenge(
        title=challenge_data.title,
        description=challenge_data.description,
        start_date=challenge_data.start_date,
        end_date=challenge_data.end_date,
        creator_id=me,
        
        # ✅ 새로운 결제 시스템
        payment_type=getattr(challenge_data, 'payment_type', PaymentType.free),
        entry_fee=getattr(challenge_data, 'entry_fee', 0),
        monthly_fee=getattr(challenge_data, 'monthly_fee', 0),
        
        # 참가자 관리
        min_participants=getattr(challenge_data, 'min_participants', 1),
        max_participants=getattr(challenge_data, 'max_participants', None),
        
        # 회차 시스템
        total_rounds=getattr(challenge_data, 'total_rounds', None),
        min_participation_rate=getattr(challenge_data, 'min_participation_rate', 80),
        # ❌ max_participation_rate 제거됨
        
        # 진행 방식
        mode=getattr(challenge_data, 'mode', ChallengeMode.online),
        same_place_for_all_rounds=getattr(challenge_data, 'same_place_for_all_rounds', False),
        
        # ✅ 간소화된 장소 정보
        default_zoom_link=getattr(challenge_data, 'default_zoom_link', None),
        default_place_name=getattr(challenge_data, 'default_place_name', None),
        default_address=getattr(challenge_data, 'default_address', None),  # road_address 통합
        default_latitude=getattr(challenge_data, 'default_latitude', None),
        default_longitude=getattr(challenge_data, 'default_longitude', None),
        # ❌ default_road_address, default_map_url 제거됨
        
        # ✅ 리워드 시스템 (reward → reward_description)
        use_reward=getattr(challenge_data, 'use_reward', False),
        reward_description=getattr(challenge_data, 'reward_description', None),
        
        # 커버 이미지
        cover_image_url=getattr(challenge_data, 'cover_image_url', None),
        
        # 기본 설정
        require_approval=getattr(challenge_data, 'require_approval', False),
        is_public=getattr(challenge_data, 'is_public', True),
        
        # ✅ 유료 챌린지는 draft 상태로 시작 (결제 완료 후 recruiting으로 변경)
        status=ChallengeStatus.draft if getattr(challenge_data, 'payment_type', PaymentType.free) != PaymentType.free else ChallengeStatus.recruiting,
    )
    
    db.add(new_challenge)
    db.flush()

    # 태그 연결 (수동 태그 + AI 자동 태그)
    connected_tags = set()
    
    # 1. 수동으로 지정된 태그들 연결
    if challenge_data.tags:
        for tag_text in challenge_data.tags:
            t = db.query(Tag).filter(Tag.tag == tag_text).first()
            if not t:
                t = Tag(tag=tag_text, is_active=True)
                db.add(t)
                db.flush()
            exists = (
                db.query(ChallengeTag)
                .filter(ChallengeTag.challenge_id == new_challenge.id, ChallengeTag.tag_id == t.id)
                .first()
            )
            if not exists:
                db.add(ChallengeTag(challenge_id=new_challenge.id, tag_id=t.id))
                connected_tags.add(tag_text)
    
    # 2. AI 자동 태그 예측 및 연결
    try:
        # 챌린지 제목과 설명을 합쳐서 분석
        text_to_analyze = f"{new_challenge.title} {new_challenge.description or ''}".strip()
        if text_to_analyze:
            predicted_tag, confidence = predict_category(text_to_analyze)
            
            # 신뢰도가 0.3 이상이고 아직 연결되지 않은 태그인 경우 연결
            if confidence > 0.3 and predicted_tag not in connected_tags:
                # 예측된 태그가 데이터베이스에 존재하는지 확인
                predicted_tag_obj = db.query(Tag).filter(
                    Tag.tag == predicted_tag, 
                    Tag.is_active == True
                ).first()
                
                if predicted_tag_obj:
                    # 이미 연결되어 있는지 확인
                    exists = db.query(ChallengeTag).filter(
                        ChallengeTag.challenge_id == new_challenge.id,
                        ChallengeTag.tag_id == predicted_tag_obj.id
                    ).first()
                    
                    if not exists:
                        db.add(ChallengeTag(
                            challenge_id=new_challenge.id, 
                            tag_id=predicted_tag_obj.id
                        ))
                        logger.info(f"AI auto-tagged challenge {new_challenge.id} with '{predicted_tag}' (confidence: {confidence:.2f})")
                        
    except Exception as e:
        logger.warning(f"AI auto-tagging failed for challenge {new_challenge.id}: {e}")

    # 회차 자동 생성
    await auto_create_rounds_on_challenge_create(db, new_challenge)

    # ✅ 생성자를 자동으로 참가시키기 (유료 챌린지면 payment_pending 상태로)
    from app.models.participation import ParticipationManager, PaymentCycle, ParticipationRole
    
    # 결제 방식 결정
    payment_cycle = None
    if new_challenge.payment_type == PaymentType.free:
        payment_cycle = PaymentCycle.free
    elif new_challenge.payment_type == PaymentType.entry_fee:
        payment_cycle = PaymentCycle.entry_fee
    elif new_challenge.payment_type == PaymentType.monthly_fee:
        payment_cycle = PaymentCycle.monthly
    elif new_challenge.payment_type == PaymentType.both:
        # both 타입은 입장비 + 월회비 둘 다 결제해야 함
        # 생성자도 예외 없이 둘 다 결제 (일단 입장비부터)
        payment_cycle = PaymentCycle.entry_fee
    
    # 생성자 참가 생성
    creator_participation = ParticipationManager.create_participation(
        user_id=me,
        challenge_id=new_challenge.id,
        role=ParticipationRole.creator
    )
    
    db.add(creator_participation)
    
    # 생성자는 항상 활성 상태로 설정
    creator_participation.status = ParticipationStatus.active
    new_challenge.current_participants = 1

    db.commit()
    db.refresh(new_challenge)
    
    # 챌린지 생성 알림 생성
    notification = Notification(
        user_id=me,
        title="🎯 챌린지 생성 완료",
        content=f"새로운 챌린지 '{new_challenge.title}'를 생성했습니다",
        event_type=NotificationEvent.challenge_created,
        target_type="challenge",
        target_id=new_challenge.id
    )
    db.add(notification)
    db.commit()
    
    # ✅ 응답에 결제 필요 여부 추가
    challenge_response = _with_tags(db, new_challenge)
    
    # 유료 챌린지의 경우 결제 정보 포함
    if payment_cycle != PaymentCycle.free:
        challenge_response["needs_payment"] = True
        challenge_response["payment_amount"] = (
            new_challenge.entry_fee if payment_cycle == PaymentCycle.entry_fee 
            else new_challenge.monthly_fee
        )
        challenge_response["payment_type"] = payment_cycle.value
        challenge_response["creator_participation_status"] = "payment_pending"
    else:
        challenge_response["needs_payment"] = False
        challenge_response["creator_participation_status"] = "active"
    
    return challenge_response

@router.get("/", response_model=List[ChallengeResponseWithTags])
def list_challenges(db: Session = Depends(get_db)):
    rows = db.query(Challenge).filter(Challenge.is_deleted == False).all()  # 삭제된 챌린지 제외
    out = []
    # 수동으로 설정된 상태를 존중
    for ch in rows:
        # ch.status = _calculate_status(ch, db, today)  # ✅ 제거 - 수동 상태 존중
        out.append(_with_tags(db, ch))
    return out

# 사용자별 참여 상태가 포함된 챌린지 목록
@router.get("/with-participation", response_model=List[dict])
def list_challenges_with_participation(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """사용자 참여 상태가 포함된 챌린지 목록"""
    rows = db.query(Challenge).filter(Challenge.is_deleted == False).all()
    out = []
    user_id = current_user.id if current_user else None
    
    for ch in rows:
        out.append(_with_tags_and_participation(db, ch, user_id))
    return out

@router.get("/active", response_model=List[ChallengeResponseWithTags])
def get_active_challenges(db: Session = Depends(get_db)):
    rows = db.query(Challenge).filter(
        Challenge.status == ChallengeStatus.active,
        Challenge.is_deleted == False
    ).all()
    return [_with_tags(db, ch) for ch in rows]

@router.get("/status/{status}", response_model=List[ChallengeResponseWithTags])
def get_challenges_by_status(status: str, db: Session = Depends(get_db)):  # ChallengeStatus enum 제거
    try:
        status_enum = ChallengeStatus(status)
        rows = db.query(Challenge).filter(
            Challenge.status == status_enum,
            Challenge.is_deleted == False
        ).all()
        return [_with_tags(db, ch) for ch in rows]
    except ValueError:
        raise HTTPException(400, f"Invalid status: {status}")

@router.get("/{challenge_id}", response_model=ChallengeResponseWithTags)
def get_challenge(challenge_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    logger.info(f"Get challenge {challenge_id}: current status = {ch.status}")
    
    # 수동으로 설정된 상태를 존중하되, 날짜 기반 자동 계산은 선택적으로만 적용
    # ch.status = _calculate_status(ch, db, date.today())  # ✅ 제거
    
    return _with_tags(db, ch)

# 사용자 참여 상태가 포함된 개별 챌린지 조회
@router.get("/{challenge_id}/with-participation", response_model=dict)
def get_challenge_with_participation(
    challenge_id: int, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """사용자 참여 상태가 포함된 개별 챌린지 정보"""
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    user_id = current_user.id if current_user else None
    return _with_tags_and_participation(db, ch, user_id)

@router.put("/{challenge_id}", response_model=ChallengeResponseWithTags)
def update_challenge(
    challenge_id: int,
    challenge_update: ChallengeUpdate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
    force: bool = Query(False, description="총회차 축소 시 의존데이터 있어도 강제 삭제"),
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not _can_edit_challenge(db, challenge_id, me):
        raise HTTPException(403, "No permission to update this challenge")

    # ✅ 새로운 검증 로직
    _validate_common_business_rules(
        getattr(challenge_update, 'start_date', None) or ch.start_date,
        getattr(challenge_update, 'end_date', None) or ch.end_date,
        getattr(challenge_update, 'payment_type', None) or ch.payment_type,
        getattr(challenge_update, 'entry_fee', None) if hasattr(challenge_update, 'entry_fee') else ch.entry_fee,
        getattr(challenge_update, 'monthly_fee', None) if hasattr(challenge_update, 'monthly_fee') else ch.monthly_fee,
    )
    
    # 리워드 검증 (reward → reward_description)
    if getattr(challenge_update, 'use_reward', None) is True and not (
        (getattr(challenge_update, 'reward_description', None) is not None and 
         str(getattr(challenge_update, 'reward_description', None)).strip()) 
        or ch.reward_description
    ):
        raise HTTPException(400, "Reward description is required when use_reward is True")

    before_total = ch.total_rounds
    data = challenge_update.model_dump(exclude_unset=True)
    
    # ❌ 제거된 필드들 필터링
    removed_fields = {'fee', 'participation_fee', 'max_participation_rate', 'is_closed', 
                      'reward', 'default_road_address', 'default_map_url'}
    data = {k: v for k, v in data.items() if k not in removed_fields}
    
    # 업데이트 적용
    for k, v in data.items():
        if hasattr(ch, k):
            setattr(ch, k, v)
    db.flush()

    if "total_rounds" in data and data["total_rounds"] is not None and data["total_rounds"] != before_total:
        _reconcile_total_rounds(db, ch, data["total_rounds"], force=force)

    db.commit()
    db.refresh(ch)
    # 수동으로 설정된 상태 존중
    # ch.status = _calculate_status(ch, db, date.today())  # ✅ 제거
    return _with_tags(db, ch)

@router.delete("/{challenge_id}")
def delete_challenge(
    challenge_id: int, 
    db: Session = Depends(get_db), 
    me: int = Depends(get_current_user_id)
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    # 권한: 오너만 삭제 (원하면 is_challenge_manager 허용으로 완화)
    if ch.creator_id != me:
        raise HTTPException(403, "Only the creator can delete this challenge")

    # 생성자 외의 다른 참가자가 있는지 확인
    other_participants = db.query(Participation).filter(
        Participation.challenge_id == challenge_id,
        Participation.user_id != me  # 생성자가 아닌 참가자들만
    ).count()
    if other_participants > 0:
        raise HTTPException(400, "Cannot delete challenge with other participants")

    # ✅ 소프트 삭제 사용 (새 모델의 메서드)
    try:
        ch.soft_delete(me)
        db.commit()
        return {"message": "Challenge deleted successfully"}
    except:
        # fallback: 직접 삭제
        db.delete(ch)
        db.commit()
        return {"message": "Challenge deleted successfully"}

@router.patch("/{challenge_id}/status")
def update_challenge_status(
    challenge_id: int, 
    new_status: str,  # ChallengeStatus enum 대신 문자열
    db: Session = Depends(get_db), 
    me: int = Depends(get_current_user_id)
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only the creator can change challenge status")
    if ch.status == ChallengeStatus.completed:
        raise HTTPException(400, "Cannot change status of completed challenge")
    
    # 새 상태 검증
    try:
        logger.info(f"Updating challenge {challenge_id} status from {ch.status} to {new_status} by user {me}")
        
        old_status = ch.status
        new_status_enum = ChallengeStatus(new_status)
        ch.status = new_status_enum
        
        logger.info(f"Before commit: challenge.status = {ch.status}")
        db.commit()
        db.refresh(ch)
        logger.info(f"After commit: challenge.status = {ch.status}")
        
        result = {"message": f"Challenge status updated to {new_status}", "challenge": _with_tags(db, ch)}
        logger.info(f"Status change successful: {old_status} → {ch.status}")
        return result
    except ValueError as e:
        logger.error(f"Invalid status value: {new_status}, error: {e}")
        raise HTTPException(400, f"Invalid status: {new_status}")
    except Exception as e:
        logger.error(f"Status change failed: {e}")
        db.rollback()
        raise HTTPException(500, f"Status change failed: {str(e)}")

# -------------------------------------------------------------------
# 새로운 결제 관련 엔드포인트
# -------------------------------------------------------------------
@router.get("/{challenge_id}/payment-info")
def get_challenge_payment_info(challenge_id: int, db: Session = Depends(get_db)):
    """챌린지 결제 정보 조회"""
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    return {
        "challenge_id": challenge_id,
        "payment_type": ch.payment_type.value if hasattr(ch.payment_type, 'value') else ch.payment_type,
        "entry_fee": ch.entry_fee,
        "monthly_fee": ch.monthly_fee,
        "is_payment_required": ch.is_payment_required(),
    }

@router.post("/{challenge_id}/calculate-payment")
def calculate_payment_amount(
    challenge_id: int,
    payment_cycle: str = Body(..., embed=True),  # "entry_fee" or "monthly_fee"
    db: Session = Depends(get_db)
):
    """결제 금액 계산"""
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    amount = ch.get_payment_amount(payment_cycle)
    return {
        "challenge_id": challenge_id,
        "payment_cycle": payment_cycle,
        "amount": amount,
        "currency": "KRW"
    }

# -------------------------------------------------------------------
# 기존 Rounds 관련 코드들은 그대로 유지 (변경사항 없음)
# -------------------------------------------------------------------
@router.get("/{challenge_id}/rounds", response_model=List[ChallengeRoundResponse])
def get_challenge_rounds(challenge_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    rows = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id)
        .order_by(ChallengeRound.round)
        .all()
    )
    if not rows:
        return []
    ids = [r.id for r in rows]
    counts = dict(
        db.query(RoundAttendance.round_id, func.count())
        .filter(RoundAttendance.round_id.in_(ids), RoundAttendance.status == "pending")
        .group_by(RoundAttendance.round_id)
        .all()
    )
    out = []
    for r in rows:
        out.append(
            ChallengeRoundResponse.model_validate(
                {
                    "id": r.id,
                    "challenge_id": r.challenge_id,
                    "mode": r.mode,
                    "round": r.round,
                    "processing_at": r.processing_at,
                    "start_time": r.start_time,
                    "finish_time": r.finish_time,
                    "description": r.description,
                    "url": r.url,
                    "place_name": r.place_name,
                    "road_address": r.road_address,
                    "address": r.address,
                    "map_url": r.map_url,
                    "lat": float(r.lat) if r.lat is not None else None,
                    "lon": float(r.lon) if r.lon is not None else None,
                    "geofence_radius_m": r.geofence_radius_m,
                    "zoom_meeting_id": r.zoom_meeting_id,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                    "planned_count": counts.get(r.id, 0),
                }
            )
        )
    return out

# 나머지 라우터 함수들도 동일한 패턴으로 수정...
# (rounds, participation 관련 함수들은 Challenge 모델 변경에 직접적 영향 없음)

@router.post("/{challenge_id}/join")
def join_challenge(challenge_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.status != ChallengeStatus.recruiting:
        logger.warning(f"Challenge {challenge_id} has status '{ch.status}', expected 'recruiting'")
        raise HTTPException(400, f"Can only join recruiting challenges (current status: {ch.status})")
    
    # 참가 가능 여부 확인 (새 모델 메서드 사용)
    try:
        can_join, message = ch.can_join(me)
        if not can_join:
            raise HTTPException(400, message)
    except:
        # fallback: 기존 로직
        exists = (
            db.query(Participation)
            .filter(Participation.challenge_id == challenge_id, Participation.user_id == me, Participation.is_active == True)
            .first()
        )
        if exists:
            raise HTTPException(400, "Already joined this challenge")
        if ch.max_participants:
            cnt = db.query(Participation).filter(Participation.challenge_id == challenge_id, Participation.is_active == True).count()
            if cnt >= ch.max_participants:
                raise HTTPException(400, "Challenge is full")
    
    db.add(Participation(challenge_id=challenge_id, user_id=me, role=ParticipationRole.participant))
    
    # 참가자 수 증가
    try:
        ch.increment_participants()
    except:
        ch.current_participants = (ch.current_participants or 0) + 1
    
    db.commit()
    
    # 챌린지 참여 알림 생성
    notification = Notification(
        user_id=me,
        title="👥 챌린지 참여 완료",
        content=f"'{ch.title}' 챌린지에 참여했습니다",
        event_type=NotificationEvent.challenge_joined,
        target_type="challenge",
        target_id=challenge_id
    )
    db.add(notification)
    db.commit()
    
    return {"message": "Joined challenge successfully"}

@router.delete("/{challenge_id}/leave")
def leave_challenge(challenge_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    part = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == me)
        .first()
    )
    if not part:
        raise HTTPException(404, "Not a participant of this challenge")
    if ch.creator_id == me:
        raise HTTPException(400, "Creator cannot leave their own challenge. Delete the challenge instead.")
    if ch.status == ChallengeStatus.completed:
        raise HTTPException(400, "Cannot leave a completed challenge")
    
    db.delete(part)
    
    # 참가자 수 감소
    try:
        ch.decrement_participants()
    except:
        if ch.current_participants > 0:
            ch.current_participants -= 1
    
    db.commit()
    return {"message": "You have left the challenge"}

@router.get("/{challenge_id}/participants")
def get_challenge_participants(challenge_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    parts = db.query(Participation).filter(Participation.challenge_id == challenge_id).all()
    users = {u.id: u for u in db.query(User).filter(User.id.in_([p.user_id for p in parts])).all()}
    return [
        {
            "user_id": p.user_id,
            "username": users.get(p.user_id).username if users.get(p.user_id) else "Unknown",
            "joined_at": p.joined_at,
            "status": p.status,
            "role": p.role.value if hasattr(p.role, "value") else p.role,
        }
        for p in parts
    ]

@router.get("/my", response_model=List[ChallengeResponseWithTags])
def get_my_challenges(db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ids = [cid for (cid,) in db.query(Participation.challenge_id).filter(Participation.user_id == me).all()]
    if not ids:
        return []
    rows = db.query(Challenge).filter(
        Challenge.id.in_(ids),
        Challenge.is_deleted == False
    ).all()
    out = []
    # 수동으로 설정된 상태 존중
    for ch in rows:
        # ch.status = _calculate_status(ch, db, today)  # ✅ 제거
        out.append(_with_tags(db, ch))
    return out

@router.delete("/{challenge_id}/kick/{user_id}")
def kick_participant(
    challenge_id: int, 
    user_id: int, 
    db: Session = Depends(get_db), 
    me: int = Depends(get_current_user_id)
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me and not is_challenge_manager(db, challenge_id, me):
        raise HTTPException(403, "No permission to kick participants")
    part = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == user_id)
        .first()
    )
    if not part:
        raise HTTPException(404, "User not in challenge")
    
    db.delete(part)
    
    # 참가자 수 감소
    try:
        ch.decrement_participants()
    except:
        if ch.current_participants > 0:
            ch.current_participants -= 1
    
    db.commit()
    return {"message": "User has been removed from the challenge"}

# -------------------------------------------------------------------
# Round 관련 함수들 (ChallengeRound는 변경 없으므로 그대로 유지)
# -------------------------------------------------------------------
@router.post("/{challenge_id}/rounds", response_model=ChallengeRoundResponse)
def create_challenge_round(
    challenge_id: int,
    round_data: ChallengeRoundCreate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not can_edit_round(db, challenge_id, None, me):
        raise HTTPException(403, "No permission to create rounds for this challenge.")
    dup = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.round == round_data.round)
        .first()
    )
    if dup:
        raise HTTPException(400, "Round number already exists")
    new_round = ChallengeRound(
        challenge_id=challenge_id,
        mode=(round_data.mode.value if hasattr(round_data.mode, "value") else round_data.mode),
        round=round_data.round,
        processing_at=round_data.processing_at,
        start_time=round_data.start_time,
        finish_time=round_data.finish_time,
        description=round_data.description,
        url=round_data.url,
        lat=round_data.lat,
        lon=round_data.lon,
        geofence_radius_m=round_data.geofence_radius_m,
        zoom_meeting_id=round_data.zoom_meeting_id,
    )
    db.add(new_round)
    db.commit()
    db.refresh(new_round)
    return new_round

@router.get("/{challenge_id}/rounds/{round_id}", response_model=ChallengeRoundResponse)
def get_challenge_round(challenge_id: int, round_id: int, db: Session = Depends(get_db)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.id == round_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Round not found")
    return r

@router.put("/{challenge_id}/rounds/{round_id}", response_model=ChallengeRoundResponse)
def update_challenge_round(
    challenge_id: int,
    round_id: int,
    round_update: ChallengeRoundUpdate,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.id == round_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Round not found")
    if not can_edit_round(db, challenge_id, round_id, me):
        raise HTTPException(403, "No permission to edit this round.")

    data = round_update.model_dump(exclude_unset=True)

    # mode 변경은 hybrid에서만 허용
    if "mode" in data and data["mode"] is not None:
        # Enum 호환 처리
        data["mode"] = data["mode"].value if hasattr(data["mode"], "value") else data["mode"]
        if ch and ch.mode != ChallengeMode.hybrid:
            raise HTTPException(400, "mode는 hybrid일 때만 변경 가능")

    # 공백 문자열은 None으로 정리
    for key in ("url", "map_url", "place_name", "road_address", "address", "description", "zoom_meeting_id"):
        if key in data and isinstance(data[key], str) and data[key].strip() == "":
            data[key] = None

    # 안전장치: 온라인 모드 + map_url만 온 경우 → url로 저장
    eff_mode = data.get("mode") or r.mode
    if eff_mode == "online" and "map_url" in data and data.get("map_url") and "url" not in data:
        data["url"] = data["map_url"]

    # 실제 반영
    for k, v in data.items():
        if hasattr(r, k):
            setattr(r, k, v)

    db.commit()
    db.refresh(r)

    planned_count = (
        db.query(func.count())
        .select_from(RoundAttendance)
        .filter(RoundAttendance.round_id == r.id, RoundAttendance.status == "pending")
        .scalar()
    )
    return ChallengeRoundResponse.model_validate({**r.__dict__, "planned_count": planned_count})

@router.delete("/{challenge_id}/rounds/{round_id}")
def delete_challenge_round(
    challenge_id: int, round_id: int,
    db: Session = Depends(get_db),
    me: int = Depends(get_current_user_id),
):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.challenge_id == challenge_id, ChallengeRound.id == round_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Round not found")
    if not can_edit_round(db, challenge_id, round_id, me):
        raise HTTPException(403, "No permission to delete this round.")
    if _round_has_dependents(r):
        raise HTTPException(409, "This round has dependent data and cannot be deleted.")

    db.delete(r)
    db.flush()  # 삭제 반영

    # 총 회차 수 동기화
    remain = db.query(ChallengeRound).filter(ChallengeRound.challenge_id == challenge_id).count()
    if ch:
        ch.total_rounds = remain

    db.commit()
    return {"message": "Round deleted successfully", "total_rounds": remain}

# -------------------------------------------------------------------
# Round 출석 관련 (기존 유지)
# -------------------------------------------------------------------
@router.post("/{challenge_id}/rounds/{round_id}/attend")
def attend_round(challenge_id: int, round_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    from app.models.participation import ParticipationStatus
    joined = (
        db.query(Participation)
        .filter(Participation.challenge_id == challenge_id, Participation.user_id == me, Participation.status == ParticipationStatus.active)
        .first()
    )
    if not joined:
        raise HTTPException(403, "Join the challenge first.")
    r = db.query(ChallengeRound).filter(ChallengeRound.id == round_id, ChallengeRound.challenge_id == challenge_id).first()
    if not r:
        raise HTTPException(404, "Round not found")
    att = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id, RoundAttendance.user_id == me).first()
    if att:
        att.status = "pending"  # 참석예정
    else:
        db.add(RoundAttendance(user_id=me, round_id=round_id, status="pending"))
    db.commit()
    return {"message": "RSVP set to attending (pending)."}

@router.delete("/{challenge_id}/rounds/{round_id}/attend")
def unattend_round(_: int, round_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    att = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id, RoundAttendance.user_id == me).first()
    if not att:
        return {"message": "Already not attending."}
    if not getattr(att, "is_checked_in", False) and not getattr(att, "checkin_time", None):
        db.delete(att)
    else:
        att.status = "absent"
    db.commit()
    return {"message": "RSVP removed."}

@router.post("/{challenge_id}/rounds/{round_id}/decline")
def decline_round_alias(challenge_id: int, round_id: int, db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    return unattend_round(challenge_id, round_id, db, me)

@router.get("/{challenge_id}/rounds/{round_id}/attendees")
def get_round_attendees(challenge_id: int, round_id: int, planned_only: bool = True, db: Session = Depends(get_db)):
    # 챌린지 존재 확인
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    q = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id)
    if planned_only:
        q = q.filter(RoundAttendance.status == "pending")
    rows = q.all()
    ids = [r.user_id for r in rows]
    if not ids:
        return []
    users = db.query(User).filter(User.id.in_(ids)).all()
    u_map = {u.id: u for u in users}
    return [
        {
            "user_id": uid,
            "username": (u_map.get(uid).username if u_map.get(uid) else None),
            "name": (u_map.get(uid).name if u_map.get(uid) else None),
            "profile_image": (u_map.get(uid).profile_image if u_map.get(uid) else None),
        }
        for uid in ids
    ]

# -------------------------------------------------------------------
# 권한 위임 관련 (기존 유지, 삭제 확인만 추가)
# -------------------------------------------------------------------
@router.post("/{challenge_id}/delegate")
def delegate_challenge(challenge_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only owner can delegate managers.")
    p = db.query(Participation).filter(Participation.challenge_id == challenge_id, Participation.user_id == user_id).first()
    if not p:
        p = Participation(challenge_id=challenge_id, user_id=user_id)
        db.add(p)
        db.flush()
    p.role = ParticipationRole.manager
    p.is_active = True
    db.commit()
    return {"message": f"user {user_id} is now manager of challenge {challenge_id}"}

@router.post("/{challenge_id}/undelegate")
def undelegate_challenge(challenge_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only owner can undelegate managers.")
    p = db.query(Participation).filter(Participation.challenge_id == challenge_id, Participation.user_id == user_id).first()
    if not p or p.role != ParticipationRole.manager:
        raise HTTPException(404, "Target user is not a manager.")
    p.role = ParticipationRole.participant
    db.commit()
    return {"message": f"user {user_id} manager revoked for challenge {challenge_id}"}

@router.post("/{challenge_id}/transfer")
def transfer_challenge(challenge_id: int, to_user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only owner can transfer ownership.")
    ch.creator_id = to_user_id
    db.commit()
    return {"message": f"challenge {challenge_id} transferred to user {to_user_id}"}

@router.post("/{challenge_id}/rounds/{round_id}/delegate-manager")
def delegate_round_manager(challenge_id: int, round_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only the creator can delegate a round manager.")
    r = db.query(ChallengeRound).filter(ChallengeRound.id == round_id, ChallengeRound.challenge_id == challenge_id).first()
    if not r:
        raise HTTPException(404, "Round not found")
    ra = db.query(RoundAttendance).filter(RoundAttendance.round_id == round_id, RoundAttendance.user_id == user_id, RoundAttendance.status == "pending").first()
    if not ra:
        raise HTTPException(400, "Only planned attendees can be delegated.")
    existing = db.query(RoundManager).filter(RoundManager.challenge_id == challenge_id, RoundManager.round_id == round_id).first()
    if existing:
        existing.user_id = user_id
    else:
        db.add(RoundManager(challenge_id=challenge_id, round_id=round_id, user_id=user_id))
    db.commit()
    return {"message": f"user {user_id} is now manager for round {round_id}"}

@router.post("/{challenge_id}/rounds/{round_id}/undelegate-manager")
def undelegate_round_manager(challenge_id: int, round_id: int, user_id: int = Body(..., embed=True), db: Session = Depends(get_db), me: int = Depends(get_current_user_id)):
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if not is_challenge_owner(db, challenge_id, me):
        raise HTTPException(403, "Only the creator can revoke a round manager.")
    rm = db.query(RoundManager).filter(RoundManager.challenge_id == challenge_id, RoundManager.round_id == round_id, RoundManager.user_id == user_id).first()
    if not rm:
        raise HTTPException(404, "Round manager not found")
    db.delete(rm)
    db.commit()
    return {"message": f"user {user_id} is no longer manager for round {round_id}"}

# -------------------------------------------------------------------
# 새로운 챌린지 관리 엔드포인트들
# -------------------------------------------------------------------
@router.post("/{challenge_id}/start")
def start_challenge_manually(
    challenge_id: int, 
    db: Session = Depends(get_db), 
    me: int = Depends(get_current_user_id)
):
    """챌린지 수동 시작"""
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only the creator can start the challenge")
    
    # 새 모델의 메서드 사용
    try:
        if ch.can_start():
            success = ch.start_challenge()
            if success:
                db.commit()
                return {"message": "Challenge started successfully", "status": ch.status}
            else:
                raise HTTPException(400, "Failed to start challenge")
        else:
            raise HTTPException(400, "Challenge cannot be started. Check minimum participants and start date.")
    except Exception:
        # fallback
        if ch.status != ChallengeStatus.recruiting:
            raise HTTPException(400, "Only recruiting challenges can be started")
        if ch.current_participants < (ch.min_participants or 1):
            raise HTTPException(400, "Not enough participants to start")
        
        ch.status = ChallengeStatus.active
        db.commit()
        return {"message": "Challenge started successfully", "status": ch.status}

@router.post("/{challenge_id}/complete")
def complete_challenge_manually(
    challenge_id: int, 
    db: Session = Depends(get_db), 
    me: int = Depends(get_current_user_id)
):
    """챌린지 수동 완료"""
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    if ch.creator_id != me:
        raise HTTPException(403, "Only the creator can complete the challenge")
    
    # 새 모델의 메서드 사용
    try:
        success = ch.complete_challenge()
        if success:
            db.commit()
            return {"message": "Challenge completed successfully", "status": ch.status}
        else:
            raise HTTPException(400, "Only active challenges can be completed")
    except Exception:
        # fallback
        if ch.status != ChallengeStatus.active:
            raise HTTPException(400, "Only active challenges can be completed")
        
        ch.status = ChallengeStatus.completed
        ch.completed_at = func.now()
        db.commit()
        return {"message": "Challenge completed successfully", "status": ch.status}

@router.get("/{challenge_id}/statistics")
def get_challenge_statistics(challenge_id: int, db: Session = Depends(get_db)):
    """챌린지 통계 정보"""
    ch = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_deleted == False
    ).first()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    
    # 기본 통계
    total_participants = db.query(Participation).filter(Participation.challenge_id == challenge_id).count()
    active_participants = db.query(Participation).filter(
        Participation.challenge_id == challenge_id, 
        Participation.is_active == True
    ).count()
    
    # 새 모델의 메서드 사용
    try:
        duration_days = ch.get_duration_days()
        remaining_days = ch.get_remaining_days()
        progress_percentage = ch.get_progress_percentage()
    except:
        # fallback 계산
        duration_days = (ch.end_date - ch.start_date).days + 1 if ch.start_date and ch.end_date else 0
        today = date.today()
        if ch.end_date and today > ch.end_date:
            remaining_days = 0
        elif ch.start_date and today < ch.start_date:
            remaining_days = (ch.end_date - ch.start_date).days + 1 if ch.end_date else 0
        else:
            remaining_days = (ch.end_date - today).days + 1 if ch.end_date else 0
        
        if duration_days > 0 and ch.start_date and ch.end_date:
            if today < ch.start_date:
                progress_percentage = 0.0
            elif today > ch.end_date:
                progress_percentage = 100.0
            else:
                passed_days = (today - ch.start_date).days + 1
                progress_percentage = (passed_days / duration_days) * 100.0
        else:
            progress_percentage = 0.0
    
    return {
        "challenge_id": challenge_id,
        "total_participants": total_participants,
        "active_participants": active_participants,
        "current_participants": ch.current_participants,
        "max_participants": ch.max_participants,
        "duration_days": duration_days,
        "remaining_days": remaining_days,
        "progress_percentage": round(progress_percentage, 1),
        "status": ch.status.value if hasattr(ch.status, 'value') else ch.status,
        "computed_status": _calculate_status(ch, db, date.today()),
        "payment_required": ch.is_payment_required() if hasattr(ch, 'is_payment_required') else (ch.payment_type != PaymentType.free),
    }


# ===== 태그 관련 API =====
@router.post("/{challenge_id}/tags/{tag_name}")
def add_tag_to_challenge(
    challenge_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """챌린지에 태그 추가"""
    # 챌린지 존재 확인
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="챌린지를 찾을 수 없습니다.")
    
    # 태그 존재 확인 및 생성
    tag = db.query(Tag).filter(Tag.tag == tag_name, Tag.is_active == True).first()
    if not tag:
        tag = Tag(tag=tag_name, is_active=True)
        db.add(tag)
        db.flush()
    
    # 이미 연결된 태그인지 확인
    existing = db.query(ChallengeTag).filter(
        ChallengeTag.challenge_id == challenge_id,
        ChallengeTag.tag_id == tag.id
    ).first()
    
    if existing:
        return {"message": "이미 연결된 태그입니다.", "tag": tag_name}
    
    # 태그 연결
    challenge_tag = ChallengeTag(challenge_id=challenge_id, tag_id=tag.id)
    db.add(challenge_tag)
    db.commit()
    
    return {"message": "태그가 성공적으로 추가되었습니다.", "tag": tag_name}


@router.post("/{challenge_id}/auto-tag")
def auto_tag_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """챌린지에 AI 기반 자동 태그 매칭"""
    from app.services.predictor import predict_category
    
    # 챌린지 존재 확인
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="챌린지를 찾을 수 없습니다.")
    
    # 챌린지 텍스트로 AI 태그 예측
    text_to_analyze = f"{challenge.title} {challenge.description or ''}".strip()
    if not text_to_analyze:
        raise HTTPException(status_code=400, detail="분석할 텍스트가 없습니다.")
    
    predicted_tag, confidence = predict_category(text_to_analyze)
    
    # 신뢰도가 낮으면 실패
    if confidence < 0.3:
        return {
            "message": "적절한 태그를 찾지 못했습니다.",
            "predicted_tag": predicted_tag,
            "confidence": confidence
        }
    
    # 예측된 태그가 실제로 존재하는지 확인
    tag = db.query(Tag).filter(Tag.tag == predicted_tag, Tag.is_active == True).first()
    if not tag:
        return {
            "message": f"예측된 태그 '{predicted_tag}'가 데이터베이스에 없습니다.",
            "predicted_tag": predicted_tag,
            "confidence": confidence
        }
    
    # 이미 연결된 태그인지 확인
    existing = db.query(ChallengeTag).filter(
        ChallengeTag.challenge_id == challenge_id,
        ChallengeTag.tag_id == tag.id
    ).first()
    
    if existing:
        return {
            "message": "이미 연결된 태그입니다.",
            "predicted_tag": predicted_tag,
            "confidence": confidence
        }
    
    # 태그 연결
    challenge_tag = ChallengeTag(challenge_id=challenge_id, tag_id=tag.id)
    db.add(challenge_tag)
    db.commit()
    
    return {
        "message": "AI 태그가 성공적으로 추가되었습니다.",
        "predicted_tag": predicted_tag,
        "confidence": confidence
    }
