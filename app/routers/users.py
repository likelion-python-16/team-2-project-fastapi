from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db

# 라우터 생성
router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def get_users():
    """모든 사용자 목록 조회"""
    return {
        "message": "사용자 목록 조회 성공",
        "users": [
            {"id": 1, "username": "admin", "email": "admin@test.com"},
            {"id": 2, "username": "user1", "email": "user1@test.com"}
        ]
    }

@router.get("/{user_id}")
async def get_user(user_id: int):
    """특정 사용자 조회"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    return {
        "message": f"사용자 {user_id} 조회 성공",
        "user": {
            "id": user_id,
            "username": f"user{user_id}",
            "email": f"user{user_id}@test.com"
        }
    }

@router.post("/")
async def create_user():
    """새 사용자 생성"""
    return {
        "message": "사용자 생성 성공",
        "user": {
            "id": 999,
            "username": "newuser",
            "email": "newuser@test.com"
        }
    }

@router.put("/{user_id}")
async def update_user(user_id: int):
    """사용자 정보 수정"""
    return {
        "message": f"사용자 {user_id} 수정 성공",
        "user": {
            "id": user_id,
            "username": f"updated_user{user_id}",
            "email": f"updated{user_id}@test.com"
        }
    }

@router.delete("/{user_id}")
async def delete_user(user_id: int):
    """사용자 삭제"""
    return {
        "message": f"사용자 {user_id} 삭제 성공"
    }