from pydantic import BaseModel, Field, condecimal
from typing import Optional, List
from datetime import datetime

class ReviewBase(BaseModel):
    rating: condecimal(ge=0.5, le=5, max_digits=2, decimal_places=1) = Field(..., description="0.5~5.0")
    comment: Optional[str] = None
    images: Optional[list] = None  # images_json과 매핑

class ReviewCreate(ReviewBase):
    round_id: Optional[int] = None
    target_id: Optional[int] = None  # 임시: 프론트엔드 호환성을 위해 추가하지만 DB에 저장하지 않음

class ReviewUpdate(BaseModel):
    rating: Optional[condecimal(ge=0.5, le=5, max_digits=2, decimal_places=1)]
    comment: Optional[str] = None
    images: Optional[list] = None

class ReviewOut(BaseModel):
    id: int
    user_id: int
    challenge_id: int
    round_id: Optional[int]
    rating: float
    comment: Optional[str]
    helpful_count: int
    status: str
    images: Optional[list]
    created_at: datetime
    updated_at: datetime
    # 추가 메타(선택): 대상 사용자 정보
    target_user_id: Optional[int] = None
    target_user_name: Optional[str] = None

    class Config:
        from_attributes = True

class ReviewList(BaseModel):
    total: int
    items: List[ReviewOut]
