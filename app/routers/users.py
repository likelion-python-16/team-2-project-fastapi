from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..core.database import get_db
from ..models.user import User
from ..schemas.auth import UserOut
from ..utils.logging import logger
from ..core.deps import get_current_user         # 토큰에서 현재 유저 뽑는 Depends 
from ..models.tag import Tag, UserTag            # 태그/유저태그 모델 
from sqlalchemy import func
from ..models.participation import Participation
from ..models.challenge import Challenge
from ..models.payment import Payment

# 라우터 생성
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

@router.get("/me")  # response_model을 굳이 강제하지 않고 dict로 반환
async def get_me(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """내 프로필(마이페이지) 기본 정보"""
    # 내 태그 이름 목록 가져오기
    links = db.query(UserTag).filter_by(user_id=me.id).all()
    tag_ids = [x.tag_id for x in links]
    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

    return {
        "id": me.id,
        "username": me.username,
        "email": me.email,
        "name": me.name,
        "manner_score": me.manner_score,
        "total_points": me.total_points,
        "is_active": me.is_active,
        "tags": [t.name for t in tags],
        # 필요 시 더 노출
        "phone": me.phone,
        "gender": me.gender,
        "region_living": me.region_living,
        "region_active": me.region_active,
        "profile_image": me.profile_image,
        "introduction": me.introduction,
        "created_at": me.created_at,
        "updated_at": me.updated_at,
    }

@router.patch("/me")
async def update_me(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """내 프로필 수정 (허용 필드만 갱신)"""
    try:
        for k in ["name", "phone", "gender", "region_living", "region_active", "introduction", "profile_image"]:
            if k in payload:
                setattr(me, k, payload[k])
        db.add(me)
        db.commit()
        db.refresh(me)
        logger.info(f"[me] 프로필 수정: user_id={me.id}")
        return {"ok": True}
    except Exception as e:
        db.rollback()
        logger.error(f"[me] 프로필 수정 오류: {e}")
        raise HTTPException(500, "프로필 수정에 실패했습니다")

@router.delete("/me")
async def delete_me(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """회원 탈퇴(소프트 비활성화)"""
    try:
        me.is_active = False
        db.add(me)
        db.commit()
        logger.warning(f"[me] 소프트탈퇴: user_id={me.id}")
        return {"ok": True}
    except Exception as e:
        db.rollback()
        logger.error(f"[me] 탈퇴 오류: {e}")
        raise HTTPException(500, "탈퇴 처리에 실패했습니다")

# =========================================
# ### 
#   - 최소 3개 강제
# =========================================

@router.get("/me/tags")
async def my_tags(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """내 관심 태그 조회"""
    links = db.query(UserTag).filter_by(user_id=me.id).all()
    if not links:
        return {"items": []}
    tag_ids = [x.tag_id for x in links]
    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    return {"items": [t.name for t in tags]}

@router.post("/me/tags")
async def set_my_tags(
    tags: List[str],
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user)
):
    """내 관심 태그 설정(최소 3개)"""
    uniq = list(dict.fromkeys([t.strip() for t in tags if t and t.strip()]))
    if len(uniq) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "관심 태그는 최소 3개 이상이어야 합니다.")

    try:
        # 기존 링크 삭제 후 재설정
        db.query(UserTag).filter_by(user_id=me.id).delete()
        for name in uniq:
            tag = db.query(Tag).filter_by(name=name).one_or_none()
            if not tag:
                tag = Tag(name=name)
                db.add(tag)
                db.flush()
            db.add(UserTag(user_id=me.id, tag_id=tag.id))
        db.commit()
        logger.info(f"[me] 태그 설정: user_id={me.id}, count={len(uniq)}")
        return {"ok": True, "count": len(uniq)}
    except Exception as e:
        db.rollback()
        logger.error(f"[me] 태그 설정 오류: {e}")
        raise HTTPException(500, "태그 설정에 실패했습니다")

@router.get("/", response_model=List[UserOut])
async def get_users(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """모든 사용자 목록 조회 (페이지네이션 포함)"""
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        logger.info(f"사용자 목록 조회: {len(users)}명")
        return users
    except Exception as e:
        logger.error(f"사용자 목록 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 목록을 가져오는데 실패했습니다"
        )

@router.get("/count")
async def get_users_count(db: Session = Depends(get_db)):
    """전체 사용자 수 조회"""
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users
        }
    except Exception as e:
        logger.error(f"사용자 수 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 수를 가져오는데 실패했습니다"
        )

@router.get("/search")
async def search_users(
    q: str,
    db: Session = Depends(get_db)
):
    """사용자 검색 (username, email, name으로)"""
    if len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="검색어는 2자 이상이어야 합니다"
        )
    
    try:
        users = db.query(User).filter(
            User.username.contains(q) |
            User.email.contains(q) |
            User.name.contains(q)
        ).limit(20).all()
        
        return {
            "query": q,
            "results": len(users),
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "name": user.name,
                    "is_active": user.is_active
                } for user in users
            ]
        }
    except Exception as e:
        logger.error(f"사용자 검색 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 검색에 실패했습니다"
        )

@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """특정 사용자 조회"""
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바르지 않은 사용자 ID입니다"
        )
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"사용자 ID {user_id}를 찾을 수 없습니다"
            )
        
        logger.info(f"사용자 조회: user_id={user_id}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보를 가져오는데 실패했습니다"
        )

@router.get("/username/{username}", response_model=UserOut)
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """사용자명으로 사용자 조회"""
    try:
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"사용자명 '{username}'을 찾을 수 없습니다"
            )
        
        logger.info(f"사용자명으로 조회: username={username}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자명 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보를 가져오는데 실패했습니다"
        )

@router.patch("/{user_id}/activate")
async def activate_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 활성화"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        user.is_active = True
        db.commit()
        
        logger.info(f"사용자 활성화: user_id={user_id}")
        return {"message": f"사용자 {user_id}가 활성화되었습니다"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"사용자 활성화 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 활성화에 실패했습니다"
        )

@router.patch("/{user_id}/deactivate")
async def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 비활성화"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        user.is_active = False
        db.commit()
        
        logger.info(f"사용자 비활성화: user_id={user_id}")
        return {"message": f"사용자 {user_id}가 비활성화되었습니다"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"사용자 비활성화 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 비활성화에 실패했습니다"
        )

@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 삭제 (주의: 실제 삭제됨)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        # 실제 삭제 (소프트 삭제 원한다면 is_deleted 플래그 사용)
        db.delete(user)
        db.commit()
        
        logger.warning(f"사용자 삭제: user_id={user_id}, username={user.username}")
        return {"message": f"사용자 {user_id}가 삭제되었습니다"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"사용자 삭제 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 삭제에 실패했습니다"
        )
    
@router.get("/me/challenges")
async def my_challenges(
    status: Optional[str] = None,   # "active" 또는 "past"
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    q = (
        db.query(Participation, Challenge)
        .join(Challenge, Participation.challenge_id == Challenge.id)
        .filter(Participation.user_id == me.id)
        .order_by(Participation.id.desc())
    )

    if status == "active":
        q = q.filter(Challenge.is_active == True)   # ← 네 필드명에 맞게 수정
    elif status == "past":
        q = q.filter(Challenge.is_active == False)

    rows = q.limit(50).all()
    items = []
    for p, c in rows:
        items.append({
            "participation_id": p.id,
            "challenge_id": c.id,
            "challenge_title": getattr(c, "title", None),
            "paid_amount": getattr(p, "paid_amount", None),
            "status": getattr(p, "status", None),
            "started_at": getattr(c, "start_at", None),
            "ended_at": getattr(c, "end_at", None),
        })
    return {"items": items}

@router.get("/me/spending")
async def my_spending(
    definition: str = "A",   # "A" 또는 "B"
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    definition = definition.upper()
    if definition not in ("A", "B"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "definition은 A 또는 B여야 합니다.")

    if definition == "A":
        total = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.user_id == me.id, Payment.status == "PAID")
            .scalar()
        )
    else:  # definition == "B"
        total = (
            db.query(func.coalesce(func.sum(Participation.paid_amount), 0))
            .filter(Participation.user_id == me.id)
            .scalar()
        )

    try:
        total_val = float(total)
    except Exception:
        total_val = 0.0

    return {"definition": definition, "total": total_val}