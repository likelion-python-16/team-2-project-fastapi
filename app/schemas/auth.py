from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re

# ---------------------------
# 요청 스키마
# ---------------------------
class SignUpIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="사용자명 (3-50자)")
    email: EmailStr = Field(..., description="이메일 주소(최대 120자)")
    password: str = Field(..., min_length=8, description="비밀번호 (8자 이상)")

    # ── [신규] 전화번호 (평문 입력; 서버에서 암호화/지문 처리)
    phone: Optional[str] = Field(None, description="전화번호(선택, 하이픈 허용)")


    # 선택 입력(서버에서 기본값 보정)
    name: Optional[str] = Field(None, max_length=100, description="실명 (선택)")
    identification_number: Optional[str] = Field(None, description="식별번호 13자리 (선택)")
    gender: Optional[str] = Field(None, description="성별: male/female/other (미입력시 other)")
    region_living: Optional[str] = Field(None, max_length=50, description="생활 지역 (선택)")
    region_active: Optional[str] = Field(None, max_length=50, description="활동 지역 (선택)")
    profile_image: Optional[str] = Field(None, max_length=255, description="프로필 이미지 URL (선택)")
    introduction: Optional[str] = Field("", description="소개 (선택, 미입력시 '')")

    # --- validators ---
    @validator('username')
    def validate_username(cls, v: str) -> str:
        if not v:
            raise ValueError('사용자명은 필수입니다')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('사용자명은 영문, 숫자, 언더스코어(_)만 사용 가능합니다')
        if not v[0].isalpha():
            raise ValueError('사용자명은 영문으로 시작해야 합니다')
        return v.lower()

    # ── [신규] phone 정규화/길이 검증(숫자만 9~15자리 권장)
    @validator('phone', pre=True)
    def normalize_phone_for_schema(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = re.sub(r'\D+', '', str(v))
        if s and not (9 <= len(s) <= 15):
            raise ValueError('전화번호는 숫자 9~15자리여야 합니다')
        return s


    @validator('email')
    def validate_email_len(cls, v: EmailStr) -> EmailStr:
        # DB: VARCHAR(120)
        if len(str(v)) > 120:
            raise ValueError('이메일은 120자 이하여야 합니다')
        return v

    @validator('name', pre=True)
    def normalize_name(cls, v: Optional[str]) -> str:
        # DB NOT NULL 대응: None/공백 → ''
        if v is None:
            return ''
        v = v.strip()
        if len(v) == 0:
            return ''
        if len(v) < 2:
            raise ValueError('실명은 2자 이상이어야 합니다')
        return v

    @validator('identification_number', pre=True)
    def validate_identification_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.replace('-', '')
        if not re.match(r'^\d{13}$', v):
            raise ValueError('식별번호는 13자리 숫자여야 합니다')
        gender_code = v[6]
        if gender_code not in ['1', '2', '3', '4']:
            raise ValueError('올바르지 않은 식별번호 형식입니다')
        return v

    @validator('gender', pre=True)
    def normalize_gender(cls, v: Optional[str]) -> str:
        # 미입력 → 'other'
        if not v:
            return 'other'
        v = str(v).strip().lower()

        # 과거 M/F/U로 보내와도 안전하게 매핑
        if v in ('m', 'male'):
            return 'male'
        if v in ('f', 'female'):
            return 'female'
        if v in ('u', 'other'):
            return 'other'

        if v not in ('male', 'female', 'other'):
            raise ValueError("gender는 'male', 'female', 'other' 중 하나여야 합니다")
        return v


    @validator('region_living', 'region_active', 'profile_image', 'introduction', pre=True)
    def normalize_text_defaults(cls, v: Optional[str]) -> str:
        # DB NOT NULL 대응: None/공백 → ''
        if v is None:
            return ''
        v = str(v).strip()
        return v

    class Config:
        schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "SecurePass123!",
                "name": "김철수",
                "identification_number": "9012011234567",
                # 선택 입력(안 보내면 자동 보정)
                "gender": "other",
                "region_living": "",
                "region_active": "",
                "profile_image": "",
                "introduction": ""
            }
        }


class LoginIn(BaseModel):
    login: str = Field(..., description="사용자명 또는 이메일")
    password: str = Field(..., description="비밀번호")

    @validator('login')
    def validate_login(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자명 또는 이메일을 입력해주세요')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "login": "johndoe",  # 또는 "john@example.com"
                "password": "SecurePass123!"
            }
        }


# ---------------------------
# 응답 스키마
# ---------------------------
class TokenOut(BaseModel):
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: Optional[int] = Field(None, description="만료 시간(초)")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class RefreshTokenIn(BaseModel):
    refresh_token: str = Field(..., description="리프레시 토큰")

    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    name: Optional[str] = ""
    is_active: Optional[bool] = True
    gender: Optional[str] = "other"
    region_living: Optional[str] = ""
    region_active: Optional[str] = ""
    profile_image: Optional[str] = ""
    introduction: Optional[str] = ""
    # 새 컬럼들 반영
    manner_score: Optional[float] = 0
    total_points: Optional[int] = 0
    penalty_total: Optional[int] = 0
    is_admin: Optional[bool] = False
    email_verified: Optional[bool] = False
    token_version: Optional[int] = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "username": "johndoe",
                "email": "john@example.com",
                "name": "김철수",
                "is_active": True,
                "gender": "other",
                "region_living": "",
                "region_active": "",
                "profile_image": "",
                "introduction": "",
                "manner_score": 0.0,
                "total_points": 0,
                "penalty_total": 0,
                "is_admin": False,
                "email_verified": False,
                "token_version": 0,
                "created_at": "2025-08-13T12:00:00",
                "updated_at": "2025-08-17T10:00:00"
            }
        }


class PasswordChangeIn(BaseModel):
    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(..., min_length=8, description="새 비밀번호")

    class Config:
        schema_extra = {
            "example": {
                "current_password": "OldPass123!",
                "new_password": "NewSecurePass123!"
            }
        }


# -----------------------------
# MyPage 관련 Schemas
# -----------------------------
class UserBrief(BaseModel):
    """간단한 사용자 정보"""
    id: int
    username: str
    name: Optional[str] = ""
    profile_image: Optional[str] = ""
    
    class Config:
        from_attributes = True

class FollowListOut(BaseModel):
    """팔로우 목록 응답"""
    items: list[UserBrief]
    total: int
    skip: int
    limit: int
    
    class Config:
        from_attributes = True

class PointHistoryOut(BaseModel):
    """포인트 히스토리"""
    id: int
    amount: int
    history_type: str
    description: Optional[str] = ""
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PointHistoryListOut(BaseModel):
    """포인트 히스토리 목록 응답"""
    items: list[PointHistoryOut]
    total: int
    skip: int
    limit: int
    current_points: Optional[int] = 0
    
    class Config:
        from_attributes = True