# app/schemas/user.py
from typing import Optional, Literal, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# ▶ 회원가입 요청
class UserRegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=30)
    email: Optional[EmailStr] = None  # 선택

# ▶ 로그인 요청 (username 또는 email)
class UserLoginIn(BaseModel):
    login: str = Field(description="username 또는 email")
    password: str

# ▶ 공용 사용자 응답 (리스트/상세에 널리 사용)
#    ✅ /users/me가 아직 UserOut을 사용해도 phone_number/region_*가 보이도록 포함
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: bool

    # --- 추가 필드 (옵션) ---
    region_living: Optional[str] = None
    region_active: Optional[str] = None
    phone_number: Optional[str] = None
    profile_image: Optional[str] = None
    introduction: Optional[str] = None
    manner_score: Optional[float] = None
    total_points: Optional[int] = None

# ▶ 내 정보 상세 응답(/users/me 전용)
class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None

    gender: Optional[Literal["male", "female", "other"]] = None
    region_living: Optional[str] = None
    region_active: Optional[str] = None
    phone_number: Optional[str] = None
    profile_image: Optional[str] = None
    introduction: Optional[str] = None

    manner_score: float = 0.0
    total_points: int = 0
    is_active: bool

# ▶ 내 정보 수정 요청(/users/me PATCH)
class MeUpdateIn(BaseModel):
    # 수정 가능 필드만
    name: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    region_living: Optional[str] = Field(None, max_length=50)
    region_active: Optional[str] = Field(None, max_length=50)
    phone_number: Optional[str] = Field(None, max_length=20)
    introduction: Optional[str] = Field(None, max_length=1000)
    profile_image: Optional[str] = None

# ▶ 요약 카드/팔로우 리스트 등
class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: Optional[str] = None
    profile_image: Optional[str] = None
    manner_score: Optional[float] = None
    is_active: bool

class FollowListOut(BaseModel):
    items: List[UserBrief]
    total: int
    skip: int
    limit: int
