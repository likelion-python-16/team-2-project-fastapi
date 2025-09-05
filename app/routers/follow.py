# app/routers/follow.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func

from app.core.database import get_db
from app.core.deps import get_current_user_dual
from app.security import get_current_user
from app.models.user import User
from app.models.challenge import Challenge
from app.models.following import Following
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["Follow"])

# Enhanced user profile model for follow system
class UserProfile(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    challenge_count: int = 0
    follower_count: int = 0
    following_count: int = 0
    is_following: Optional[bool] = None
    
    class Config:
        from_attributes = True

class ChallengeCard(BaseModel):
    id: int
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    mode: Optional[str] = None
    payment_type: str
    entry_fee: int = 0
    monthly_fee: int = 0
    current_participants: int = 0
    max_participants: Optional[int] = None
    cover_image: Optional[str] = None

    class Config:
        from_attributes = True

def _to_card(ch: Challenge) -> ChallengeCard:
    # payment_type 결정
    entry_fee_val = getattr(ch, 'entry_fee', 0) or 0
    monthly_fee_val = getattr(ch, 'monthly_fee', 0) or 0
    
    if entry_fee_val > 0 and monthly_fee_val > 0:
        payment_type = "both"
    elif entry_fee_val > 0:
        payment_type = "entry_fee"
    elif monthly_fee_val > 0:
        payment_type = "monthly_fee"
    else:
        payment_type = "free"
    
    return ChallengeCard(
        id=ch.id,
        title=ch.title,
        start_date=ch.start_date.isoformat() if ch.start_date else None,
        end_date=ch.end_date.isoformat() if ch.end_date else None,
        status=ch.status,
        mode=getattr(ch, 'mode', None),
        payment_type=payment_type,
        entry_fee=entry_fee_val,
        monthly_fee=monthly_fee_val,
        current_participants=getattr(ch, 'current_participants', 0) or 0,
        max_participants=getattr(ch, 'max_participants', None),
        cover_image=getattr(ch, 'cover_image', None),
    )

# Enhanced follow endpoint with dual auth support
@router.post("/follow/{target_user_id}")
def follow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """팔로우 기능 (Enhanced with dual authentication)"""
    if target_user_id == me.id:
        raise HTTPException(status_code=400, detail="자기 자신을 팔로우할 수 없습니다.")

    target = db.query(User).filter(User.id == target_user_id, User.is_active == True).first()
    if not target:
        raise HTTPException(status_code=404, detail="대상 사용자를 찾을 수 없습니다.")

    exists = db.query(Following).filter(
        and_(
            Following.follower_id == me.id,
            Following.following_id == target_user_id
        )
    ).first()
    if exists:
        return {"message": "이미 팔로우 중입니다.", "status": "already_following"}

    new_follow = Following(follower_id=me.id, following_id=target_user_id)
    db.add(new_follow)
    db.commit()
    
    # Return enhanced response with current follow status
    follower_count = db.query(Following).filter(Following.following_id == target_user_id).count()
    return {
        "message": "팔로우했습니다.", 
        "status": "followed",
        "target_user_id": target_user_id,
        "follower_count": follower_count
    }

# Legacy endpoint for backward compatibility
@router.post("/follow/{target_user_id}/legacy")
def follow_user_legacy(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """Legacy follow endpoint for backward compatibility"""
    if target_user_id == me.id:
        raise HTTPException(status_code=400, detail="자기 자신을 팔로우할 수 없습니다.")

    target = db.query(User).filter(User.id == target_user_id, User.is_active == True).first()
    if not target:
        raise HTTPException(status_code=404, detail="대상 사용자를 찾을 수 없습니다.")

    exists = db.query(Following).filter(
        and_(
            Following.follower_id == me.id,
            Following.following_id == target_user_id
        )
    ).first()
    if exists:
        return {"message": "이미 팔로우 중입니다."}

    new_follow = Following(follower_id=me.id, following_id=target_user_id)
    db.add(new_follow)
    db.commit()
    return {"message": "팔로우했습니다."}

# Enhanced unfollow endpoint
@router.delete("/follow/{target_user_id}")
def unfollow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """언팔로우 기능 (Enhanced with dual authentication)"""
    rel = db.query(Following).filter(
        and_(
            Following.follower_id == me.id,
            Following.following_id == target_user_id
        )
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="팔로우 관계가 없습니다.")
    
    db.delete(rel)
    db.commit()
    
    # Return enhanced response with current follow status
    follower_count = db.query(Following).filter(Following.following_id == target_user_id).count()
    return {
        "message": "언팔로우했습니다.", 
        "status": "unfollowed",
        "target_user_id": target_user_id,
        "follower_count": follower_count
    }

# Legacy endpoint for backward compatibility
@router.delete("/follow/{target_user_id}/legacy")
def unfollow_user_legacy(
    target_user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """Legacy unfollow endpoint for backward compatibility"""
    rel = db.query(Following).filter(
        and_(
            Following.follower_id == me.id,
            Following.following_id == target_user_id
        )
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="팔로우 관계가 없습니다.")
    db.delete(rel)
    db.commit()
    return {"message": "언팔로우했습니다."}

# Enhanced following challenges with dual auth support
@router.get("/following/challenges", response_model=List[ChallengeCard])
def following_challenges(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, description="Filter by challenge status"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """팔로잉하는 사용자들의 챌린지 목록 (Enhanced)"""
    subq = db.query(Following.following_id).filter(Following.follower_id == me.id).subquery()

    query = (
        db.query(Challenge)
        .filter(
            Challenge.creator_id.in_(subq),
            Challenge.is_public == True,
            Challenge.is_deleted == False
        )
    )
    
    # Add status filter if provided
    if status_filter:
        query = query.filter(Challenge.status == status_filter)
    
    rows = (
        query
        .order_by(desc(getattr(Challenge, "created_at", Challenge.id)))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_to_card(c) for c in rows]

# Legacy endpoint for backward compatibility
@router.get("/following/challenges/legacy", response_model=List[ChallengeCard])
def following_challenges_legacy(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """Legacy following challenges endpoint"""
    subq = db.query(Following.following_id).filter(Following.follower_id == me.id).subquery()

    rows = (
        db.query(Challenge)
        .filter(Challenge.creator_id.in_(subq))
        .order_by(desc(getattr(Challenge, "created_at", Challenge.id)))
        .limit(limit)
        .all()
    )
    return [_to_card(c) for c in rows]

# Enhanced following users endpoint
@router.get("/following/users")
def get_following_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_profile: bool = Query(False, description="Include full user profiles"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """현재 사용자가 팔로우하는 사용자 목록 (Enhanced)"""
    
    if include_profile:
        # Return detailed user profiles
        following_users = (
            db.query(User)
            .join(Following, Following.following_id == User.id)
            .filter(Following.follower_id == me.id, User.is_active == True)
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        profiles = []
        for user in following_users:
            # Count user stats
            challenge_count = db.query(Challenge).filter(
                Challenge.creator_id == user.id,
                Challenge.is_deleted == False
            ).count()
            follower_count = db.query(Following).filter(Following.following_id == user.id).count()
            following_count = db.query(Following).filter(Following.follower_id == user.id).count()
            
            profiles.append(UserProfile(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=getattr(user, 'full_name', None),
                profile_picture=getattr(user, 'profile_picture', None),
                bio=getattr(user, 'bio', None),
                location=getattr(user, 'location', None),
                challenge_count=challenge_count,
                follower_count=follower_count,
                following_count=following_count,
                is_following=True
            ))
        
        total = db.query(Following).filter(Following.follower_id == me.id).count()
        return {
            "users": profiles,
            "total": total,
            "offset": offset,
            "limit": limit
        }
    else:
        # Return simple ID list for backward compatibility
        following_ids = (
            db.query(Following.following_id)
            .filter(Following.follower_id == me.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {"following_user_ids": [row.following_id for row in following_ids]}

# Legacy endpoint for backward compatibility  
@router.get("/following/users/legacy")
def get_following_users_legacy(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """Legacy following users endpoint"""
    following_ids = db.query(Following.following_id).filter(Following.follower_id == me.id).all()
    return {"following_user_ids": [row.following_id for row in following_ids]}

# New enhanced endpoints
@router.get("/followers", response_model=List[UserProfile])
def get_followers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """내 팔로워 목록 조회"""
    followers = (
        db.query(User)
        .join(Following, Following.follower_id == User.id)
        .filter(Following.following_id == me.id, User.is_active == True)
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    profiles = []
    for user in followers:
        # Count user stats
        challenge_count = db.query(Challenge).filter(
            Challenge.creator_id == user.id,
            Challenge.is_deleted == False
        ).count()
        follower_count = db.query(Following).filter(Following.following_id == user.id).count()
        following_count = db.query(Following).filter(Following.follower_id == user.id).count()
        
        # Check if I'm following them back
        is_following = db.query(Following).filter(
            Following.follower_id == me.id,
            Following.following_id == user.id
        ).first() is not None
        
        profiles.append(UserProfile(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=getattr(user, 'full_name', None),
            profile_picture=getattr(user, 'profile_picture', None),
            bio=getattr(user, 'bio', None),
            location=getattr(user, 'location', None),
            challenge_count=challenge_count,
            follower_count=follower_count,
            following_count=following_count,
            is_following=is_following
        ))
    
    return profiles

@router.get("/follow/status/{user_id}")
def get_follow_status(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """특정 사용자와의 팔로우 관계 확인"""
    if user_id == me.id:
        return {
            "user_id": user_id,
            "is_following": False,
            "is_follower": False,
            "relationship": "self"
        }
    
    is_following = db.query(Following).filter(
        Following.follower_id == me.id,
        Following.following_id == user_id
    ).first() is not None
    
    is_follower = db.query(Following).filter(
        Following.follower_id == user_id,
        Following.following_id == me.id
    ).first() is not None
    
    relationship = "none"
    if is_following and is_follower:
        relationship = "mutual"
    elif is_following:
        relationship = "following"
    elif is_follower:
        relationship = "follower"
    
    return {
        "user_id": user_id,
        "is_following": is_following,
        "is_follower": is_follower,
        "relationship": relationship
    }

@router.post("/follow/batch")
def batch_follow(
    user_ids: List[int] = Body(..., description="List of user IDs to follow"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user_dual),
):
    """여러 사용자를 한번에 팔로우"""
    results = []
    
    for user_id in user_ids:
        if user_id == me.id:
            results.append({
                "user_id": user_id,
                "status": "error",
                "message": "자기 자신을 팔로우할 수 없습니다."
            })
            continue
        
        # Check if user exists and is active
        target = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not target:
            results.append({
                "user_id": user_id,
                "status": "error", 
                "message": "사용자를 찾을 수 없습니다."
            })
            continue
        
        # Check if already following
        exists = db.query(Following).filter(
            Following.follower_id == me.id,
            Following.following_id == user_id
        ).first()
        
        if exists:
            results.append({
                "user_id": user_id,
                "status": "already_following",
                "message": "이미 팔로우 중입니다."
            })
        else:
            # Add follow relationship
            new_follow = Following(follower_id=me.id, following_id=user_id)
            db.add(new_follow)
            results.append({
                "user_id": user_id,
                "status": "followed",
                "message": "팔로우했습니다."
            })
    
    db.commit()
    return {"results": results}

@router.get("/users/{user_id}/follow-stats")
def get_user_follow_stats(
    user_id: int,
    db: Session = Depends(get_db),
    me: Optional[User] = Depends(get_current_user_dual),
):
    """사용자의 팔로우 통계 조회"""
    target_user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    follower_count = db.query(Following).filter(Following.following_id == user_id).count()
    following_count = db.query(Following).filter(Following.follower_id == user_id).count()
    
    # Check relationship if authenticated
    is_following = False
    is_follower = False
    if me:
        is_following = db.query(Following).filter(
            Following.follower_id == me.id,
            Following.following_id == user_id
        ).first() is not None
        
        is_follower = db.query(Following).filter(
            Following.follower_id == user_id,
            Following.following_id == me.id
        ).first() is not None
    
    return {
        "user_id": user_id,
        "username": target_user.username,
        "follower_count": follower_count,
        "following_count": following_count,
        "is_following": is_following if me else None,
        "is_follower": is_follower if me else None
    }