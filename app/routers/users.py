from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..core.database import get_db
from ..models.user import User
from ..schemas.auth import UserOut
from ..utils.logging import logger

# 라우터 생성
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

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